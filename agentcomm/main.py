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
import qasync

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
    from agentcomm.agents.webhook_handler import WebhookHandler
    from agentcomm.agents.ngrok_manager import NgrokManager
    from agentcomm.llm.llm_router import LLMRouter
    from agentcomm.config.settings import Settings
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Please ensure all dependencies are installed by running: pip install -r requirements.txt")
    sys.exit(1)


async def main_coro(app):
    """Main coroutine for the application"""
    try:
        # Initialize configuration
        config_store = ConfigStore()
        settings = Settings()

        # Initialize agent registry
        agent_registry = AgentRegistry(config_store)

        # Initialize LLM router with config_store
        llm_router = LLMRouter(config_store=config_store)

        # Load LLM configuration
        llm_config = config_store.get_llm_config()
        if llm_config:
            llm_router = LLMRouter.create_from_config(llm_config)
            llm_router.config_store = config_store  # Set config_store for reloading

        # Get system prompt from config
        system_prompt = llm_config.get("system_prompt") if llm_config else None

        # Initialize webhook handler
        webhook_port = settings.get("webhook_port", 8000)
        webhook_handler = WebhookHandler(port=webhook_port, host="localhost")
        logger.info(f"Webhook handler initialized on port {webhook_port}")

        # Initialize ngrok manager if enabled
        ngrok_manager = None
        if settings.get("ngrok.enabled", False):
            ngrok_auth_token = settings.get("ngrok.auth_token", "")
            ngrok_region = settings.get("ngrok.region", "us")

            if ngrok_auth_token:
                ngrok_manager = NgrokManager(auth_token=ngrok_auth_token, region=ngrok_region)
                logger.info("ngrok manager initialized")
            else:
                logger.warning("ngrok is enabled but auth token is not configured")

        # Initialize session manager
        session_manager = SessionManager(
            agent_registry,
            llm_router,
            system_prompt=system_prompt,
            webhook_handler=webhook_handler,
            ngrok_manager=ngrok_manager
        )
        
        # Start async components
        await session_manager.start()

        # Load saved threads
        threads_data = config_store.get_threads()
        if threads_data:
            session_manager.load_threads(threads_data)
            logger.info("Loaded saved threads from config")

        # Register auto-save callback
        def auto_save():
            threads_data = session_manager.save_threads()
            config_store.save_threads(threads_data)
            logger.debug("Threads auto-saved")

        session_manager.register_auto_save_callback(auto_save)

        # setApplicationName
        app.setApplicationName("A2A Client")

        # Create and show the main window
        main_window = MainWindow(session_manager, agent_registry, llm_router)
        main_window.show()

        # Register cleanup function to save threads on exit
        def save_on_exit():
            logger.info("Saving threads before exit...")
            threads_data = session_manager.save_threads()
            config_store.save_threads(threads_data)
            logger.info("Threads saved successfully")

        app.aboutToQuit.connect(save_on_exit)
        
        # Wait for the application to exit (keep coroutine alive)
        future = asyncio.Future()
        app.aboutToQuit.connect(lambda: future.set_result(None))
        await future

    except Exception as e:
        logger.error(f"Error in main coroutine: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    try:
        app = QApplication(sys.argv)
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        with loop:
            loop.run_until_complete(main_coro(app))
            
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


