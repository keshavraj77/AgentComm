"""
LLM Router for routing requests to the appropriate LLM provider
"""

import logging
from typing import Dict, Any, Optional, AsyncGenerator, List, Union

from agentcomm.llm.llm_provider import LLMProvider
from agentcomm.llm.providers.openai import OpenAIProvider
from agentcomm.llm.providers.gemini import GeminiProvider
from agentcomm.llm.providers.anthropic import AnthropicProvider
from agentcomm.llm.providers.local import LocalLLMProvider

logger = logging.getLogger(__name__)

class LLMRouter:
    """
    Routes requests to the appropriate LLM provider
    """
    
    def __init__(self, config_store=None):
        """
        Initialize the LLM router

        Args:
            config_store: Optional config store for reloading configuration
        """
        self.providers: Dict[str, LLMProvider] = {}
        self.default_provider: Optional[str] = None
        self.last_responses: Dict[str, str] = {}  # Store last responses by provider
        self.config_store = config_store
    
    def register_provider(self, name: str, provider: LLMProvider, is_default: bool = False):
        """
        Register an LLM provider
        
        Args:
            name: Name of the provider
            provider: LLM provider instance
            is_default: Whether this provider should be the default
        """
        self.providers[name] = provider
        logger.info(f"Registered LLM provider: {name}")
        
        if is_default or self.default_provider is None:
            self.default_provider = name
            logger.info(f"Set default LLM provider: {name}")
    
    def get_provider(self, name: Optional[str] = None) -> Optional[LLMProvider]:
        """
        Get an LLM provider by name
        
        Args:
            name: Name of the provider (if None, returns the default provider)
            
        Returns:
            LLM provider instance or None if not found
        """
        if name is None:
            if self.default_provider is None:
                return None
            return self.providers.get(self.default_provider)
        
        return self.providers.get(name)
    
    def get_all_providers(self) -> Dict[str, LLMProvider]:
        """
        Get all registered LLM providers
        
        Returns:
            Dict of provider names to provider instances
        """
        return self.providers
        
    def has_provider(self, name: str) -> bool:
        """
        Check if a provider exists
        
        Args:
            name: Name of the provider
            
        Returns:
            True if the provider exists, False otherwise
        """
        return name in self.providers
    
    def set_default_provider(self, name: str) -> bool:
        """
        Set the default LLM provider
        
        Args:
            name: Name of the provider
            
        Returns:
            True if successful, False if the provider doesn't exist
        """
        if name in self.providers:
            self.default_provider = name
            logger.info(f"Set default LLM provider: {name}")
            return True
        
        logger.warning(f"Provider not found: {name}")
        return False
    
    async def generate(
        self,
        provider_name: str,
        prompt: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> str:
        """
        Generate text using the specified provider, returning the complete response
        
        Args:
            provider_name: Name of the provider to use
            prompt: The prompt to send to the LLM
            chat_history: Optional chat history for context
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Complete generated text
        """
        provider = self.get_provider(provider_name)
        
        if provider is None:
            logger.error(f"No provider available for: {provider_name}")
            return f"Error: No provider available for: {provider_name}"
        
        # Add chat history to kwargs if provided
        if chat_history:
            kwargs["chat_history"] = chat_history
        
        response = await provider.generate_complete(prompt, **kwargs)
        self.last_responses[provider_name] = response
        return response
    
    async def generate_stream(
        self,
        provider_name: str,
        prompt: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate text using the specified provider

        Args:
            prompt: The prompt to send to the LLM
            provider_name: Name of the provider to use (if None, uses the default provider)
            **kwargs: Additional provider-specific parameters

        Yields:
            Generated text chunks
        """
        provider = self.get_provider(provider_name)

        if provider is None:
            logger.error(f"No provider available for: {provider_name}")
            yield f"Error: No provider available for: {provider_name}"
            return

        logger.info(f"LLMRouter.generate_stream - Provider: {provider_name}")
        logger.debug(f"Chat history length: {len(chat_history) if chat_history else 0}")
        logger.debug(f"Additional kwargs: {list(kwargs.keys())}")

        # Add chat history to kwargs if provided
        if chat_history:
            kwargs["chat_history"] = chat_history

        # Initialize an empty response
        full_response = ""

        async for chunk in provider.generate(prompt, **kwargs):
            full_response += chunk
            yield chunk

        # Store the complete response
        self.last_responses[provider_name] = full_response
        logger.info(f"LLMRouter.generate_stream complete - Total response length: {len(full_response)}")
    
    async def get_last_response(self, provider_name: str) -> str:
        """
        Get the last response from a provider
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Last response from the provider or empty string if no response
        """
        return self.last_responses.get(provider_name, "")
    
    async def generate_complete(
        self,
        prompt: str,
        provider_name: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> str:
        """
        Generate text using the specified provider, returning the complete response
        
        Args:
            prompt: The prompt to send to the LLM
            provider_name: Name of the provider to use (if None, uses the default provider)
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Complete generated text
        """
        provider = self.get_provider(provider_name)
        
        if provider is None:
            logger.error(f"No provider available for: {provider_name or 'default'}")
            return f"Error: No provider available for: {provider_name or 'default'}"
        
        # Add chat history to kwargs if provided
        if chat_history:
            kwargs["chat_history"] = chat_history
        
        response = await provider.generate_complete(prompt, **kwargs)
        if provider_name:
            self.last_responses[provider_name] = response
        return response
    
    def get_available_models(self, provider_name: Optional[str] = None) -> List[str]:
        """
        Get a list of available models for the specified provider
        
        Args:
            provider_name: Name of the provider (if None, uses the default provider)
            
        Returns:
            List of model names
        """
        provider = self.get_provider(provider_name)
        
        if provider is None:
            logger.error(f"No provider available for: {provider_name or 'default'}")
            return []
        
        return provider.available_models
    
    def reload_config(self):
        """
        Reload configuration from the config store
        """
        if self.config_store is None:
            logger.warning("No config store available for reloading configuration")
            return False

        try:
            # Get the updated LLM configuration
            llm_config = self.config_store.get_llm_config()
            if not llm_config:
                logger.warning("No LLM configuration found")
                return False

            # Clear existing providers
            self.providers.clear()

            # Recreate providers from the updated config
            default_provider = llm_config.get("default_provider")
            providers_config = llm_config.get("providers", {})

            for name, provider_config in providers_config.items():
                try:
                    if name == "OpenAI":
                        provider = OpenAIProvider(
                            api_key=provider_config.get("api_key"),
                            default_model=provider_config.get("default_model", "gpt-3.5-turbo"),
                            temperature=provider_config.get("temperature", 0.7),
                            max_tokens=provider_config.get("max_tokens", 1000)
                        )
                        self.register_provider(name, provider, is_default=(name == default_provider))

                    elif name == "Google Gemini":
                        provider = GeminiProvider(
                            api_key=provider_config.get("api_key"),
                            default_model=provider_config.get("default_model", "gemini-1.5-pro"),
                            temperature=provider_config.get("temperature", 0.7),
                            max_tokens=provider_config.get("max_tokens", 1000)
                        )
                        self.register_provider(name, provider, is_default=(name == default_provider))

                    elif name == "Anthropic Claude":
                        provider = AnthropicProvider(
                            api_key=provider_config.get("api_key"),
                            default_model=provider_config.get("default_model", "claude-3-sonnet-20240229"),
                            temperature=provider_config.get("temperature", 0.7),
                            max_tokens=provider_config.get("max_tokens", 1000)
                        )
                        self.register_provider(name, provider, is_default=(name == default_provider))

                    elif name == "Local LLM":
                        provider = LocalLLMProvider(
                            host=provider_config.get("host", "http://localhost:11434"),
                            default_model=provider_config.get("default_model", "llama3"),
                            temperature=provider_config.get("temperature", 0.7),
                            max_tokens=provider_config.get("max_tokens", 1000)
                        )
                        self.register_provider(name, provider, is_default=(name == default_provider))

                    else:
                        logger.warning(f"Unknown provider type: {name}")

                except Exception as e:
                    logger.error(f"Error reinitializing provider {name}: {e}")

            logger.info("LLM configuration reloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Error reloading LLM configuration: {e}")
            return False

    async def close(self):
        """
        Close all providers
        """
        for name, provider in self.providers.items():
            try:
                await provider.close()
                logger.info(f"Closed LLM provider: {name}")
            except Exception as e:
                logger.error(f"Error closing LLM provider {name}: {e}")
    
    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> 'LLMRouter':
        """
        Create an LLM router from a configuration dictionary
        
        Args:
            config: Configuration dictionary
            
        Returns:
            LLM router instance
        """
        router = cls()
        
        default_provider = config.get("default_provider")
        providers_config = config.get("providers", {})
        
        for name, provider_config in providers_config.items():
            try:
                if name == "OpenAI":
                    provider = OpenAIProvider(
                        api_key=provider_config.get("api_key"),
                        default_model=provider_config.get("default_model", "gpt-3.5-turbo"),
                        temperature=provider_config.get("temperature", 0.7),
                        max_tokens=provider_config.get("max_tokens", 1000)
                    )
                    router.register_provider(name, provider, is_default=(name == default_provider))
                
                elif name == "Google Gemini":
                    provider = GeminiProvider(
                        api_key=provider_config.get("api_key"),
                        default_model=provider_config.get("default_model", "gemini-1.5-pro"),
                        temperature=provider_config.get("temperature", 0.7),
                        max_tokens=provider_config.get("max_tokens", 1000)
                    )
                    router.register_provider(name, provider, is_default=(name == default_provider))
                
                elif name == "Anthropic Claude":
                    provider = AnthropicProvider(
                        api_key=provider_config.get("api_key"),
                        default_model=provider_config.get("default_model", "claude-3-sonnet-20240229"),
                        temperature=provider_config.get("temperature", 0.7),
                        max_tokens=provider_config.get("max_tokens", 1000)
                    )
                    router.register_provider(name, provider, is_default=(name == default_provider))
                
                elif name == "Local LLM":
                    provider = LocalLLMProvider(
                        host=provider_config.get("host", "http://localhost:11434"),
                        default_model=provider_config.get("default_model", "llama3"),
                        temperature=provider_config.get("temperature", 0.7),
                        max_tokens=provider_config.get("max_tokens", 1000)
                    )
                    router.register_provider(name, provider, is_default=(name == default_provider))
                
                else:
                    logger.warning(f"Unknown provider type: {name}")
            
            except Exception as e:
                logger.error(f"Error initializing provider {name}: {e}")
        
        return router


