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
    Local LLM provider implementation for Ollama and similar local LLM servers
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
        
        # Create HTTP client
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"Local LLM provider initialized with host: {host}")
    
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
            # Prepare parameters
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
            history = kwargs.get("history")
            if history and isinstance(history, list):
                # Convert history to messages format
                messages = []
                for msg in history:
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
        
        except Exception as e:
            logger.error(f"Error generating text from local LLM: {e}")
            yield f"Error: {e}"
    
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
            # Prepare parameters
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
            history = kwargs.get("history")
            if history and isinstance(history, list):
                # Convert history to messages format
                messages = []
                for msg in history:
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
        
        except Exception as e:
            logger.error(f"Error generating text from local LLM: {e}")
            return f"Error: {e}"
    
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


