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
from agentcomm.agents.webhook_handler import WebhookHandler
from agentcomm.agents.ngrok_manager import NgrokManager
from agentcomm.llm.llm_router import LLMRouter
from agentcomm.llm.chat_history import ChatHistory
from agentcomm.core.thread import Thread

logger = logging.getLogger(__name__)

# Maximum number of threads per entity
MAX_THREADS_PER_ENTITY = 4

class SessionManager:
    """
    Manages the communication between the UI and the backend components
    Handles agent and LLM interactions, chat history, and session state
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        llm_router: LLMRouter,
        system_prompt: Optional[str] = None,
        webhook_handler: Optional[WebhookHandler] = None,
        ngrok_manager: Optional[NgrokManager] = None
    ):
        """
        Initialize the session manager

        Args:
            agent_registry: Registry of available agents
            llm_router: Router for LLM requests
            system_prompt: Optional system prompt for LLM interactions
            webhook_handler: Optional webhook handler for push notifications
            ngrok_manager: Optional ngrok manager for secure tunneling
        """
        self.agent_registry = agent_registry
        self.llm_router = llm_router
        self.agent_comm: Optional[AgentComm] = None
        self.webhook_handler = webhook_handler
        self.ngrok_manager = ngrok_manager
        self.current_entity_id: Optional[str] = None
        self.current_entity_type: Optional[str] = None
        self.current_thread_id: Optional[str] = None

        # Threads structure: {entity_id: {thread_id: Thread}}
        self.threads: Dict[str, Dict[str, Thread]] = {}

        self.message_callbacks: List[Callable[[str, str, str], None]] = []
        self.streaming_callbacks: List[Callable[[str, str, str], None]] = []
        self.error_callbacks: List[Callable[[str], None]] = []
        self.thread_callbacks: List[Callable[[], None]] = []  # Callbacks for thread changes
        self.system_prompt = system_prompt or "You are a helpful AI assistant. Provide clear, accurate, and concise responses to user queries."

        # Auto-save callback
        self.auto_save_callback: Optional[Callable[[], None]] = None

    async def start(self):
        """Start the session manager and async components"""
        # Start webhook handler if available
        if self.webhook_handler:
            logger.info("Starting webhook server...")
            asyncio.create_task(self.webhook_handler.start())
            # Give the server a moment to start
            await asyncio.sleep(0.5)
            logger.info(f"Webhook server started on {self.webhook_handler.host}:{self.webhook_handler.port}")

        # Start ngrok tunnel if ngrok manager is available
        if self.ngrok_manager:
            await self._start_ngrok_tunnel()
        
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

    def register_thread_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback for thread changes

        Args:
            callback: Function to call when threads are modified
        """
        self.thread_callbacks.append(callback)

    def register_auto_save_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback for auto-saving threads

        Args:
            callback: Function to call when threads should be saved
        """
        self.auto_save_callback = callback

    async def _start_ngrok_tunnel(self):
        """Start ngrok tunnel for webhook handler"""
        if not self.webhook_handler or not self.ngrok_manager:
            return

        try:
            logger.info("Starting ngrok tunnel for webhook handler...")
            public_url = await self.ngrok_manager.start_tunnel(self.webhook_handler.port)
            if public_url:
                logger.info(f"ngrok tunnel started: {public_url}")
            else:
                logger.error("Failed to start ngrok tunnel")
        except Exception as e:
            logger.error(f"Error starting ngrok tunnel: {e}")

    def select_agent(self, agent_id: str, thread_id: Optional[str] = None) -> bool:
        """
        Select an agent to interact with

        Args:
            agent_id: ID of the agent to select
            thread_id: Optional thread ID to select (creates new if None)

        Returns:
            True if the agent was selected successfully, False otherwise
        """
        try:
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                return False

            self.current_entity_id = agent_id
            self.current_entity_type = "agent"
            
            # Initialize threads dict for this agent if it doesn't exist
            if agent_id not in self.threads:
                self.threads[agent_id] = {}

            # Select or create thread
            if thread_id and thread_id in self.threads[agent_id]:
                self.current_thread_id = thread_id
            elif self.threads[agent_id]:
                # Select the most recent thread
                most_recent = max(self.threads[agent_id].values(), key=lambda t: t.created_at)
                self.current_thread_id = most_recent.thread_id
            else:
                # Create a new thread
                self.current_thread_id = self.create_thread(agent_id, "agent")
            
            # Create AgentComm with the current thread_id
            self.agent_comm = AgentComm(
                agent,
                webhook_handler=self.webhook_handler,
                ngrok_manager=self.ngrok_manager,
                thread_id=self.current_thread_id
            )

            return True
        except Exception as e:
            logger.error(f"Error selecting agent {agent_id}: {e}")
            self._notify_error(f"Error selecting agent: {e}")
            return False

    def select_llm(self, llm_id: str, thread_id: Optional[str] = None) -> bool:
        """
        Select an LLM to interact with directly

        Args:
            llm_id: ID of the LLM to select
            thread_id: Optional thread ID to select (creates new if None)

        Returns:
            True if the LLM was selected successfully, False otherwise
        """
        try:
            if not self.llm_router.has_provider(llm_id):
                logger.error(f"LLM provider {llm_id} not found")
                return False

            self.current_entity_id = llm_id
            self.current_entity_type = "llm"
            self.agent_comm = None

            # Initialize threads dict for this LLM if it doesn't exist
            if llm_id not in self.threads:
                self.threads[llm_id] = {}

            # Select or create thread
            if thread_id and thread_id in self.threads[llm_id]:
                self.current_thread_id = thread_id
            elif self.threads[llm_id]:
                # Select the most recent thread
                most_recent = max(self.threads[llm_id].values(), key=lambda t: t.created_at)
                self.current_thread_id = most_recent.thread_id
            else:
                # Create a new thread
                self.current_thread_id = self.create_thread(llm_id, "llm")

            return True
        except Exception as e:
            logger.error(f"Error selecting LLM {llm_id}: {e}")
            self._notify_error(f"Error selecting LLM: {e}")
            return False
    
    def create_thread(self, entity_id: str, entity_type: str) -> Optional[str]:
        """
        Create a new thread for an entity

        Args:
            entity_id: ID of the agent or LLM
            entity_type: Type of entity ("agent" or "llm")

        Returns:
            Thread ID if created successfully, None otherwise
        """
        try:
            # Check if entity has reached max threads
            if entity_id in self.threads and len(self.threads[entity_id]) >= MAX_THREADS_PER_ENTITY:
                logger.warning(f"Entity {entity_id} has reached maximum thread limit ({MAX_THREADS_PER_ENTITY})")
                self._notify_error(f"Maximum thread limit reached ({MAX_THREADS_PER_ENTITY})")
                return None

            # Create new thread
            thread = Thread(entity_id, entity_type)

            # Initialize threads dict for this entity if needed
            if entity_id not in self.threads:
                self.threads[entity_id] = {}

            # Add thread
            self.threads[entity_id][thread.thread_id] = thread
            logger.info(f"Created thread {thread.thread_id} for {entity_type} {entity_id}")

            # Notify callbacks
            self._notify_thread_change()

            return thread.thread_id
        except Exception as e:
            logger.error(f"Error creating thread: {e}")
            self._notify_error(f"Error creating thread: {e}")
            return None

    def switch_thread(self, thread_id: str) -> bool:
        """
        Switch to a different thread

        Args:
            thread_id: ID of the thread to switch to

        Returns:
            True if switched successfully, False otherwise
        """
        try:
            if not self.current_entity_id:
                logger.error("No entity selected")
                return False

            if thread_id in self.threads.get(self.current_entity_id, {}):
                self.current_thread_id = thread_id
                logger.info(f"Switched to thread {thread_id}")
                return True
            else:
                logger.error(f"Thread {thread_id} not found for entity {self.current_entity_id}")
                return False
        except Exception as e:
            logger.error(f"Error switching thread: {e}")
            return False

    def delete_thread(self, thread_id: str) -> bool:
        """
        Delete a thread

        Args:
            thread_id: ID of the thread to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if not self.current_entity_id:
                logger.error("No entity selected")
                return False

            if thread_id in self.threads.get(self.current_entity_id, {}):
                del self.threads[self.current_entity_id][thread_id]
                logger.info(f"Deleted thread {thread_id}")

                # If we deleted the current thread, switch to another or create new
                if self.current_thread_id == thread_id:
                    if self.threads[self.current_entity_id]:
                        # Switch to the first available thread
                        self.current_thread_id = list(self.threads[self.current_entity_id].keys())[0]
                    else:
                        # Create a new thread
                        self.current_thread_id = self.create_thread(self.current_entity_id, self.current_entity_type)

                # Notify callbacks
                self._notify_thread_change()

                return True
            else:
                logger.error(f"Thread {thread_id} not found")
                return False
        except Exception as e:
            logger.error(f"Error deleting thread: {e}")
            return False

    def rename_thread(self, thread_id: str, new_title: str) -> bool:
        """
        Rename a thread

        Args:
            thread_id: ID of the thread to rename
            new_title: New title for the thread

        Returns:
            True if renamed successfully, False otherwise
        """
        try:
            if not self.current_entity_id:
                logger.error("No entity selected")
                return False

            if thread_id in self.threads.get(self.current_entity_id, {}):
                self.threads[self.current_entity_id][thread_id].rename(new_title)
                logger.info(f"Renamed thread {thread_id} to '{new_title}'")

                # Notify callbacks
                self._notify_thread_change()

                return True
            else:
                logger.error(f"Thread {thread_id} not found")
                return False
        except Exception as e:
            logger.error(f"Error renaming thread: {e}")
            return False

    def get_threads_for_entity(self, entity_id: Optional[str] = None) -> List[Thread]:
        """
        Get all threads for an entity

        Args:
            entity_id: ID of the entity (uses current entity if None)

        Returns:
            List of Thread objects
        """
        entity_id = entity_id or self.current_entity_id
        if not entity_id:
            return []

        return list(self.threads.get(entity_id, {}).values())

    def get_current_thread(self) -> Optional[Thread]:
        """
        Get the current thread

        Returns:
            Thread object or None if no thread is selected
        """
        if self.current_entity_id and self.current_thread_id:
            return self.threads.get(self.current_entity_id, {}).get(self.current_thread_id)
        return None

    def get_current_chat_history(self) -> Optional[ChatHistory]:
        """
        Get the chat history for the current thread

        Returns:
            ChatHistory object or None if no thread is selected
        """
        thread = self.get_current_thread()
        return thread.chat_history if thread else None
        
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
                
            if self.current_entity_type == "agent" and self.agent_comm:
                # Send message to agent
                if stream:
                    async for chunk in self.agent_comm.send_message_stream(message):
                        for callback in self.streaming_callbacks:
                            callback(self.current_entity_id, chunk, "agent")

                    # Get the full response from the agent
                    response = await self.agent_comm.get_last_response()

                    # Add agent response to chat history
                    if history and response:
                        history.add_assistant_message(response)

                    # Trigger auto-save
                    if self.auto_save_callback:
                        self.auto_save_callback()

                    # Don't notify message_callbacks for streaming - the UI already has the complete message
                    # from the streaming chunks
                else:
                    response = await self.agent_comm.send_message(message)

                    # Add agent response to chat history
                    if history and response:
                        history.add_assistant_message(response)

                    # Trigger auto-save
                    if self.auto_save_callback:
                        self.auto_save_callback()

                    # Notify callbacks about the agent response
                    for callback in self.message_callbacks:
                        callback(self.current_entity_id, response, "agent")

                return True

            elif self.current_entity_type == "llm":
                # Send message to LLM
                logger.info(f"Sending message to LLM: {self.current_entity_id}")
                logger.debug(f"Message: {message[:100]}...")

                if stream:
                    async for chunk in self.llm_router.generate_stream(
                        self.current_entity_id, message, history.get_messages() if history else None,
                        system=self.system_prompt
                    ):
                        for callback in self.streaming_callbacks:
                            callback(self.current_entity_id, chunk, "llm")

                    # Get the full response from the LLM
                    response = await self.llm_router.get_last_response(self.current_entity_id)
                    logger.info(f"LLM response received. Length: {len(response)}")

                    # Add LLM response to chat history
                    if history and response:
                        history.add_assistant_message(response)

                    # Trigger auto-save
                    if self.auto_save_callback:
                        self.auto_save_callback()

                    # Don't notify message_callbacks for streaming - the UI already has the complete message
                    # from the streaming chunks
                else:
                    response = await self.llm_router.generate(
                        self.current_entity_id, message, history.get_messages() if history else None,
                        system=self.system_prompt
                    )
                    logger.info(f"LLM response received (non-streaming). Length: {len(response)}")

                    # Add LLM response to chat history
                    if history and response:
                        history.add_assistant_message(response)

                    # Trigger auto-save
                    if self.auto_save_callback:
                        self.auto_save_callback()

                    # Notify callbacks about the LLM response
                    for callback in self.message_callbacks:
                        callback(self.current_entity_id, response, "llm")
                        
                return True
            else:
                logger.error("No agent or LLM selected")
                self._notify_error("No agent or LLM selected")
                return False
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self._notify_error(f"Error sending message: {e}")
            return False
            
    def reset_current_thread(self) -> bool:
        """
        Reset the current thread by clearing all messages

        Returns:
            True if the thread was reset successfully, False otherwise
        """
        try:
            history = self.get_current_chat_history()
            if history:
                history.clear()
                logger.info("Thread reset successfully")

                # Trigger auto-save to persist the cleared state
                if self.auto_save_callback:
                    self.auto_save_callback()

                return True
            else:
                logger.warning("No active thread to reset")
                return False
        except Exception as e:
            logger.error(f"Error resetting thread: {e}")
            self._notify_error(f"Error resetting thread: {e}")
            return False

    def _notify_error(self, error_message: str) -> None:
        """
        Notify error callbacks about an error

        Args:
            error_message: Error message to send
        """
        for callback in self.error_callbacks:
            callback(error_message)

    def _notify_thread_change(self) -> None:
        """
        Notify thread callbacks about thread changes
        """
        for callback in self.thread_callbacks:
            callback()

        # Trigger auto-save
        if self.auto_save_callback:
            self.auto_save_callback()

    def save_threads(self) -> Dict[str, Any]:
        """
        Save all threads to a dictionary for persistence

        Returns:
            Dictionary representation of all threads
        """
        saved_threads = {}
        for entity_id, entity_threads in self.threads.items():
            saved_threads[entity_id] = {
                thread_id: thread.to_dict()
                for thread_id, thread in entity_threads.items()
            }
        return saved_threads

    def load_threads(self, threads_data: Dict[str, Any]) -> None:
        """
        Load threads from a dictionary

        Args:
            threads_data: Dictionary representation of threads
        """
        try:
            self.threads = {}
            for entity_id, entity_threads in threads_data.items():
                self.threads[entity_id] = {}
                for thread_id, thread_data in entity_threads.items():
                    self.threads[entity_id][thread_id] = Thread.from_dict(thread_data)
            logger.info(f"Loaded {sum(len(t) for t in self.threads.values())} threads")
        except Exception as e:
            logger.error(f"Error loading threads: {e}")
            self.threads = {}


