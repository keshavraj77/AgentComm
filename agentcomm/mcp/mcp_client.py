import logging
from mcp import ClientSession
from mcp.types import Tool, Resource, Prompt

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, server_id: str, session: ClientSession):
        self.server_id = server_id
        self.session = session
        self.tools: list[Tool] = []
        self.resources: list[Resource] = []
        self.prompts: list[Prompt] = []
        self.is_connected = False

    async def initialize(self):
        # Note: Session context is managed by the transport client (StdioMCPClient/SSEMCPClient)
        await self.session.initialize()
        self.is_connected = True
        await self._discover_capabilities()

    async def _discover_capabilities(self):
        # Try to discover tools - handle servers that don't support each method
        try:
            tools_result = await self.session.list_tools()
            self.tools = tools_result.tools if tools_result else []
        except Exception as e:
            logger.warning(f"Could not list tools from {self.server_id}: {e}")
            self.tools = []

        try:
            resources_result = await self.session.list_resources()
            self.resources = resources_result.resources if resources_result else []
        except Exception as e:
            logger.warning(f"Could not list resources from {self.server_id}: {e}")
            self.resources = []

        try:
            prompts_result = await self.session.list_prompts()
            self.prompts = prompts_result.prompts if prompts_result else []
        except Exception as e:
            logger.warning(f"Could not list prompts from {self.server_id}: {e}")
            self.prompts = []

    async def call_tool(self, tool_name: str, arguments: dict):
        if not self.is_connected:
            raise RuntimeError(f"MCP server {self.server_id} is not connected")

        result = await self.session.call_tool(tool_name, arguments)
        return result

    async def read_resource(self, uri: str):
        if not self.is_connected:
            raise RuntimeError(f"MCP server {self.server_id} is not connected")

        result = await self.session.read_resource(uri)
        return result

    async def get_prompt(self, prompt_name: str, arguments: dict | None = None):
        if not self.is_connected:
            raise RuntimeError(f"MCP server {self.server_id} is not connected")

        result = await self.session.get_prompt(prompt_name, arguments)
        return result

    async def close(self):
        if self.is_connected:
            await self.session.__aexit__(None, None, None)
            self.is_connected = False

    def get_tools_for_llm(self) -> list[dict]:
        tools_for_llm = []
        for tool in self.tools:
            tools_for_llm.append({
                "type": "function",
                "function": {
                    "name": f"mcp_{self.server_id}_{tool.name}",
                    "description": tool.description or f"Tool from MCP server {self.server_id}",
                    "parameters": tool.inputSchema
                }
            })
        return tools_for_llm

    def get_tool_name_mapping(self) -> dict[str, str]:
        mapping = {}
        for tool in self.tools:
            mangled_name = f"mcp_{self.server_id}_{tool.name}"
            mapping[mangled_name] = tool.name
        return mapping
