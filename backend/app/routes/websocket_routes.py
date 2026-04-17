"""
WebSocket Routes

Real-time communication endpoints for live updates and notifications.
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
from datetime import datetime

from app.websocket import manager
from app.auth import get_current_user_ws
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    session_key: Optional[str] = Query(None),
):
    """
    WebSocket connection endpoint.
    
    Authentication:
    - Authenticated users: ?token=<jwt_token>
    - Anonymous users: ?session_key=<unique_session_id>
    
    Message Types (Client -> Server):
    - ping: Heartbeat to keep connection alive
    - join_room: Join a collaborative room
    - leave_room: Leave a room
    
    Message Types (Server -> Client):
    - connected: Welcome message
    - pong: Response to ping
    - claim_verified: Claim verification complete
    - review_queue_update: Review queue has new items
    - model_accuracy_change: Model accuracy changed
    - ab_test_results: A/B test results available
    - system_alert: System-wide alert
    - user_activity: Activity in a room
    - room_joined: Successfully joined room
    - room_left: Successfully left room
    """
    
    # Authenticate user if token provided
    user_id = None
    if token:
        try:
            user = await get_current_user_ws(token)
            user_id = user.id
        except Exception as e:
            logger.warning(f"WebSocket auth failed: {e}")
            await websocket.close(code=1008, reason="Authentication failed")
            return
    
    # Require either user_id or session_key
    if not user_id and not session_key:
        await websocket.close(code=1008, reason="Missing authentication or session_key")
        return
    
    # Connect
    await manager.connect(websocket, user_id=user_id, session_key=session_key)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "ping":
                await manager.handle_ping(websocket)
            
            elif message_type == "join_room":
                room = data.get("room")
                if room:
                    await manager.join_room(websocket, room)
                    logger.info(f"User {user_id} joined room: {room}")
            
            elif message_type == "leave_room":
                room = data.get("room")
                if room:
                    await manager.leave_room(websocket, room)
                    logger.info(f"User {user_id} left room: {room}")
            
            else:
                # Unknown message type
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message_type}",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    websocket
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected: user_id={user_id}, session={session_key}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.get("/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Returns:
    - active_users: Number of authenticated users connected
    - total_connections: Total number of active connections
    - rooms: List of active rooms with connection counts
    """
    
    rooms_info = {}
    for room, connections in manager.rooms.items():
        rooms_info[room] = len(connections)
    
    return {
        "active_users": manager.get_active_users_count(),
        "total_connections": manager.get_total_connections_count(),
        "rooms": rooms_info,
        "timestamp": datetime.utcnow().isoformat()
    }
