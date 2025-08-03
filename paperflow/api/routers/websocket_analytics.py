"""
WebSocket router for real-time analytics updates.

This module provides WebSocket endpoints for streaming real-time analytics
data to dashboards and administrative interfaces.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_user_websocket
from ..schemas.analytics import RealtimeUpdate, WebSocketMessage
from ...services.analytics import DashboardService, AnalyticsService
from ...models.analytics import RealtimeMetrics

logger = logging.getLogger(__name__)

# Connection manager for WebSocket clients
class ConnectionManager:
    """Manages WebSocket connections for real-time analytics."""
    
    def __init__(self):
        # Active connections: {connection_id: {websocket, project_id, user_id}}
        self.active_connections: Dict[str, Dict] = {}
        # Project subscriptions: {project_id: set of connection_ids}
        self.project_subscriptions: Dict[str, Set[str]] = {}
        # User connections: {user_id: set of connection_ids}
        self.user_connections: Dict[str, Set[str]] = {}
        
    async def connect(self, websocket: WebSocket, project_id: str, user_id: str = None) -> str:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        
        connection_id = str(uuid4())
        
        # Store connection info
        self.active_connections[connection_id] = {
            'websocket': websocket,
            'project_id': project_id,
            'user_id': user_id,
            'connected_at': datetime.utcnow(),
            'last_ping': datetime.utcnow()
        }
        
        # Add to project subscription
        if project_id not in self.project_subscriptions:
            self.project_subscriptions[project_id] = set()
        self.project_subscriptions[project_id].add(connection_id)
        
        # Add to user connections
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
        
        logger.info(f"WebSocket connection {connection_id} established for project {project_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection."""
        if connection_id in self.active_connections:
            connection_info = self.active_connections[connection_id]
            project_id = connection_info['project_id']
            user_id = connection_info['user_id']
            
            # Remove from active connections
            del self.active_connections[connection_id]
            
            # Remove from project subscription
            if project_id in self.project_subscriptions:
                self.project_subscriptions[project_id].discard(connection_id)
                if not self.project_subscriptions[project_id]:
                    del self.project_subscriptions[project_id]
            
            # Remove from user connections
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            logger.info(f"WebSocket connection {connection_id} disconnected")
    
    async def send_personal_message(self, connection_id: str, message: dict):
        """Send a message to a specific connection."""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]['websocket']
            try:
                await websocket.send_text(json.dumps(message))
                # Update last activity
                self.active_connections[connection_id]['last_ping'] = datetime.utcnow()
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    async def broadcast_to_project(self, project_id: str, message: dict):
        """Broadcast a message to all connections subscribed to a project."""
        if project_id in self.project_subscriptions:
            disconnected = []
            for connection_id in self.project_subscriptions[project_id].copy():
                try:
                    await self.send_personal_message(connection_id, message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {connection_id}: {e}")
                    disconnected.append(connection_id)
            
            # Clean up disconnected connections
            for connection_id in disconnected:
                self.disconnect(connection_id)
    
    async def broadcast_to_user(self, user_id: str, message: dict):
        """Broadcast a message to all connections for a specific user."""
        if user_id in self.user_connections:
            disconnected = []
            for connection_id in self.user_connections[user_id].copy():
                try:
                    await self.send_personal_message(connection_id, message)
                except Exception as e:
                    logger.error(f"Error broadcasting to user {user_id}: {e}")
                    disconnected.append(connection_id)
            
            # Clean up disconnected connections
            for connection_id in disconnected:
                self.disconnect(connection_id)
    
    def get_project_connection_count(self, project_id: str) -> int:
        """Get the number of active connections for a project."""
        return len(self.project_subscriptions.get(project_id, set()))
    
    def get_total_connections(self) -> int:
        """Get total number of active connections."""
        return len(self.active_connections)
    
    async def cleanup_stale_connections(self):
        """Remove connections that haven't sent a ping recently."""
        stale_threshold = datetime.utcnow() - timedelta(minutes=5)
        stale_connections = []
        
        for connection_id, info in self.active_connections.items():
            if info['last_ping'] < stale_threshold:
                stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            logger.info(f"Removing stale connection {connection_id}")
            self.disconnect(connection_id)
    
    def get_connection_stats(self) -> Dict:
        """Get statistics about active connections."""
        return {
            'total_connections': len(self.active_connections),
            'projects_with_connections': len(self.project_subscriptions),
            'users_connected': len(self.user_connections),
            'connections_per_project': {
                project_id: len(connections) 
                for project_id, connections in self.project_subscriptions.items()
            }
        }


# Global connection manager instance
manager = ConnectionManager()

# WebSocket router
router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/analytics/{project_id}")
async def websocket_analytics_endpoint(
    websocket: WebSocket,
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time analytics updates.
    
    Provides live analytics data including:
    - Active user counts
    - Recent events
    - Live page views
    - Download notifications
    - Real-time metrics updates
    """
    connection_id = None
    
    try:
        # Accept connection (authentication handled via query params if needed)
        connection_id = await manager.connect(websocket, project_id)
        
        # Send initial connection confirmation
        await manager.send_personal_message(connection_id, {
            'type': 'connection_established',
            'connection_id': connection_id,
            'project_id': project_id,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Send initial analytics data
        dashboard_service = DashboardService(db)
        initial_data = await dashboard_service.get_realtime_dashboard(project_id)
        
        await manager.send_personal_message(connection_id, {
            'type': 'initial_data',
            'project_id': project_id,
            'data': {
                'active_users': initial_data.active_users,
                'recent_events': initial_data.recent_events,
                'live_page_views': initial_data.live_page_views,
                'current_downloads': initial_data.current_downloads
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # 30 second timeout
                )
                
                # Parse and handle message
                try:
                    data = json.loads(message)
                    await handle_websocket_message(connection_id, data, db)
                except json.JSONDecodeError:
                    await manager.send_personal_message(connection_id, {
                        'type': 'error',
                        'message': 'Invalid JSON message',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await manager.send_personal_message(connection_id, {
                    'type': 'ping',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for project {project_id}")
    except Exception as e:
        logger.error(f"WebSocket error for project {project_id}: {e}")
    finally:
        if connection_id:
            manager.disconnect(connection_id)


async def handle_websocket_message(connection_id: str, message: dict, db: AsyncSession):
    """Handle incoming WebSocket messages."""
    message_type = message.get('type')
    
    if message_type == 'ping':
        # Respond to ping
        await manager.send_personal_message(connection_id, {
            'type': 'pong',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    elif message_type == 'subscribe_events':
        # Subscribe to specific event types
        event_types = message.get('event_types', [])
        # Store subscription preferences (implementation would depend on requirements)
        await manager.send_personal_message(connection_id, {
            'type': 'subscription_updated',
            'event_types': event_types,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    elif message_type == 'request_update':
        # Manually request analytics update
        connection_info = manager.active_connections.get(connection_id)
        if connection_info:
            project_id = connection_info['project_id']
            dashboard_service = DashboardService(db)
            
            try:
                realtime_data = await dashboard_service.get_realtime_dashboard(project_id)
                await manager.send_personal_message(connection_id, {
                    'type': 'analytics_update',
                    'project_id': project_id,
                    'data': {
                        'active_users': realtime_data.active_users,
                        'recent_events': realtime_data.recent_events,
                        'live_page_views': realtime_data.live_page_views,
                        'current_downloads': realtime_data.current_downloads
                    },
                    'timestamp': datetime.utcnow().isoformat()
                })
            except Exception as e:
                await manager.send_personal_message(connection_id, {
                    'type': 'error',
                    'message': f'Failed to get analytics update: {str(e)}',
                    'timestamp': datetime.utcnow().isoformat()
                })
    
    else:
        await manager.send_personal_message(connection_id, {
            'type': 'error',
            'message': f'Unknown message type: {message_type}',
            'timestamp': datetime.utcnow().isoformat()
        })


class AnalyticsWebSocketService:
    """Service for managing analytics WebSocket notifications."""
    
    def __init__(self):
        self.manager = manager
    
    async def notify_new_visitor(self, project_id: str, visitor_data: dict):
        """Notify about a new visitor."""
        message = {
            'type': 'new_visitor',
            'project_id': project_id,
            'data': visitor_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        await self.manager.broadcast_to_project(project_id, message)
    
    async def notify_event(self, project_id: str, event_type: str, event_data: dict):
        """Notify about a new event."""
        message = {
            'type': 'new_event',
            'project_id': project_id,
            'event_type': event_type,
            'data': event_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        await self.manager.broadcast_to_project(project_id, message)
    
    async def notify_download(self, project_id: str, download_data: dict):
        """Notify about a download event."""
        message = {
            'type': 'download',
            'project_id': project_id,
            'data': download_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        await self.manager.broadcast_to_project(project_id, message)
    
    async def send_metrics_update(self, project_id: str, metrics_data: dict):
        """Send updated metrics to all project subscribers."""
        message = {
            'type': 'metrics_update',
            'project_id': project_id,
            'data': metrics_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        await self.manager.broadcast_to_project(project_id, message)
    
    async def send_alert(self, project_id: str, alert_type: str, alert_data: dict):
        """Send alert notifications."""
        message = {
            'type': 'alert',
            'project_id': project_id,
            'alert_type': alert_type,
            'data': alert_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        await self.manager.broadcast_to_project(project_id, message)
    
    def get_connection_stats(self) -> Dict:
        """Get WebSocket connection statistics."""
        return self.manager.get_connection_stats()


# Global WebSocket service instance
websocket_service = AnalyticsWebSocketService()


# Background task for sending periodic updates
async def analytics_update_task():
    """Background task that sends periodic analytics updates."""
    while True:
        try:
            # Get all projects with active connections
            active_projects = list(manager.project_subscriptions.keys())
            
            if active_projects:
                # This would typically use a database connection
                # For now, we'll just send heartbeat updates
                for project_id in active_projects:
                    await websocket_service.send_metrics_update(project_id, {
                        'heartbeat': True,
                        'connection_count': manager.get_project_connection_count(project_id)
                    })
            
            # Clean up stale connections
            await manager.cleanup_stale_connections()
            
            # Wait 30 seconds before next update
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Error in analytics update task: {e}")
            await asyncio.sleep(10)  # Shorter delay on error


# WebSocket connection info endpoint
@router.get("/analytics/connections")
async def get_websocket_connections():
    """Get information about active WebSocket connections."""
    return {
        'stats': manager.get_connection_stats(),
        'timestamp': datetime.utcnow().isoformat()
    }


# Utility functions for integration with analytics services
async def notify_analytics_event(project_id: str, event_type: str, event_data: dict):
    """Utility function to notify WebSocket clients about analytics events."""
    await websocket_service.notify_event(project_id, event_type, event_data)


async def send_realtime_update(project_id: str, update_data: dict):
    """Utility function to send real-time updates to WebSocket clients."""
    await websocket_service.send_metrics_update(project_id, update_data)