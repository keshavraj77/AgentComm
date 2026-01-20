import asyncio
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Optional, Dict, Any, List

from agentcomm.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class StdioMCPClient:
    def __init__(
        self,
        server_id: str,
        command: str,
        args: list[str],
        env: Optional[Dict[str, str]] = None
    ):
        self.server_id = server_id
        self.command = command
        self.args = args
        self.env = env or {}
        self.client: Optional[MCPClient] = None
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
        self._connection_task: Optional[asyncio.Task] = None
        self._tools: List[Dict[str, Any]] = []
        self._is_connected = False
        self._connection_ready = asyncio.Event()
        self._shutdown_event = asyncio.Event()

    async def connect(self) -> MCPClient:
        """Start the connection in a background task and wait for it to be ready."""
        if self._is_connected and self.client:
            return self.client
        
        # Start connection in background task
        self._connection_task = asyncio.create_task(self._run_connection())
        
        # Wait for the connection to be ready with timeout
        try:
            await asyncio.wait_for(self._connection_ready.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for MCP server {self.server_id} to connect")
            raise RuntimeError(f"Timeout connecting to MCP server {self.server_id}")
        
        if not self.client:
            raise RuntimeError(f"Failed to connect to MCP server {self.server_id}")
        
        return self.client

    async def _run_connection(self):
        """Run the MCP connection within proper context management."""
        read_stream = None
        write_stream = None
        session = None
        
        try:
            # Open stdio connection
            async with stdio_client(self.server_params) as (read, write):
                read_stream, write_stream = read, write
                
                # Create and initialize session
                async with ClientSession(read, write) as sess:
                    session = sess
                    await session.initialize()
                    
                    # Create the client wrapper
                    self.client = MCPClient(self.server_id, session)
                    self.client.is_connected = True
                    
                    # Discover capabilities
                    await self.client._discover_capabilities()
                    
                    self._is_connected = True
                    self._connection_ready.set()
                    
                    logger.info(f"MCP server {self.server_id} connected with {len(self.client.tools)} tools")
                    
                    # Keep the connection alive until shutdown is requested
                    await self._shutdown_event.wait()
                    
        except asyncio.CancelledError:
            logger.info(f"MCP connection for {self.server_id} cancelled")
            self._connection_ready.set()
        except Exception as e:
            logger.error(f"Error in MCP connection for {self.server_id}: {e}", exc_info=True)
            self._connection_ready.set()  # Unblock waiters even on error
        finally:
            # Clean up resources
            self._is_connected = False
            if self.client:
                self.client.is_connected = False
            self.client = None
            
            # Ensure streams are properly closed
            if session:
                try:
                    await session.__aexit__(None, None, None)
                except Exception as e:
                    logger.debug(f"Error closing session for {self.server_id}: {e}")

    async def disconnect(self):
        """Signal the connection to shut down."""
        self._shutdown_event.set()
        
        if self._connection_task:
            try:
                await asyncio.wait_for(self._connection_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for MCP server {self.server_id} to disconnect, cancelling")
                self._connection_task.cancel()
                try:
                    await self._connection_task
                except asyncio.CancelledError:
                    pass
            finally:
                self._connection_task = None
        
        self._is_connected = False
        self.client = None
