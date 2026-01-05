"""
Application settings for the A2A Client
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Settings:
    """
    Application settings for the A2A Client
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the settings
        
        Args:
            config_dir: Optional path to the configuration directory
        """
        if config_dir is None:
            self.config_dir = Path(__file__).parent
        else:
            self.config_dir = Path(config_dir)
        
        self.settings_file = self.config_dir / "settings.json"
        self.settings = self._load_settings()
        
        logger.info(f"Settings initialized from {self.settings_file}")
    
    def _load_settings(self) -> Dict[str, Any]:
        """
        Load settings from the settings file
        
        Returns:
            Dict containing the settings
        """
        default_settings = {
            "webhook_port": 8000,
            "webhook_host": "localhost",
            "default_agent": "interview_prep",
            "default_llm_provider": "OpenAI",
            "ngrok": {
                "enabled": False,
                "auth_token": "",
                "region": "us"  # Supported regions: us, eu, ap, au, sa, jp, in
            },
            "ui": {
                "theme": "light",
                "font_size": 12,
                "window_width": 800,
                "window_height": 600,
                "show_toolbar": True,
                "show_statusbar": True
            },
            "logging": {
                "level": "INFO",
                "file": "agentcomm.log",
                "max_size": 1048576,  # 1 MB
                "backup_count": 3
            }
        }
        
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                
                # Merge with default settings to ensure all keys exist
                merged_settings = default_settings.copy()
                self._deep_update(merged_settings, settings)
                
                return merged_settings
            else:
                # Create default settings file
                with open(self.settings_file, 'w') as f:
                    json.dump(default_settings, f, indent=2)
                
                logger.info(f"Created default settings file: {self.settings_file}")
                return default_settings
        
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return default_settings
    
    def _deep_update(self, d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep update a dictionary
        
        Args:
            d: Dictionary to update
            u: Dictionary with updates
            
        Returns:
            Updated dictionary
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v
        return d
    
    def save_settings(self) -> bool:
        """
        Save settings to the settings file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            
            logger.info(f"Settings saved to {self.settings_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value
        
        Args:
            key: Setting key (can use dot notation for nested settings)
            default: Default value if the key doesn't exist
            
        Returns:
            Setting value or default
        """
        try:
            if '.' in key:
                parts = key.split('.')
                value = self.settings
                for part in parts:
                    value = value.get(part, {})
                
                if value == {}:
                    return default
                
                return value
            
            return self.settings.get(key, default)
        
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """
        Set a setting value
        
        Args:
            key: Setting key (can use dot notation for nested settings)
            value: Setting value
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if '.' in key:
                parts = key.split('.')
                setting = self.settings
                for part in parts[:-1]:
                    if part not in setting:
                        setting[part] = {}
                    setting = setting[part]
                
                setting[parts[-1]] = value
            else:
                self.settings[key] = value
            
            return self.save_settings()
        
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            return False
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all settings
        
        Returns:
            Dict containing all settings
        """
        return self.settings.copy()


