"""
A2A Protocol Client Implementation
"""

import json
import uuid
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List, Union

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class Message(BaseModel):
    """Message model for A2A protocol"""
    content: str
    content_type: str = "text/plain"
    message_id: Optional[str] = None
    role: Optional[str] = None
    context_id: Optional[str] = None
    task_id: Optional[str] = None

class PushNotificationConfig(BaseModel):
    """Push notification configuration for A2A protocol"""
    url: str
    authentication: Optional[Dict[str, Any]] = None
    token: Optional[str] = None
    id: Optional[str] = None

class A2AClient:
    """Main A2A protocol client implementation"""
    
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """
        Initialize the A2A client
        
        Args:
            http_client: Optional httpx AsyncClient instance
        """
        self.http_client = http_client or httpx.AsyncClient()
    
    async def send_message(
        self,
        agent_url: str,
        message: Union[str, Message],
        context_id: Optional[str] = None,
        webhook_url: Optional[str] = None,
        auth_headers: Optional[Dict[str, str]] = None,
        blocking: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a message to an A2A agent and stream the response
        
        Args:
            agent_url: URL of the A2A agent
            message: Message to send (string or Message object)
            context_id: Optional context ID for continuing a conversation
            webhook_url: Optional webhook URL for push notifications
            auth_headers: Optional authentication headers
            blocking: Whether to wait for the task to complete
            
        Yields:
            Dict containing the response from the agent
        """
        # Prepare the message
        if isinstance(message, str):
            msg = Message(
                content=message,
                message_id=str(uuid.uuid4()),
                role="user",
                context_id=context_id
            )
        else:
            msg = message
            if not msg.message_id:
                msg.message_id = str(uuid.uuid4())
            if not msg.role:
                msg.role = "user"
            if context_id and not msg.context_id:
                msg.context_id = context_id
        
        # Prepare the request payload
        payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": msg.message_id,
                    "role": msg.role,
                    "parts": [
                        {
                            "kind": "text",
                            "text": msg.content
                        }
                    ]
                },
                "configuration": {}
            },
            "id": str(uuid.uuid4())
        }
        
        # Add context ID if provided
        if msg.context_id:
            payload["params"]["message"]["contextId"] = msg.context_id
        
        # Add task ID if provided
        if msg.task_id:
            payload["params"]["message"]["taskId"] = msg.task_id
        
        # Add push notification configuration if webhook URL is provided
        if webhook_url:
            push_config = {
                "url": webhook_url,
            }
            
            if auth_headers:
                push_config["authentication"] = {
                    "schemes": list(auth_headers.keys())
                }
                # Convert to proper type for PushNotificationConfig
                if isinstance(push_config, dict):
                    push_config = PushNotificationConfig(**push_config)
            
            payload["params"]["configuration"]["pushNotificationConfig"] = push_config
        
        # Add blocking parameter
        payload["params"]["configuration"]["blocking"] = blocking
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json"
        }
        
        if auth_headers:
            headers.update(auth_headers)
        
        try:
            # Send the request
            logger.debug(f"Sending request to {agent_url}: {payload}")
            response = await self.http_client.post(
                agent_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            logger.debug(f"Received response: {result}")
            
            # Yield the result
            yield result
            
            # If the response contains a task, check its status
            if "result" in result and isinstance(result["result"], dict) and "task" in result["result"]:
                task = result["result"]["task"]
                task_id = task["id"]
                
                # If the task is not completed and blocking is True, poll for updates
                if blocking and task["status"]["state"] not in ["completed", "failed", "canceled"]:
                    async for update in self.poll_task(agent_url, task_id, auth_headers):
                        yield update
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            yield {
                "error": {
                    "code": e.response.status_code,
                    "message": f"HTTP error: {e}"
                }
            }
        
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            yield {
                "error": {
                    "code": -1,
                    "message": f"Error: {e}"
                }
            }
    
    async def poll_task(
        self,
        agent_url: str,
        task_id: str,
        auth_headers: Optional[Dict[str, str]] = None,
        interval: float = 1.0,
        max_attempts: int = 60
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Poll for task updates
        
        Args:
            agent_url: URL of the A2A agent
            task_id: ID of the task to poll
            auth_headers: Optional authentication headers
            interval: Polling interval in seconds
            max_attempts: Maximum number of polling attempts
            
        Yields:
            Dict containing the task update
        """
        # Prepare the request payload
        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "params": {
                "id": task_id
            },
            "id": str(uuid.uuid4())
        }
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json"
        }
        
        if auth_headers:
            headers.update(auth_headers)
        
        attempts = 0
        while attempts < max_attempts:
            try:
                # Send the request
                response = await self.http_client.post(
                    agent_url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                # Parse the response
                result = response.json()
                logger.debug(f"Received task update: {result}")
                
                # Yield the result
                yield result
                
                # Check if the task is completed
                if "result" in result and isinstance(result["result"], dict) and "status" in result["result"]:
                    status = result["result"]["status"]["state"]
                    if status in ["completed", "failed", "canceled"]:
                        break
                
                # Wait before polling again
                await asyncio.sleep(interval)
                attempts += 1
            
            except Exception as e:
                logger.error(f"Error polling task: {e}")
                yield {
                    "error": {
                        "code": -1,
                        "message": f"Error polling task: {e}"
                    }
                }
                break
    
    async def send_streaming_message(
        self,
        agent_url: str,
        message: Union[str, Message],
        context_id: Optional[str] = None,
        auth_headers: Optional[Dict[str, str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a message to an A2A agent and stream the response using Server-Sent Events
        
        Args:
            agent_url: URL of the A2A agent
            message: Message to send (string or Message object)
            context_id: Optional context ID for continuing a conversation
            auth_headers: Optional authentication headers
            
        Yields:
            Dict containing the streaming response from the agent
        """
        # Prepare the message
        if isinstance(message, str):
            msg = Message(
                content=message,
                message_id=str(uuid.uuid4()),
                role="user",
                context_id=context_id
            )
        else:
            msg = message
            if not msg.message_id:
                msg.message_id = str(uuid.uuid4())
            if not msg.role:
                msg.role = "user"
            if context_id and not msg.context_id:
                msg.context_id = context_id
        
        # Prepare the request payload
        payload = {
            "jsonrpc": "2.0",
            "method": "message/stream",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": msg.message_id,
                    "role": msg.role,
                    "parts": [
                        {
                            "kind": "text",
                            "text": msg.content
                        }
                    ]
                }
            },
            "id": str(uuid.uuid4())
        }
        
        # Add context ID if provided
        if msg.context_id:
            payload["params"]["message"]["contextId"] = msg.context_id
        
        # Add task ID if provided
        if msg.task_id:
            payload["params"]["message"]["taskId"] = msg.task_id
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        if auth_headers:
            headers.update(auth_headers)
        
        try:
            # Send the request
            logger.debug(f"Sending streaming request to {agent_url}: {payload}")
            async with self.http_client.stream(
                "POST",
                agent_url,
                json=payload,
                headers=headers
            ) as response:
                response.raise_for_status()
                
                # Process the streaming response
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    # Process complete SSE events
                    while "\n\n" in buffer:
                        event, buffer = buffer.split("\n\n", 1)
                        lines = event.strip().split("\n")
                        
                        data_lines = []
                        for line in lines:
                            if line.startswith("data:"):
                                data_lines.append(line[5:].strip())
                        
                        if data_lines:
                            data = "".join(data_lines)
                            try:
                                result = json.loads(data)
                                logger.debug(f"Received streaming response: {result}")
                                yield result
                            except json.JSONDecodeError as e:
                                logger.error(f"Error parsing SSE data: {e}")
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            yield {
                "error": {
                    "code": e.response.status_code,
                    "message": f"HTTP error: {e}"
                }
            }
        
        except Exception as e:
            logger.error(f"Error sending streaming message: {e}")
            yield {
                "error": {
                    "code": -1,
                    "message": f"Error: {e}"
                }
            }
    
    async def cancel_task(
        self,
        agent_url: str,
        task_id: str,
        auth_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Cancel a task
        
        Args:
            agent_url: URL of the A2A agent
            task_id: ID of the task to cancel
            auth_headers: Optional authentication headers
            
        Returns:
            Dict containing the response from the agent
        """
        # Prepare the request payload
        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/cancel",
            "params": {
                "id": task_id
            },
            "id": str(uuid.uuid4())
        }
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json"
        }
        
        if auth_headers:
            headers.update(auth_headers)
        
        try:
            # Send the request
            logger.debug(f"Sending cancel request to {agent_url}: {payload}")
            response = await self.http_client.post(
                agent_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            logger.debug(f"Received cancel response: {result}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error canceling task: {e}")
            return {
                "error": {
                    "code": -1,
                    "message": f"Error: {e}"
                }
            }
    
    async def close(self):
        """Close the HTTP client"""
        await self.http_client.aclose()


