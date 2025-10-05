"""
A2A SDK Client Wrapper
Wraps the official a2a-sdk to provide a unified interface for A2A agent communication
"""

import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator, List

import httpx
from a2a.client import A2AClient, ClientFactory, ClientConfig
from a2a.types import (
    AgentCard, TransportProtocol, SecurityScheme,
    HTTPAuthSecurityScheme, APIKeySecurityScheme,
    AgentCapabilities, Role
)
from a2a.client import create_text_message_object
from a2a.client.auth import InMemoryContextCredentialStore

logger = logging.getLogger(__name__)


class A2ASDKClientWrapper:
    """
    Wrapper for the official A2A SDK to provide a unified interface
    """

    def __init__(self):
        """Initialize the A2A SDK client wrapper"""
        self.http_client = httpx.AsyncClient()
        self.clients: Dict[str, Any] = {}
        self.credential_store = InMemoryContextCredentialStore()

    def _create_agent_card(
        self,
        agent_url: str,
        transport: str = "jsonrpc",
        auth_type: str = "none",
        api_key_name: Optional[str] = None
    ) -> AgentCard:
        """
        Create an AgentCard for the agent

        Args:
            agent_url: URL of the agent
            transport: Transport protocol ("jsonrpc", "grpc", "http")
            auth_type: Authentication type
            api_key_name: API key header name

        Returns:
            AgentCard instance
        """
        # Map transport string to TransportProtocol
        transport_protocol = TransportProtocol.jsonrpc
        if transport == "grpc":
            transport_protocol = TransportProtocol.grpc
        elif transport == "http":
            transport_protocol = TransportProtocol.http_json

        # Create security schemes if authentication is required
        security_schemes = {}
        security = None
        if auth_type != "none":
            if auth_type == "api_key" and api_key_name:
                security_schemes["api_key"] = APIKeySecurityScheme(
                    type="apiKey",
                    name=api_key_name,
                    in_="header"
                )
                security = [{"api_key": []}]
            elif auth_type == "bearer":
                security_schemes["bearer"] = HTTPAuthSecurityScheme(
                    type="http",
                    scheme="bearer"
                )
                security = [{"bearer": []}]
            elif auth_type == "basic":
                security_schemes["basic"] = HTTPAuthSecurityScheme(
                    type="http",
                    scheme="basic"
                )
                security = [{"basic": []}]

        # Create capabilities
        capabilities = AgentCapabilities(
            streaming=True,
            push_notifications=False
        )

        # Create and return the agent card
        return AgentCard(
            url=agent_url,
            name="A2A Agent",
            description="A2A Protocol Agent",
            version="1.0.0",
            preferred_transport=transport_protocol,
            capabilities=capabilities,
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
            skills=[],
            security_schemes=security_schemes if security_schemes else None,
            security=security
        )

    async def get_client(
        self,
        agent_url: str,
        transport: str = "jsonrpc",
        auth_type: str = "none",
        api_key_name: Optional[str] = None,
        token: Optional[str] = None
    ):
        """
        Get or create an A2A client for the agent

        Args:
            agent_url: URL of the agent
            transport: Transport protocol
            auth_type: Authentication type
            api_key_name: API key header name
            token: Authentication token

        Returns:
            A2A client instance
        """
        client_key = f"{agent_url}:{transport}"

        if client_key not in self.clients:
            # Create agent card
            agent_card = self._create_agent_card(
                agent_url, transport, auth_type, api_key_name
            )

            # Store credentials if provided
            if token and auth_type != "none":
                if auth_type == "api_key" and api_key_name:
                    self.credential_store.set_credential(
                        agent_url, api_key_name, token
                    )
                elif auth_type == "bearer":
                    self.credential_store.set_credential(
                        agent_url, "Authorization", f"Bearer {token}"
                    )
                elif auth_type == "basic":
                    self.credential_store.set_credential(
                        agent_url, "Authorization", f"Basic {token}"
                    )

            # Create client using ClientFactory
            try:
                logger.info(f"Creating A2A client for {agent_url} using {transport}")
                logger.debug(f"Agent card: {agent_card}")

                # Create client config
                client_config = ClientConfig(
                    httpx_client=self.http_client,
                    streaming=True
                )

                # Create factory and client
                factory = ClientFactory(config=client_config)
                client = factory.create(agent_card)
                self.clients[client_key] = client
                logger.info(f"Successfully created A2A client for {agent_url} using {transport}")
            except Exception as e:
                logger.error(f"Error creating A2A client with factory: {e}", exc_info=True)
                # Fallback to legacy A2AClient
                try:
                    logger.info(f"Attempting to create legacy A2A client for {agent_url}")
                    client = A2AClient(
                        httpx_client=self.http_client,
                        agent_card=agent_card,
                        url=agent_url
                    )
                    self.clients[client_key] = client
                    logger.info(f"Successfully created legacy A2A client for {agent_url}")
                except Exception as e2:
                    logger.error(f"Error creating legacy A2A client: {e2}", exc_info=True)
                    raise

        return self.clients[client_key]

    async def send_message(
        self,
        agent_url: str,
        message: str,
        transport: str = "jsonrpc",
        auth_type: str = "none",
        api_key_name: Optional[str] = None,
        token: Optional[str] = None,
        context_id: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a message to an A2A agent

        Args:
            agent_url: URL of the agent
            message: Message to send
            transport: Transport protocol
            auth_type: Authentication type
            api_key_name: API key header name
            token: Authentication token
            context_id: Optional context ID
            task_id: Optional task ID

        Yields:
            Response dictionaries from the agent
        """
        try:
            logger.info(f"Sending message to {agent_url} via {transport}")
            logger.debug(f"Message: {message[:100]}...")

            # Get or create client
            client = await self.get_client(
                agent_url, transport, auth_type, api_key_name, token
            )

            # Create message object
            logger.debug(f"Creating message object with context_id={context_id}, task_id={task_id}")
            msg = create_text_message_object(
                role=Role.user,
                content=message
            )
            # Add context_id and task_id if provided
            if context_id:
                msg.context_id = context_id
            if task_id:
                msg.task_id = task_id

            # Add authentication headers if needed
            headers = {}
            if token and auth_type != "none":
                if auth_type == "api_key" and api_key_name:
                    headers[api_key_name] = token
                elif auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {token}"
                elif auth_type == "basic":
                    headers["Authorization"] = f"Basic {token}"

            # Send message and yield responses
            logger.info(f"Calling client.send_message() method")
            async for response in client.send_message(msg):
                logger.debug(f"Received response: {response}")
                yield {
                    "result": response
                }

        except Exception as e:
            logger.error(f"Error sending message via A2A SDK: {e}", exc_info=True)
            yield {
                "error": {
                    "code": -1,
                    "message": f"Error: {e}"
                }
            }

    async def send_streaming_message(
        self,
        agent_url: str,
        message: str,
        transport: str = "jsonrpc",
        auth_type: str = "none",
        api_key_name: Optional[str] = None,
        token: Optional[str] = None,
        context_id: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a streaming message to an A2A agent

        Args:
            agent_url: URL of the agent
            message: Message to send
            transport: Transport protocol
            auth_type: Authentication type
            api_key_name: API key header name
            token: Authentication token
            context_id: Optional context ID
            task_id: Optional task ID

        Yields:
            Streaming response chunks from the agent
        """
        try:
            logger.info(f"Sending streaming message to {agent_url} via {transport}")
            logger.debug(f"Message: {message[:100]}...")

            # Get or create client
            client = await self.get_client(
                agent_url, transport, auth_type, api_key_name, token
            )

            # Create message object
            logger.debug(f"Creating message object with context_id={context_id}, task_id={task_id}")
            msg = create_text_message_object(
                role=Role.user,
                content=message
            )
            # Add context_id and task_id if provided
            if context_id:
                msg.context_id = context_id
            if task_id:
                msg.task_id = task_id

            # Add authentication headers if needed
            headers = {}
            if token and auth_type != "none":
                if auth_type == "api_key" and api_key_name:
                    headers[api_key_name] = token
                elif auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {token}"
                elif auth_type == "basic":
                    headers["Authorization"] = f"Basic {token}"

            # Send message and stream responses
            logger.info(f"Calling client.send_message() method")
            chunk_count = 0
            async for chunk in client.send_message(msg):
                chunk_count += 1
                logger.info(f"Received chunk #{chunk_count}: type={type(chunk).__name__}")
                logger.debug(f"Chunk content: {chunk}")
                yield {
                    "result": chunk
                }
            logger.info(f"Streaming completed. Total chunks received: {chunk_count}")

        except Exception as e:
            logger.error(f"Error sending streaming message via A2A SDK: {e}", exc_info=True)
            yield {
                "error": {
                    "code": -1,
                    "message": f"Error: {e}"
                }
            }

    async def close(self):
        """Close all clients and the HTTP client"""
        self.clients.clear()
        await self.http_client.aclose()
