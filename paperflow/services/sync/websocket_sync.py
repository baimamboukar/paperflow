"""
WebSocket synchronization service for Paperflow.

This service provides real-time sync progress updates via WebSocket connections,
allowing clients to receive live updates during sync operations.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Callable
from weakref import WeakSet

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from paperflow.config.settings import Settings
from paperflow.models.sync import SyncResult, SyncStatus, SyncStage
from paperflow.services.base import BaseService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class WebSocketMessage(BaseModel):
    """WebSocket message structure."""
    type: str
    data: Dict[str, Any]
    timestamp: datetime = datetime.now()
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps({
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        })


class SyncProgressMessage(WebSocketMessage):
    """Sync progress update message."""
    
    def __init__(self, sync_result: SyncResult):
        super().__init__(
            type="sync_progress",
            data={
                "operation_id": sync_result.operation_id,
                "status": sync_result.status.value,
                "stage": sync_result.progress.stage.value,
                "current_step": sync_result.progress.current_step,
                "percentage": sync_result.progress.percentage,
                "completed_steps": sync_result.progress.completed_steps,
                "total_steps": sync_result.progress.total_steps,
                "success": sync_result.success,
                "error": sync_result.error_message,
                "warnings": sync_result.warnings,
                "metrics": {
                    "files_pulled": sync_result.metrics.files_pulled,
                    "files_pushed": sync_result.metrics.files_pushed,
                    "files_modified": sync_result.metrics.files_modified,
                    "conflicts": len(sync_result.conflicts),
                    "build_time": sync_result.metrics.build_time_seconds,
                    "deploy_time": sync_result.metrics.deploy_time_seconds
                }
            }
        )


class SyncCompletedMessage(WebSocketMessage):
    """Sync completion message."""
    
    def __init__(self, sync_result: SyncResult):
        super().__init__(
            type="sync_completed",
            data={
                "operation_id": sync_result.operation_id,
                "success": sync_result.success,
                "status": sync_result.status.value,
                "error": sync_result.error_message,
                "duration": sync_result.get_duration(),
                "deployment_url": sync_result.deployment_url,
                "summary": sync_result.get_summary()
            }
        )


class ConflictDetectedMessage(WebSocketMessage):
    """Conflict detection message."""
    
    def __init__(self, sync_result: SyncResult):
        super().__init__(
            type="conflicts_detected",
            data={
                "operation_id": sync_result.operation_id,
                "conflicts": [
                    {
                        "file_path": conflict.file_path,
                        "conflict_type": conflict.conflict_type,
                        "resolution": conflict.resolution.value if conflict.resolution else None,
                        "details": conflict.details
                    }
                    for conflict in sync_result.conflicts
                ]
            }
        )


class QueueStatusMessage(WebSocketMessage):
    """Queue status update message."""
    
    def __init__(self, queue_stats: Dict[str, Any]):
        super().__init__(
            type="queue_status",
            data=queue_stats
        )


class WebSocketConnection:
    """Represents a WebSocket connection."""
    
    def __init__(self, websocket: WebSocket, connection_id: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.subscriptions: Set[str] = set()  # Operation IDs or channels
        self.connected_at = datetime.now()
        self.last_ping = datetime.now()
        self.user_id: Optional[str] = None
        self.project_id: Optional[str] = None
    
    async def send_message(self, message: WebSocketMessage) -> bool:
        """Send message to WebSocket client."""
        try:
            await self.websocket.send_text(message.to_json())
            return True
        except Exception as e:
            logger.warning(f"Failed to send message to {self.connection_id}: {e}")
            return False
    
    async def send_json(self, data: Dict[str, Any]) -> bool:
        """Send JSON data to WebSocket client."""
        try:
            await self.websocket.send_json(data)
            return True
        except Exception as e:
            logger.warning(f"Failed to send JSON to {self.connection_id}: {e}")
            return False
    
    def subscribe_to_operation(self, operation_id: str) -> None:
        """Subscribe to sync operation updates."""
        self.subscriptions.add(f"operation:{operation_id}")
    
    def subscribe_to_project(self, project_id: str) -> None:
        """Subscribe to project-wide updates."""
        self.subscriptions.add(f"project:{project_id}")
        self.project_id = project_id
    
    def subscribe_to_global(self) -> None:
        """Subscribe to global updates."""
        self.subscriptions.add("global")
    
    def unsubscribe(self, subscription: str) -> None:
        """Unsubscribe from updates."""
        self.subscriptions.discard(subscription)
    
    def is_subscribed_to(self, channel: str) -> bool:
        """Check if connection is subscribed to channel."""
        return channel in self.subscriptions


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.operation_subscribers: Dict[str, Set[str]] = {}  # operation_id -> connection_ids
        self.project_subscribers: Dict[str, Set[str]] = {}   # project_id -> connection_ids
        self.global_subscribers: Set[str] = set()            # connection_ids for global updates
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
    
    def start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_connections())
        self._ping_task = asyncio.create_task(self._ping_connections())
    
    def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        self._shutdown_event.set()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()
    
    async def connect(self, websocket: WebSocket, connection_id: str) -> WebSocketConnection:
        """Accept new WebSocket connection."""
        await websocket.accept()
        
        connection = WebSocketConnection(websocket, connection_id)
        self.connections[connection_id] = connection
        
        logger.info(f"WebSocket connection established: {connection_id}")
        
        # Send welcome message
        welcome_message = WebSocketMessage(
            type="connected",
            data={"connection_id": connection_id, "server_time": datetime.now().isoformat()}
        )
        await connection.send_message(welcome_message)
        
        return connection
    
    async def disconnect(self, connection_id: str) -> None:
        """Handle WebSocket disconnection."""
        if connection_id in self.connections:
            connection = self.connections.pop(connection_id)
            
            # Remove from all subscriptions
            for subscription in connection.subscriptions:
                if subscription.startswith("operation:"):
                    operation_id = subscription.split(":", 1)[1]
                    if operation_id in self.operation_subscribers:
                        self.operation_subscribers[operation_id].discard(connection_id)
                
                elif subscription.startswith("project:"):
                    project_id = subscription.split(":", 1)[1]
                    if project_id in self.project_subscribers:
                        self.project_subscribers[project_id].discard(connection_id)
                
                elif subscription == "global":
                    self.global_subscribers.discard(connection_id)
            
            logger.info(f"WebSocket connection closed: {connection_id}")
    
    async def subscribe_to_operation(self, connection_id: str, operation_id: str) -> bool:
        """Subscribe connection to operation updates."""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        connection.subscribe_to_operation(operation_id)
        
        if operation_id not in self.operation_subscribers:
            self.operation_subscribers[operation_id] = set()
        
        self.operation_subscribers[operation_id].add(connection_id)
        
        logger.debug(f"Connection {connection_id} subscribed to operation {operation_id}")
        return True
    
    async def subscribe_to_project(self, connection_id: str, project_id: str) -> bool:
        """Subscribe connection to project updates."""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        connection.subscribe_to_project(project_id)
        
        if project_id not in self.project_subscribers:
            self.project_subscribers[project_id] = set()
        
        self.project_subscribers[project_id].add(connection_id)
        
        logger.debug(f"Connection {connection_id} subscribed to project {project_id}")
        return True
    
    async def subscribe_to_global(self, connection_id: str) -> bool:
        """Subscribe connection to global updates."""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        connection.subscribe_to_global()
        self.global_subscribers.add(connection_id)
        
        logger.debug(f"Connection {connection_id} subscribed to global updates")
        return True
    
    async def broadcast_to_operation(self, operation_id: str, message: WebSocketMessage) -> int:
        """Broadcast message to all subscribers of an operation."""
        sent_count = 0
        
        if operation_id in self.operation_subscribers:
            connection_ids = self.operation_subscribers[operation_id].copy()
            
            for connection_id in connection_ids:
                if connection_id in self.connections:
                    connection = self.connections[connection_id]
                    if await connection.send_message(message):
                        sent_count += 1
                    else:
                        # Remove failed connection
                        await self.disconnect(connection_id)
        
        return sent_count
    
    async def broadcast_to_project(self, project_id: str, message: WebSocketMessage) -> int:
        """Broadcast message to all subscribers of a project."""
        sent_count = 0
        
        if project_id in self.project_subscribers:
            connection_ids = self.project_subscribers[project_id].copy()
            
            for connection_id in connection_ids:
                if connection_id in self.connections:
                    connection = self.connections[connection_id]
                    if await connection.send_message(message):
                        sent_count += 1
                    else:
                        # Remove failed connection
                        await self.disconnect(connection_id)
        
        return sent_count
    
    async def broadcast_global(self, message: WebSocketMessage) -> int:
        """Broadcast message to all global subscribers."""
        sent_count = 0
        
        connection_ids = self.global_subscribers.copy()
        
        for connection_id in connection_ids:
            if connection_id in self.connections:
                connection = self.connections[connection_id]
                if await connection.send_message(message):
                    sent_count += 1
                else:
                    # Remove failed connection
                    await self.disconnect(connection_id)
        
        return sent_count
    
    async def send_to_connection(self, connection_id: str, message: WebSocketMessage) -> bool:
        """Send message to specific connection."""
        if connection_id in self.connections:
            connection = self.connections[connection_id]
            return await connection.send_message(message)
        
        return False
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.connections)
    
    def get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        return {
            "total_connections": len(self.connections),
            "operation_subscriptions": len(self.operation_subscribers),
            "project_subscriptions": len(self.project_subscribers),
            "global_subscriptions": len(self.global_subscribers)
        }
    
    async def _cleanup_connections(self) -> None:
        """Background task to cleanup stale connections."""
        while not self._shutdown_event.is_set():
            try:
                current_time = datetime.now()
                stale_connections = []
                
                for connection_id, connection in self.connections.items():
                    # Remove connections that haven't responded to ping in 5 minutes
                    if (current_time - connection.last_ping).total_seconds() > 300:
                        stale_connections.append(connection_id)
                
                for connection_id in stale_connections:
                    await self.disconnect(connection_id)
                
                # Wait 1 minute before next cleanup
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")
                await asyncio.sleep(60)
    
    async def _ping_connections(self) -> None:
        """Background task to ping connections."""
        while not self._shutdown_event.is_set():
            try:
                ping_message = WebSocketMessage(
                    type="ping",
                    data={"server_time": datetime.now().isoformat()}
                )
                
                failed_connections = []
                
                for connection_id, connection in self.connections.items():
                    if not await connection.send_message(ping_message):
                        failed_connections.append(connection_id)
                    else:
                        connection.last_ping = datetime.now()
                
                # Clean up failed connections
                for connection_id in failed_connections:
                    await self.disconnect(connection_id)
                
                # Wait 30 seconds before next ping
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in ping task: {e}")
                await asyncio.sleep(30)


class WebSocketSyncService(BaseService):
    """
    WebSocket synchronization service.
    
    Provides real-time sync progress updates via WebSocket connections.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize WebSocket sync service."""
        super().__init__(settings)
        
        self.websocket_manager = WebSocketManager()
        self.sync_handlers: List[Callable] = []
    
    def _perform_initialization(self) -> None:
        """Perform service-specific initialization."""
        logger.info("Initializing WebSocketSyncService")
        
        # Start background tasks
        self.websocket_manager.start_background_tasks()
        
        logger.info("WebSocketSyncService initialized")
    
    def _perform_cleanup(self) -> None:
        """Perform service cleanup."""
        logger.info("Cleaning up WebSocketSyncService")
        
        # Stop background tasks
        self.websocket_manager.stop_background_tasks()
        
        # Close all connections
        asyncio.create_task(self._close_all_connections())
        
        logger.info("WebSocketSyncService cleanup completed")
    
    async def _close_all_connections(self) -> None:
        """Close all WebSocket connections."""
        connection_ids = list(self.websocket_manager.connections.keys())
        
        for connection_id in connection_ids:
            await self.websocket_manager.disconnect(connection_id)
    
    # WebSocket Connection Management
    
    async def handle_websocket_connection(self, websocket: WebSocket, connection_id: str) -> None:
        """Handle new WebSocket connection."""
        try:
            connection = await self.websocket_manager.connect(websocket, connection_id)
            
            # Handle messages from client
            while True:
                try:
                    data = await websocket.receive_json()
                    await self._handle_client_message(connection, data)
                
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    break
        
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
        
        finally:
            await self.websocket_manager.disconnect(connection_id)
    
    async def _handle_client_message(self, connection: WebSocketConnection, data: Dict[str, Any]) -> None:
        """Handle message from WebSocket client."""
        try:
            message_type = data.get("type")
            
            if message_type == "subscribe_operation":
                operation_id = data.get("operation_id")
                if operation_id:
                    await self.websocket_manager.subscribe_to_operation(
                        connection.connection_id, operation_id
                    )
            
            elif message_type == "subscribe_project":
                project_id = data.get("project_id")
                if project_id:
                    await self.websocket_manager.subscribe_to_project(
                        connection.connection_id, project_id
                    )
            
            elif message_type == "subscribe_global":
                await self.websocket_manager.subscribe_to_global(connection.connection_id)
            
            elif message_type == "unsubscribe":
                subscription = data.get("subscription")
                if subscription:
                    connection.unsubscribe(subscription)
            
            elif message_type == "pong":
                # Client responded to ping
                connection.last_ping = datetime.now()
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
        
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
    
    # Sync Event Broadcasting
    
    async def broadcast_sync_progress(self, sync_result: SyncResult) -> None:
        """Broadcast sync progress update."""
        message = SyncProgressMessage(sync_result)
        
        # Broadcast to operation subscribers
        await self.websocket_manager.broadcast_to_operation(
            sync_result.operation_id, message
        )
        
        # Broadcast to global subscribers
        await self.websocket_manager.broadcast_global(message)
    
    async def broadcast_sync_completed(self, sync_result: SyncResult) -> None:
        """Broadcast sync completion."""
        message = SyncCompletedMessage(sync_result)
        
        # Broadcast to operation subscribers
        await self.websocket_manager.broadcast_to_operation(
            sync_result.operation_id, message
        )
        
        # Broadcast to global subscribers
        await self.websocket_manager.broadcast_global(message)
    
    async def broadcast_conflicts_detected(self, sync_result: SyncResult) -> None:
        """Broadcast conflict detection."""
        message = ConflictDetectedMessage(sync_result)
        
        # Broadcast to operation subscribers
        await self.websocket_manager.broadcast_to_operation(
            sync_result.operation_id, message
        )
        
        # Broadcast to global subscribers
        await self.websocket_manager.broadcast_global(message)
    
    async def broadcast_queue_status(self, queue_stats: Dict[str, Any]) -> None:
        """Broadcast queue status update."""
        message = QueueStatusMessage(queue_stats)
        
        # Broadcast to global subscribers only
        await self.websocket_manager.broadcast_global(message)
    
    # Service Integration
    
    def add_sync_handler(self, handler: Callable) -> None:
        """Add sync event handler."""
        self.sync_handlers.append(handler)
    
    async def on_sync_started(self, sync_result: SyncResult) -> None:
        """Handle sync started event."""
        await self.broadcast_sync_progress(sync_result)
    
    async def on_sync_progress(self, sync_result: SyncResult) -> None:
        """Handle sync progress event."""
        await self.broadcast_sync_progress(sync_result)
    
    async def on_sync_completed(self, sync_result: SyncResult) -> None:
        """Handle sync completed event."""
        await self.broadcast_sync_completed(sync_result)
    
    async def on_conflicts_detected(self, sync_result: SyncResult) -> None:
        """Handle conflicts detected event."""
        await self.broadcast_conflicts_detected(sync_result)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        return self.websocket_manager.get_subscription_stats()