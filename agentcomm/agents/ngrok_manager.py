"""
ngrok Manager for creating secure tunnels for webhook endpoints
"""

import logging
import asyncio
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class NgrokManager:
    """Manages ngrok tunnel lifecycle for webhook endpoints"""

    def __init__(self, auth_token: str, region: str = "us"):
        """
        Initialize the ngrok manager

        Args:
            auth_token: ngrok authentication token
            region: ngrok region (us, eu, ap, au, sa, jp, in)
        """
        self.auth_token = auth_token
        self.region = region
        self.tunnel = None
        self.public_url = None
        self._pyngrok_available = False

        # Check if pyngrok is available
        try:
            from pyngrok import ngrok, conf
            self._pyngrok_available = True
            logger.info("pyngrok is available")
        except ImportError:
            logger.warning("pyngrok is not installed. Push notifications will not work. Install with: pip install pyngrok")

    async def start_tunnel(self, port: int) -> Optional[str]:
        """
        Start ngrok tunnel for the specified port

        Args:
            port: Local port to expose

        Returns:
            Public URL or None if failed
        """
        if not self._pyngrok_available:
            logger.error("Cannot start ngrok tunnel: pyngrok is not installed")
            return None

        if not self.auth_token:
            logger.error("Cannot start ngrok tunnel: auth token is not configured")
            return None

        try:
            from pyngrok import ngrok, conf

            # Set ngrok auth token
            logger.info(f"Configuring ngrok with region={self.region}")
            ngrok.set_auth_token(self.auth_token)

            # Configure ngrok
            conf.get_default().region = self.region

            # Start tunnel
            logger.info(f"Starting ngrok tunnel for port {port}...")
            self.tunnel = ngrok.connect(port, "http")
            self.public_url = self.tunnel.public_url

            # Ensure HTTPS
            if self.public_url.startswith("http://"):
                self.public_url = self.public_url.replace("http://", "https://")

            logger.info(f"ngrok tunnel established: {self.public_url}")
            return self.public_url

        except Exception as e:
            logger.error(f"Error starting ngrok tunnel: {e}")
            self.tunnel = None
            self.public_url = None
            return None

    def get_public_url(self) -> Optional[str]:
        """
        Get the public URL of the tunnel

        Returns:
            Public URL or None if tunnel is not active
        """
        return self.public_url

    def is_active(self) -> bool:
        """
        Check if the tunnel is active

        Returns:
            True if tunnel is active, False otherwise
        """
        return self.tunnel is not None and self.public_url is not None

    async def stop_tunnel(self):
        """Stop the ngrok tunnel"""
        if not self._pyngrok_available:
            return

        if self.tunnel is not None:
            try:
                from pyngrok import ngrok

                logger.info(f"Stopping ngrok tunnel: {self.public_url}")
                ngrok.disconnect(self.tunnel.public_url)
                self.tunnel = None
                self.public_url = None
                logger.info("ngrok tunnel stopped")
            except Exception as e:
                logger.error(f"Error stopping ngrok tunnel: {e}")

    async def restart_tunnel(self, port: int) -> Optional[str]:
        """
        Restart the ngrok tunnel

        Args:
            port: Local port to expose

        Returns:
            Public URL or None if failed
        """
        logger.info("Restarting ngrok tunnel...")
        await self.stop_tunnel()
        await asyncio.sleep(1)  # Wait a bit before restarting
        return await self.start_tunnel(port)

    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.tunnel is not None:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.stop_tunnel())
                else:
                    loop.run_until_complete(self.stop_tunnel())
            except Exception as e:
                logger.error(f"Error in NgrokManager cleanup: {e}")
