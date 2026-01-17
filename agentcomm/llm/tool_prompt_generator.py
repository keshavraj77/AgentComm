"""
Tool Prompt Generator - Creates system prompts that instruct LLMs to use MCP tools
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def generate_tool_system_prompt(tools: Optional[List[Dict[str, Any]]] = None, base_prompt: str = "") -> str:
    """
    Generate a system prompt that instructs the LLM to use available tools

    Args:
        tools: List of tool definitions in LLM function format
        base_prompt: Existing base system prompt to augment

    Returns:
        Enhanced system prompt with tool instructions
    """
    if not tools or len(tools) == 0:
        return base_prompt

    # Extract tool summaries
    tool_summaries = []
    for tool in tools:
        if "function" in tool:
            func = tool["function"]
            name = func.get("name", "unknown")
            description = func.get("description", "No description")
            tool_summaries.append(f"  - {name}: {description}")

    tool_list = "\n".join(tool_summaries)
    tool_count = len(tools)

    # Build the enhanced prompt
    tool_instructions = f"""
You have access to {tool_count} tools that you can use to help answer the user's questions:

{tool_list}

IMPORTANT INSTRUCTIONS FOR TOOL USAGE:
1. When you need information that requires external data (files, APIs, databases, web search), use the appropriate tool
2. Call tools when you have all required parameters to make the call
3. If you need clarifying information from the user before calling a tool, ask for it first
4. You can call multiple tools if needed to answer the question thoroughly
5. **CRITICAL**: After you call a tool, you will receive the tool result in the NEXT message with role="tool". You MUST read and use this tool result to answer the user's question. DO NOT ignore tool results or ask the same question again.
6. If a tool returns an error, explain the error to the user and suggest alternatives

HOW TO USE TOOL RESULTS:
- When you see a message with role="tool", this is the result from your previous tool call
- Read the entire tool result carefully
- Extract the relevant information from the tool result
- Format and present the information to the user in a clear, helpful way
- DO NOT ask for information that was already provided in the tool result

Example tool usage flow:
1. User asks a question that requires external data
2. You identify the appropriate tool and call it with necessary parameters
3. System returns tool result with role="tool" containing the data
4. You read the tool result and present the information clearly to the user

BEST PRACTICES:
- When requesting paginated data, use reasonable page sizes (10-20 items) unless user requests more
- Smaller responses are easier to process and present
- Always wait for and use tool results before responding to the user

Remember: You are an intelligent assistant with access to tools. Use them when appropriate and ALWAYS use the tool results to answer questions. Tool results appear as messages with role="tool" immediately after you make a tool call.
"""

    # Combine with base prompt
    if base_prompt:
        return f"{base_prompt}\n\n{tool_instructions}"
    else:
        return f"You are a helpful AI assistant with access to tools.{tool_instructions}"


def generate_lightweight_tool_prompt(tools: Optional[List[Dict[str, Any]]] = None, base_prompt: str = "") -> str:
    """
    Generate a minimal system prompt for tool usage (when context is limited)

    Args:
        tools: List of tool definitions
        base_prompt: Existing base system prompt

    Returns:
        Lightweight prompt with tool count
    """
    if not tools or len(tools) == 0:
        return base_prompt

    tool_count = len(tools)
    tool_instructions = f"\n\nYou have access to {tool_count} tools. Use them when needed to answer questions that require external data (files, APIs, search, etc.)."

    if base_prompt:
        return f"{base_prompt}{tool_instructions}"
    else:
        return f"You are a helpful AI assistant.{tool_instructions}"
