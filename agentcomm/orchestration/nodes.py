"""
LangGraph Node Wrappers

Wraps A2A agents and LLM providers as LangGraph nodes that can be
composed into orchestration workflows.
"""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from agentcomm.orchestration.state import OrchestrationState, AgentMessage

logger = logging.getLogger(__name__)


class A2AAgentNode:
    """
    Wraps an A2A agent as a LangGraph node.

    Integrates with the existing AgentComm class to communicate with
    A2A protocol-compliant agents.

    Example:
        node = A2AAgentNode(agent, webhook_handler, ngrok_manager)
        result = await node(state)
    """

    def __init__(
        self,
        agent,
        webhook_handler=None,
        ngrok_manager=None,
        message_formatter: Optional[Callable[[OrchestrationState], str]] = None,
        timeout: int = 60
    ):
        """
        Initialize the A2A agent node.

        Args:
            agent: Agent configuration object from AgentRegistry
            webhook_handler: WebhookHandler for push notifications
            ngrok_manager: NgrokManager for tunnel management
            message_formatter: Custom function to format state into agent input
            timeout: Request timeout in seconds
        """
        from agentcomm.agents.agent_comm import AgentComm

        self.agent = agent
        self.agent_comm = AgentComm(
            agent,
            use_sdk=True,
            webhook_handler=webhook_handler,
            ngrok_manager=ngrok_manager
        )
        self.message_formatter = message_formatter or self._default_formatter
        self.timeout = timeout

    def _default_formatter(self, state: OrchestrationState) -> str:
        """
        Format orchestration state into a message for the agent.

        Includes user input and previous agent responses for context,
        enabling collaborative dialogue patterns.
        """
        parts = [f"User request: {state['user_input']}"]

        # Include previous messages for context in dialogue workflows
        if state.get('messages'):
            parts.append("\n--- Previous Responses ---")
            for msg in state['messages']:
                parts.append(f"\n[{msg['agent_name']}]:\n{msg['content']}")

        # Include any shared context
        if state.get('shared_context'):
            context_str = "\n".join(
                f"- {k}: {v}" for k, v in state['shared_context'].items()
            )
            parts.append(f"\n--- Shared Context ---\n{context_str}")

        return "\n".join(parts)

    async def __call__(self, state: OrchestrationState) -> Dict[str, Any]:
        """
        Execute the agent node.

        Args:
            state: Current orchestration state

        Returns:
            State update with agent message or error
        """
        try:
            logger.info(f"Executing A2A agent node: {self.agent.id}")

            # Format input for this agent
            input_message = self.message_formatter(state)

            # Collect streaming response
            full_response = ""
            async for chunk in self.agent_comm.send_message_stream(input_message):
                # Filter out status signals, accumulate content
                if not chunk.startswith("<<<"):
                    full_response += chunk

            # Create agent message
            agent_message = AgentMessage(
                agent_id=self.agent.id,
                agent_name=self.agent.name,
                content=full_response.strip(),
                timestamp=datetime.now().isoformat(),
                metadata={
                    "context_id": self.agent_comm.context_id,
                    "node_type": "agent"
                }
            )

            logger.info(f"A2A agent {self.agent.id} completed successfully")
            return {"messages": [agent_message]}

        except Exception as e:
            logger.error(f"A2A agent {self.agent.id} failed: {e}")
            return {
                "errors": [{
                    "agent_id": self.agent.id,
                    "agent_name": self.agent.name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }]
            }


class LLMNode:
    """
    Wraps an LLM provider as a LangGraph node.

    Integrates with the existing LLMRouter to access various LLM providers
    (OpenAI, Anthropic, Gemini, Local).

    Example:
        node = LLMNode(llm_router, "OpenAI", system_prompt="You are helpful")
        result = await node(state)
    """

    def __init__(
        self,
        llm_router,
        provider_name: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        message_formatter: Optional[Callable[[OrchestrationState], str]] = None
    ):
        """
        Initialize the LLM node.

        Args:
            llm_router: LLMRouter instance for provider access
            provider_name: Name of the provider (e.g., "OpenAI", "Anthropic")
            model: Specific model to use (default: provider's default)
            system_prompt: System prompt for the LLM
            temperature: Sampling temperature
            message_formatter: Custom function to format state into LLM input
        """
        self.llm_router = llm_router
        self.provider_name = provider_name
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.message_formatter = message_formatter or self._default_formatter

    def _default_formatter(self, state: OrchestrationState) -> str:
        """
        Format orchestration state into a message for the LLM.
        """
        parts = [state['user_input']]

        # Include previous messages for context
        if state.get('messages'):
            parts.insert(0, "Previous responses from other agents:")
            for msg in state['messages']:
                parts.insert(1, f"\n[{msg['agent_name']}]: {msg['content']}")
            parts.append("\n---\nBased on the above context, please provide your response:")

        return "\n".join(parts)

    async def __call__(self, state: OrchestrationState) -> Dict[str, Any]:
        """
        Execute the LLM node.

        Args:
            state: Current orchestration state

        Returns:
            State update with LLM message or error
        """
        try:
            logger.info(f"Executing LLM node: {self.provider_name}")

            # Format input
            input_message = self.message_formatter(state)

            # Build chat history from previous messages if needed
            chat_history = []
            for msg in state.get('messages', []):
                chat_history.append({
                    "role": "assistant",
                    "content": f"[{msg['agent_name']}]: {msg['content']}"
                })

            # Call LLM via router
            full_response = ""
            async for chunk in self.llm_router.generate_stream(
                provider_name=self.provider_name,
                prompt=input_message,
                model=self.model,
                system=self.system_prompt,
                temperature=self.temperature
            ):
                # Filter out thinking signals
                if not chunk.startswith("<<<THINKING>>>"):
                    full_response += chunk

            # Create agent message
            agent_message = AgentMessage(
                agent_id=f"llm_{self.provider_name}",
                agent_name=self.provider_name,
                content=full_response.strip(),
                timestamp=datetime.now().isoformat(),
                metadata={
                    "model": self.model or "default",
                    "node_type": "llm"
                }
            )

            logger.info(f"LLM {self.provider_name} completed successfully")
            return {"messages": [agent_message]}

        except Exception as e:
            logger.error(f"LLM {self.provider_name} failed: {e}")
            return {
                "errors": [{
                    "agent_id": f"llm_{self.provider_name}",
                    "agent_name": self.provider_name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }]
            }


