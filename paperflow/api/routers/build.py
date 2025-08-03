"""
Build router for Paperflow API.

This module provides endpoints for building LaTeX documents,
monitoring build progress, and managing build operations.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse

from paperflow.api.dependencies import (
    ConnectionManager,
    get_connection_manager,
    get_current_user,
    get_project_service,
    require_authentication,
    validate_project_id,
)
from paperflow.api.schemas.base import APIResponse, TaskInfo
from paperflow.api.schemas.build import (
    BuildConfigResponse,
    BuildLogsResponse,
    BuildQueueResponse,
    BuildRequest,
    BuildRequestResponse,
    BuildResultResponse,
    BuildStatsResponse,
    BuildStatusResponse,
)
from paperflow.api.schemas.websocket import (
    WebSocketMessage,
    WebSocketMessageType,
    create_build_progress_message,
)
from paperflow.services.project_service import ProjectService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter()


async def get_project_or_404(
    project_id: str,
    project_service: ProjectService,
    current_user: Optional[Dict[str, Any]] = None,
) -> Any:
    """Get project by ID or raise 404 error."""
    try:
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found",
            )
        return project
    except Exception as e:
        logger.error(f"Error fetching project {project_id}: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching project",
        )


@router.post("/{project_id}", response_model=BuildRequestResponse)
async def build_project(
    build_request: BuildRequest,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    connection_manager: ConnectionManager = Depends(get_connection_manager),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """
    Build a LaTeX project.

    Initiates a build process for the specified project with the given
    configuration. Returns a task ID for tracking build progress.
    """
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)

        logger.info(f"Starting build for project {project_id}")

        # Create build task
        task_id = await project_service.create_build_task(
            project_id=project_id,
            build_config=build_request.dict(),
            initiated_by=current_user.get("user_id", "unknown"),
        )

        # Schedule background build
        background_tasks.add_task(
            _execute_build,
            project_id=project_id,
            task_id=task_id,
            build_request=build_request,
            project_service=project_service,
            connection_manager=connection_manager,
            user_id=current_user.get("user_id"),
        )

        task_info = TaskInfo(
            task_id=task_id,
            status="pending",
            message="Build initiated",
            started_at=datetime.utcnow(),
        )

        return BuildRequestResponse(
            success=True,
            message=f"Build initiated for project '{project_id}'",
            data=task_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating build for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error initiating build: {str(e)}",
        )


@router.get("/{project_id}/status", response_model=BuildStatusResponse)
async def get_build_status(
    project_id: str = Depends(validate_project_id),
    task_id: Optional[str] = Query(None, description="Specific build task ID"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get current build status for a project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)

        logger.info(f"Getting build status for project {project_id}")

        # Get build status
        if task_id:
            build_info = await project_service.get_build_task_status(task_id)
        else:
            build_info = await project_service.get_latest_build_status(project_id)

        if not build_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No build information found",
            )

        return BuildStatusResponse(
            success=True,
            message=f"Build status retrieved for project '{project_id}'",
            data=build_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting build status for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving build status",
        )


@router.get("/{project_id}/logs", response_model=BuildLogsResponse)
async def get_build_logs(
    project_id: str = Depends(validate_project_id),
    task_id: Optional[str] = Query(None, description="Specific build task ID"),
    limit: int = Query(
        1000, ge=1, le=10000, description="Maximum number of log entries"
    ),
    level: Optional[str] = Query(None, description="Filter by log level"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get build logs for a project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)

        logger.info(f"Getting build logs for project {project_id}")

        # Get build logs
        if task_id:
            logs = await project_service.get_build_task_logs(
                task_id=task_id, limit=limit, level=level
            )
        else:
            logs = await project_service.get_latest_build_logs(
                project_id=project_id, limit=limit, level=level
            )

        return BuildLogsResponse(
            success=True,
            message=f"Build logs retrieved for project '{project_id}'",
            data=logs,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting build logs for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving build logs",
        )


@router.get("/{project_id}/result", response_model=BuildResultResponse)
async def get_build_result(
    project_id: str = Depends(validate_project_id),
    task_id: Optional[str] = Query(None, description="Specific build task ID"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get build result for a project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)

        logger.info(f"Getting build result for project {project_id}")

        # Get build result
        if task_id:
            result = await project_service.get_build_task_result(task_id)
        else:
            result = await project_service.get_latest_build_result(project_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No build result found"
            )

        return BuildResultResponse(
            success=True,
            message=f"Build result retrieved for project '{project_id}'",
            data=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting build result for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving build result",
        )


@router.get("/{project_id}/output")
async def download_build_output(
    project_id: str = Depends(validate_project_id),
    task_id: Optional[str] = Query(None, description="Specific build task ID"),
    filename: Optional[str] = Query(None, description="Specific output file"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Download build output file."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)

        logger.info(f"Downloading build output for project {project_id}")

        # Get output file path
        if task_id:
            output_path = await project_service.get_build_task_output(
                task_id=task_id, filename=filename
            )
        else:
            output_path = await project_service.get_latest_build_output(
                project_id=project_id, filename=filename
            )

        if not output_path or not output_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Build output file not found",
            )

        # Return file
        return FileResponse(
            path=output_path,
            filename=output_path.name,
            media_type="application/octet-stream",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading build output for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error downloading build output",
        )


@router.post("/{project_id}/cancel")
async def cancel_build(
    project_id: str = Depends(validate_project_id),
    task_id: Optional[str] = Query(
        None, description="Specific build task ID to cancel"
    ),
    project_service: ProjectService = Depends(get_project_service),
    connection_manager: ConnectionManager = Depends(get_connection_manager),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Cancel an ongoing build operation."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)

        logger.info(f"Canceling build for project {project_id}")

        # Cancel build
        cancelled_tasks = await project_service.cancel_build(
            project_id=project_id,
            task_id=task_id,
            cancelled_by=current_user.get("user_id", "unknown"),
        )

        # Notify via WebSocket
        for cancelled_task_id in cancelled_tasks:
            message = WebSocketMessage(
                type=WebSocketMessageType.BUILD_CANCELLED,
                channel="build",
                data={
                    "build_id": cancelled_task_id,
                    "project_name": project_id,
                    "message": "Build cancelled by user",
                },
            )
            await connection_manager.broadcast_to_channel(
                message.json(), f"build:{project_id}"
            )

        return APIResponse(
            success=True,
            message=f"Build cancelled for project '{project_id}' ({len(cancelled_tasks)} tasks)",
            data={"cancelled_tasks": cancelled_tasks},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error canceling build for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error canceling build: {str(e)}",
        )


@router.delete("/{project_id}/clean")
async def clean_build_artifacts(
    project_id: str = Depends(validate_project_id),
    keep_outputs: bool = Query(True, description="Keep main output files (PDF, etc.)"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Clean build artifacts and auxiliary files."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)

        logger.info(f"Cleaning build artifacts for project {project_id}")

        # Clean artifacts
        cleaned_files = await project_service.clean_build_artifacts(
            project_id=project_id, keep_outputs=keep_outputs
        )

        return APIResponse(
            success=True,
            message=f"Build artifacts cleaned for project '{project_id}'",
            data={"cleaned_files": cleaned_files, "count": len(cleaned_files)},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning artifacts for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cleaning build artifacts: {str(e)}",
        )


@router.get("/queue", response_model=BuildQueueResponse)
async def get_build_queue(
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get current build queue status."""
    try:
        logger.info("Getting build queue status")

        # Get queue status
        queue_status = await project_service.get_build_queue_status()

        return BuildQueueResponse(
            success=True, message="Build queue status retrieved", data=queue_status
        )

    except Exception as e:
        logger.error(f"Error getting build queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving build queue status",
        )


