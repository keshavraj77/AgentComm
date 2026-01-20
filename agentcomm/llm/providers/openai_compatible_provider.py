"""
OpenAI-Compatible Provider Base Class

This base class can be used by any LLM provider that supports the OpenAI API format,
including:
- Local LLMs (LM Studio, Ollama, vLLM, etc.)
- Google Gemini (via OpenAI-compatible endpoint)
- Anthropic Claude (via their API which follows OpenAI conventions)
- DeepSeek, Qwen, and other providers with OpenAI-compatible endpoints
"""

import json
import logging
import asyncio
import httpx
from typing import Dict, Any, Optional, AsyncGenerator, List

from agentcomm.llm.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    """
    Base provider for any LLM that supports OpenAI-compatible API format

    Subclasses only need to provide:
    - base_url: The API endpoint URL
    - api_key: The API key (or None for local endpoints)
    - default_model: The default model name
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        default_model: str = "default",
        **kwargs
    ):
        """
        Initialize the OpenAI-compatible provider

        Args:
            base_url: Base URL for the API endpoint (e.g., "http://localhost:1234/v1")
            api_key: API key (optional for local endpoints)
            default_model: Default model name
            **kwargs: Additional configuration parameters
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.default_model = default_model
        self.default_params = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
            "top_p": kwargs.get("top_p", 1.0),
        }

        # Create HTTP client
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers=headers
        )

        logger.info(f"OpenAI-compatible provider initialized: {base_url}")

    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate text with streaming response

        Args:
            prompt: The prompt to send to the model
            tools: Optional list of tool definitions in OpenAI format
            **kwargs: Additional parameters

        Yields:
            Generated text chunks
        """
        try:
            model = kwargs.get("model", self.default_model)

            # Build messages array
            messages = self._build_messages(prompt, kwargs)

            # Prepare request payload
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "temperature": kwargs.get("temperature", self.default_params["temperature"]),
                "max_tokens": kwargs.get("max_tokens", self.default_params["max_tokens"]),
                "top_p": kwargs.get("top_p", self.default_params["top_p"])
            }

            # Only add tools if provided and not empty
            if tools and len(tools) > 0:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            endpoint = f"{self.base_url}/chat/completions"

            # Send the request and stream the response
            async with self.client.stream("POST", endpoint, json=payload) as response:
                response.raise_for_status()

                # State for thinking parsing
                thinking_state = {
                    "in_thinking": False,
                    "current_tag": None,
                    "buffer": ""
                }

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    # OpenAI streaming format: "data: {json}"
                    if line.startswith("data: "):
                        line = line[6:]  # Remove "data: " prefix

                    if line == "[DONE]":
                        break

                    try:
                        data = json.loads(line)

                        # Extract content
                        content = ""
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})

                            # Check for specific reasoning_content field (DeepSeek R1)
                            if "reasoning_content" in delta and delta["reasoning_content"]:
                                thinking_content = delta["reasoning_content"]
                                yield f"<<<THINKING>>>{thinking_content}"
                                continue

                            # Standard content
                            content = delta.get("content", "")

                        if content:
                            # Process content for thinking tags
                            async for chunk in self._process_thinking_tags(content, thinking_state):
                                yield chunk

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse response line: {line}")

        except Exception as e:
            logger.error(f"Error generating text: {e}")
            yield f"Error: {e}"

    async def generate_complete(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs):
        """
        Generate complete text response (non-streaming)

        Args:
            prompt: The prompt to send to the model
            tools: Optional list of tool definitions
            **kwargs: Additional parameters including:
                - return_tool_calls: If True, returns Dict[str, Any] with 'content' and 'tool_calls'

        Returns:
            Complete generated text (str) or structured response (dict)
        """
        try:
            model = kwargs.get("model", self.default_model)
            return_tool_calls = kwargs.get("return_tool_calls", False)

            # Build messages array
            messages = self._build_messages(prompt, kwargs)

            # Prepare request payload
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "temperature": kwargs.get("temperature", self.default_params["temperature"]),
                "max_tokens": kwargs.get("max_tokens", self.default_params["max_tokens"]),
                "top_p": kwargs.get("top_p", self.default_params["top_p"])
            }

            # Only add tools if provided and not empty
            if tools and len(tools) > 0:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            endpoint = f"{self.base_url}/chat/completions"

            # Send the request
            response = await self.client.post(endpoint, json=payload)
            response.raise_for_status()

            # Parse the response
            data = response.json()

            # Extract content and tool calls
            if "choices" in data and len(data["choices"]) > 0:
                message = data["choices"][0].get("message", {})
                content = message.get("content", "") or ""
                tool_calls = message.get("tool_calls", [])

                # Return structured response if requested
                if return_tool_calls:
                    return {
                        "content": content,
                        "tool_calls": tool_calls
                    }

                # Otherwise return just content
                if content:
                    return content

                # If only tool calls, indicate that
                if tool_calls:
                    return "[Tool calls requested - use return_tool_calls=True to access them]"

            if "error" in data:
                error_msg = f"Error: {data['error']}"
                if return_tool_calls:
                    return {"content": error_msg, "tool_calls": []}
                return error_msg

            if return_tool_calls:
                return {"content": "Error: Could not extract content from response", "tool_calls": []}
            return "Error: Could not extract content from response"

        except Exception as e:
            logger.error(f"Error generating text: {e}")
            error_msg = f"Error: {e}"
            if kwargs.get("return_tool_calls", False):
                return {"content": error_msg, "tool_calls": []}
            return error_msg

    def _build_messages(self, prompt: str, kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build messages array from prompt and kwargs

        Args:
            prompt: Current prompt (may be empty for tool calling loop)
            kwargs: Additional parameters including system, chat_history

        Returns:
            List of message dictionaries
        """
        messages = []

        # Add system message if provided
        system = kwargs.get("system", "")
        if system:
            messages.append({"role": "system", "content": system})

        # Add chat history if provided
        chat_history = kwargs.get("chat_history") or kwargs.get("history")
        if chat_history and isinstance(chat_history, list):
            for msg in chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                # Handle tool result messages
                if role == "tool":
                    messages.append({
                        "role": "tool",
                        "content": content,
                        "tool_call_id": msg.get("tool_call_id", ""),
                        "name": msg.get("name", "")
                    })
                # Handle assistant messages with tool calls
                elif role == "assistant":
                    msg_dict = {"role": "assistant", "content": content}
                    if "tool_calls" in msg:
                        msg_dict["tool_calls"] = msg["tool_calls"]
                    messages.append(msg_dict)
                else:
                    messages.append({"role": role, "content": content})

        # Add the current message (only if not empty - for tool calling loop)
        if prompt:
            messages.append({"role": "user", "content": prompt})

        return messages

    async def _process_thinking_tags(self, content: str, state: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        Process content for thinking tags like <think>, <reasoning>, <thought>
        Handles split tags across chunks.
        """
        # Supported tags
        tags = ["think", "reasoning", "thought"]

        # If we have a buffer (potential partial tag), prepend it
        if state["buffer"]:
            content = state["buffer"] + content
            state["buffer"] = ""

        current_pos = 0
        total_len = len(content)

        while current_pos < total_len:
            # If we are inside a thinking block
            if state["in_thinking"]:
                tag = state["current_tag"]
                close_tag = f"</{tag}>"

                # Look for closing tag
                close_pos = content.find(close_tag, current_pos)

                if close_pos != -1:
                    # Found closing tag
                    if close_pos > current_pos:
                        yield f"<<<THINKING>>>{content[current_pos:close_pos]}"

                    # Reset state
                    state["in_thinking"] = False
                    state["current_tag"] = None
                    current_pos = close_pos + len(close_tag)
                else:
                    # Closing tag not found, might be split
                    remaining = content[current_pos:]

                    if len(remaining) < 15:
                        partial_match = False
                        for t in tags:
                            ct = f"</{t}>"
                            for i in range(1, len(ct)):
                                if remaining.endswith(ct[:i]):
                                    valid_content = remaining[:-i]
                                    if valid_content:
                                        yield f"<<<THINKING>>>{valid_content}"
                                    state["buffer"] = remaining[-i:]
                                    partial_match = True
                                    current_pos = total_len
                                    break
                            if partial_match:
                                break
                        if partial_match:
                            continue

                    # No closing tag, yield all as thinking
                    yield f"<<<THINKING>>>{remaining}"
                    current_pos = total_len
            else:
                # We are NOT in a thinking block - look for opening tag
                found_tag = None
                start_pos = -1
                earliest_pos = -1

                for tag in tags:
                    open_tag = f"<{tag}>"
                    pos = content.find(open_tag, current_pos)
                    if pos != -1:
                        if earliest_pos == -1 or pos < earliest_pos:
                            earliest_pos = pos
                            found_tag = tag
                            start_pos = pos

                if found_tag:
                    # Found an opening tag
                    if start_pos > current_pos:
                        yield content[current_pos:start_pos]

                    # Set state
                    state["in_thinking"] = True
                    state["current_tag"] = found_tag
                    current_pos = start_pos + len(f"<{found_tag}>")
                else:
                    # Opening tag not found - check for partial opening tag at end
                    remaining = content[current_pos:]

                    if len(remaining) < 15:
                        partial_match = False
                        for t in tags:
                            ot = f"<{t}>"
                            for i in range(1, len(ot)):
                                if remaining.endswith(ot[:i]):
                                    valid_content = remaining[:-i]
                                    if valid_content:
                                        yield valid_content
                                    state["buffer"] = remaining[-i:]
                                    partial_match = True
                                    current_pos = total_len
                                    break
                            if partial_match:
                                break
                        if partial_match:
                            continue

                    # No tag, yield all as normal content
                    yield remaining
                    current_pos = total_len

    @property
    def available_models(self) -> List[str]:
        """
        Get a list of available models

        Returns:
            List of model names (providers should override this)
        """
        return [self.default_model]

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