class AggregatorNode:
    """
    Aggregates outputs from multiple agents into a final response.

    Supports different aggregation strategies:
    - concat: Concatenate all responses
    - summarize: Use an LLM to summarize responses
    - select_best: Select the best response based on criteria
    """

    def __init__(
        self,
        strategy: str = "concat",
        llm_router=None,
        summarizer_provider: str = "OpenAI"
    ):
        """
        Initialize the aggregator node.

        Args:
            strategy: Aggregation strategy ("concat", "summarize", "select_best")
            llm_router: LLMRouter for summarization (required if strategy="summarize")
            summarizer_provider: LLM provider to use for summarization
        """
        self.strategy = strategy
        self.llm_router = llm_router
        self.summarizer_provider = summarizer_provider

    async def __call__(self, state: OrchestrationState) -> Dict[str, Any]:
        """
        Aggregate messages from all agents.

        Args:
            state: Current orchestration state

        Returns:
            State update with final_output
        """
        messages = state.get('messages', [])

        if not messages:
            return {"final_output": "No responses to aggregate"}

        if self.strategy == "concat":
            output = self._concat_messages(messages)
        elif self.strategy == "summarize":
            output = await self._summarize_messages(messages, state['user_input'])
        elif self.strategy == "select_best":
            output = self._select_best(messages)
        else:
            output = self._concat_messages(messages)

        return {"final_output": output}

    def _concat_messages(self, messages: list) -> str:
        """Concatenate all messages"""
        parts = []
        for msg in messages:
            parts.append(f"**{msg['agent_name']}:**\n{msg['content']}")
        return "\n\n---\n\n".join(parts)

    async def _summarize_messages(self, messages: list, user_input: str) -> str:
        """Use LLM to summarize all responses"""
        if not self.llm_router:
            return self._concat_messages(messages)

        # Build prompt for summarization
        responses_text = "\n\n".join([
            f"[{msg['agent_name']}]: {msg['content']}"
            for msg in messages
        ])

        prompt = f"""Original user request: {user_input}

The following responses were received from multiple agents:

{responses_text}

Please synthesize these responses into a single coherent answer that addresses the user's original request."""

        # Generate summary
        summary = ""
        async for chunk in self.llm_router.generate_stream(
            provider_name=self.summarizer_provider,
            prompt=prompt,
            system="You are a helpful assistant that synthesizes multiple responses into coherent summaries."
        ):
            if not chunk.startswith("<<<"):
                summary += chunk

        return summary.strip()

    def _select_best(self, messages: list) -> str:
        """Select the longest/most detailed response"""
        if not messages:
            return ""
        best = max(messages, key=lambda m: len(m['content']))
        return f"**{best['agent_name']}:**\n{best['content']}"


class ConditionalNode:
    """
    Routes workflow based on conditions.

    Evaluates a condition against the current state and returns
    the appropriate next node.
    """

    def __init__(
        self,
        condition_func: Callable[[OrchestrationState], str],
        route_mapping: Dict[str, str]
    ):
        """
        Initialize the conditional node.

        Args:
            condition_func: Function that evaluates state and returns a route key
            route_mapping: Mapping from route keys to node IDs
        """
        self.condition_func = condition_func
        self.route_mapping = route_mapping

    def __call__(self, state: OrchestrationState) -> str:
        """
        Evaluate condition and return next node.

        Args:
            state: Current orchestration state

        Returns:
            Node ID to route to
        """
        result = self.condition_func(state)
        return self.route_mapping.get(result, list(self.route_mapping.values())[0])


def create_dialogue_condition(max_iterations: int = 3):
    """
    Create a condition function for dialogue loops.

    Returns a function that checks if the dialogue should continue
    or move to aggregation.

    Args:
        max_iterations: Maximum number of dialogue rounds

    Returns:
        Condition function for use with ConditionalNode
    """
    def condition(state: OrchestrationState) -> str:
        current_iteration = state.get('iteration', 0)
        max_iter = state.get('execution_metadata', {}).get('max_iterations', max_iterations)

        if current_iteration >= max_iter:
            return "aggregate"

        # Could add consensus detection here
        return "continue"

    return condition
