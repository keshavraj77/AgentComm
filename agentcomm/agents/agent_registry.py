"""
Agent Registry for managing available agents
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union

from agentcomm.core.config_store import ConfigStore

logger = logging.getLogger(__name__)

class AgentCapabilities:
    """Agent capabilities model"""
    
    def __init__(
        self,
        streaming: bool = False,
        push_notifications: bool = False,
        file_upload: bool = False,
        tool_use: bool = False
    ):
        self.streaming = streaming
        self.push_notifications = push_notifications
        self.file_upload = file_upload
        self.tool_use = tool_use
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentCapabilities':
        """Create from dictionary"""
        return cls(
            streaming=data.get('streaming', False),
            push_notifications=data.get('push_notifications', False),
            file_upload=data.get('file_upload', False),
            tool_use=data.get('tool_use', False)
        )
    
    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary"""
        return {
            'streaming': self.streaming,
            'push_notifications': self.push_notifications,
            'file_upload': self.file_upload,
            'tool_use': self.tool_use
        }


class AgentAuthentication:
    """Agent authentication model"""
    
    def __init__(
        self,
        auth_type: str,
        api_key_name: Optional[str] = None,
        token: Optional[str] = None
    ):
        self.auth_type = auth_type  # "api_key", "bearer", "basic", "none"
        self.api_key_name = api_key_name
        self.token = token
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentAuthentication':
        """Create from dictionary"""
        return cls(
            auth_type=data.get('auth_type', 'none'),
            api_key_name=data.get('api_key_name'),
            token=data.get('token')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'auth_type': self.auth_type,
            'api_key_name': self.api_key_name,
            'token': self.token
        }
    
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        headers = {}
        
        if self.auth_type == 'api_key' and self.api_key_name and self.token:
            headers[self.api_key_name] = self.token
        elif self.auth_type == 'bearer' and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        elif self.auth_type == 'basic' and self.token:
            headers['Authorization'] = f'Basic {self.token}'
        
        return headers


class Agent:
    """Agent model"""

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        url: str,
        capabilities: AgentCapabilities,
        authentication: AgentAuthentication,
        default_input_modes: List[str],
        default_output_modes: List[str],
        transport: str = "jsonrpc",
        skills: Optional[List[Dict[str, Any]]] = None,
        is_default: bool = False,
        is_built_in: bool = True
    ):
        self.id = id
        self.name = name
        self.description = description
        self.url = url
        self.transport = transport  # "jsonrpc", "grpc", "http"
        self.capabilities = capabilities
        self.authentication = authentication
        self.default_input_modes = default_input_modes
        self.default_output_modes = default_output_modes
        self.skills = skills or []
        self.is_default = is_default
        self.is_built_in = is_built_in
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Agent':
        """Create from dictionary"""
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            url=data.get('url', ''),
            transport=data.get('transport', 'jsonrpc'),
            capabilities=AgentCapabilities.from_dict(data.get('capabilities', {})),
            authentication=AgentAuthentication.from_dict(data.get('authentication', {})),
            default_input_modes=data.get('default_input_modes', ['text/plain']),
            default_output_modes=data.get('default_output_modes', ['text/plain']),
            skills=data.get('skills', []),
            is_default=data.get('is_default', False),
            is_built_in=data.get('is_built_in', True)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'url': self.url,
            'transport': self.transport,
            'capabilities': self.capabilities.to_dict(),
            'authentication': self.authentication.to_dict(),
            'default_input_modes': self.default_input_modes,
            'default_output_modes': self.default_output_modes,
            'skills': self.skills,
            'is_default': self.is_default,
            'is_built_in': self.is_built_in
        }


