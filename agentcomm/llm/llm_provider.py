"""
LLM Provider Interface
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncGenerator, List, Callable, Awaitable

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """
    Abstract base class for LLM providers
    """
    
    @abstractmethod
    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate text from LLM, streaming response

        Args:
            prompt: The prompt to send to LLM
            tools: Optional list of tools/functions available to the LLM
            **kwargs: Additional provider-specific parameters

        Yields:
            Generated text chunks or tool calls
        """
        yield ""
    
    @abstractmethod
    async def generate_complete(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> str:
        """
        Generate text from the LLM, returning the complete response

        Args:
            prompt: The prompt to send to the LLM
            tools: Optional list of tools/functions available to the LLM
            **kwargs: Additional provider-specific parameters

        Returns:
            Complete generated text
        """
        pass
    
    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """
        Get a list of available models for this provider
        
        Returns:
            List of model names
        """
        pass
    
    @abstractmethod
    async def close(self):
        """
        Close any resources used by the provider
        """
        pass


