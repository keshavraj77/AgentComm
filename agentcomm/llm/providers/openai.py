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

    async def generate_complete(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> str:
        """
        Generate text from OpenAI, returning complete response

        Args:
            prompt: The prompt to send to model
            tools: Optional list of tools/functions available to LLM
            **kwargs: Additional parameters to pass to API

        Returns:
            Complete generated text
        """
        if not self.client:
            logger.error("OpenAI client not initialized. Please install the openai package.")
            return "Error: OpenAI client not initialized. Please install the openai package."

        if not self.api_key:
            logger.error("OpenAI API key not provided. Please provide a valid API key.")
            return "Error: OpenAI API key not provided. Please provide a valid API key."

        try:
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
                messages.extend(history)

            # Add current user message
            messages.append({"role": "user", "content": prompt})

            # Prepare API call parameters
            api_params = {
                "model": model,
                "messages": messages,
                "stream": False,
                **params
            }

            # Add tools if provided
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = "auto"

            # Create completion
            response = self.client.chat.completions.create(**api_params)

            # Extract content
            result = response.choices[0].message.content

            logger.info(f"OpenAI response complete. Response length: {len(result)}")
            logger.debug(f"Response: {result[:200]}...")

            return result

        except Exception as e:
            logger.error(f"Error generating text from OpenAI (complete): {e}", exc_info=True)
            return f"Error: {e}"

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


