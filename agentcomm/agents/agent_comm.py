"""
Agent Communication Manager for handling communication with agents
"""

import uuid
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List, Callable, Union

from agentcomm.agents.agent_registry import Agent, AgentRegistry
from agentcomm.agents.a2a_client import A2AClient, Message
from agentcomm.agents.webhook_handler import WebhookHandler

logger = logging.getLogger(__name__)

class AgentComm:
    """
    Simplified wrapper for agent communication
    """
    
    def __init__(self, agent: Agent):
        """
        Initialize the agent communication wrapper
        
        Args:
            agent: Agent to communicate with
        """
        self.agent = agent
        self.a2a_client = A2AClient()
        self.context_id: Optional[str] = None
        self.last_response: Optional[str] = None
        self.last_task_id: Optional[str] = None
    
    async def send_message(self, message: str) -> str:
        """
        Send a message to the agent and return the complete response
        
        Args:
            message: Message to send
            
        Returns:
            Complete response from the agent
        """
        try:
            # Prepare the message
            msg = Message(
                content=message,
                content_type="text/plain",
                message_id=str(uuid.uuid4()),
                role="user",
                context_id=self.context_id
            )
            
            # Get authentication headers
            auth_headers = self.agent.authentication.get_headers()
            
            # Send the message
            response_text = ""
            async for response in self.a2a_client.send_message(
                agent_url=self.agent.url,
                message=msg,
                context_id=self.context_id,
                auth_headers=auth_headers
            ):
                # Process the response
                if "result" in response and isinstance(response["result"], dict):
                    result = response["result"]
                    
                    # Check if the result is a message
                    if "kind" in result and result["kind"] == "message":
                        if "content" in result:
                            response_text = result["content"]
                    
                    # Check if the result is a task
                    elif "kind" in result and result["kind"] == "task":
                        self.last_task_id = result["id"]
                        
                        # Check if the task has artifacts with content
                        if "artifacts" in result and isinstance(result["artifacts"], list):
                            for artifact in result["artifacts"]:
                                if "parts" in artifact and isinstance(artifact["parts"], list):
                                    for part in artifact["parts"]:
                                        if "content" in part:
                                            response_text += part["content"]
            
            # Store the context ID for future messages if available in the last response
            last_response = None
            async for response in self.a2a_client.send_message(
                agent_url=self.agent.url,
                message=msg,
                context_id=self.context_id,
                auth_headers=auth_headers
            ):
                last_response = response
            
            if last_response and "context" in last_response and "id" in last_response["context"]:
                self.context_id = last_response["context"]["id"]
            
            # Store the response
            self.last_response = response_text
            
            return response_text
        
        except Exception as e:
            logger.error(f"Error sending message to agent: {e}")
            return f"Error: {e}"
    
    async def send_message_stream(self, message: str) -> AsyncGenerator[str, None]:
        """
        Send a message to the agent and stream the response
        
        Args:
            message: Message to send
            
        Yields:
            Response chunks from the agent
        """
        try:
            # Prepare the message
            msg = Message(
                content=message,
                content_type="text/plain",
                message_id=str(uuid.uuid4()),
                role="user",
                context_id=self.context_id
            )
            
            # Get authentication headers
            auth_headers = self.agent.authentication.get_headers()
            
            # Send the message
            response_text = ""
            async for response in self.a2a_client.send_streaming_message(
                agent_url=self.agent.url,
                message=msg,
                context_id=self.context_id,
                auth_headers=auth_headers
            ):
                # Process the response
                if "result" in response and isinstance(response["result"], dict):
                    result = response["result"]
                    
                    # Check if the result is a message
                    if "kind" in result and result["kind"] == "message":
                        if "content" in result:
                            chunk = result["content"]
                            response_text += chunk
                            yield chunk
                    
                    # Check if the result is a task
                    elif "kind" in result and result["kind"] == "task":
                        self.last_task_id = result["id"]
                        
                        # Check if the task has artifacts with content
                        if "artifacts" in result and isinstance(result["artifacts"], list):
                            for artifact in result["artifacts"]:
                                if "parts" in artifact and isinstance(artifact["parts"], list):
                                    for part in artifact["parts"]:
                                        if "content" in part:
                                            chunk = part["content"]
                                            response_text += chunk
                                            yield chunk
            
            # Store the context ID for future messages if available in the last response
            last_response = None
            async for response in self.a2a_client.send_streaming_message(
                agent_url=self.agent.url,
                message=msg,
                context_id=self.context_id,
                auth_headers=auth_headers
            ):
                last_response = response
            
            if last_response and "context" in last_response and "id" in last_response["context"]:
                self.context_id = last_response["context"]["id"]
            
            # Store the response
            self.last_response = response_text
        
        except Exception as e:
            logger.error(f"Error sending message to agent: {e}")
            yield f"Error: {e}"
    
    async def get_last_response(self) -> str:
        """
        Get the last response from the agent
        
        Returns:
            Last response from the agent
        """
        return self.last_response or ""
    
    async def cancel_task(self) -> bool:
        """
        Cancel the current task
        
        Returns:
            True if successful, False otherwise
        """
        if not self.last_task_id:
            logger.error("No task to cancel")
            return False
        
        try:
            # Get authentication headers
            auth_headers = self.agent.authentication.get_headers()
            
            # Cancel the task
            response = await self.a2a_client.cancel_task(
                agent_url=self.agent.url,
                task_id=self.last_task_id,
                auth_headers=auth_headers
            )
            
            return "result" in response and isinstance(response["result"], dict)
        
        except Exception as e:
            logger.error(f"Error canceling task: {e}")
            return False


