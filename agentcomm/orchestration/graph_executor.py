"""
Graph Executor

Builds and executes LangGraph StateGraph workflows with streaming support.
Integrates with the existing callback system for UI updates.
"""

import logging
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional, Callable, List
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from agentcomm.orchestration.state import OrchestrationState, create_initial_state
from agentcomm.orchestration.workflow import Workflow, WorkflowNode
from agentcomm.orchestration.nodes import (
    A2AAgentNode, LLMNode, AggregatorNode, ConditionalNode
)

logger = logging.getLogger(__name__)


class GraphExecutor:
    """
    Executes LangGraph workflows with streaming support.

    Integrates with:
    - SessionManager callbacks for UI updates
    - Checkpointing for optional persistence
    - AgentComm and LLMRouter for node execution

    Usage:
        executor = GraphExecutor(agent_registry, llm_router)
        async for event in executor.execute(workflow, "user input"):
            print(event)
    """

    def __init__(
        self,
        agent_registry,
        llm_router,
        webhook_handler=None,
        ngrok_manager=None,
        enable_checkpointing: bool = False,
        stream_callback: Optional[Callable[[str, str, str], None]] = None
    ):
        """
        Initialize the graph executor.

        Args:
            agent_registry: AgentRegistry for agent lookup
            llm_router: LLMRouter for LLM access
            webhook_handler: WebhookHandler for A2A push notifications
            ngrok_manager: NgrokManager for tunnel management
            enable_checkpointing: Whether to enable state checkpointing
            stream_callback: Callback for streaming updates (node_id, content, type)
        """
        self.agent_registry = agent_registry
        self.llm_router = llm_router
        self.webhook_handler = webhook_handler
        self.ngrok_manager = ngrok_manager
        self.enable_checkpointing = enable_checkpointing
        self.checkpointer = MemorySaver() if enable_checkpointing else None
        self.stream_callback = stream_callback

        # Track active executions
        self.active_executions: Dict[str, Any] = {}

    def _create_node_callable(self, node: WorkflowNode) -> Optional[Callable]:
        """
        Create a callable for a workflow node.

        Args:
            node: WorkflowNode definition

        Returns:
            Async callable for the node, or None if invalid
        """
        if node.node_type == "agent":
            # Look up agent from registry
            agent = self.agent_registry.get_agent(node.config.get("agent_id", node.node_id))
            if not agent:
                logger.error(f"Agent not found: {node.node_id}")
                return None

            return A2AAgentNode(
                agent=agent,
                webhook_handler=self.webhook_handler,
                ngrok_manager=self.ngrok_manager,
                timeout=node.config.get("timeout", 60)
            )

        elif node.node_type == "llm":
            provider_name = node.config.get("provider", node.node_id.replace("llm_", ""))
            return LLMNode(
                llm_router=self.llm_router,
                provider_name=provider_name,
                model=node.config.get("model"),
                system_prompt=node.config.get("system_prompt"),
                temperature=node.config.get("temperature", 0.7)
            )

        elif node.node_type == "aggregator":
            return AggregatorNode(
                strategy=node.config.get("strategy", "concat"),
                llm_router=self.llm_router,
                summarizer_provider=node.config.get("summarizer_provider", "OpenAI")
            )

        elif node.node_type in ("start", "end"):
            # Pass-through nodes
            async def pass_through(state: OrchestrationState) -> Dict[str, Any]:
                return {}
            return pass_through

        elif node.node_type == "parallel":
            # Parallel node handled specially in graph building
            return None

        else:
            logger.warning(f"Unknown node type: {node.node_type}")
            return None

    def build_graph(self, workflow: Workflow) -> StateGraph:
        """
        Build a LangGraph StateGraph from a Workflow definition.

        Args:
            workflow: Workflow definition

        Returns:
            Compiled StateGraph ready for execution
        """
        builder = StateGraph(OrchestrationState)

        # Create node callables
        node_callables: Dict[str, Callable] = {}
        for node in workflow.nodes:
            callable_node = self._create_node_callable(node)
            if callable_node:
                node_callables[node.node_id] = callable_node

        # Add nodes to graph
        for node_id, callable_node in node_callables.items():
            builder.add_node(node_id, callable_node)

        # Add edges
        for edge in workflow.edges:
            if edge.source == "start" or edge.source == START:
                builder.add_edge(START, edge.target)
            elif edge.target == "end" or edge.target == END:
                builder.add_edge(edge.source, END)
            elif edge.is_conditional and edge.mapping:
                # Conditional edge
                condition_node = workflow.get_node(edge.source)
                if condition_node and condition_node.node_type == "conditional":
                    condition_func = self._create_condition_func(
                        condition_node.config.get("condition", "")
                    )
                    builder.add_conditional_edges(
                        edge.source,
                        condition_func,
                        edge.mapping
                    )
            else:
                builder.add_edge(edge.source, edge.target)

        # Set entry point if not already set
        if workflow.entry_node and workflow.entry_node not in ("start", START):
            builder.add_edge(START, workflow.entry_node)

        return builder.compile(checkpointer=self.checkpointer)

    def _create_condition_func(self, condition: str) -> Callable[[OrchestrationState], str]:
        """
        Create a condition function from a condition string.

        Supports simple conditions like:
        - "iteration < 3" -> checks iteration count
        - "has_errors" -> checks for errors
        - "messages_count > 2" -> checks message count

        Args:
            condition: Condition string

        Returns:
            Condition function
        """
        def condition_func(state: OrchestrationState) -> str:
            try:
                # Simple iteration check
                if "iteration" in condition:
                    max_iter = state.get('execution_metadata', {}).get('max_iterations', 3)
                    if state.get('iteration', 0) >= max_iter:
                        return "aggregate"
                    return "continue"

                # Error check
                if condition == "has_errors":
                    if state.get('errors'):
                        return "error"
                    return "success"

                # Default
                return "continue"
            except Exception as e:
                logger.error(f"Condition evaluation error: {e}")
                return "error"

        return condition_func

    async def execute(
        self,
        workflow: Workflow,
        user_input: str,
        thread_id: Optional[str] = None,
        shared_context: Optional[Dict[str, Any]] = None,
        max_iterations: int = 3
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a workflow with streaming updates.

        Args:
            workflow: Workflow to execute
            user_input: User's input message
            thread_id: Optional thread ID for checkpointing
            shared_context: Optional initial shared context
            max_iterations: Maximum dialogue iterations

        Yields:
            Execution events with type, node, and output
        """
        # Validate workflow
        errors = workflow.validate()
        if errors:
            yield {
                "type": "error",
                "errors": errors,
                "message": "Workflow validation failed"
            }
            return

        # Build graph
        try:
            graph = self.build_graph(workflow)
        except Exception as e:
            logger.error(f"Failed to build graph: {e}")
            yield {
                "type": "error",
                "errors": [str(e)],
                "message": "Failed to build workflow graph"
            }
            return

        # Create initial state
        initial_state = create_initial_state(
            user_input=user_input,
            shared_context=shared_context,
            max_iterations=max_iterations
        )
        initial_state['execution_metadata']['started_at'] = datetime.now().isoformat()

        # Track execution
        execution_id = thread_id or str(datetime.now().timestamp())
        self.active_executions[execution_id] = {
            "workflow_id": workflow.workflow_id,
            "started_at": datetime.now().isoformat(),
            "status": "running"
        }

        yield {
            "type": "workflow_started",
            "workflow_id": workflow.workflow_id,
            "workflow_name": workflow.name,
            "execution_id": execution_id
        }

        # Configure execution
        config = {}
        if thread_id and self.checkpointer:
            config["configurable"] = {"thread_id": thread_id}

        try:
            # Stream execution
            async for event in graph.astream(initial_state, config=config):
                for node_name, output in event.items():
                    # Emit node completion event
                    yield {
                        "type": "node_complete",
                        "node": node_name,
                        "output": output
                    }

                    # Notify via callback
                    if self.stream_callback and "messages" in output:
                        for msg in output["messages"]:
                            self.stream_callback(
                                msg["agent_id"],
                                msg["content"],
                                "orchestration"
                            )

                    # Handle errors
                    if "errors" in output and output["errors"]:
                        yield {
                            "type": "node_error",
                            "node": node_name,
                            "errors": output["errors"]
                        }

            # Execution complete
            self.active_executions[execution_id]["status"] = "completed"
            self.active_executions[execution_id]["completed_at"] = datetime.now().isoformat()

            yield {
                "type": "workflow_complete",
                "execution_id": execution_id
            }

        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            self.active_executions[execution_id]["status"] = "failed"
            self.active_executions[execution_id]["error"] = str(e)

            yield {
                "type": "workflow_error",
                "execution_id": execution_id,
                "error": str(e)
            }

    async def execute_parallel_nodes(
        self,
        nodes: List[WorkflowNode],
        state: OrchestrationState
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple nodes in parallel.

        Args:
            nodes: List of nodes to execute in parallel
            state: Current orchestration state

        Returns:
            List of results from all nodes
        """
        callables = []
        for node in nodes:
            callable_node = self._create_node_callable(node)
            if callable_node:
                callables.append(callable_node(state))

        results = await asyncio.gather(*callables, return_exceptions=True)

        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "errors": [{
                        "node_id": nodes[i].node_id,
                        "error": str(result)
                    }]
                })
            else:
                processed_results.append(result)

        return processed_results

    def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution.

        Args:
            execution_id: ID of execution to cancel

        Returns:
            True if cancelled successfully
        """
        if execution_id in self.active_executions:
            self.active_executions[execution_id]["status"] = "cancelled"
            self.active_executions[execution_id]["cancelled_at"] = datetime.now().isoformat()
            logger.info(f"Cancelled execution: {execution_id}")
            return True
        return False

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of an execution.

        Args:
            execution_id: ID of execution

        Returns:
            Execution status dict or None
        """
        return self.active_executions.get(execution_id)

    def get_all_executions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tracked executions.

        Returns:
            Dict of execution_id -> status
        """
        return self.active_executions.copy()
