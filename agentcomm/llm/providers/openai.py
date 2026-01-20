"""
OpenAI Provider Implementation
"""

import os
import logging
from typing import Optional, AsyncGenerator, List, Dict, Any

from agentcomm.llm.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider implementation (for openai>=1.0.0)
    """

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the OpenAI provider

        Args:
            api_key: OpenAI API key (if None, will try to get from environment)
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.default_model = kwargs.get("default_model", "gpt-3.5-turbo")
        self.default_params = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
            "top_p": kwargs.get("top_p", 1.0),
            "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
            "presence_penalty": kwargs.get("presence_penalty", 0.0)
        }

        # Initialize the client
        self.client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI module imported successfully")
            except ImportError:
                logger.error("Failed to import openai package. Please install it with: pip install openai>=1.0.0")

    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate text from OpenAI, streaming response

        Args:
            prompt: The prompt to send to model
            tools: Optional list of tools/functions available to LLM
            **kwargs: Additional parameters to pass to API

        Yields:
            Generated text chunks
        """
        if not self.client:
            logger.error("OpenAI client not initialized. Please install the openai package.")
            yield "Error: OpenAI client not initialized. Please install the openai package."
            return

        if not self.api_key:
            logger.error("OpenAI API key not provided. Please provide a valid API key.")
            yield "Error: OpenAI API key not provided. Please provide a valid API key."
            return

        try:
            # Prepare parameters
            model = kwargs.get("model", self.default_model)
            params = self.default_params.copy()
            params.update({k: v for k, v in kwargs.items() if k in self.default_params})

            logger.info(f"OpenAI generate (streaming) - Model: {model}, Params: {params}")
            logger.debug(f"Prompt: {prompt[:100]}...")
            if tools:
                logger.debug(f"Tools provided: {len(tools)} tools")

            # Create messages
            messages = []

            # Add system message if provided
            system_message = kwargs.get("system")
            if system_message:
                messages.append({"role": "system", "content": system_message})
                logger.debug(f"System message added: {system_message[:50]}...")

            # Add chat history if provided
            history = kwargs.get("history") or kwargs.get("chat_history")
            if history and isinstance(history, list):
                logger.debug(f"Chat history provided with {len(history)} messages")
                messages.extend(history)

            # Add current user message
            messages.append({"role": "user", "content": prompt})

            # Prepare API call parameters
            api_params = {
                "model": model,
                "messages": messages,
                "stream": True,
                **params
            }

            # Add tools if provided
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = "auto"

            # Create streaming completion
            stream = self.client.chat.completions.create(**api_params)

            # Process streaming response
            full_response = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content

            logger.info(f"OpenAI streaming complete. Total response length: {len(full_response)}")
            logger.debug(f"Full response: {full_response[:200]}...")

        except Exception as e:
            logger.error(f"Error generating text from OpenAI (streaming): {e}", exc_info=True)
            yield f"Error: {e}"

    async def generate_complete(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs):
        """
        Generate text from OpenAI, returning complete response

        Args:
            prompt: The prompt to send to model
            tools: Optional list of tools/functions available to LLM
            **kwargs: Additional parameters including:
                - return_tool_calls: If True, returns Dict[str, Any] with 'content' and 'tool_calls'
                                     If False, returns str with just content

        Returns:
            Complete generated text (str) or structured response (dict) depending on return_tool_calls
        """
        if not self.client:
            logger.error("OpenAI client not initialized. Please install the openai package.")
            return "Error: OpenAI client not initialized. Please install the openai package."

        if not self.api_key:
            logger.error("OpenAI API key not provided. Please provide a valid API key.")
            return "Error: OpenAI API key not provided. Please provide a valid API key."

        try:
            return_tool_calls = kwargs.get("return_tool_calls", False)
            
            # Prepare parameters
            model = kwargs.get("model", self.default_model)
            params = self.default_params.copy()
            params.update({k: v for k, v in kwargs.items() if k in self.default_params})

            logger.info(f"OpenAI generate_complete - Model: {model}, Params: {params}")
            logger.debug(f"Prompt: {prompt[:100]}...")
            if tools:
                logger.debug(f"Tools provided: {len(tools)} tools")

            # Create messages
            messages = []

            # Add system message if provided
            system_message = kwargs.get("system")
            if system_message:
                messages.append({"role": "system", "content": system_message})
                logger.debug(f"System message added: {system_message[:50]}...")

            # Add chat history if provided
            history = kwargs.get("history") or kwargs.get("chat_history")
            if history and isinstance(history, list):
                logger.debug(f"Chat history provided with {len(history)} messages")
                for msg in history:
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

            # Add current user message (only if not empty - for tool calling loop)
            if prompt:
                messages.append({"role": "user", "content": prompt})

            # Prepare API call parameters
            api_params = {
                "model": model,
                "messages": messages,
                "stream": False,
                **params
            }

            # Add tools if provided
            if tools and len(tools) > 0:
                api_params["tools"] = tools
                api_params["tool_choice"] = "auto"

            # Create completion
            response = self.client.chat.completions.create(**api_params)

            # Extract content and tool calls
            message = response.choices[0].message
            content = message.content or ""
            tool_calls = message.tool_calls or []
            
            # Convert tool_calls to dict format if present
            tool_calls_list = []
            if tool_calls:
                for tc in tool_calls:
                    tool_calls_list.append({
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })
            
            # Return structured response if tool calls requested
            if return_tool_calls:
                return {
                    "content": content,
                    "tool_calls": tool_calls_list
                }
            
            # Otherwise return just content
            if content:
                logger.info(f"OpenAI response complete. Response length: {len(content)}")
                logger.debug(f"Response: {content[:200]}...")
                return content
            
            # If only tool calls, indicate that
            if tool_calls_list:
                return "[Tool calls requested - use return_tool_calls=True to access them]"
            
            if return_tool_calls:
                return {"content": "Error: Could not extract content from response", "tool_calls": []}
            return "Error: Could not extract content from response"

        except Exception as e:
            logger.error(f"Error generating text from OpenAI (complete): {e}", exc_info=True)
            error_msg = f"Error: {e}"
            if kwargs.get("return_tool_calls", False):
                return {"content": error_msg, "tool_calls": []}
            return error_msg

    @property
    def available_models(self) -> List[str]:
        """
        Get a list of available models for this provider

        Returns:
            List of model names
        """
        return [
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ]

    async def close(self):
        """
        Close the client
        """
        if self.client:
            self.client.close()


