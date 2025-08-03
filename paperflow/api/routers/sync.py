"""
Synchronization router for Paperflow API.

This module provides endpoints for synchronizing projects
with external services like Overleaf, GitHub, and others.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status
)

from paperflow.api.dependencies import (
    get_current_user,
    get_git_service,
    get_github_service,
    get_project_service,
    require_authentication,
    validate_project_id,
)
from paperflow.api.schemas.base import APIResponse, TaskInfo
from paperflow.api.schemas.sync import (
    ConflictResolutionRequest,
    GitHubSyncRequest,
    OverleafSyncRequest,
    SyncDryRunResponse,
    SyncDryRunResult,
    SyncHistoryResponse,
    SyncProvider,
    SyncRequestResponse,
    SyncResultResponse,
    SyncSchedule,
    SyncStatusResponse,
)
from paperflow.services.git_service import GitService
from paperflow.services.github_service import GitHubService
from paperflow.services.project_service import ProjectService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter()


async def get_project_or_404(
    project_id: str,
    project_service: ProjectService,
    current_user: Optional[Dict[str, Any]] = None
) -> Any:
    """Get project by ID or raise 404 error."""
    try:
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found"
            )
        return project
    except Exception as e:
        logger.error(f"Error fetching project {project_id}: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching project"
        )


@router.post("/{project_id}/overleaf", response_model=SyncRequestResponse)
async def sync_from_overleaf(
    sync_request: OverleafSyncRequest,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """
    Synchronize project with Overleaf.
    
    Supports pull, push, and bidirectional sync with conflict resolution.
    Returns a task ID for tracking the sync operation.
    """
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Starting Overleaf sync for project {project_id}")
        
        # Create sync task
        task_id = await project_service.create_sync_task(
            project_id=project_id,
            provider=SyncProvider.OVERLEAF,
            direction=sync_request.direction,
            config=sync_request.config.dict(),
            initiated_by=current_user.get("user_id", "unknown")
        )
        
        # Schedule background sync
        background_tasks.add_task(
            _execute_overleaf_sync,
            project_id=project_id,
            task_id=task_id,
            sync_request=sync_request,
            project_service=project_service,
            user_id=current_user.get("user_id")
        )
        
        task_info = TaskInfo(
            task_id=task_id,
            status="pending",
            message="Overleaf sync initiated",
            started_at=datetime.utcnow()
        )
        
        return SyncRequestResponse(
            success=True,
            message=f"Overleaf sync initiated for project '{project_id}'",
            data=task_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating Overleaf sync for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error initiating Overleaf sync: {str(e)}"
        )


@router.post("/{project_id}/github", response_model=SyncRequestResponse)
async def sync_to_github(
    sync_request: GitHubSyncRequest,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    github_service: GitHubService = Depends(get_github_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """
    Synchronize project with GitHub.
    
    Supports push to GitHub repository with optional pull request creation.
    Returns a task ID for tracking the sync operation.
    """
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Starting GitHub sync for project {project_id}")
        
        # Validate GitHub configuration
        if not sync_request.config.repository:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub repository is required"
            )
        
        # Create sync task
        task_id = await project_service.create_sync_task(
            project_id=project_id,
            provider=SyncProvider.GITHUB,
            direction=sync_request.direction,
            config=sync_request.config.dict(),
            initiated_by=current_user.get("user_id", "unknown")
        )
        
        # Schedule background sync
        background_tasks.add_task(
            _execute_github_sync,
            project_id=project_id,
            task_id=task_id,
            sync_request=sync_request,
            project_service=project_service,
            github_service=github_service,
            user_id=current_user.get("user_id")
        )
        
        task_info = TaskInfo(
            task_id=task_id,
            status="pending",
            message="GitHub sync initiated",
            started_at=datetime.utcnow()
        )
        
        return SyncRequestResponse(
            success=True,
            message=f"GitHub sync initiated for project '{project_id}'",
            data=task_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating GitHub sync for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error initiating GitHub sync: {str(e)}"
        )


@router.get("/{project_id}/status", response_model=SyncStatusResponse)
async def get_sync_status(
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get current synchronization status for a project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Getting sync status for project {project_id}")
        
        # Get sync status
        sync_status = await project_service.get_sync_status(project_id)
        
        return SyncStatusResponse(
            success=True,
            message=f"Sync status retrieved for project '{project_id}'",
            data=sync_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync status for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving sync status"
        )


@router.post("/{project_id}/schedule")
async def schedule_auto_sync(
    schedule: SyncSchedule,
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Schedule automatic synchronization for a project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Scheduling auto sync for project {project_id}")
        
        # Schedule auto sync
        await project_service.schedule_auto_sync(
            project_id=project_id,
            schedule=schedule.dict(),
            scheduled_by=current_user.get("user_id", "unknown")
        )
        
        return APIResponse(
            success=True,
            message=f"Auto sync scheduled for project '{project_id}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling auto sync for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scheduling auto sync: {str(e)}"
        )


@router.delete("/{project_id}/schedule")
async def cancel_auto_sync(
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Cancel automatic synchronization for a project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Canceling auto sync for project {project_id}")
        
        # Cancel auto sync
        await project_service.cancel_auto_sync(
            project_id=project_id,
            cancelled_by=current_user.get("user_id", "unknown")
        )
        
        return APIResponse(
            success=True,
            message=f"Auto sync cancelled for project '{project_id}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error canceling auto sync for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error canceling auto sync: {str(e)}"
        )


@router.get("/{project_id}/history", response_model=SyncHistoryResponse)
async def get_sync_history(
    project_id: str = Depends(validate_project_id),
    limit: int = Query(50, ge=1, le=200, description="Number of history entries"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    provider: Optional[SyncProvider] = Query(None, description="Filter by provider"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get synchronization history for a project."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Getting sync history for project {project_id}")
        
        # Get sync history
        history = await project_service.get_sync_history(
            project_id=project_id,
            limit=limit,
            offset=offset,
            provider=provider
        )
        
        return SyncHistoryResponse(
            success=True,
            message=f"Sync history retrieved for project '{project_id}'",
            data=history
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync history for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving sync history"
        )


@router.post("/{project_id}/dry-run", response_model=SyncDryRunResponse)
async def sync_dry_run(
    sync_request: OverleafSyncRequest | GitHubSyncRequest,
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Perform a dry run sync to preview changes without applying them.
    
    This is useful for understanding what changes would be made
    before performing an actual sync operation.
    """
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Performing sync dry run for project {project_id}")
        
        # Perform dry run based on provider
        if sync_request.provider == SyncProvider.OVERLEAF:
            dry_run_result = await _execute_overleaf_dry_run(
                project_id, sync_request, project_service
            )
        elif sync_request.provider == SyncProvider.GITHUB:
            dry_run_result = await _execute_github_dry_run(
                project_id, sync_request, project_service
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dry run not supported for provider: {sync_request.provider}"
            )
        
        return SyncDryRunResponse(
            success=True,
            message=f"Dry run completed for project '{project_id}'",
            data=dry_run_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing dry run for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error performing dry run: {str(e)}"
        )


