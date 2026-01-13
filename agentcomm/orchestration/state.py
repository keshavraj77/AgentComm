"""
Orchestration State Schema

Defines the state structure for LangGraph-based agent orchestration workflows.
The state supports parallel execution and collaborative dialogue patterns.
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from operator import add


class AgentMessage(TypedDict):
    """
    Message from an agent or LLM in the orchestration workflow.

    Attributes:
        agent_id: Unique identifier of the agent/LLM
        agent_name: Human-readable name
        content: The message content
        timestamp: ISO format timestamp
        metadata: Additional context (e.g., context_id, model used)
    """
    agent_id: str
    agent_name: str
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]]


class OrchestrationState(TypedDict):
    """
    State schema for agent orchestration workflows.

    Uses LangGraph's reducer pattern for parallel-safe operations:
    - 'messages' and 'errors' use the 'add' reducer to concatenate
      results from parallel node executions.

    Attributes:
        user_input: The original user request
        messages: Accumulated messages from all agents (parallel-safe)
        shared_context: Shared data accessible by all nodes
        iteration: Current iteration count for dialogue loops
        final_output: Aggregated final output
        errors: Error tracking (parallel-safe)
        execution_metadata: Runtime metadata (max_iterations, etc.)
    """
    # User's original input
    user_input: str

    # Messages from all agents - uses 'add' reducer for parallel safety
    messages: Annotated[List[AgentMessage], add]

    # Shared context any node can read/write
    shared_context: Dict[str, Any]

    # Iteration count for dialogue loops
    iteration: int

    # Final aggregated output
    final_output: Optional[str]

    # Error tracking - uses 'add' reducer for parallel safety
    errors: Annotated[List[Dict[str, str]], add]

    # Execution metadata (max_iterations, timeout, etc.)
    execution_metadata: Dict[str, Any]


def create_initial_state(
    user_input: str,
    shared_context: Optional[Dict[str, Any]] = None,
    max_iterations: int = 3
) -> OrchestrationState:
    """
    Create an initial orchestration state.

    Args:
        user_input: The user's request to process
        shared_context: Optional initial shared context
        max_iterations: Maximum dialogue iterations (default: 3)

    Returns:
        A properly initialized OrchestrationState
    """
    return OrchestrationState(
        user_input=user_input,
        messages=[],
        shared_context=shared_context or {},
        iteration=0,
        final_output=None,
        errors=[],
        execution_metadata={
            "max_iterations": max_iterations,
            "started_at": None,
            "completed_at": None,
        }
    )
