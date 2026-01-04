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
    
    async def generate(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
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
                async for chunk in self._generate_openai(prompt, **kwargs):
                    yield chunk
            else:
                async for chunk in self._generate_ollama(prompt, **kwargs):
                    yield chunk
        
        except Exception as e:
            logger.error(f"Error generating text from local LLM: {e}")
            yield f"Error: {e}"
    
    async def _generate_openai(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
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
        
        # Add the current message
        messages.append({"role": "user", "content": prompt})
        
        # Prepare request payload
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": kwargs.get("temperature", self.default_params["temperature"]),
            "max_tokens": kwargs.get("max_tokens", self.default_params["max_tokens"]),
            "top_p": kwargs.get("top_p", self.default_params["top_p"])
        }
        
        endpoint = f"{self.host}/chat/completions"
        
        # Send the request and stream the response
        async with self.client.stream("POST", endpoint, json=payload) as response:
            response.raise_for_status()
            
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
                    
                    # Extract the generated text from OpenAI format
                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse response line: {line}")
    
    async def _generate_ollama(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
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
            
            # Add the current message
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
            
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Extract the generated text
                    if "response" in data:
                        yield data["response"]
                    elif "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                    elif "error" in data:
                        yield f"Error: {data['error']}"
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse response line: {line}")
    
    async def generate_complete(self, prompt: str, **kwargs) -> str:
        """
        Generate text from local LLM, returning the complete response
        
        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            Complete generated text
        """
        try:
            if self.api_type == "openai":
                return await self._generate_complete_openai(prompt, **kwargs)
            else:
                return await self._generate_complete_ollama(prompt, **kwargs)
        
        except Exception as e:
            logger.error(f"Error generating text from local LLM: {e}")
            return f"Error: {e}"
    
    async def _generate_complete_openai(self, prompt: str, **kwargs) -> str:
        """
        Generate complete text using OpenAI-compatible API
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
        
        # Add the current message
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
        
        endpoint = f"{self.host}/chat/completions"
        
        # Send the request
        response = await self.client.post(endpoint, json=payload)
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        
        # Extract the generated text from OpenAI format
        if "choices" in data and len(data["choices"]) > 0:
            message = data["choices"][0].get("message", {})
            content = message.get("content", "")
            if content:
                return content
        
        if "error" in data:
            return f"Error: {data['error']}"
        
        return "Error: Could not extract content from response"
    
    async def _generate_complete_ollama(self, prompt: str, **kwargs) -> str:
        """
        Generate complete text using Ollama API
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
            "stream": False,
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
            
            # Add the current message
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
        
        # Extract the generated text
        if "response" in data:
            return data["response"]
        elif "message" in data and "content" in data["message"]:
            return data["message"]["content"]
        elif "error" in data:
            return f"Error: {data['error']}"
        
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


