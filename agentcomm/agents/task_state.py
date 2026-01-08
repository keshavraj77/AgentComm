"""
A2A Task State definitions and utilities
"""

from enum import Enum
from typing import Optional


class TaskState(Enum):
    """
    A2A Task State enum matching the protocol specification.

    Task states are categorized as:
    - Terminal: completed, failed, cancelled, rejected (task is done)
    - Interrupted: input_required, auth_required (waiting for user action)
    - Active: submitted, working (task is in progress)
    - Unknown: unspecified
    """
    UNSPECIFIED = "unspecified"
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INPUT_REQUIRED = "input-required"
    REJECTED = "rejected"
    AUTH_REQUIRED = "auth-required"

    @classmethod
    def from_string(cls, state_str: str) -> "TaskState":
        """
        Parse a task state from string representation.

        Handles various formats:
        - "TaskState.completed" (SDK format)
        - "completed" (plain format)
        - "COMPLETED" (uppercase)
        - "input-required" or "input_required" (hyphen/underscore variants)

        Args:
            state_str: String representation of the state

        Returns:
            TaskState enum value
        """
        if not state_str:
            return cls.UNSPECIFIED

        # Normalize the string
        normalized = str(state_str).lower()

        # Remove "TaskState." prefix if present (SDK format)
        if "taskstate." in normalized:
            normalized = normalized.split("taskstate.")[-1]

        # Handle underscore/hyphen variants
        normalized = normalized.replace("_", "-")

        # Map to enum values
        state_mapping = {
            "unspecified": cls.UNSPECIFIED,
            "submitted": cls.SUBMITTED,
            "working": cls.WORKING,
            "completed": cls.COMPLETED,
            "failed": cls.FAILED,
            "cancelled": cls.CANCELLED,
            "canceled": cls.CANCELLED,  # Handle American spelling
            "input-required": cls.INPUT_REQUIRED,
            "rejected": cls.REJECTED,
            "auth-required": cls.AUTH_REQUIRED,
        }

        return state_mapping.get(normalized, cls.UNSPECIFIED)

    def is_terminal(self) -> bool:
        """Check if this is a terminal state (task is done)"""
        return self in (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.REJECTED,
        )

    def is_interrupted(self) -> bool:
        """Check if this is an interrupted state (waiting for user action)"""
        return self in (
            TaskState.INPUT_REQUIRED,
            TaskState.AUTH_REQUIRED,
        )

    def is_active(self) -> bool:
        """Check if this is an active state (task in progress)"""
        return self in (
            TaskState.SUBMITTED,
            TaskState.WORKING,
        )

    def should_stream_content(self) -> bool:
        """
        Check if content should be streamed directly to user.

        Terminal states and interrupted states should stream content.
        Active states should show as status updates.
        """
        return self.is_terminal() or self.is_interrupted()

    def should_show_status(self) -> bool:
        """
        Check if status messages should be shown in loading indicator.

        Active states (submitted, working) should show status messages.
        """
        return self.is_active()


class TaskStateResult:
    """
    Result container for task state handling.

    Attributes:
        state: Current TaskState
        content: Content to stream to user (for terminal/interrupted states)
        status_message: Status message for loading indicator (for active states)
        should_poll: Whether to poll/wait for more updates
        is_final: Whether this is the final response
    """

    def __init__(
        self,
        state: TaskState,
        content: Optional[str] = None,
        status_message: Optional[str] = None,
        should_poll: bool = False,
        is_final: bool = False,
        task_id: Optional[str] = None,
    ):
        self.state = state
        self.content = content
        self.status_message = status_message
        self.should_poll = should_poll
        self.is_final = is_final
        self.task_id = task_id

    def __repr__(self) -> str:
        return (
            f"TaskStateResult(state={self.state.value}, "
            f"content_len={len(self.content) if self.content else 0}, "
            f"status={self.status_message}, "
            f"should_poll={self.should_poll}, "
            f"is_final={self.is_final})"
        )
