"""
Webhook handler for A2A push notifications
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, List

import uvicorn
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

class WebhookHandler:
    """Handles incoming webhook notifications from agents"""
    
    def __init__(self, port: int = 8000, host: str = "localhost"):
        """
        Initialize the webhook handler
        
        Args:
            port: Port to listen on
            host: Host to bind to
        """
        self.port = port
        self.host = host
        self.app = FastAPI(title="A2A Client Webhook Handler")
        self.callbacks: Dict[str, List[Callable]] = {}
        self.tokens: Dict[str, str] = {}
        
        # Register routes
        self.app.post("/webhook")(self.handle_webhook)
        self.app.post("/webhook/{task_id}")(self.handle_task_webhook)
        
        logger.info(f"Webhook handler initialized on {host}:{port}")
    
    async def handle_webhook(self, request: Request, authorization: Optional[str] = Header(None)):
        """
        Handle incoming webhook notifications
        
        Args:
            request: FastAPI request object
            authorization: Optional authorization header
            
        Returns:
            JSONResponse with acknowledgment
        """
        try:
            # Parse the request body
            body = await request.json()
            logger.debug(f"Received webhook notification: {body}")
            
            # Validate the request
            if "jsonrpc" not in body or body.get("jsonrpc") != "2.0":
                raise HTTPException(status_code=400, detail="Invalid JSON-RPC request")
            
            if "method" not in body or body.get("method") != "pushNotifications/send":
                raise HTTPException(status_code=400, detail="Invalid method")
            
            if "params" not in body or "task" not in body.get("params", {}):
                raise HTTPException(status_code=400, detail="Invalid params")
            
            # Extract task information
            task = body["params"]["task"]
            task_id = task.get("id")
            
            if not task_id:
                raise HTTPException(status_code=400, detail="Missing task ID")
            
            # Validate token if available
            if task_id in self.tokens:
                expected_token = self.tokens[task_id]
                if authorization:
                    # Extract token from Authorization header
                    auth_parts = authorization.split()
                    if len(auth_parts) == 2 and auth_parts[0].lower() == "bearer":
                        token = auth_parts[1]
                        if token != expected_token:
                            raise HTTPException(status_code=401, detail="Invalid token")
                    else:
                        raise HTTPException(status_code=401, detail="Invalid authorization header format")
                else:
                    raise HTTPException(status_code=401, detail="Missing authorization header")
            
            # Process the notification
            await self._process_notification(task_id, task)
            
            # Return acknowledgment
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": {"acknowledged": True},
                "id": body.get("id")
            })
        
        except HTTPException:
            raise
        
        except Exception as e:
            logger.error(f"Error handling webhook notification: {e}")
            # Get request ID if available
            request_id = None
            try:
                body_data = await request.json()
                request_id = body_data.get("id")
            except:
                pass
                
            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {e}"
                    },
                    "id": request_id
                }
            )
    
    async def handle_task_webhook(
        self,
        task_id: str,
        request: Request,
        authorization: Optional[str] = Header(None)
    ):
        """
        Handle incoming webhook notifications for a specific task
        
        Args:
            task_id: ID of the task
            request: FastAPI request object
            authorization: Optional authorization header
            
        Returns:
            JSONResponse with acknowledgment
        """
        try:
            # Parse the request body
            body = await request.json()
            logger.debug(f"Received webhook notification for task {task_id}: {body}")
            
            # Validate the request
            if "jsonrpc" not in body or body.get("jsonrpc") != "2.0":
                raise HTTPException(status_code=400, detail="Invalid JSON-RPC request")
            
            if "method" not in body or body.get("method") != "pushNotifications/send":
                raise HTTPException(status_code=400, detail="Invalid method")
            
            if "params" not in body or "task" not in body.get("params", {}):
                raise HTTPException(status_code=400, detail="Invalid params")
            
            # Extract task information
            task = body["params"]["task"]
            
            # Validate token if available
            if task_id in self.tokens:
                expected_token = self.tokens[task_id]
                if authorization:
                    # Extract token from Authorization header
                    auth_parts = authorization.split()
                    if len(auth_parts) == 2 and auth_parts[0].lower() == "bearer":
                        token = auth_parts[1]
                        if token != expected_token:
                            raise HTTPException(status_code=401, detail="Invalid token")
                    else:
                        raise HTTPException(status_code=401, detail="Invalid authorization header format")
                else:
                    raise HTTPException(status_code=401, detail="Missing authorization header")
            
            # Process the notification
            await self._process_notification(task_id, task)
            
            # Return acknowledgment
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": {"acknowledged": True},
                "id": body.get("id")
            })
        
        except HTTPException:
            raise
        
        except Exception as e:
            logger.error(f"Error handling webhook notification: {e}")
            # Get request ID if available
            request_id = None
            try:
                body_data = await request.json()
                request_id = body_data.get("id")
            except:
                pass
                
            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {e}"
                    },
                    "id": request_id
                }
            )
    
    async def _process_notification(self, task_id: str, task: Dict[str, Any]):
        """
        Process a notification for a task
        
        Args:
            task_id: ID of the task
            task: Task data
        """
        if task_id in self.callbacks:
            for callback in self.callbacks[task_id]:
                try:
                    await callback(task)
                except Exception as e:
                    logger.error(f"Error in callback for task {task_id}: {e}")
    
    def register_callback(self, task_id: str, callback: Callable, token: Optional[str] = None):
        """
        Register a callback for a task
        
        Args:
            task_id: ID of the task
            callback: Callback function to call when a notification is received
            token: Optional token for authentication
        """
        if task_id not in self.callbacks:
            self.callbacks[task_id] = []
        
        self.callbacks[task_id].append(callback)
        
        if token:
            self.tokens[task_id] = token
        
        logger.debug(f"Registered callback for task {task_id}")
    
    def unregister_callback(self, task_id: str, callback: Optional[Callable] = None):
        """
        Unregister a callback for a task
        
        Args:
            task_id: ID of the task
            callback: Optional callback function to unregister (if None, all callbacks are unregistered)
        """
        if task_id in self.callbacks:
            if callback is None:
                self.callbacks.pop(task_id)
                if task_id in self.tokens:
                    self.tokens.pop(task_id)
                logger.debug(f"Unregistered all callbacks for task {task_id}")
            else:
                if callback in self.callbacks[task_id]:
                    self.callbacks[task_id].remove(callback)
                    logger.debug(f"Unregistered callback for task {task_id}")
                
                if not self.callbacks[task_id]:
                    self.callbacks.pop(task_id)
                    if task_id in self.tokens:
                        self.tokens.pop(task_id)
    
    async def start(self):
        """Start the webhook server"""
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def start_background(self):
        """Start the webhook server in the background"""
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.start())
        return task


