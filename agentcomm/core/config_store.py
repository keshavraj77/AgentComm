"""
Configuration management for the A2A Client
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigStore:
    """
    Manages configuration settings for the A2A Client
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the configuration store

        Args:
            config_dir: Optional path to the configuration directory
        """
        if config_dir is None:
            self.config_dir = Path(__file__).parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.agents_file = self.config_dir / "agents.json"
        self.llm_config_file = self.config_dir / "llm_config.json"
        self.threads_file = self.config_dir / "threads.json"
        self.mcp_servers_file = self.config_dir / "mcp_servers.json"

        # Initialize config files from examples if they don't exist
        self._initialize_config_files()

        # Load configurations
        self.agents_config = self._load_config(self.agents_file)
        self.llm_config = self._load_config(self.llm_config_file)
        self.threads_config = self._load_config(self.threads_file)
        self.mcp_servers_config = self._load_config(self.mcp_servers_file)

        logger.info(f"Configuration loaded from {self.config_dir}")

    def _initialize_config_files(self) -> None:
        """
        Initialize config files from examples if they don't exist
        """
        import shutil

        # Map of config files to their example templates
        config_files = {
            'agents.json': 'agents.example.json',
            'llm_config.json': 'llm_config.example.json'
        }

        for config_name, example_name in config_files.items():
            config_path = self.config_dir / config_name
            example_path = self.config_dir / example_name

            if not config_path.exists() and example_path.exists():
                logger.info(f"Creating {config_name} from example template")
                shutil.copy(example_path, config_path)
                logger.warning(f"Please configure {config_name} with your API keys and settings")

    def _load_config(self, config_file: Path) -> Dict[str, Any]:
        """
        Load configuration from a JSON file
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            Dict containing the configuration
        """
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Configuration file not found: {config_file}")
                return {}
        except Exception as e:
            logger.error(f"Error loading configuration from {config_file}: {e}")
            return {}
    
    def save_config(self, config_type: str) -> bool:
        """
        Save configuration to a JSON file

        Args:
            config_type: Type of configuration to save ('agents', 'llm', 'threads', or 'mcp_servers')

        Returns:
            True if successful, False otherwise
        """
        try:
            if config_type == 'agents':
                with open(self.agents_file, 'w') as f:
                    json.dump(self.agents_config, f, indent=2)
            elif config_type == 'llm':
                with open(self.llm_config_file, 'w') as f:
                    json.dump(self.llm_config, f, indent=2)
            elif config_type == 'threads':
                with open(self.threads_file, 'w') as f:
                    json.dump(self.threads_config, f, indent=2)
            elif config_type == 'mcp_servers':
                with open(self.mcp_servers_file, 'w') as f:
                    json.dump(self.mcp_servers_config, f, indent=2)
            else:
                logger.error(f"Unknown configuration type: {config_type}")
                return False

            logger.info(f"Configuration saved: {config_type}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration {config_type}: {e}")
            return False
    
    def get_agent_config(self, agent_id: Optional[str] = None) -> Any:
        """
        Get agent configuration
        
        Args:
            agent_id: Optional agent ID to get specific agent configuration
            
        Returns:
            List or Dict containing agent configuration
        """
        if agent_id is None:
            return self.agents_config
        
        for agent in self.agents_config:
            if isinstance(agent, dict) and agent.get('id') == agent_id:
                return agent
        
        return {}
    
    def get_llm_config(self, provider_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get LLM configuration
        
        Args:
            provider_name: Optional provider name to get specific provider configuration
            
        Returns:
            Dict containing LLM configuration
        """
        if provider_name is None:
            return self.llm_config
        
        providers = self.llm_config.get('providers', {})
        return providers.get(provider_name, {})
    
    def set_api_key(self, provider_name: str, api_key: str) -> bool:
        """
        Set API key for a provider

        Args:
            provider_name: Name of the provider
            api_key: API key to set

        Returns:
            True if successful, False otherwise
        """
        try:
            providers = self.llm_config.get('providers', {})
            if provider_name in providers:
                providers[provider_name]['api_key'] = api_key
                return self.save_config('llm')
            else:
                logger.error(f"Provider not found: {provider_name}")
                return False
        except Exception as e:
            logger.error(f"Error setting API key for {provider_name}: {e}")
            return False

    def get_threads(self) -> Dict[str, Any]:
        """
        Get thread configuration

        Returns:
            Dict containing thread configuration
        """
        return self.threads_config

    def save_threads(self, threads_data: Dict[str, Any]) -> bool:
        """
        Save thread configuration

        Args:
            threads_data: Thread data to save

        Returns:
            True if successful, False otherwise
        """
        try:
            self.threads_config = threads_data
            return self.save_config('threads')
        except Exception as e:
            logger.error(f"Error saving threads: {e}")
            return False

    def get_mcp_servers(self) -> Dict[str, Any]:
        """
        Get MCP servers configuration

        Returns:
            Dict containing MCP servers configuration
        """
        return self.mcp_servers_config

    def save_mcp_servers(self, mcp_servers_data: Dict[str, Any]) -> bool:
        """
        Save MCP servers configuration

        Args:
            mcp_servers_data: MCP servers data to save

        Returns:
            True if successful, False otherwise
        """
        try:
            self.mcp_servers_config = mcp_servers_data
            return self.save_config('mcp_servers')
        except Exception as e:
            logger.error(f"Error saving MCP servers: {e}")
            return False


