#!/usr/bin/env python3
"""
Thread management for AgentComm
Represents individual conversation threads with agents or LLMs
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from agentcomm.llm.chat_history import ChatHistory


class Thread:
    """
    Represents a conversation thread with an agent or LLM
    """

    def __init__(
        self,
        entity_id: str,
        entity_type: str,
        thread_id: Optional[str] = None,
        title: Optional[str] = None,
        created_at: Optional[datetime] = None,
        chat_history: Optional[ChatHistory] = None
    ):
        """
        Initialize a thread

        Args:
            entity_id: ID of the agent or LLM
            entity_type: Type of entity ("agent" or "llm")
            thread_id: Unique thread ID (auto-generated if not provided)
            title: Thread title (auto-generated if not provided)
            created_at: Creation timestamp (defaults to current time)
            chat_history: Chat history for this thread (new if not provided)
        """
        self.thread_id = thread_id or str(uuid.uuid4())
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.created_at = created_at or datetime.now()
        self.title = title or f"Chat {self.created_at.strftime('%H:%M:%S')}"
        self.chat_history = chat_history or ChatHistory()

    def rename(self, new_title: str) -> None:
        """
        Rename the thread

        Args:
            new_title: New title for the thread
        """
        self.title = new_title

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the thread to a dictionary for persistence

        Returns:
            Dictionary representation of the thread
        """
        return {
            "thread_id": self.thread_id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "chat_history": self.chat_history.save_to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Thread':
        """
        Create a thread from a dictionary

        Args:
            data: Dictionary representation of the thread

        Returns:
            Thread object
        """
        chat_history = ChatHistory.load_from_dict(data.get("chat_history", {}))
        created_at = datetime.fromisoformat(data["created_at"]) if "created_at" in data else None

        return cls(
            entity_id=data["entity_id"],
            entity_type=data["entity_type"],
            thread_id=data.get("thread_id"),
            title=data.get("title"),
            created_at=created_at,
            chat_history=chat_history
        )
