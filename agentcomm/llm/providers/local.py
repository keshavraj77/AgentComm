"""
Local LLM Provider Implementation
"""

import os
import json
import logging
import asyncio
import httpx
from typing import Dict, Any, Optional, AsyncGenerator, List

from agentcomm.llm.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

class LocalLLMProvider(LLMProvider):
    """
    Local LLM provider implementation for Ollama and OpenAI-compatible local LLM servers
    """
    
    def __init__(
        self,
        host: str = "http://localhost:11434",
        default_model: str = "llama3",
        **kwargs
    ):
        """
        Initialize the local LLM provider
        
        Args:
            host: Host URL for the local LLM server
            default_model: Default model to use
            **kwargs: Additional configuration parameters
        """
        self.host = host
        self.default_model = default_model
        self.default_params = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
            "top_p": kwargs.get("top_p", 1.0),
            "top_k": kwargs.get("top_k", 40),
            "repeat_penalty": kwargs.get("repeat_penalty", 1.1)
        }
        
        # Detect API type based on host URL
        # If host contains '/v1', assume OpenAI-compatible API
        self.api_type = "openai" if "/v1" in host else "ollama"
        
        # Create HTTP client
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"Local LLM provider initialized with host: {host}, API type: {self.api_type}")
    
    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate text from local LLM, streaming the response
        
        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional parameters to pass to the API
            
        Yields:
            Generated text chunks
        """
        try:
            if self.api_type == "openai":
                async for chunk in self._generate_openai(prompt, tools=tools, **kwargs):
                    yield chunk
            else:
                async for chunk in self._generate_ollama(prompt, tools=tools, **kwargs):
                    yield chunk
        
        except Exception as e:
            logger.error(f"Error generating text from local LLM: {e}")
            yield f"Error: {e}"
    
    async def _generate_openai(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate text using OpenAI-compatible API
        """
        model = kwargs.get("model", self.default_model)
        
        # Build messages array
        messages = []
        
        # Add system message if provided
        system = kwargs.get("system", "")
        if system:
            messages.append({"role": "system", "content": system})
        
        # Add chat history if provided
        chat_history = kwargs.get("chat_history")
        if chat_history and isinstance(chat_history, list):
            for msg in chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})

        # Add the current message (only if not empty - for tool calling loop)
        if prompt:
            messages.append({"role": "user", "content": prompt})

        # Prepare request payload
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools or [],
            "stream": True,
            "temperature": kwargs.get("temperature", self.default_params["temperature"]),
            "max_tokens": kwargs.get("max_tokens", self.default_params["max_tokens"]),
            "top_p": kwargs.get("top_p", self.default_params["top_p"])
        }
        
        endpoint = f"{self.host}/chat/completions"
        
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
                        
                        # Check for specific reasoning_content field (DeepSeek R1 via some providers)
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
    
    async def _generate_ollama(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate text using Ollama API
        """
        model = kwargs.get("model", self.default_model)
        params = self.default_params.copy()
        params.update({k: v for k, v in kwargs.items() if k in self.default_params})
        
        # Create the system prompt if provided
        system = kwargs.get("system", "")
        
        # Create the request payload
        payload = {
            "model": model,
            "prompt": prompt,
            "tools": tools or [],
            "stream": True,
            **params
        }
        
        # Add system message if provided
        if system:
            payload["system"] = system
        
        # Add chat history if provided
        chat_history = kwargs.get("chat_history")
        if chat_history and isinstance(chat_history, list):
            # Convert history to messages format
            messages = []
            for msg in chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})

            # Add the current message (only if not empty - for tool calling loop)
            if prompt:
                messages.append({"role": "user", "content": prompt})

            # Update payload to use messages instead of prompt
            payload.pop("prompt", None)
            payload["messages"] = messages
        
        # Determine the API endpoint based on whether we're using chat or completion
        if "messages" in payload:
            endpoint = f"{self.host}/api/chat"
        else:
            endpoint = f"{self.host}/api/generate"
        
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
                
                try:
                    data = json.loads(line)
                    
                    # Check for explicit thinking field (Ollama native)
                    if "thinking" in data and data["thinking"]:
                         yield f"<<<THINKING>>>{data['thinking']}"
                         # Some models might send both thinking field and content field
                         # Continue to process content if present
                    
                    # Extract the generated text
                    content = ""
                    if "response" in data:
                        content = data["response"]
                    elif "message" in data and "content" in data["message"]:
                        content = data["message"]["content"]
                    elif "error" in data:
                        yield f"Error: {data['error']}"
                        continue
                        
                    if content:
                        # Process content for thinking tags
                        async for chunk in self._process_thinking_tags(content, thinking_state):
                            yield chunk
                            
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse response line: {line}")

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
                    # Yield everything up to the closing tag as thinking
                    if close_pos > current_pos:
                        yield f"<<<THINKING>>>{content[current_pos:close_pos]}"
                    
                    # Reset state
                    state["in_thinking"] = False
                    state["current_tag"] = None
                    current_pos = close_pos + len(close_tag)
                else:
                    # Closing tag not found, might be split
                    # Check if the end of content looks like a partial closing tag
                    # e.g. "</", "</th", "</think"
                    # Max length of a closing tag is around 13 chars </reasoning>
                    remaining = content[current_pos:]
                    
                    # If remaining is very short, it could be a partial tag end
                    if len(remaining) < 15:
                        partial_match = False
                        for t in tags:
                            ct = f"</{t}>"
                            for i in range(1, len(ct)):
                                if remaining.endswith(ct[:i]):
                                    # Found partial closing tag at end
                                    # Yield content up to the partial tag start
                                    valid_content = remaining[:-i]
                                    if valid_content:
                                        yield f"<<<THINKING>>>{valid_content}"
                                    
                                    state["buffer"] = remaining[-i:]
                                    partial_match = True
                                    current_pos = total_len # End loop
                                    break
                            if partial_match:
                                break
                        
                        if partial_match:
                            continue
                            
                    # No closing tag, yield all as thinking
                    yield f"<<<THINKING>>>{remaining}"
                    current_pos = total_len
            else:
                # We are NOT in a thinking block
                # Look for opening tag
                found_tag = None
                start_pos = -1
                
                # Check for all tags, find the earliest one
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
                    # Yield everything before it as normal content
                    if start_pos > current_pos:
                        yield content[current_pos:start_pos]
                    
                    # Set state
                    state["in_thinking"] = True
                    state["current_tag"] = found_tag
                    current_pos = start_pos + len(f"<{found_tag}>")
                else:
                    # Opening tag not found
                    # Check for partial opening tag at end
                    remaining = content[current_pos:]
                    
                    if len(remaining) < 15:
                        partial_match = False
                        for t in tags:
                            ot = f"<{t}>"
                            for i in range(1, len(ot)):
                                if remaining.endswith(ot[:i]):
                                    # Found partial opening tag
                                    # Yield content up to partial tag
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
    
    async def generate_complete(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs):
        """
        Generate text from local LLM, returning the complete response

        Args:
            prompt: The prompt to send to the model
            tools: Optional list of tool definitions
            **kwargs: Additional parameters including:
                - return_tool_calls: If True, returns Dict[str, Any] with 'content' and 'tool_calls'
                                     If False, returns str with just content

        Returns:
            Complete generated text (str) or structured response (dict) depending on return_tool_calls
        """
        try:
            return_tool_calls = kwargs.get("return_tool_calls", False)

            if self.api_type == "openai":
                result = await self._generate_complete_openai(prompt, tools=tools, **kwargs)
            else:
                result = await self._generate_complete_ollama(prompt, tools=tools, **kwargs)

            return result

        except Exception as e:
            logger.error(f"Error generating text from local LLM: {e}")
            error_msg = f"Error: {e}"
            if kwargs.get("return_tool_calls", False):
                return {"content": error_msg, "tool_calls": []}
            return error_msg
    
    async def _generate_complete_openai(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> str:
        """
        Generate complete text using OpenAI-compatible API

        Returns str if return_tool_calls=False, otherwise returns Dict with content and tool_calls
        """
        model = kwargs.get("model", self.default_model)
        return_tool_calls = kwargs.get("return_tool_calls", False)

        # Build messages array
        messages = []

        # Add system message if provided
        system = kwargs.get("system", "")
        if system:
            messages.append({"role": "system", "content": system})

        # Add chat history if provided
        chat_history = kwargs.get("chat_history")
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

        # Prepare request payload
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": kwargs.get("temperature", self.default_params["temperature"]),
            "max_tokens": kwargs.get("max_tokens", self.default_params["max_tokens"]),
            "top_p": kwargs.get("top_p", self.default_params["top_p"])
        }

        # Only add tools if provided
        if tools and len(tools) > 0:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        endpoint = f"{self.host}/chat/completions"

        # Send the request
        response = await self.client.post(endpoint, json=payload)
        response.raise_for_status()

        # Parse the response
        data = response.json()

        # Extract the generated text from OpenAI format
        if "choices" in data and len(data["choices"]) > 0:
            message = data["choices"][0].get("message", {})
            content = message.get("content", "") or ""
            tool_calls = message.get("tool_calls", [])

            # If tool calls are present and requested, return structured response
            if return_tool_calls and (tool_calls or content):
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
            if return_tool_calls:
                return {"content": f"Error: {data['error']}", "tool_calls": []}
            return f"Error: {data['error']}"

        if return_tool_calls:
            return {"content": "Error: Could not extract content from response", "tool_calls": []}
        return "Error: Could not extract content from response"
    
    async def _generate_complete_ollama(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> str:
        """
        Generate complete text using Ollama API

        Returns str if return_tool_calls=False, otherwise returns Dict with content and tool_calls
        """
        model = kwargs.get("model", self.default_model)
        return_tool_calls = kwargs.get("return_tool_calls", False)
        params = self.default_params.copy()
        params.update({k: v for k, v in kwargs.items() if k in self.default_params})

        # Create the system prompt if provided
        system = kwargs.get("system", "")

        # Create the request payload
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            **params
        }

        # Only add tools if provided
        if tools and len(tools) > 0:
            payload["tools"] = tools

        # Add system message if provided
        if system:
            payload["system"] = system

        # Add chat history if provided
        chat_history = kwargs.get("chat_history")
        if chat_history and isinstance(chat_history, list):
            # Convert history to messages format
            messages = []
            for msg in chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                # Handle tool result messages
                if role == "tool":
                    messages.append({
                        "role": "tool",
                        "content": content,
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

            # Update payload to use messages instead of prompt
            payload.pop("prompt", None)
            payload["messages"] = messages

        # Determine the API endpoint based on whether we're using chat or completion
        if "messages" in payload:
            endpoint = f"{self.host}/api/chat"
        else:
            endpoint = f"{self.host}/api/generate"

        # Send the request
        response = await self.client.post(endpoint, json=payload)
        response.raise_for_status()

        # Parse the response
        data = response.json()

        # Extract the generated text and tool calls
        content = ""
        tool_calls = []

        if "response" in data:
            content = data["response"]
        elif "message" in data:
            msg = data["message"]
            content = msg.get("content", "") or ""
            # Ollama may return tool_calls in the message
            if "tool_calls" in msg:
                tool_calls = msg["tool_calls"]
        elif "error" in data:
            error_msg = f"Error: {data['error']}"
            if return_tool_calls:
                return {"content": error_msg, "tool_calls": []}
            return error_msg

        # Return structured response if tool calls requested
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

        if return_tool_calls:
            return {"content": "Error: Could not extract content from response", "tool_calls": []}
        return "Error: Could not extract content from response"
    
    @property
    def available_models(self) -> List[str]:
        """
        Get a list of available models for this provider
        
        Returns:
            List of model names
        """
        # These are common Ollama models, but the actual list depends on what's installed
        return [
            "llama3",
            "llama3:8b",
            "llama3:70b",
            "mistral",
            "mixtral",
            "phi3",
            "gemma",
            "codellama"
        ]
    
    async def close(self):
        """
        Close the client
        """
        await self.client.aclose()


