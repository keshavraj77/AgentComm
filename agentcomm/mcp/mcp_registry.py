import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from agentcomm.mcp.mcp_client import MCPClient
from agentcomm.mcp.transports.stdio_client import StdioMCPClient
from agentcomm.mcp.transports.sse_client import SSEMCPClient


@dataclass
class MCPServerConfig:
    server_id: str
    name: str
    transport: str
    command: Optional[str] = None
    args: Optional[List[str]] = None
    url: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None


class MCPRegistry:
    def __init__(self):
        self.servers: Dict[str, MCPServerConfig] = {}
        self.active_clients: Dict[str, MCPClient] = {}
        self.lock = asyncio.Lock()

    def add_server(self, config: MCPServerConfig):
        self.servers[config.server_id] = config

    def remove_server(self, server_id: str):
        if server_id in self.servers:
            del self.servers[server_id]

    def get_server(self, server_id: str) -> Optional[MCPServerConfig]:
        return self.servers.get(server_id)

    def get_all_servers(self) -> List[MCPServerConfig]:
        return list(self.servers.values())

    async def connect_server(self, server_id: str) -> MCPClient:
        async with self.lock:
            if server_id in self.active_clients:
                return self.active_clients[server_id]

            config = self.servers.get(server_id)
            if not config:
                raise ValueError(f"Server {server_id} not found")

            # Validate required environment variables
            if config.env:
                missing_vars = []
                for key, value in config.env.items():
                    if not value or value.strip() == "":
                        missing_vars.append(key)
                
                if missing_vars:
                    raise ValueError(
                        f"MCP server '{config.name}' ({server_id}) requires environment variables: {', '.join(missing_vars)}. "
                        f"Please configure them in the MCP settings."
                    )

            if config.transport == "stdio":
                if not config.command or not config.args:
                    raise ValueError("stdio transport requires command and args")
                transport_client = StdioMCPClient(
                    server_id=server_id,
                    command=config.command,
                    args=config.args,
                    env=config.env
                )
            elif config.transport == "sse":
                if not config.url:
                    raise ValueError("sse transport requires url")
                transport_client = SSEMCPClient(
                    server_id=server_id,
                    url=config.url,
                    headers=config.headers
                )
            else:
                raise ValueError(f"Unknown transport: {config.transport}")

            client = await transport_client.connect()
            self.active_clients[server_id] = client
            return client

    async def disconnect_server(self, server_id: str):
        async with self.lock:
            if server_id in self.active_clients:
                client = self.active_clients[server_id]
                await client.close()
                del self.active_clients[server_id]

    async def disconnect_all(self):
        async with self.lock:
            for server_id in list(self.active_clients.keys()):
                await self.disconnect_server(server_id)

    def get_active_servers(self) -> List[str]:
        return list(self.active_clients.keys())

    def get_client(self, server_id: str) -> Optional[MCPClient]:
        return self.active_clients.get(server_id)

    async def get_tools_for_servers(self, server_ids: List[str]) -> List[Dict[str, Any]]:
        all_tools = []
        for server_id in server_ids:
            client = await self.connect_server(server_id)
            tools = client.get_tools_for_llm()
            all_tools.extend(tools)
        return all_tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        parts = tool_name.split("_", 2)
        if len(parts) < 3 or parts[0] != "mcp":
            raise ValueError(f"Invalid MCP tool name format: {tool_name}")

        server_id = parts[1]
        actual_tool_name = "_".join(parts[2:])

        client = await self.connect_server(server_id)
        result = await client.call_tool(actual_tool_name, arguments)
        return result

    def get_server_id_from_tool_name(self, tool_name: str) -> Optional[str]:
        parts = tool_name.split("_", 2)
        if len(parts) >= 2 and parts[0] == "mcp":
            return parts[1]
        return None