@router.get("/stats", response_model=BuildStatsResponse)
async def get_build_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days for statistics"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get build statistics."""
    try:
        logger.info(f"Getting build statistics for last {days} days")

        # Get build statistics
        stats = await project_service.get_build_statistics(days=days)

        return BuildStatsResponse(
            success=True,
            message=f"Build statistics retrieved for last {days} days",
            data=stats,
        )

    except Exception as e:
        logger.error(f"Error getting build statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving build statistics",
        )


@router.get("/config", response_model=BuildConfigResponse)
async def get_build_config(
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get build configuration."""
    try:
        logger.info("Getting build configuration")

        # Get build configuration
        config = await project_service.get_build_config()

        return BuildConfigResponse(
            success=True, message="Build configuration retrieved", data=config
        )

    except Exception as e:
        logger.error(f"Error getting build configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving build configuration",
        )


@router.websocket("/{project_id}/ws")
async def build_websocket(
    websocket: WebSocket,
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    connection_manager: ConnectionManager = Depends(get_connection_manager),
):
    """
    WebSocket endpoint for real-time build updates.

    Provides real-time updates on build progress, logs, and completion status.
    """
    channel = f"build:{project_id}"

    try:
        # Accept WebSocket connection
        await connection_manager.connect(websocket, channel)

        logger.info(f"WebSocket connected for build updates: {project_id}")

        # Send initial status
        try:
            build_status = await project_service.get_latest_build_status(project_id)
            if build_status:
                initial_message = WebSocketMessage(
                    type=WebSocketMessageType.BUILD_PROGRESS,
                    channel="build",
                    data={
                        "build_id": build_status.build_id,
                        "project_name": project_id,
                        "status": build_status.status,
                        "progress": build_status.progress or 0,
                        "current_step": build_status.current_step or "Unknown",
                    },
                )
                await websocket.send_text(initial_message.json())
        except Exception as e:
            logger.warning(f"Could not send initial build status: {e}")

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (like ping)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle ping messages
                if message.get("type") == "ping":
                    pong_message = WebSocketMessage(
                        type=WebSocketMessageType.PONG,
                        channel="system",
                        data={"timestamp": datetime.utcnow().isoformat()},
                    )
                    await websocket.send_text(pong_message.json())

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for build updates: {project_id}")
    except Exception as e:
        logger.error(f"WebSocket error for build updates {project_id}: {e}")
    finally:
        # Clean up connection
        try:
            connection_manager.disconnect(websocket, channel)
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")


# Background task functions
async def _execute_build(
    project_id: str,
    task_id: str,
    build_request: BuildRequest,
    project_service: ProjectService,
    connection_manager: ConnectionManager,
    user_id: Optional[str] = None,
):
    """Execute build in background with real-time updates."""
    channel = f"build:{project_id}"

    try:
        logger.info(f"Executing build for project {project_id}, task {task_id}")

        # Send build started message
        started_message = WebSocketMessage(
            type=WebSocketMessageType.BUILD_STARTED,
            channel="build",
            data={
                "build_id": task_id,
                "project_name": project_id,
                "target": build_request.target,
                "engine": build_request.engine,
            },
        )
        await connection_manager.broadcast_to_channel(started_message.json(), channel)

        # Update task status
        await project_service.update_build_task(task_id, status="running")

        # Progress callback for real-time updates
        async def progress_callback(progress: int, step: str, message: str = ""):
            progress_msg = create_build_progress_message(
                build_id=task_id,
                project_name=project_id,
                progress=progress,
                current_step=step,
                user_id=user_id,
            )
            await connection_manager.broadcast_to_channel(progress_msg.json(), channel)

        # Log callback for real-time log streaming
        async def log_callback(
            level: str, message: str, file: str = None, line: int = None
        ):
            log_message = WebSocketMessage(
                type=WebSocketMessageType.BUILD_LOG,
                channel="build",
                data={
                    "build_id": task_id,
                    "project_name": project_id,
                    "level": level,
                    "message": message,
                    "file": file,
                    "line": line,
                },
            )
            await connection_manager.broadcast_to_channel(log_message.json(), channel)

        # Perform actual build
        result = await project_service.build_project(
            project_id=project_id,
            task_id=task_id,
            build_config=build_request.dict(),
            progress_callback=progress_callback,
            log_callback=log_callback,
        )

        # Send completion message
        if result.success:
            completed_message = WebSocketMessage(
                type=WebSocketMessageType.BUILD_COMPLETED,
                channel="build",
                data={
                    "build_id": task_id,
                    "project_name": project_id,
                    "result": result.dict(),
                    "output_files": result.output_files,
                },
            )
        else:
            completed_message = WebSocketMessage(
                type=WebSocketMessageType.BUILD_FAILED,
                channel="build",
                data={
                    "build_id": task_id,
                    "project_name": project_id,
                    "error": result.message,
                    "errors": [error.dict() for error in result.errors],
                },
            )

        await connection_manager.broadcast_to_channel(completed_message.json(), channel)

        # Update task with result
        await project_service.complete_build_task(task_id, result)

        logger.info(f"Build completed for project {project_id}, task {task_id}")

    except Exception as e:
        logger.error(f"Build failed for project {project_id}, task {task_id}: {e}")

        # Send failure message
        failed_message = WebSocketMessage(
            type=WebSocketMessageType.BUILD_FAILED,
            channel="build",
            data={"build_id": task_id, "project_name": project_id, "error": str(e)},
        )
        await connection_manager.broadcast_to_channel(failed_message.json(), channel)

        # Update task with failure
        await project_service.fail_build_task(task_id, str(e))
