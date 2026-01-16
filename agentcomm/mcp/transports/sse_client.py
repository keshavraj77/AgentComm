import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from typing import Optional, Dict, Any

from agentcomm.mcp.mcp_client import MCPClient


class SSEMCPClient:
    def __init__(
        self,
        server_id: str,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ):
        self.server_id = server_id
        self.url = url
        self.headers = headers or {}
        self.client: Optional[MCPClient] = None

    async def connect(self) -> MCPClient:
        sse_transport = sse_client(self.url, self.headers)
        read, write = sse_transport

        session = ClientSession(read, write)
        client = MCPClient(self.server_id, session)
        await client.initialize()
        self.client = client
        return client

    async def disconnect(self):
        if self.client:
            await self.client.close()
            self.client = None