class AgentRegistry:
    """
    Manages the collection of available agents
    """
    
    def __init__(self, config_store: Optional[ConfigStore] = None):
        """
        Initialize the agent registry
        
        Args:
            config_store: Optional ConfigStore instance
        """
        self.config_store = config_store or ConfigStore()
        self.agents: Dict[str, Agent] = {}
        self.load_agents()
    
    def load_agents(self):
        """Load agents from configuration file"""
        try:
            agents_config = self.config_store.get_agent_config()
            
            if not agents_config:
                logger.warning("No agents found in configuration")
                return
            
            for agent_data in agents_config:
                try:
                    agent = Agent.from_dict(agent_data)
                    self.agents[agent.id] = agent
                    logger.debug(f"Loaded agent: {agent.name} ({agent.id})")
                except Exception as e:
                    logger.error(f"Error loading agent: {e}")
            
            logger.info(f"Loaded {len(self.agents)} agents")
        except Exception as e:
            logger.error(f"Error loading agents: {e}")
    
    def add_agent(self, agent: Union[Agent, Dict[str, Any]]) -> bool:
        """
        Add or update an agent in the registry
        
        Args:
            agent: Agent instance or dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if isinstance(agent, dict):
                agent = Agent.from_dict(agent)
            
            self.agents[agent.id] = agent
            logger.info(f"Added agent: {agent.name} ({agent.id})")
            
            # Update configuration
            agents_config = self.config_store.get_agent_config()
            
            # Find and update existing agent or add new one
            found = False
            for i, agent_data in enumerate(agents_config):
                if agent_data.get('id') == agent.id:
                    agents_config[i] = agent.to_dict()
                    found = True
                    break
            
            if not found:
                agents_config.append(agent.to_dict())
            
            # Save configuration
            # We don't directly modify agents_config in ConfigStore
            # Instead, we'll save the updated config
            return self.config_store.save_config('agents')
        
        except Exception as e:
            logger.error(f"Error adding agent: {e}")
            return False
    
    def remove_agent(self, agent_id: str) -> bool:
        """
        Remove an agent from the registry
        
        Args:
            agent_id: ID of the agent to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if agent_id in self.agents:
                agent = self.agents.pop(agent_id)
                logger.info(f"Removed agent: {agent.name} ({agent.id})")
                
                # Update configuration
                agents_config = self.config_store.get_agent_config()
                agents_config = [a for a in agents_config if a.get('id') != agent_id]
                # We don't directly modify agents_config in ConfigStore
                # Instead, we'll save the updated config
                return self.config_store.save_config('agents')
            else:
                logger.warning(f"Agent not found: {agent_id}")
                return False
        
        except Exception as e:
            logger.error(f"Error removing agent: {e}")
            return False
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """
        Get an agent by ID
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            Agent instance or None if not found
        """
        return self.agents.get(agent_id)
    
    def get_default_agent(self) -> Optional[Agent]:
        """
        Get the default agent
        
        Returns:
            Default agent or None if not found
        """
        for agent in self.agents.values():
            if agent.is_default:
                return agent
        
        # If no default agent is found, return the first one
        if self.agents:
            return next(iter(self.agents.values()))
        
        return None
    
    def get_all_agents(self) -> List[Agent]:
        """
        Get all agents
        
        Returns:
            List of all agents
        """
        return list(self.agents.values())
    
    def set_default_agent(self, agent_id: str) -> bool:
        """
        Set the default agent
        
        Args:
            agent_id: ID of the agent to set as default
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if agent_id not in self.agents:
                logger.warning(f"Agent not found: {agent_id}")
                return False
            
            # Update all agents
            for aid, agent in self.agents.items():
                agent.is_default = (aid == agent_id)
            
            # Update configuration
            agents_config = self.config_store.get_agent_config()
            for agent_data in agents_config:
                agent_data['is_default'] = (agent_data.get('id') == agent_id)
            
            # We don't directly modify agents_config in ConfigStore
            # Instead, we'll save the updated config
            return self.config_store.save_config('agents')
        
        except Exception as e:
            logger.error(f"Error setting default agent: {e}")
            return False


