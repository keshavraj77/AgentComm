"""
Agent Communication Manager for handling communication with agents
"""

import uuid
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List, Callable, Union

from agentcomm.agents.agent_registry import Agent, AgentRegistry
from agentcomm.agents.a2a_client import A2AClient, Message
from agentcomm.agents.a2a_sdk_client import A2ASDKClientWrapper
from agentcomm.agents.webhook_handler import WebhookHandler

logger = logging.getLogger(__name__)

class AgentComm:
    """
    Simplified wrapper for agent communication
    """

    def __init__(self, agent: Agent, use_sdk: bool = True):
        """
        Initialize the agent communication wrapper

        Args:
            agent: Agent to communicate with
            use_sdk: Whether to use the official A2A SDK (default: True)
        """
        self.agent = agent
        self.use_sdk = use_sdk

        if use_sdk:
            self.a2a_sdk_client = A2ASDKClientWrapper()
            self.a2a_client = None
        else:
            self.a2a_client = A2AClient()
            self.a2a_sdk_client = None

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
            response_text = ""

            if self.use_sdk and self.a2a_sdk_client:
                # Use the official A2A SDK
                async for response in self.a2a_sdk_client.send_message(
                    agent_url=self.agent.url,
                    message=message,
                    transport=self.agent.transport,
                    auth_type=self.agent.authentication.auth_type,
                    api_key_name=self.agent.authentication.api_key_name,
                    token=self.agent.authentication.token,
                    context_id=self.context_id
                ):
                    if "result" in response:
                        result = response["result"]
                        # Extract text from response
                        if hasattr(result, 'parts'):
                            for part in result.parts:
                                if hasattr(part, 'text'):
                                    response_text += part.text
                        elif isinstance(result, dict):
                            # Handle dict responses
                            if "content" in result:
                                response_text = result["content"]
                            elif "text" in result:
                                response_text = result["text"]

                        # Extract context ID
                        if hasattr(result, 'context_id'):
                            self.context_id = result.context_id
                        elif isinstance(result, dict) and "contextId" in result:
                            self.context_id = result["contextId"]

            else:
                # Use legacy client
                msg = Message(
                    content=message,
                    content_type="text/plain",
                    message_id=str(uuid.uuid4()),
                    role="user",
                    context_id=self.context_id
                )

                auth_headers = self.agent.authentication.get_headers()

                async for response in self.a2a_client.send_message(
                    agent_url=self.agent.url,
                    message=msg,
                    context_id=self.context_id,
                    auth_headers=auth_headers
                ):
                    if "result" in response and isinstance(response["result"], dict):
                        result = response["result"]

                        if "kind" in result and result["kind"] == "message":
                            if "content" in result:
                                response_text = result["content"]

                        elif "kind" in result and result["kind"] == "task":
                            self.last_task_id = result["id"]

                            if "artifacts" in result and isinstance(result["artifacts"], list):
                                for artifact in result["artifacts"]:
                                    if "parts" in artifact and isinstance(artifact["parts"], list):
                                        for part in artifact["parts"]:
                                            if "content" in part:
                                                response_text += part["content"]

                    if "context" in response and "id" in response["context"]:
                        self.context_id = response["context"]["id"]

            self.last_response = response_text

            # If we didn't get any response, return a generic error message
            if not response_text:
                error_msg = "Unable to get a response from the agent. Please try again."
                logger.warning(f"No response text received from agent. Returning generic error message.")
                self.last_response = error_msg
                return error_msg

            return response_text

        except Exception as e:
            logger.error(f"Error sending message to agent: {e}", exc_info=True)
            error_msg = f"Error communicating with agent: {str(e)}. Please try again."
            self.last_response = error_msg
            return error_msg
    
    async def send_message_stream(self, message: str) -> AsyncGenerator[str, None]:
        """
        Send a message to the agent and stream the response

        Args:
            message: Message to send

        Yields:
            Response chunks from the agent
        """
        try:
            response_text = ""
            last_task_state = None

            if self.use_sdk and self.a2a_sdk_client:
                # Use the official A2A SDK
                logger.info(f"Using A2A SDK to send streaming message")
                async for response in self.a2a_sdk_client.send_streaming_message(
                    agent_url=self.agent.url,
                    message=message,
                    transport=self.agent.transport,
                    auth_type=self.agent.authentication.auth_type,
                    api_key_name=self.agent.authentication.api_key_name,
                    token=self.agent.authentication.token,
                    context_id=self.context_id
                ):
                    logger.info(f"=== AgentComm received response ===")
                    logger.info(f"Response keys: {response.keys() if isinstance(response, dict) else 'not a dict'}")

                    if "result" in response:
                        result = response["result"]
                        logger.info(f"Processing result of type: {type(result).__name__}")
                        logger.info(f"Result class module: {type(result).__module__}")
                        chunk = ""

                        # Handle Message responses directly (not in tuple)
                        if type(result).__name__ == 'Message' and not isinstance(result, tuple):
                            logger.info(f"Result is a Message object")
                            if hasattr(result, 'model_dump'):
                                logger.info(f"Message dump: {result.model_dump()}")

                            if hasattr(result, 'parts') and result.parts:
                                logger.info(f"Message has {len(result.parts)} parts")
                                for idx, part in enumerate(result.parts):
                                    logger.info(f"Part {idx} type: {type(part).__name__}")
                                    # Handle Part wrapper with root attribute
                                    if hasattr(part, 'root'):
                                        if hasattr(part.root, 'text') and part.root.text:
                                            chunk += part.root.text
                                            logger.info(f"✓ Extracted text from message part root: {part.root.text[:100]}...")
                                    # Direct text/content attributes
                                    elif hasattr(part, 'text') and part.text:
                                        chunk += part.text
                                        logger.info(f"✓ Extracted text from message part: {part.text[:100]}...")
                                    elif hasattr(part, 'content') and part.content:
                                        chunk += part.content
                                        logger.info(f"✓ Extracted content from message part: {part.content[:100]}...")

                        # Handle tuple responses (Task, Event or None)
                        elif isinstance(result, tuple):
                            logger.info(f"Result is tuple with {len(result)} elements")
                            task = result[0] if len(result) > 0 else None
                            event = result[1] if len(result) > 1 else None

                            logger.info(f"Task type: {type(task).__name__ if task else 'None'}")
                            logger.info(f"Event type: {type(event).__name__ if event else 'None'}")

                            # Log task details
                            task_state = 'unknown'
                            if task:
                                logger.info(f"Task ID: {task.id if hasattr(task, 'id') else 'unknown'}")
                                task_state = task.status.state if hasattr(task, 'status') and hasattr(task.status, 'state') else 'unknown'
                                logger.info(f"Task status: {task_state}")

                                # Log status details
                                if hasattr(task, 'status'):
                                    logger.info(f"Status attributes: {[a for a in dir(task.status) if not a.startswith('_')]}")
                                    if hasattr(task.status, 'message') and task.status.message:
                                        logger.info(f"Status message: {task.status.message}")

                                # Dump the full task for debugging
                                if hasattr(task, 'model_dump'):
                                    task_dict = task.model_dump()
                                    logger.info(f"Full task dump: {task_dict}")

                            # Log event details
                            if event:
                                logger.info(f"Event type: {type(event).__name__}")
                                if hasattr(event, 'model_dump'):
                                    event_dict = event.model_dump()
                                    logger.info(f"Full event dump: {event_dict}")

                            # Check if task is completed
                            is_completed = str(task_state) == 'TaskState.completed'

                            # If task just transitioned to completed, send a clear signal
                            if is_completed and last_task_state != 'TaskState.completed':
                                logger.info(f"Task transitioned to completed - sending CLEAR signal")
                                yield "<<<CLEAR>>>"
                                response_text = ""  # Reset accumulated text

                            # Update the last known state
                            last_task_state = str(task_state)

                            # If task is completed, ONLY extract from artifacts (the final result)
                            # Don't include status messages in the final output
                            if is_completed:
                                logger.info(f"Task completed - extracting ONLY from artifacts")
                                if task and hasattr(task, 'artifacts') and task.artifacts:
                                    logger.info(f"Task has {len(task.artifacts)} artifacts")
                                    for idx, artifact in enumerate(task.artifacts):
                                        logger.info(f"Artifact {idx}: {artifact}")
                                        if hasattr(artifact, 'parts') and artifact.parts:
                                            for part_idx, part in enumerate(artifact.parts):
                                                logger.info(f"  Part {part_idx} type: {type(part).__name__}")
                                                # Handle Part wrapper with root attribute
                                                if hasattr(part, 'root'):
                                                    if hasattr(part.root, 'text') and part.root.text:
                                                        chunk += part.root.text
                                                        logger.info(f"  ✓ Extracted text from artifact part root: {part.root.text[:100]}...")
                                                # Direct text/content attributes
                                                elif hasattr(part, 'text') and part.text:
                                                    chunk += part.text
                                                    logger.info(f"  ✓ Extracted text from artifact part: {part.text[:100]}...")
                                                elif hasattr(part, 'content') and part.content:
                                                    chunk += part.content
                                                    logger.info(f"  ✓ Extracted content from artifact part: {part.content[:100]}...")
                            else:
                                # Task is in progress - extract status messages and/or artifact updates
                                logger.info(f"Task in progress - extracting status messages and artifact updates")

                                # Extract status messages (e.g., "Processing...")
                                if task and hasattr(task, 'status'):
                                    if hasattr(task.status, 'message') and task.status.message:
                                        # Check if status message is a Message object with parts
                                        if hasattr(task.status.message, 'parts'):
                                            logger.info(f"Status message has {len(task.status.message.parts)} parts!")
                                            for idx, part in enumerate(task.status.message.parts):
                                                logger.info(f"Part {idx}: {part}")
                                                logger.info(f"Part {idx} type: {type(part).__name__}")

                                                # Handle Part wrapper with root attribute
                                                if hasattr(part, 'root'):
                                                    logger.info(f"Part has 'root' attribute: {type(part.root).__name__}")
                                                    if hasattr(part.root, 'text') and part.root.text:
                                                        chunk += part.root.text
                                                        logger.info(f"✓ Extracted text from status message root: {part.root.text[:100]}...")
                                                # Direct text attribute
                                                elif hasattr(part, 'text') and part.text:
                                                    chunk += part.text
                                                    logger.info(f"✓ Extracted text from status message: {part.text[:100]}...")

                                # Extract artifact updates (only from event, not task, to avoid duplicates)
                                if event and hasattr(event, 'artifact') and event.artifact:
                                    logger.info(f"Event has artifact update - extracting incremental update")
                                    if hasattr(event.artifact, 'parts'):
                                        for part in event.artifact.parts:
                                            # Handle Part wrapper with root attribute
                                            if hasattr(part, 'root'):
                                                if hasattr(part.root, 'text') and part.root.text:
                                                    chunk += part.root.text
                                                    logger.info(f"✓ Extracted text from event artifact root: {part.root.text[:100]}...")
                                            # Direct text/content attributes
                                            elif hasattr(part, 'text') and part.text:
                                                chunk += part.text
                                                logger.info(f"✓ Extracted text from event artifact: {part.text[:100]}...")
                                            elif hasattr(part, 'content') and part.content:
                                                chunk += part.content
                                                logger.info(f"✓ Extracted content from event artifact: {part.content[:100]}...")

                            if not chunk and task:
                                logger.info(f"Task has no artifacts (artifacts={task.artifacts if hasattr(task, 'artifacts') else 'N/A'})")

                        # Handle Message responses
                        elif hasattr(result, 'parts'):
                            logger.info(f"Result has 'parts' attribute with {len(result.parts)} parts")
                            for part in result.parts:
                                if hasattr(part, 'text'):
                                    chunk += part.text
                                    logger.debug(f"Extracted text from part: {part.text[:100]}...")

                        # Handle dict responses
                        elif isinstance(result, dict):
                            logger.info(f"Result is dict with keys: {result.keys()}")
                            if "content" in result:
                                chunk = result["content"]
                            elif "text" in result:
                                chunk = result["text"]

                        # Try to extract from other object types
                        else:
                            logger.info(f"Result attributes: {[a for a in dir(result) if not a.startswith('_')]}")
                            if hasattr(result, 'content'):
                                chunk = result.content
                                logger.info(f"Extracted content: {chunk[:100]}...")

                        if chunk:
                            logger.info(f"✓✓✓ SUCCESS: Yielding chunk of length {len(chunk)}")
                            logger.info(f"✓✓✓ Chunk preview: {chunk[:200]}...")
                            response_text += chunk
                            yield chunk
                        else:
                            logger.warning(f"✗✗✗ PROBLEM: No chunk extracted from result")
                            logger.warning(f"✗✗✗ Result type was: {type(result).__name__}")

                        # Extract context ID
                        if isinstance(result, tuple) and len(result) > 0:
                            task = result[0]
                            if hasattr(task, 'context_id'):
                                self.context_id = task.context_id
                        elif hasattr(result, 'context_id'):
                            self.context_id = result.context_id
                        elif isinstance(result, dict) and "contextId" in result:
                            self.context_id = result["contextId"]

            else:
                # Use legacy client
                msg = Message(
                    content=message,
                    content_type="text/plain",
                    message_id=str(uuid.uuid4()),
                    role="user",
                    context_id=self.context_id
                )

                auth_headers = self.agent.authentication.get_headers()

                async for response in self.a2a_client.send_streaming_message(
                    agent_url=self.agent.url,
                    message=msg,
                    context_id=self.context_id,
                    auth_headers=auth_headers
                ):
                    if "result" in response and isinstance(response["result"], dict):
                        result = response["result"]
                        chunk = ""

                        if "kind" in result and result["kind"] == "message":
                            if "content" in result:
                                chunk = result["content"]

                        elif "kind" in result and result["kind"] == "task":
                            self.last_task_id = result["id"]

                            if "artifacts" in result and isinstance(result["artifacts"], list):
                                for artifact in result["artifacts"]:
                                    if "parts" in artifact and isinstance(artifact["parts"], list):
                                        for part in artifact["parts"]:
                                            if "content" in part:
                                                chunk += part["content"]

                        if chunk:
                            response_text += chunk
                            yield chunk

                    if "context" in response and "id" in response["context"]:
                        self.context_id = response["context"]["id"]

            self.last_response = response_text

            # If we didn't get any response, send a generic error message
            if not response_text:
                error_msg = "Unable to get a response from the agent. Please try again."
                logger.warning(f"No response text received from agent. Sending generic error message.")
                yield error_msg
                self.last_response = error_msg

        except Exception as e:
            logger.error(f"Error sending message to agent: {e}", exc_info=True)
            error_msg = f"Error communicating with agent: {str(e)}. Please try again."
            yield error_msg
            self.last_response = error_msg
    
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


