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
from agentcomm.agents.ngrok_manager import NgrokManager
from agentcomm.agents.task_state import TaskState, TaskStateResult, DEFAULT_STATE_MESSAGES

logger = logging.getLogger(__name__)




class AgentComm:
    """
    Simplified wrapper for agent communication
    """

    def __init__(
        self,
        agent: Agent,
        use_sdk: bool = True,
        webhook_handler: Optional[WebhookHandler] = None,
        ngrok_manager: Optional[NgrokManager] = None,
        thread_id: Optional[str] = None
    ):
        """
        Initialize the agent communication wrapper

        Args:
            agent: Agent to communicate with
            use_sdk: Whether to use the official A2A SDK (default: True)
            webhook_handler: Optional webhook handler for push notifications
            ngrok_manager: Optional ngrok manager for secure tunneling
            thread_id: Optional thread ID for associating webhook callbacks
        """
        self.agent = agent
        self.use_sdk = use_sdk
        self.webhook_handler = webhook_handler
        self.ngrok_manager = ngrok_manager
        self.thread_id = thread_id

        if use_sdk:
            self.a2a_sdk_client = A2ASDKClientWrapper()
            self.a2a_client = None
        else:
            self.a2a_client = A2AClient()
            self.a2a_sdk_client = None

        self.context_id: Optional[str] = None
        self.last_response: Optional[str] = None
        self.last_task_id: Optional[str] = None

    def _generate_push_notification_config(self) -> Optional[Dict[str, Any]]:
        """
        Generate push notification config for agent requests

        Returns:
            Push notification config dict or None if not available
        """
        if not self.webhook_handler or not self.agent.capabilities.push_notifications:
            return None

        import uuid

        # Determine webhook URL
        if self.ngrok_manager and self.ngrok_manager.is_active():
            base_url = self.ngrok_manager.get_public_url()
            webhook_url = f"{base_url}/webhook"
            logger.info(f"Using ngrok webhook URL for push notifications: {webhook_url}")
        else:
            webhook_url = f"http://localhost:{self.webhook_handler.port}/webhook"
            logger.debug("Using localhost webhook URL (push notifications may not work with remote agents)")

        # Generate authentication token
        token = str(uuid.uuid4())

        # Create push notification config according to A2A spec
        push_config = {
            "id": str(uuid.uuid4()),
            "url": webhook_url,
            "token": token
        }

        # Add authentication if available
        auth_headers = self.agent.authentication.get_headers()
        if auth_headers:
            schemes = []
            credentials = None

            for header_name, header_value in auth_headers.items():
                if header_name.lower() == "authorization":
                    if header_value.startswith("Bearer "):
                        schemes.append("Bearer")
                        credentials = header_value.split(" ", 1)[1] if len(header_value.split(" ", 1)) > 1 else None
                    elif header_value.startswith("Basic "):
                        schemes.append("Basic")
                        credentials = header_value.split(" ", 1)[1] if len(header_value.split(" ", 1)) > 1 else None
                else:
                    schemes.append(header_name)

            if schemes:
                push_config["authentication"] = {"schemes": schemes}
                if credentials:
                    push_config["authentication"]["credentials"] = credentials

        return push_config

    def _parse_task_state(self, task: Any) -> TaskState:
        """
        Parse task state from a task object.

        Args:
            task: Task object from A2A SDK

        Returns:
            TaskState enum value
        """
        if not task or not hasattr(task, 'status') or not hasattr(task.status, 'state'):
            return TaskState.UNSPECIFIED

        state_str = str(task.status.state)
        return TaskState.from_string(state_str)

    def _extract_content_from_artifacts(self, task: Any) -> str:
        """
        Extract text content from task artifacts.

        Used for terminal and interrupted states where artifacts contain the final response.

        Args:
            task: Task object from A2A SDK

        Returns:
            Extracted text content
        """
        content = ""

        if not task:
            logger.debug("Task is None, cannot extract artifacts")
            return content

        if not hasattr(task, 'artifacts') or not task.artifacts:
            return content

        for artifact in task.artifacts:
            if not hasattr(artifact, 'parts') or not artifact.parts:
                continue

            for part in artifact.parts:
                # Handle Part wrapper with root attribute (SDK format)
                if hasattr(part, 'root'):
                    if hasattr(part.root, 'text') and part.root.text:
                        content += part.root.text
                # Direct text/content attributes
                elif hasattr(part, 'text') and part.text:
                    content += part.text
                elif hasattr(part, 'content') and part.content:
                    content += part.content

        if content:
            logger.info(f"Extracted {len(content)} chars from artifacts")
        return content

    def _extract_content_from_messages(self, task: Any) -> str:
        """
        Extract text content from task messages.

        Some agents return content in messages instead of artifacts.
        This is used as a fallback when artifacts are empty.

        Args:
            task: Task object from A2A SDK

        Returns:
            Extracted text content from messages
        """
        content = ""

        if not task:
            return content

        if not hasattr(task, 'messages') or not task.messages:
            return content

        for message in task.messages:
            # Check if message has parts
            if hasattr(message, 'parts') and message.parts:
                for part in message.parts:
                    # Handle Part wrapper with root attribute (SDK format)
                    if hasattr(part, 'root'):
                        if hasattr(part.root, 'text') and part.root.text:
                            content += part.root.text
                    # Direct text attribute
                    elif hasattr(part, 'text') and part.text:
                        content += part.text
                    # Direct content attribute
                    elif hasattr(part, 'content') and part.content:
                        content += str(part.content)

            # Check if message has direct content attribute
            elif hasattr(message, 'content'):
                if isinstance(message.content, str):
                    content += message.content
                elif isinstance(message.content, list):
                    for item in message.content:
                        if hasattr(item, 'text'):
                            content += item.text
                        elif isinstance(item, dict) and 'text' in item:
                            content += item['text']

        if content:
            logger.info(f"Extracted {len(content)} chars from messages")
        return content

    def _extract_status_message(self, task: Any) -> Optional[str]:
        """
        Extract status message from task.status.message.

        Used for active states where status message shows progress,
        and also as a fallback for terminal states.

        Args:
            task: Task object from A2A SDK

        Returns:
            Status message text or None
        """
        if not task or not hasattr(task, 'status'):
            return None

        status = task.status
        if not hasattr(status, 'message') or not status.message:
            return None

        message = status.message
        text = ""

        # Check if message has parts
        if hasattr(message, 'parts') and message.parts:
            for part in message.parts:
                # Handle Part wrapper with root attribute
                if hasattr(part, 'root'):
                    if hasattr(part.root, 'text') and part.root.text:
                        text += part.root.text
                # Direct text attribute
                elif hasattr(part, 'text') and part.text:
                    text += part.text

        if text:
            logger.info(f"Extracted {len(text)} chars from status.message")
        return text if text else None

    def _extract_event_artifact_content(self, event: Any) -> str:
        """
        Extract content from an event's artifact (incremental updates).

        Args:
            event: Event object from A2A SDK streaming

        Returns:
            Extracted text content
        """
        content = ""

        if not event or not hasattr(event, 'artifact') or not event.artifact:
            return content

        artifact = event.artifact
        if not hasattr(artifact, 'parts') or not artifact.parts:
            return content

        for part in artifact.parts:
            # Handle Part wrapper with root attribute
            if hasattr(part, 'root'):
                if hasattr(part.root, 'text') and part.root.text:
                    content += part.root.text
            elif hasattr(part, 'text') and part.text:
                content += part.text
            elif hasattr(part, 'content') and part.content:
                content += part.content

        return content

    def _process_task_response(self, task: Any, event: Any = None, last_state: Optional[TaskState] = None) -> TaskStateResult:
        """
        Process a task response and determine how to handle it.

        Args:
            task: Task object from A2A SDK
            event: Optional event object for streaming updates
            last_state: Previous task state for detecting transitions

        Returns:
            TaskStateResult with appropriate content and handling instructions
        """
        state = self._parse_task_state(task)
        task_id = task.id if task and hasattr(task, 'id') else None

        logger.info(f"Processing task response - State: {state.value}, Task ID: {task_id}")

        # Check for state transition to completed (send CLEAR signal)
        is_transition_to_terminal = (
            state.is_terminal() and
            last_state is not None and
            not last_state.is_terminal()
        )

        if state.is_terminal():
            # Terminal states: extract content with fallback priority:
            # 1. artifacts (rare, but spec-compliant)
            # 2. status.message (common location for completed task content)
            # 3. messages (alternative location)
            content = self._extract_content_from_artifacts(task)
            logger.info(f"Terminal state ({state.value}) - Extracted {len(content)} chars from artifacts")

            if not content:
                logger.info("Artifacts empty, trying to extract from status.message")
                content = self._extract_status_message(task) or ""
                logger.info(f"Terminal state ({state.value}) - Extracted {len(content)} chars from status.message")

            if not content:
                logger.info("Status message empty, trying to extract from messages")
                content = self._extract_content_from_messages(task)
                logger.info(f"Terminal state ({state.value}) - Extracted {len(content)} chars from messages")

            return TaskStateResult(
                state=state,
                content=content if content else DEFAULT_STATE_MESSAGES.get(state, "Task finished."),
                is_final=True,
                should_poll=False,
                task_id=task_id,
            )

        elif state.is_interrupted():
            # Interrupted states (input-required, auth-required): stream content as-is
            # First try artifacts, then messages, then status message
            content = self._extract_content_from_artifacts(task)
            if not content:
                logger.info("Artifacts empty for interrupted state, trying messages")
                content = self._extract_content_from_messages(task)
            if not content:
                content = self._extract_status_message(task) or ""

            logger.info(f"Interrupted state ({state.value}) - Extracted {len(content)} chars")

            return TaskStateResult(
                state=state,
                content=content,
                status_message=DEFAULT_STATE_MESSAGES.get(state, "Action required."),
                is_final=True,  # Interrupted states are "final" in that user needs to respond
                should_poll=False,
                task_id=task_id,
            )

        elif state.is_active():
            # Active states (submitted, working): show status message
            status_msg = self._extract_status_message(task)

            # Use default message if no agent-provided status
            if not status_msg:
                status_msg = DEFAULT_STATE_MESSAGES.get(state, "Processing...")

            # Check for incremental content from event
            event_content = self._extract_event_artifact_content(event) if event else ""

            return TaskStateResult(
                state=state,
                content=event_content if event_content else None,
                status_message=status_msg,
                should_poll=True,  # Need to poll/wait for completion
                is_final=False,
                task_id=task_id,
            )

        else:
            # Unknown/unspecified state
            logger.warning(f"Unknown task state: {state.value}")
            return TaskStateResult(
                state=state,
                should_poll=True,
                is_final=False,
                task_id=task_id,
            )

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
                push_config = self._generate_push_notification_config()
                async for response in self.a2a_sdk_client.send_message(
                    agent_url=self.agent.url,
                    message=message,
                    transport=self.agent.transport,
                    auth_type=self.agent.authentication.auth_type,
                    api_key_name=self.agent.authentication.api_key_name,
                    token=self.agent.authentication.token,
                    context_id=self.context_id,
                    push_notification_config=push_config
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
        Send a message to the agent and stream the response.

        Task State Handling:
        - Terminal states (completed, failed, cancelled, rejected): Stream content from artifacts
        - Interrupted states (input-required, auth-required): Stream content as-is (prompts for user)
        - Active states (submitted, working): Emit status messages, poll/wait for completion

        Args:
            message: Message to send

        Yields:
            Response chunks from the agent. Special signals:
            - "<<<STATUS>>>text": Status message to show in loading indicator
            - "<<<CLEAR>>>": Clear previous streaming content (on state transition)
        """
        try:
            response_text = ""
            yielded_any_content = False
            last_state: Optional[TaskState] = None
            task_id: Optional[str] = None
            webhook_queue: Optional[asyncio.Queue] = None
            last_status_message: Optional[str] = None

            if self.use_sdk and self.a2a_sdk_client:
                logger.info("Using A2A SDK to send streaming message")
                push_config = self._generate_push_notification_config()

                # Webhook callback for push notifications
                async def webhook_callback(task_data: Dict[str, Any]):
                    """Handle incoming webhook notifications"""
                    logger.info("Webhook callback received task data")
                    if webhook_queue:
                        await webhook_queue.put(task_data)

                # Create webhook queue if push notifications are enabled
                if push_config and self.webhook_handler:
                    webhook_queue = asyncio.Queue()
                    logger.info("Created webhook queue for push notifications")

                # Process streaming responses
                async for response in self.a2a_sdk_client.send_streaming_message(
                    agent_url=self.agent.url,
                    message=message,
                    transport=self.agent.transport,
                    auth_type=self.agent.authentication.auth_type,
                    api_key_name=self.agent.authentication.api_key_name,
                    token=self.agent.authentication.token,
                    context_id=self.context_id,
                    push_notification_config=push_config
                ):
                    if "result" not in response:
                        continue

                    result = response["result"]
                    logger.debug(f"Processing result of type: {type(result).__name__}")

                    # Handle direct Message responses (not task-based)
                    if type(result).__name__ == 'Message' and not isinstance(result, tuple):
                        chunk = self._extract_message_content(result)
                        if chunk:
                            response_text += chunk
                            yield chunk
                            yielded_any_content = True
                        continue

                    # Handle tuple responses (Task, Event)
                    if isinstance(result, tuple):
                        task = result[0] if len(result) > 0 else None
                        event = result[1] if len(result) > 1 else None

                        if not task:
                            continue

                        # Register webhook callback on first task response
                        if hasattr(task, 'id') and task.id and not task_id:
                            task_id = task.id
                            self.last_task_id = task_id
                            if webhook_queue and self.webhook_handler and push_config:
                                token = push_config.get('token')
                                self.webhook_handler.register_callback(
                                    task_id,
                                    webhook_callback,
                                    token,
                                    thread_id=self.thread_id
                                )
                                logger.info(f"Registered webhook callback for task {task_id}")

                        # Process task response using clean state handling
                        task_result = self._process_task_response(task, event, last_state)

                        # Check for state transition to terminal (send CLEAR signal)
                        if (task_result.state.is_terminal() and
                            last_state is not None and
                            not last_state.is_terminal()):
                            logger.info("State transitioned to terminal - sending CLEAR signal")
                            yield "<<<CLEAR>>>"
                            response_text = ""

                        # Update last state
                        last_state = task_result.state

                        # Handle based on state category
                        if task_result.state.should_stream_content():
                            # Terminal or interrupted states: stream content
                            if task_result.content:
                                response_text += task_result.content
                                yield task_result.content
                                yielded_any_content = True
                                logger.info(f"Yielded content ({len(task_result.content)} chars) for state {task_result.state.value}")

                        elif task_result.state.should_show_status():
                            # Active states: emit status message
                            if task_result.status_message and task_result.status_message != last_status_message:
                                last_status_message = task_result.status_message
                                yield f"<<<STATUS>>>{task_result.status_message}"
                                yielded_any_content = True
                                logger.info(f"Yielded status signal (length: {len(task_result.status_message)})")

                            # Also yield any incremental content from events
                            if task_result.content:
                                response_text += task_result.content
                                yield task_result.content
                                yielded_any_content = True

                        # Extract context ID
                        if hasattr(task, 'context_id') and task.context_id:
                            self.context_id = task.context_id

                    # Handle dict responses (legacy format)
                    elif isinstance(result, dict):
                        chunk = result.get("content") or result.get("text") or ""
                        if chunk:
                            response_text += chunk
                            yield chunk
                            yielded_any_content = True

                        if "contextId" in result:
                            self.context_id = result["contextId"]

                            yielded_any_content = True

                # If still active after streaming (waiting for webhook or manual poll)
                if task_id and last_state and last_state.is_active():
                    # Send task ID signal for UI manual polling
                    yield f"<<<TASK_ID>>>{task_id}"
                    
                    if push_config and webhook_queue:
                        # Push notifications ENABLED: Wait for webhook
                        logger.info(f"Stream complete in active state ({last_state.value}), waiting for webhook")
                        async for chunk in self._wait_for_webhook_completion(
                            webhook_queue, task_id, last_state
                        ):
                            if chunk.startswith("<<<"):
                                yield chunk
                                yielded_any_content = True
                            else:
                                response_text += chunk
                                yield chunk
                                yielded_any_content = True
                    else:
                        # Push notifications DISABLED: Signal UI to show manual poll button
                        logger.info(f"Stream complete in active state ({last_state.value}), requesting manual poll")
                        yield "<<<POLL_REQUIRED>>>"
                        yielded_any_content = True

                # Cleanup webhook callback
                    logger.info(f"Cleaned up webhook callback for task {task_id}")

            else:
                # Legacy client path (unchanged)
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

                        if result.get("kind") == "message":
                            chunk = result.get("content", "")

                        elif result.get("kind") == "task":
                            self.last_task_id = result.get("id")
                            # Extract from artifacts
                            for artifact in result.get("artifacts", []):
                                for part in artifact.get("parts", []):
                                    chunk += part.get("content", "")

                        if chunk:
                            response_text += chunk
                            yield chunk
                            yielded_any_content = True

                    if "context" in response and "id" in response["context"]:
                        self.context_id = response["context"]["id"]

            self.last_response = response_text

            # Fallback error message if nothing yielded
            if not response_text and not yielded_any_content:
                error_msg = "Unable to get a response from the agent. Please try again."
                logger.warning("No response received from agent")
                yield error_msg
                self.last_response = error_msg

        except Exception as e:
            logger.error(f"Error sending message to agent: {e}", exc_info=True)
            error_msg = f"Error communicating with agent: {str(e)}. Please try again."
            yield error_msg
            self.last_response = error_msg

    def _extract_message_content(self, message: Any) -> str:
        """Extract text content from a Message object."""
        content = ""
        if hasattr(message, 'parts') and message.parts:
            for part in message.parts:
                if hasattr(part, 'root') and hasattr(part.root, 'text') and part.root.text:
                    content += part.root.text
                elif hasattr(part, 'text') and part.text:
                    content += part.text
                elif hasattr(part, 'content') and part.content:
                    content += part.content
        return content

    async def _wait_for_webhook_completion(
        self,
        webhook_queue: asyncio.Queue,
        task_id: str,
        initial_state: TaskState
    ) -> AsyncGenerator[str, None]:
        """
        Wait for webhook notifications until task reaches terminal/interrupted state.

        Args:
            webhook_queue: Queue receiving webhook notifications
            task_id: Task ID to track
            initial_state: Initial task state when entering this wait

        Yields:
            Content chunks and status signals
        """
        timeout_seconds = 300  # 5 minutes
        start_time = asyncio.get_event_loop().time()
        last_status: Optional[str] = None

        while True:
            try:
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                    logger.warning(f"Webhook timeout after {timeout_seconds}s")
                    break

                # Wait for webhook notification
                task_data = await asyncio.wait_for(webhook_queue.get(), timeout=1.0)
                logger.info(f"Webhook notification #{len(webhook_queue._queue) + 1} received for task {task_id}")

                # Reset timeout counter since we received activity
                start_time = asyncio.get_event_loop().time()

                # Fetch latest task status immediately upon notification
                task_result = await self.get_task_status(task_id)
                state = task_result.state
                logger.info(f"Task status update: {state.value}")

                if state.is_terminal():
                    # Terminal state reached - display final content and exit loop
                    yield "<<<CLEAR>>>"

                    if task_result.content:
                        logger.info(f"Yielded final content (length: {len(task_result.content)})")
                        yield task_result.content

                    break

                elif state.is_interrupted():
                    # Interrupted state (input/auth required) - user action needed
                    if task_result.content:
                        logger.info(f"Yielded interrupted content (length: {len(task_result.content)})")
                        yield task_result.content
                    elif task_result.status_message:
                        logger.info(f"Yielded interrupted status signal (length: {len(task_result.status_message)})")
                        yield f"<<<STATUS>>>{task_result.status_message}"

                    break

                elif state.is_active():
                    # Active state (working/submitted) - task still in progress
                    if task_result.status_message:
                        if task_result.status_message != last_status:
                            last_status = task_result.status_message
                            logger.info(f"Yielded new status signal (length: {len(last_status)})")
                            yield f"<<<STATUS>>>{last_status}"
                    
                    # Continue waiting for next notification
                    continue

                else:
                    # Unspecified or unknown state - should not happen
                    continue



            except asyncio.TimeoutError:
                # No notification yet, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error processing webhook: {e}", exc_info=True)
                break

    def _extract_webhook_artifacts(self, task_data: Dict[str, Any]) -> str:
        """Extract content from webhook task data artifacts."""
        content = ""
        for artifact in task_data.get('artifacts', []):
            if isinstance(artifact, dict):
                for part in artifact.get('parts', []):
                    if isinstance(part, dict):
                        content += part.get('text', '') or part.get('content', '')
        return content

    def _extract_webhook_status_message(self, task_data: Dict[str, Any]) -> Optional[str]:
        """Extract status message from webhook task data."""
        status = task_data.get('status', {})
        message = status.get('message', {})
        if isinstance(message, dict):
            for part in message.get('parts', []):
                if isinstance(part, dict):
                    text = part.get('text', '') or part.get('content', '')
                    if text:
                        return text
        return None
    
    async def get_last_response(self) -> str:
        """
        Get the last response from the agent
        
        Returns:
            Last response from the agent
        """
        return self.last_response or ""
    async def get_task_status(self, task_id: str) -> TaskStateResult:
        """
        Get the current status of a task via task/get API.
        
        Used for manual polling when push notifications are disabled.
        
        Args:
            task_id: ID of the task to check
            
        Returns:
            TaskStateResult with current status
        """
        try:
            # Get authentication headers
            auth_headers = self.agent.authentication.get_headers()
            
            # Call task/get endpoint
            if self.use_sdk and self.a2a_sdk_client:
                response = await self.a2a_sdk_client.get_task(
                    agent_url=self.agent.url,
                    task_id=task_id,
                    transport=self.agent.transport,
                    auth_type=self.agent.authentication.auth_type,
                    api_key_name=self.agent.authentication.api_key_name,
                    token=self.agent.authentication.token
                )
            else:
                response = await self.a2a_client.get_task(
                    agent_url=self.agent.url,
                    task_id=task_id,
                    auth_headers=auth_headers
                )
            
            task = None
            if "result" in response and isinstance(response["result"], dict):
                result = response["result"]
                # Handle both wrapped task and direct task object
                if "task" in result:
                    task = result["task"]
                elif "kind" in result and result["kind"] == "task":
                    task = result
                elif "id" in result: # Assume it's the task object
                    task = result
                    
            if not task:
                logger.error(f"Failed to get task status for {task_id}")
                return TaskStateResult(
                    state=TaskState.UNSPECIFIED,
                    content="Failed to retrieve task status.",
                    is_final=True
                )
                
            # Process the task response
            # Since this is a polling check, pass None for event and last_state since we want absolute state
            return self._process_task_response(task)
            
        except Exception as e:
            logger.error(f"Error getting task status: {e}")
            return TaskStateResult(
                state=TaskState.FAILED,
                content=f"Error checking task status: {str(e)}",
                is_final=True
            )

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
        webhook_handler: Optional[WebhookHandler] = None,
        ngrok_manager: Optional[NgrokManager] = None
    ):
        """
        Initialize the agent communication manager

        Args:
            agent_registry: AgentRegistry instance
            a2a_client: Optional A2AClient instance
            webhook_handler: Optional WebhookHandler instance
            ngrok_manager: Optional NgrokManager instance for secure tunneling
        """
        self.agent_registry = agent_registry
        self.a2a_client = a2a_client or A2AClient()
        self.webhook_handler = webhook_handler
        self.ngrok_manager = ngrok_manager
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
        
        # Prepare webhook URL and push notification config if needed
        webhook_config = None
        push_notification_config = None
        if use_webhook and self.webhook_handler:
            if not webhook_url:
                # Use ngrok public URL if available, otherwise fall back to localhost
                if self.ngrok_manager and self.ngrok_manager.is_active():
                    base_url = self.ngrok_manager.get_public_url()
                    webhook_url = f"{base_url}/webhook"
                    logger.info(f"Using ngrok webhook URL: {webhook_url}")
                else:
                    webhook_url = f"http://localhost:{self.webhook_handler.port}/webhook"
                    logger.warning("ngrok not available, using localhost webhook URL (may not work with remote agents)")

            # Generate a token for authentication
            token = str(uuid.uuid4())

            webhook_config = {
                "url": webhook_url,
                "token": token
            }

            # Create push notification config according to A2A spec
            push_notification_config = {
                "id": str(uuid.uuid4()),
                "url": webhook_url,
                "token": token
            }
            
            # Add authentication if available
            if auth_headers:
                schemes = []
                credentials = None
                
                for header_name, header_value in auth_headers.items():
                    if header_name.lower() == "authorization":
                        if header_value.startswith("Bearer "):
                            schemes.append("Bearer")
                            credentials = header_value.split(" ", 1)[1] if len(header_value.split(" ", 1)) > 1 else None
                        elif header_value.startswith("Basic "):
                            schemes.append("Basic")
                            credentials = header_value.split(" ", 1)[1] if len(header_value.split(" ", 1)) > 1 else None
                    else:
                        schemes.append(header_name)
                
                if schemes:
                    push_notification_config["authentication"] = {
                        "schemes": schemes
                    }
                    if credentials:
                        push_notification_config["authentication"]["credentials"] = credentials
        
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


