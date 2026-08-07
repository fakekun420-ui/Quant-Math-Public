"""
WebSocket Manager for Real-time Updates
"""
import asyncio
import json
import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasting."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._heartbeat_task = None
        
    async def start(self):
        """Start the WebSocket manager."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        logger.info("WebSocket manager started")
        
    async def stop(self):
        """Stop the WebSocket manager."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        # Close all connections
        for conn in self.active_connections:
            try:
                await conn.close()
            except Exception:
                pass
        self.active_connections.clear()
        logger.info("WebSocket manager stopped")
        
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
        
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
            
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return
            
        message_text = json.dumps(message)
        disconnected = []
        
        for conn in self.active_connections:
            try:
                await conn.send_text(message_text)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(conn)
                
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
            
    async def _heartbeat(self):
        """Send periodic heartbeat to keep connections alive."""
        while True:
            await asyncio.sleep(30)
            if self.active_connections:
                await self.broadcast({"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()})
                
    async def send_system_event(self, event_type: str, data: dict):
        """Send a system event to all clients."""
        await self.broadcast({
            "type": "system_event",
            "event_type": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        })


ws_manager = WebSocketManager()