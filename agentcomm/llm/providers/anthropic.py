"""
Anthropic Claude Provider Implementation
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List

from agentcomm.llm.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude API provider implementation
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the Anthropic provider
        
        Args:
            api_key: Anthropic API key (if None, will try to get from environment)
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.default_model = kwargs.get("default_model", "claude-3-sonnet-20240229")
        self.default_params = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
            "top_p": kwargs.get("top_p", 1.0)
        }
        
        # We'll initialize the client when needed to avoid import errors
        self._anthropic_module = None
        self.client = None
        if self.api_key:
            try:
                import anthropic
                self._anthropic_module = anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.error("Failed to import anthropic package. Please install it with: pip install anthropic>=0.5.0")
            except Exception as e:
                logger.error(f"Error initializing Anthropic client: {e}")
    
    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate text from Claude, streaming the response
        
        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional parameters to pass to the API
            
        Yields:
            Generated text chunks
        """
        if not self._anthropic_module or not self.client:
            logger.error("Anthropic client not initialized. Please provide a valid API key.")
            yield "Error: Anthropic client not initialized. Please provide a valid API key."
            return
        
        try:
            # Prepare parameters
            model = kwargs.get("model", self.default_model)
            params = self.default_params.copy()
            params.update({k: v for k, v in kwargs.items() if k in self.default_params})
            
            # Create the system prompt if provided
            system = kwargs.get("system", "")
            
            # Create messages
            messages = [{"role": "user", "content": prompt}]
            
            # Add chat history if provided
            history = kwargs.get("history", [])
            if history and isinstance(history, list):
                # Convert history to Claude format
                claude_messages = []
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        claude_messages.append({"role": "user", "content": content})
                    elif role == "assistant":
                        claude_messages.append({"role": "assistant", "content": content})
                    elif role == "system":
                        system = content
                
                # Add the current message
                messages = claude_messages + messages
            
            # Run in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Create the completion
            def create_completion():
                return self.client.messages.create(
                    model=model,
                    messages=messages,
                    system=system,
                    stream=True,
                    tools=tools,
                    **params
                )
            
            # Execute in a thread
            response = await loop.run_in_executor(None, create_completion)
            
            # Process the streaming response
            current_block_type = "text"
            
            for chunk in response:
                # Handle extended thinking blocks (Claude 3.7+)
                if hasattr(chunk, 'type'):
                    if chunk.type == 'content_block_start':
                        if hasattr(chunk, 'content_block') and hasattr(chunk.content_block, 'type'):
                            current_block_type = chunk.content_block.type
                            if current_block_type == 'thinking' and hasattr(chunk.content_block, 'thinking'):
                                # Initial thinking content
                                yield f"<<<THINKING>>>{chunk.content_block.thinking}"
                    elif chunk.type == 'content_block_delta':
                        if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'type'):
                            if chunk.delta.type == 'thinking_delta' and hasattr(chunk.delta, 'thinking'):
                                yield f"<<<THINKING>>>{chunk.delta.thinking}"
                            elif chunk.delta.type == 'text_delta' and hasattr(chunk.delta, 'text'):
                                yield chunk.delta.text
                            # Fallback for generic delta if types match context
                            elif hasattr(chunk.delta, 'text') and current_block_type == 'text':
                                yield chunk.delta.text
                            elif hasattr(chunk.delta, 'thinking') and current_block_type == 'thinking':
                                yield f"<<<THINKING>>>{chunk.delta.thinking}"
                
                # Legacy/Standard block handling
                elif hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                    yield chunk.delta.text
        
        except Exception as e:
            logger.error(f"Error generating text from Claude: {e}")
            yield f"Error: {e}"
    
    async def generate_complete(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> str:
        """
        Generate text from Claude, returning the complete response
        
        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            Complete generated text
        """
        if not self._anthropic_module or not self.client:
            logger.error("Anthropic client not initialized. Please provide a valid API key.")
            return "Error: Anthropic client not initialized. Please provide a valid API key."
        
        try:
            # Prepare parameters
            model = kwargs.get("model", self.default_model)
            params = self.default_params.copy()
            params.update({k: v for k, v in kwargs.items() if k in self.default_params})
            
            # Create the system prompt if provided
            system = kwargs.get("system", "")
            
            # Create messages
            messages = [{"role": "user", "content": prompt}]
            
            # Add chat history if provided
            history = kwargs.get("history", [])
            if history and isinstance(history, list):
                # Convert history to Claude format
                claude_messages = []
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        claude_messages.append({"role": "user", "content": content})
                    elif role == "assistant":
                        claude_messages.append({"role": "assistant", "content": content})
                    elif role == "system":
                        system = content
                
                # Add the current message
                messages = claude_messages + messages
            
            # Run in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Create the completion
            def create_completion():
                return self.client.messages.create(
                    model=model,
                    messages=messages,
                    system=system,
                    stream=False,
                    tools=tools,
                    **params
                )
            
            # Execute in a thread
            response = await loop.run_in_executor(None, create_completion)
            
            # Extract the content from the response
            if hasattr(response, 'content') and response.content:
                if isinstance(response.content, list):
                    # Handle content blocks
                    text_content = []
                    for block in response.content:
                        if hasattr(block, 'text'):
                            text_content.append(block.text)
                        elif isinstance(block, dict) and 'text' in block:
                            text_content.append(block['text'])
                    return ''.join(text_content)
                elif isinstance(response.content, str):
                    return response.content
            
            return "Error: Could not extract content from response"
        
        except Exception as e:
            logger.error(f"Error generating text from Claude: {e}")
            return f"Error: {e}"
    
    @property
    def available_models(self) -> List[str]:
        """
        Get a list of available models for this provider
        
        Returns:
            List of model names
        """
        return [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0",
            "claude-instant-1.2"
        ]
    
    async def close(self):
        """
        Close the client
        """
        # Anthropic's client doesn't have a close method
        pass

