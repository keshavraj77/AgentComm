# MCP Integration for AgentComm

This document describes the MCP (Model Context Protocol) integration in AgentComm.

## Overview

MCP integration allows users to onboard MCP servers and use their tools/resources when chatting with LLMs. MCP servers expose tools that LLMs can call to perform actions like:
- File system operations (read/write files)
- GitHub integration (issues, repos)
- Database access
- Web searches
- Custom business logic

## Architecture

### Components

1. **MCPClient** (`agentcomm/mcp/mcp_client.py`)
   - Base wrapper for MCP server communication
   - Manages session, tools, resources, prompts
   - Provides `get_tools_for_llm()` to convert MCP tools to LLM function format

2. **Transport Clients** (`agentcomm/mcp/transports/`)
   - `stdio_client.py`: For stdio transport (subprocess-based)
   - `sse_client.py`: For SSE transport (HTTP with Server-Sent Events)

3. **MCPRegistry** (`agentcomm/mcp/mcp_registry.py`)
   - Manages registered MCP servers
   - Connects/disconnects MCP servers
   - Provides tools to LLMs in proper format
   - Executes tool calls on behalf of LLMs

4. **Configuration**
   - `mcp_servers.json`: Stores MCP server configurations
   - Supports both stdio and SSE transports
   - Updated via ConfigStore

5. **SessionManager Integration**
   - Manages enabled MCP servers per thread
   - Passes MCP tools to LLMs when generating responses
   - Methods: `enable_mcp_server()`, `disable_mcp_server()`, `set_enabled_mcp_servers()`

## How It Works

### 1. Onboarding MCP Servers

Users add MCP servers via `mcp_servers.json`:

```json
{
  "mcp_servers": [
    {
      "server_id": "filesystem",
      "name": "Local Filesystem",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
      "env": {}
    },
    {
      "server_id": "github",
      "name": "GitHub",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {"GITHUB_TOKEN": "your-token"}
    }
  ]
}
```

### 2. Selecting MCP Servers

When chatting with an LLM, users can enable MCP servers:
- UI shows available MCP servers (from `mcp_servers.json`)
- User selects which servers to enable for the current thread
- `SessionManager.set_enabled_mcp_servers()` stores the selection

### 3. Chat Flow with MCP

1. User sends message to LLM
2. `SessionManager.send_message()` checks enabled MCP servers
3. Calls `MCPRegistry.get_tools_for_servers()` to collect all tools
4. Passes tools to LLM via `LLMRouter.generate_stream(tools=...)`
5. LLM decides whether to call tools based on user request
6. If LLM calls a tool:
   - Tool name format: `mcp_{server_id}_{tool_name}`
   - `MCPRegistry.call_tool()` routes to correct MCP server
   - MCP server executes tool and returns result
   - Result is fed back to LLM
7. LLM generates final response incorporating tool results

### 4. Tool Format

MCP tools are converted to LLM function format:

```python
{
  "type": "function",
  "function": {
    "name": "mcp_filesystem_read_file",
    "description": "Read file contents",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string"}
      },
      "required": ["path"]
    }
  }
}
```

## MCP Server Configuration

### stdio Transport

```json
{
  "server_id": "my-stdio-server",
  "name": "My Stdio Server",
  "transport": "stdio",
  "command": "python",
  "args": ["-m", "my_mcp_server"],
  "env": {
    "MY_ENV_VAR": "value"
  }
}
```

### SSE Transport

```json
{
  "server_id": "my-sse-server",
  "name": "My SSE Server",
  "transport": "sse",
  "url": "http://localhost:8000/mcp",
  "headers": {
    "Authorization": "Bearer token"
  }
}
```

## Usage Example

```python
# In main.py initialization
from agentcomm.mcp.mcp_registry import MCPRegistry, MCPServerConfig

# Create MCP registry
mcp_registry = MCPRegistry()

# Load servers from config
mcp_config = config_store.get_mcp_servers()
for server_config in mcp_config.get("mcp_servers", []):
    config = MCPServerConfig(**server_config)
    mcp_registry.add_server(config)

# Pass to SessionManager
session_manager = SessionManager(
    agent_registry=agent_registry,
    llm_router=llm_router,
    mcp_registry=mcp_registry
)

# Enable MCP servers for current thread
session_manager.set_enabled_mcp_servers(["filesystem", "github"])

# Send message - tools will be automatically included
await session_manager.send_message("Read my README.md file")
```

## Current Status

### Completed
- ✅ MCP directory structure
- ✅ MCPClient base class
- ✅ stdio transport client
- ✅ SSE transport client
- ✅ MCPRegistry
- ✅ Configuration support (ConfigStore updates)
- ✅ SessionManager integration
- ✅ OpenAI provider tool support

### Pending
- ⏳ UI: Settings dialog for managing MCP servers
- ⏳ UI: AgentSelector MCP server toggles
- ⏳ UI: ChatWidget tool call display
- ⏳ main.py initialization
- ⏳ Other LLM providers (Anthropic, Gemini, Local)

## Testing MCP Integration

### Test with Filesystem Server

1. Ensure Node.js and npm are installed
2. Run filesystem MCP server:
   ```bash
   npx -y @modelcontextprotocol/server-filesystem /path/to/project
   ```
3. Add server to `mcp_servers.json`
4. Enable server in AgentComm
5. Chat: "List all files in the current directory"

### Test with GitHub Server

1. Get GitHub personal access token
2. Configure in `mcp_servers.json`:
   ```json
   {
     "server_id": "github",
     "name": "GitHub",
     "transport": "stdio",
     "command": "npx",
     "args": ["-y", "@modelcontextprotocol/server-github"],
     "env": {"GITHUB_TOKEN": "your-token"}
   }
   ```
3. Enable server in AgentComm
4. Chat: "List issues in my repository"

## Security Considerations

- stdio transport servers run as subprocesses with same permissions as AgentComm
- SSE transport servers require proper authentication headers
- API keys stored in config (same as LLM providers)
- Tool execution is synchronous to MCP server

## Future Enhancements

- [ ] Tool execution progress reporting
- [ ] Resource reading (beyond tools)
- [ ] Prompt templates from MCP servers
- [ ] MCP server auto-discovery
- [ ] Permission controls per tool
- [ ] Tool execution logging
- [ ] Full tool call streaming support
