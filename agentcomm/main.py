#!/usr/bin/env python3
"""
A2A Client with Base LLM Integration
Main entry point for the application
"""

import os
import sys
import logging
from pathlib import Path
import asyncio

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("agentcomm")

# Ensure data directory exists
data_dir = Path(__file__).parent / "data"
data_dir.mkdir(exist_ok=True)

try:
    from PyQt6.QtWidgets import QApplication
    from agentcomm.ui.main_window import MainWindow
    from agentcomm.core.config_store import ConfigStore
    from agentcomm.core.session_manager import SessionManager
    from agentcomm.agents.agent_registry import AgentRegistry
    from agentcomm.llm.llm_router import LLMRouter
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Please ensure all dependencies are installed by running: pip install -r requirements.txt")
    sys.exit(1)


def main():
    """Main entry point for the application"""
    try:
        # Initialize configuration
        config_store = ConfigStore()
        
        # Initialize agent registry
        agent_registry = AgentRegistry(config_store)
        
        # Initialize LLM router
        llm_router = LLMRouter()
        
        # Load LLM configuration
        llm_config = config_store.get_llm_config()
        if llm_config:
            llm_router = LLMRouter.create_from_config(llm_config)

        # Get system prompt from config
        system_prompt = llm_config.get("system_prompt") if llm_config else None

        # Initialize session manager
        session_manager = SessionManager(agent_registry, llm_router, system_prompt=system_prompt)
        
        # Start the UI
        app = QApplication(sys.argv)
        app.setApplicationName("A2A Client")
        
        # Create and show the main window
        main_window = MainWindow(session_manager, agent_registry, llm_router)
        main_window.show()
        
        # Start the application event loop
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


