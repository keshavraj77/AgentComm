#!/usr/bin/env python3
"""
Session Manager for A2A Client
Manages the communication between the UI and the backend components
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any

from agentcomm.agents.agent_registry import AgentRegistry
from agentcomm.agents.agent_comm import AgentComm
from agentcomm.llm.llm_router import LLMRouter
from agentcomm.llm.chat_history import ChatHistory

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages the communication between the UI and the backend components
    Handles agent and LLM interactions, chat history, and session state
    """
    
    def __init__(self, agent_registry: AgentRegistry, llm_router: LLMRouter, system_prompt: Optional[str] = None):
        """
        Initialize the session manager

        Args:
            agent_registry: Registry of available agents
            llm_router: Router for LLM requests
            system_prompt: Optional system prompt for LLM interactions
        """
        self.agent_registry = agent_registry
        self.llm_router = llm_router
        self.agent_comm: Optional[AgentComm] = None
        self.current_agent_id: Optional[str] = None
        self.current_llm_id: Optional[str] = None
        self.chat_histories: Dict[str, ChatHistory] = {}
        self.message_callbacks: List[Callable[[str, str, str], None]] = []
        self.streaming_callbacks: List[Callable[[str, str, str], None]] = []
        self.error_callbacks: List[Callable[[str], None]] = []
        self.system_prompt = system_prompt or "You are a helpful AI assistant. Provide clear, accurate, and concise responses to user queries."
        
    def register_message_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Register a callback for new messages
        
        Args:
            callback: Function to call when a new message is received
                     Arguments: (sender_id, message_text, message_type)
        """
        self.message_callbacks.append(callback)
        
    def register_streaming_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Register a callback for streaming messages
        
        Args:
            callback: Function to call when a streaming chunk is received
                     Arguments: (sender_id, message_chunk, message_type)
        """
        self.streaming_callbacks.append(callback)
        
    def register_error_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback for errors
        
        Args:
            callback: Function to call when an error occurs
                     Arguments: (error_message)
        """
        self.error_callbacks.append(callback)
        
    def select_agent(self, agent_id: str) -> bool:
        """
        Select an agent to interact with
        
        Args:
            agent_id: ID of the agent to select
            
        Returns:
            True if the agent was selected successfully, False otherwise
        """
        try:
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                return False
                
            self.current_agent_id = agent_id
            self.agent_comm = AgentComm(agent)
            
            # Create chat history for this agent if it doesn't exist
            if agent_id not in self.chat_histories:
                self.chat_histories[agent_id] = ChatHistory()
                
            return True
        except Exception as e:
            logger.error(f"Error selecting agent {agent_id}: {e}")
            self._notify_error(f"Error selecting agent: {e}")
            return False
            
    def select_llm(self, llm_id: str) -> bool:
        """
        Select an LLM to interact with directly
        
        Args:
            llm_id: ID of the LLM to select
            
        Returns:
            True if the LLM was selected successfully, False otherwise
        """
        try:
            if not self.llm_router.has_provider(llm_id):
                logger.error(f"LLM provider {llm_id} not found")
                return False
                
            self.current_llm_id = llm_id
            self.current_agent_id = None
            self.agent_comm = None
            
            # Create chat history for this LLM if it doesn't exist
            if llm_id not in self.chat_histories:
                self.chat_histories[llm_id] = ChatHistory()
                
            return True
        except Exception as e:
            logger.error(f"Error selecting LLM {llm_id}: {e}")
            self._notify_error(f"Error selecting LLM: {e}")
            return False
    
    def get_current_chat_history(self) -> Optional[ChatHistory]:
        """
        Get the chat history for the current agent or LLM
        
        Returns:
            ChatHistory object or None if no agent or LLM is selected
        """
        if self.current_agent_id:
            return self.chat_histories.get(self.current_agent_id)
        elif self.current_llm_id:
            return self.chat_histories.get(self.current_llm_id)
        return None
        
    async def send_message(self, message: str, stream: bool = True) -> bool:
        """
        Send a message to the current agent or LLM
        
        Args:
            message: Message text to send
            stream: Whether to stream the response
            
        Returns:
            True if the message was sent successfully, False otherwise
        """
        if not message.strip():
            return False
            
        try:
            # Add user message to chat history
            history = self.get_current_chat_history()
            if history:
                history.add_user_message(message)
                
            # Notify callbacks about the user message
            for callback in self.message_callbacks:
                callback("user", message, "user")
                
            if self.current_agent_id and self.agent_comm:
                # Send message to agent
                if stream:
                    async for chunk in self.agent_comm.send_message_stream(message):
                        for callback in self.streaming_callbacks:
                            callback(self.current_agent_id, chunk, "agent")

                    # Get the full response from the agent
                    response = await self.agent_comm.get_last_response()

                    # Add agent response to chat history
                    if history and response:
                        history.add_assistant_message(response)

                    # Don't notify message_callbacks for streaming - the UI already has the complete message
                    # from the streaming chunks
                else:
                    response = await self.agent_comm.send_message(message)
                    
                    # Add agent response to chat history
                    if history and response:
                        history.add_assistant_message(response)
                        
                    # Notify callbacks about the agent response
                    for callback in self.message_callbacks:
                        callback(self.current_agent_id, response, "agent")
                        
                return True
                
            elif self.current_llm_id:
                # Send message to LLM
                logger.info(f"Sending message to LLM: {self.current_llm_id}")
                logger.debug(f"Message: {message[:100]}...")

                if stream:
                    async for chunk in self.llm_router.generate_stream(
                        self.current_llm_id, message, history.get_messages() if history else None,
                        system=self.system_prompt
                    ):
                        for callback in self.streaming_callbacks:
                            callback(self.current_llm_id, chunk, "llm")

                    # Get the full response from the LLM
                    response = await self.llm_router.get_last_response(self.current_llm_id)
                    logger.info(f"LLM response received. Length: {len(response)}")

                    # Add LLM response to chat history
                    if history and response:
                        history.add_assistant_message(response)

                    # Don't notify message_callbacks for streaming - the UI already has the complete message
                    # from the streaming chunks
                else:
                    response = await self.llm_router.generate(
                        self.current_llm_id, message, history.get_messages() if history else None,
                        system=self.system_prompt
                    )
                    logger.info(f"LLM response received (non-streaming). Length: {len(response)}")
                    
                    # Add LLM response to chat history
                    if history and response:
                        history.add_assistant_message(response)
                        
                    # Notify callbacks about the LLM response
                    for callback in self.message_callbacks:
                        callback(self.current_llm_id, response, "llm")
                        
                return True
            else:
                logger.error("No agent or LLM selected")
                self._notify_error("No agent or LLM selected")
                return False
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self._notify_error(f"Error sending message: {e}")
            return False
            
    def _notify_error(self, error_message: str) -> None:
        """
        Notify error callbacks about an error
        
        Args:
            error_message: Error message to send
        """
        for callback in self.error_callbacks:
            callback(error_message)


