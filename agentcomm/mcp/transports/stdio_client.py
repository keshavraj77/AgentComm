import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Optional, Dict, Any

from agentcomm.mcp.mcp_client import MCPClient


class StdioMCPClient:
    def __init__(
        self,
        server_id: str,
        command: str,
        args: list[str],
        env: Optional[Dict[str, str]] = None
    ):
        self.server_id = server_id
        self.command = command
        self.args = args
        self.env = env or {}
        self.client: Optional[MCPClient] = None
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )

    async def connect(self) -> MCPClient:
        stdio_transport = stdio_client(self.server_params)
        read, write = stdio_transport

        session = ClientSession(read, write)
        client = MCPClient(self.server_id, session)
        await client.initialize()
        self.client = client
        return client

    async def disconnect(self):
        if self.client:
            await self.client.close()
            self.client = None