@router.post("/{project_id}/resolve-conflicts")
async def resolve_sync_conflicts(
    resolution_request: ConflictResolutionRequest,
    project_id: str = Depends(validate_project_id),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """
    Resolve synchronization conflicts manually.
    
    This endpoint allows users to resolve conflicts that occurred
    during a sync operation by specifying resolution strategies.
    """
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Resolving sync conflicts for project {project_id}")
        
        # Resolve conflicts
        await project_service.resolve_sync_conflicts(
            project_id=project_id,
            conflicts=resolution_request.conflicts,
            resolved_by=current_user.get("user_id", "unknown")
        )
        
        return APIResponse(
            success=True,
            message=f"Sync conflicts resolved for project '{project_id}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving conflicts for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resolving conflicts: {str(e)}"
        )


@router.post("/{project_id}/cancel")
async def cancel_sync(
    project_id: str = Depends(validate_project_id),
    task_id: Optional[str] = Query(None, description="Specific task ID to cancel"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Cancel an ongoing synchronization operation."""
    try:
        # Verify project exists
        await get_project_or_404(project_id, project_service, current_user)
        
        logger.info(f"Canceling sync for project {project_id}")
        
        # Cancel sync
        cancelled_tasks = await project_service.cancel_sync(
            project_id=project_id,
            task_id=task_id,
            cancelled_by=current_user.get("user_id", "unknown")
        )
        
        return APIResponse(
            success=True,
            message=f"Sync cancelled for project '{project_id}' ({len(cancelled_tasks)} tasks)",
            data={"cancelled_tasks": cancelled_tasks}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error canceling sync for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error canceling sync: {str(e)}"
        )


# Background task functions
async def _execute_overleaf_sync(
    project_id: str,
    task_id: str,
    sync_request: OverleafSyncRequest,
    project_service: ProjectService,
    user_id: Optional[str] = None
):
    """Execute Overleaf sync in background."""
    try:
        logger.info(f"Executing Overleaf sync for project {project_id}, task {task_id}")
        
        # Update task status
        await project_service.update_sync_task(task_id, status="running")
        
        # Perform actual sync
        result = await project_service.sync_with_overleaf(
            project_id=project_id,
            task_id=task_id,
            config=sync_request.config,
            direction=sync_request.direction,
            force=sync_request.force,
            dry_run=sync_request.dry_run
        )
        
        # Update task with result
        await project_service.complete_sync_task(task_id, result)
        
        logger.info(f"Overleaf sync completed for project {project_id}, task {task_id}")
        
    except Exception as e:
        logger.error(f"Overleaf sync failed for project {project_id}, task {task_id}: {e}")
        await project_service.fail_sync_task(task_id, str(e))


async def _execute_github_sync(
    project_id: str,
    task_id: str,
    sync_request: GitHubSyncRequest,
    project_service: ProjectService,
    github_service: GitHubService,
    user_id: Optional[str] = None
):
    """Execute GitHub sync in background."""
    try:
        logger.info(f"Executing GitHub sync for project {project_id}, task {task_id}")
        
        # Update task status
        await project_service.update_sync_task(task_id, status="running")
        
        # Perform actual sync
        result = await project_service.sync_with_github(
            project_id=project_id,
            task_id=task_id,
            config=sync_request.config,
            direction=sync_request.direction,
            force=sync_request.force,
            commit_message=sync_request.commit_message,
            create_pr=sync_request.create_pr,
            pr_title=sync_request.pr_title,
            pr_description=sync_request.pr_description
        )
        
        # Update task with result
        await project_service.complete_sync_task(task_id, result)
        
        logger.info(f"GitHub sync completed for project {project_id}, task {task_id}")
        
    except Exception as e:
        logger.error(f"GitHub sync failed for project {project_id}, task {task_id}: {e}")
        await project_service.fail_sync_task(task_id, str(e))


async def _execute_overleaf_dry_run(
    project_id: str,
    sync_request: OverleafSyncRequest,
    project_service: ProjectService
) -> SyncDryRunResult:
    """Execute Overleaf dry run sync."""
    try:
        return await project_service.overleaf_dry_run(
            project_id=project_id,
            config=sync_request.config,
            direction=sync_request.direction
        )
    except Exception as e:
        logger.error(f"Overleaf dry run failed for project {project_id}: {e}")
        raise


async def _execute_github_dry_run(
    project_id: str,
    sync_request: GitHubSyncRequest,
    project_service: ProjectService
) -> SyncDryRunResult:
    """Execute GitHub dry run sync."""
    try:
        return await project_service.github_dry_run(
            project_id=project_id,
            config=sync_request.config,
            direction=sync_request.direction
        )
    except Exception as e:
        logger.error(f"GitHub dry run failed for project {project_id}: {e}")
        raise