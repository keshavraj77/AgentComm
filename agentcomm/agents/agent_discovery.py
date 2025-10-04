"""
Agent Discovery for fetching agent capabilities from endpoints
"""

import json
import logging
from typing import Dict, Any, Optional, List

import httpx

from agentcomm.agents.agent_registry import Agent, AgentCapabilities, AgentAuthentication

logger = logging.getLogger(__name__)

class AgentDiscovery:
    """
    Discovers agent capabilities from endpoints
    """
    
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """
        Initialize the agent discovery service
        
        Args:
            http_client: Optional httpx AsyncClient instance
        """
        self.http_client = http_client or httpx.AsyncClient()
    
    async def discover_agent(
        self,
        url: str,
        auth_headers: Optional[Dict[str, str]] = None
    ) -> Optional[Agent]:
        """
        Discover an agent by fetching its agent card
        
        Args:
            url: URL of the agent
            auth_headers: Optional authentication headers
            
        Returns:
            Agent instance or None if discovery fails
        """
        try:
            # Normalize URL
            if not url.endswith('/'):
                url = url + '/'
            
            # Prepare headers
            headers = {
                "Accept": "application/json"
            }
            
            if auth_headers:
                headers.update(auth_headers)
            
            # Fetch agent card
            logger.debug(f"Discovering agent at {url}")
            response = await self.http_client.get(url, headers=headers)
            response.raise_for_status()
            
            # Parse agent card
            agent_card = response.json()
            logger.debug(f"Received agent card: {agent_card}")
            
            # Extract agent information
            agent_id = agent_card.get('name', '').lower().replace(' ', '_')
            name = agent_card.get('name', '')
            description = agent_card.get('description', '')
            agent_url = agent_card.get('url', url)
            
            # Extract capabilities
            capabilities_data = agent_card.get('capabilities', {})
            capabilities = AgentCapabilities(
                streaming=capabilities_data.get('streaming', False),
                push_notifications=capabilities_data.get('pushNotifications', False),
                file_upload=False,  # Not directly in A2A spec, infer from skills if needed
                tool_use=False      # Not directly in A2A spec, infer from skills if needed
            )
            
            # Extract authentication
            auth_type = "none"
            api_key_name = None
            token = None
            
            security_schemes = agent_card.get('securitySchemes', {})
            if security_schemes:
                # Look for API key security scheme
                for scheme_name, scheme in security_schemes.items():
                    if scheme.get('type') == 'apiKey':
                        auth_type = 'api_key'
                        api_key_name = scheme.get('name')
                        break
                    elif scheme.get('type') == 'http' and scheme.get('scheme') == 'bearer':
                        auth_type = 'bearer'
                        break
                    elif scheme.get('type') == 'http' and scheme.get('scheme') == 'basic':
                        auth_type = 'basic'
                        break
            
            authentication = AgentAuthentication(
                auth_type=auth_type,
                api_key_name=api_key_name,
                token=token
            )
            
            # Extract input/output modes
            default_input_modes = agent_card.get('defaultInputModes', ['text/plain'])
            default_output_modes = agent_card.get('defaultOutputModes', ['text/plain'])
            
            # Extract skills
            skills = []
            for skill_data in agent_card.get('skills', []):
                skill = {
                    'id': skill_data.get('id', ''),
                    'name': skill_data.get('name', ''),
                    'description': skill_data.get('description', ''),
                    'tags': skill_data.get('tags', [])
                }
                
                # Add input/output modes if they override defaults
                if 'inputModes' in skill_data:
                    skill['inputModes'] = skill_data['inputModes']
                if 'outputModes' in skill_data:
                    skill['outputModes'] = skill_data['outputModes']
                
                skills.append(skill)
            
            # Create agent
            agent = Agent(
                id=agent_id,
                name=name,
                description=description,
                url=agent_url,
                capabilities=capabilities,
                authentication=authentication,
                default_input_modes=default_input_modes,
                default_output_modes=default_output_modes,
                skills=skills,
                is_default=False,
                is_built_in=False
            )
            
            logger.info(f"Discovered agent: {agent.name} ({agent.id})")
            return agent
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error discovering agent at {url}: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Error discovering agent at {url}: {e}")
            return None
    
    async def discover_agents(
        self,
        urls: List[str],
        auth_headers: Optional[Dict[str, str]] = None
    ) -> List[Agent]:
        """
        Discover multiple agents
        
        Args:
            urls: List of agent URLs
            auth_headers: Optional authentication headers
            
        Returns:
            List of discovered agents
        """
        agents = []
        
        for url in urls:
            agent = await self.discover_agent(url, auth_headers)
            if agent:
                agents.append(agent)
        
        return agents
    
    async def close(self):
        """Close the HTTP client"""
        await self.http_client.aclose()


