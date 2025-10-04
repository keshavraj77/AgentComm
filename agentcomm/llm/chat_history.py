#!/usr/bin/env python3
"""
Chat History for A2A Client
Manages the chat history for conversations with agents and LLMs
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

class ChatMessage:
    """
    Represents a single message in a chat history
    """
    
    def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None):
        """
        Initialize a chat message
        
        Args:
            role: Role of the message sender (user, assistant, system)
            content: Content of the message
            timestamp: Timestamp of the message (defaults to current time)
        """
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the message to a dictionary
        
        Returns:
            Dictionary representation of the message
        """
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """
        Create a message from a dictionary
        
        Args:
            data: Dictionary representation of the message
            
        Returns:
            ChatMessage object
        """
        timestamp = datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else None
        return cls(data["role"], data["content"], timestamp)


class ChatHistory:
    """
    Manages the chat history for a conversation
    """
    
    def __init__(self):
        """
        Initialize an empty chat history
        """
        self.messages: List[ChatMessage] = []
        
    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the chat history
        
        Args:
            role: Role of the message sender (user, assistant, system)
            content: Content of the message
        """
        self.messages.append(ChatMessage(role, content))
        
    def add_user_message(self, content: str) -> None:
        """
        Add a user message to the chat history
        
        Args:
            content: Content of the message
        """
        self.add_message("user", content)
        
    def add_assistant_message(self, content: str) -> None:
        """
        Add an assistant message to the chat history
        
        Args:
            content: Content of the message
        """
        self.add_message("assistant", content)
        
    def add_system_message(self, content: str) -> None:
        """
        Add a system message to the chat history
        
        Args:
            content: Content of the message
        """
        self.add_message("system", content)
        
    def get_messages(self) -> List[Dict[str, str]]:
        """
        Get the messages in a format suitable for LLM APIs
        
        Returns:
            List of message dictionaries with role and content
        """
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]
        
    def get_full_messages(self) -> List[Dict[str, Any]]:
        """
        Get the full message objects including timestamps
        
        Returns:
            List of full message dictionaries
        """
        return [msg.to_dict() for msg in self.messages]
        
    def clear(self) -> None:
        """
        Clear the chat history
        """
        self.messages = []
        
    def save_to_dict(self) -> Dict[str, Any]:
        """
        Save the chat history to a dictionary
        
        Returns:
            Dictionary representation of the chat history
        """
        return {
            "messages": [msg.to_dict() for msg in self.messages]
        }
        
    @classmethod
    def load_from_dict(cls, data: Dict[str, Any]) -> 'ChatHistory':
        """
        Load a chat history from a dictionary
        
        Args:
            data: Dictionary representation of the chat history
            
        Returns:
            ChatHistory object
        """
        history = cls()
        for msg_data in data.get("messages", []):
            history.messages.append(ChatMessage.from_dict(msg_data))
        return history