class AgentCommunicationManager:
    """
    Handles communication with agents
    """
    
    def __init__(
        self,
        agent_registry: AgentRegistry,
        a2a_client: Optional[A2AClient] = None,
        webhook_handler: Optional[WebhookHandler] = None
    ):
        """
        Initialize the agent communication manager
        
        Args:
            agent_registry: AgentRegistry instance
            a2a_client: Optional A2AClient instance
            webhook_handler: Optional WebhookHandler instance
        """
        self.agent_registry = agent_registry
        self.a2a_client = a2a_client or A2AClient()
        self.webhook_handler = webhook_handler
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.message_callbacks: Dict[str, List[Callable]] = {}
    
    async def send_message(
        self,
        agent_id: str,
        message: Union[str, Message],
        context_id: Optional[str] = None,
        task_id: Optional[str] = None,
        use_streaming: Optional[bool] = None,
        use_webhook: Optional[bool] = None,
        webhook_url: Optional[str] = None,
        blocking: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a message to an agent and stream the response
        
        Args:
            agent_id: ID of the agent to send the message to
            message: Message to send (string or Message object)
            context_id: Optional context ID for continuing a conversation
            task_id: Optional task ID for continuing a task
            use_streaming: Whether to use streaming (if None, use agent capabilities)
            use_webhook: Whether to use webhooks (if None, use agent capabilities)
            webhook_url: Optional webhook URL (if None, use default)
            blocking: Whether to wait for the task to complete
            
        Yields:
            Dict containing the response from the agent
        """
        # Get the agent
        agent = self.agent_registry.get_agent(agent_id)
        if not agent:
            logger.error(f"Agent not found: {agent_id}")
            yield {
                "error": {
                    "code": -1,
                    "message": f"Agent not found: {agent_id}"
                }
            }
            return
        
        # Prepare the message
        if isinstance(message, str):
            msg = Message(
                content=message,
                content_type="text/plain",
                message_id=str(uuid.uuid4()),
                role="user",
                context_id=context_id,
                task_id=task_id
            )
        else:
            msg = message
            if not msg.message_id:
                msg.message_id = str(uuid.uuid4())
            if not msg.role:
                msg.role = "user"
            if context_id and not msg.context_id:
                msg.context_id = context_id
            if task_id and not msg.task_id:
                msg.task_id = task_id
        
        # Determine whether to use streaming
        if use_streaming is None:
            use_streaming = agent.capabilities.streaming
        
        # Determine whether to use webhooks
        if use_webhook is None:
            use_webhook = agent.capabilities.push_notifications
        
        # Get authentication headers
        auth_headers = agent.authentication.get_headers()
        
        # Prepare webhook URL if needed
        webhook_config = None
        if use_webhook and self.webhook_handler:
            if not webhook_url:
                webhook_url = f"http://localhost:{self.webhook_handler.port}/webhook"
            
            # Generate a token for authentication
            token = str(uuid.uuid4())
            
            webhook_config = {
                "url": webhook_url,
                "token": token
            }
        
        try:
            # Send the message
            if use_streaming:
                # Use streaming
                async for response in self.a2a_client.send_streaming_message(
                    agent_url=agent.url,
                    message=msg,
                    context_id=msg.context_id,
                    auth_headers=auth_headers
                ):
                    # Process the response
                    await self._process_response(response, agent_id)
                    
                    # Yield the response
                    yield response
            else:
                # Use regular message sending
                async for response in self.a2a_client.send_message(
                    agent_url=agent.url,
                    message=msg,
                    context_id=msg.context_id,
                    webhook_url=webhook_config["url"] if webhook_config else None,
                    auth_headers=auth_headers,
                    blocking=blocking
                ):
                    # Process the response
                    await self._process_response(response, agent_id)
                    
                    # Register webhook callback if needed
                    if webhook_config and self.webhook_handler:
                        if "result" in response and isinstance(response["result"], dict) and "task" in response["result"]:
                            task = response["result"]["task"]
                            if "id" in task and isinstance(task["id"], str):
                                task_id_str = task["id"]
                                
                                # Register the webhook callback
                                self.webhook_handler.register_callback(
                                    task_id=task_id_str,
                                    callback=lambda task: self._handle_webhook_notification(task, agent_id),
                                    token=webhook_config["token"]
                                )
                    
                    # Yield the response
                    yield response
        
        except Exception as e:
            logger.error(f"Error sending message to agent {agent_id}: {e}")
            yield {
                "error": {
                    "code": -1,
                    "message": f"Error: {e}"
                }
            }
    
    async def _process_response(self, response: Dict[str, Any], agent_id: str):
        """
        Process a response from an agent
        
        Args:
            response: Response from the agent
            agent_id: ID of the agent
        """
        try:
            # Check if the response contains a task
            if "result" in response and isinstance(response["result"], dict):
                result = response["result"]
                
                # Check if the result is a task
                if "kind" in result and result["kind"] == "task":
                    task = result
                    task_id = task["id"]
                    
                    # Store the task
                    self.active_tasks[task_id] = {
                        "agent_id": agent_id,
                        "task": task
                    }
                    
                    # Notify callbacks
                    await self._notify_callbacks(task_id, task)
                
                # Check if the result is a message
                elif "kind" in result and result["kind"] == "message":
                    message = result
                    task_id = message.get("taskId")
                    
                    if task_id:
                        # Notify callbacks
                        await self._notify_callbacks(task_id, message)
                
                # Check if the result is a task status update
                elif "kind" in result and result["kind"] == "status-update":
                    update = result
                    task_id = update["taskId"]
                    
                    # Update the task
                    if task_id in self.active_tasks:
                        self.active_tasks[task_id]["task"]["status"] = update["status"]
                    
                    # Notify callbacks
                    await self._notify_callbacks(task_id, update)
                
                # Check if the result is a task artifact update
                elif "kind" in result and result["kind"] == "artifact-update":
                    update = result
                    task_id = update["taskId"]
                    
                    # Update the task
                    if task_id in self.active_tasks:
                        if "artifacts" not in self.active_tasks[task_id]["task"]:
                            self.active_tasks[task_id]["task"]["artifacts"] = []
                        
                        # Find existing artifact or add new one
                        artifact_id = update["artifact"]["artifactId"]
                        found = False
                        
                        for i, artifact in enumerate(self.active_tasks[task_id]["task"]["artifacts"]):
                            if artifact["artifactId"] == artifact_id:
                                if update.get("append", False):
                                    # Append to existing artifact
                                    for part in update["artifact"]["parts"]:
                                        artifact["parts"].append(part)
                                else:
                                    # Replace existing artifact
                                    self.active_tasks[task_id]["task"]["artifacts"][i] = update["artifact"]
                                found = True
                                break
                        
                        if not found:
                            # Add new artifact
                            self.active_tasks[task_id]["task"]["artifacts"].append(update["artifact"])
                    
                    # Notify callbacks
                    await self._notify_callbacks(task_id, update)
        
        except Exception as e:
            logger.error(f"Error processing response: {e}")
    
    async def _handle_webhook_notification(self, task: Dict[str, Any], agent_id: str):
        """
        Handle a webhook notification
        
        Args:
            task: Task data
            agent_id: ID of the agent
        """
        try:
            # Store the task
            task_id = task["id"]
            self.active_tasks[task_id] = {
                "agent_id": agent_id,
                "task": task
            }
            
            # Notify callbacks
            await self._notify_callbacks(task_id, task)
        
        except Exception as e:
            logger.error(f"Error handling webhook notification: {e}")
    
    def register_message_callback(self, task_id: str, callback: Callable):
        """
        Register a callback for a task
        
        Args:
            task_id: ID of the task
            callback: Callback function to call when a message is received
        """
        if task_id not in self.message_callbacks:
            self.message_callbacks[task_id] = []
        
        self.message_callbacks[task_id].append(callback)
        logger.debug(f"Registered message callback for task {task_id}")
    
    def unregister_message_callback(self, task_id: str, callback: Optional[Callable] = None):
        """
        Unregister a callback for a task
        
        Args:
            task_id: ID of the task
            callback: Optional callback function to unregister (if None, all callbacks are unregistered)
        """
        if task_id in self.message_callbacks:
            if callback is None:
                self.message_callbacks.pop(task_id)
                logger.debug(f"Unregistered all message callbacks for task {task_id}")
            else:
                if callback in self.message_callbacks[task_id]:
                    self.message_callbacks[task_id].remove(callback)
                    logger.debug(f"Unregistered message callback for task {task_id}")
                
                if not self.message_callbacks[task_id]:
                    self.message_callbacks.pop(task_id)
    
    async def _notify_callbacks(self, task_id: str, data: Dict[str, Any]):
        """
        Notify callbacks for a task
        
        Args:
            task_id: ID of the task
            data: Data to pass to the callbacks
        """
        if task_id in self.message_callbacks:
            for callback in self.message_callbacks[task_id]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Error in message callback for task {task_id}: {e}")
    
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a task
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            Dict containing the response from the agent
        """
        if task_id not in self.active_tasks:
            logger.error(f"Task not found: {task_id}")
            return {
                "error": {
                    "code": -1,
                    "message": f"Task not found: {task_id}"
                }
            }
        
        # Get the agent
        agent_id = self.active_tasks[task_id]["agent_id"]
        agent = self.agent_registry.get_agent(agent_id)
        
        if not agent:
            logger.error(f"Agent not found: {agent_id}")
            return {
                "error": {
                    "code": -1,
                    "message": f"Agent not found: {agent_id}"
                }
            }
        
        # Get authentication headers
        auth_headers = agent.authentication.get_headers()
        
        try:
            # Cancel the task
            response = await self.a2a_client.cancel_task(
                agent_url=agent.url,
                task_id=task_id,
                auth_headers=auth_headers
            )
            
            # Process the response
            if "result" in response and isinstance(response["result"], dict) and "status" in response["result"]:
                # Update the task
                self.active_tasks[task_id]["task"]["status"] = response["result"]["status"]
                
                # Notify callbacks
                await self._notify_callbacks(task_id, self.active_tasks[task_id]["task"])
            
            return response
        
        except Exception as e:
            logger.error(f"Error canceling task: {e}")
            return {
                "error": {
                    "code": -1,
                    "message": f"Error: {e}"
                }
            }
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a task
        
        Args:
            task_id: ID of the task
            
        Returns:
            Task data or None if not found
        """
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]["task"]
        
        return None
    
    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active tasks
        
        Returns:
            Dict of active tasks
        """
        return self.active_tasks


