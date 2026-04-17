"""
WebSocket Manager

Real-time communication for live updates, notifications, and collaborative features.
"""

import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts"""
    
    def __init__(self):
        # Active connections by user_id
        self.active_connections: Dict[int, Set[WebSocket]] = defaultdict(set)
        
        # Anonymous connections (by session_key)
        self.anonymous_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        
        # Room-based connections (for collaborative features)
        self.rooms: Dict[str, Set[WebSocket]] = defaultdict(set)
        
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[int] = None,
        session_key: Optional[str] = None
    ):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        
        # Store connection
        if user_id:
            self.active_connections[user_id].add(websocket)
        elif session_key:
            self.anonymous_connections[session_key].add(websocket)
        
        # Store metadata
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "session_key": session_key,
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow(),
        }
        
        logger.info(f"WebSocket connected: user_id={user_id}, session={session_key}")
        
        # Send welcome message
        await self.send_personal_message(
            {
                "type": "connected",
                "message": "Connected to FactCheck AI",
                "timestamp": datetime.utcnow().isoformat()
            },
            websocket
        )
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        metadata = self.connection_metadata.get(websocket, {})
        user_id = metadata.get("user_id")
        session_key = metadata.get("session_key")
        
        # Remove from active connections
        if user_id and websocket in self.active_connections[user_id]:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        if session_key and websocket in self.anonymous_connections[session_key]:
            self.anonymous_connections[session_key].remove(websocket)
            if not self.anonymous_connections[session_key]:
                del self.anonymous_connections[session_key]
        
        # Remove from rooms
        for room_connections in self.rooms.values():
            room_connections.discard(websocket)
        
        # Remove metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        
        logger.info(f"WebSocket disconnected: user_id={user_id}, session={session_key}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.disconnect(websocket)
    
    async def send_to_user(self, message: dict, user_id: int):
        """Send message to all connections of a specific user"""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send to user {user_id}: {e}")
                    disconnected.append(connection)
            
            # Clean up disconnected
            for conn in disconnected:
                self.disconnect(conn)
    
    async def broadcast(self, message: dict, exclude: Optional[WebSocket] = None):
        """Broadcast message to all connected clients"""
        all_connections = set()
        
        # Collect all connections
        for connections in self.active_connections.values():
            all_connections.update(connections)
        for connections in self.anonymous_connections.values():
            all_connections.update(connections)
        
        # Send to all (except excluded)
        disconnected = []
        for connection in all_connections:
            if connection == exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast failed: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_to_room(self, room: str, message: dict):
        """Broadcast message to all connections in a room"""
        if room not in self.rooms:
            return
        
        disconnected = []
        for connection in self.rooms[room]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Room broadcast failed: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn)
    
    async def join_room(self, websocket: WebSocket, room: str):
        """Add connection to a room"""
        self.rooms[room].add(websocket)
        logger.info(f"Connection joined room: {room}")
        
        await self.send_personal_message(
            {
                "type": "room_joined",
                "room": room,
                "timestamp": datetime.utcnow().isoformat()
            },
            websocket
        )
    
    async def leave_room(self, websocket: WebSocket, room: str):
        """Remove connection from a room"""
        if room in self.rooms:
            self.rooms[room].discard(websocket)
            if not self.rooms[room]:
                del self.rooms[room]
        
        await self.send_personal_message(
            {
                "type": "room_left",
                "room": room,
                "timestamp": datetime.utcnow().isoformat()
            },
            websocket
        )
    
    def get_active_users_count(self) -> int:
        """Get count of active authenticated users"""
        return len(self.active_connections)
    
    def get_total_connections_count(self) -> int:
        """Get total number of active connections"""
        total = sum(len(conns) for conns in self.active_connections.values())
        total += sum(len(conns) for conns in self.anonymous_connections.values())
        return total
    
    def get_room_size(self, room: str) -> int:
        """Get number of connections in a room"""
        return len(self.rooms.get(room, set()))
    
    async def handle_ping(self, websocket: WebSocket):
        """Handle ping message and update last_ping time"""
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]["last_ping"] = datetime.utcnow()
        
        await self.send_personal_message(
            {
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            },
            websocket
        )


# Global connection manager instance
manager = ConnectionManager()


# ── Notification Helpers ──────────────────────────────────────

async def notify_claim_verified(user_id: int, claim_data: dict):
    """Notify user that their claim verification is complete"""
    await manager.send_to_user(
        {
            "type": "claim_verified",
            "data": claim_data,
            "timestamp": datetime.utcnow().isoformat()
        },
        user_id
    )


async def notify_review_queue_update(priority: str = "all"):
    """Notify all users about review queue updates"""
    await manager.broadcast(
        {
            "type": "review_queue_update",
            "priority": priority,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


async def notify_model_accuracy_change(accuracy: float, time_window: str):
    """Notify about model accuracy changes"""
    await manager.broadcast(
        {
            "type": "model_accuracy_change",
            "accuracy": accuracy,
            "time_window": time_window,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


async def notify_ab_test_results(test_id: int, test_name: str):
    """Notify about A/B test results availability"""
    await manager.broadcast(
        {
            "type": "ab_test_results",
            "test_id": test_id,
            "test_name": test_name,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


async def notify_system_alert(alert_type: str, message: str, severity: str = "info"):
    """Notify about system alerts"""
    await manager.broadcast(
        {
            "type": "system_alert",
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


async def notify_user_activity(room: str, activity: dict):
    """Notify room about user activity (collaborative features)"""
    await manager.broadcast_to_room(
        room,
        {
            "type": "user_activity",
            "activity": activity,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
