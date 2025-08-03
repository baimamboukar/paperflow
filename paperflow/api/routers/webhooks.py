"""
Webhooks router for Paperflow API.

This module provides endpoints for handling webhook events
from external services like GitHub, Overleaf, and others.
"""

import hashlib
import hmac
import json
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    status
)
from fastapi.responses import JSONResponse

from paperflow.api.dependencies import (
    get_api_settings,
    get_github_service,
    get_project_service,
    validate_project_id,
    APISettings,
)
from paperflow.api.schemas.base import APIResponse, WebhookPayload
from paperflow.services.github_service import GitHubService
from paperflow.services.project_service import ProjectService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter()


def verify_github_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """Verify GitHub webhook signature."""
    if not signature.startswith("sha256="):
        return False
    
    signature = signature[7:]  # Remove 'sha256=' prefix
    
    # Calculate expected signature
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures securely
    return hmac.compare_digest(signature, expected_signature)


def verify_overleaf_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """Verify Overleaf webhook signature."""
    # Overleaf uses HMAC-SHA256 similar to GitHub
    if not signature:
        return False
    
    # Calculate expected signature
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures securely
    return hmac.compare_digest(signature, expected_signature)


@router.post("/github/{project_id}")
async def github_webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(validate_project_id),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    project_service: ProjectService = Depends(get_project_service),
    github_service: GitHubService = Depends(get_github_service),
    api_settings: APISettings = Depends(get_api_settings),
):
    """
    Handle GitHub webhook events for a specific project.
    
    Supports events like:
    - push: Trigger sync or build when repository is updated
    - pull_request: Handle PR events for project collaboration
    - release: Handle release events for project versioning
    - workflow_run: Handle GitHub Actions workflow events
    """
    try:
        # Read request body
        payload = await request.body()
        
        # Verify webhook signature if secret is configured
        if api_settings.github_webhook_secret:
            if not x_hub_signature_256:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing GitHub signature"
                )
            
            if not verify_github_signature(
                payload,
                x_hub_signature_256,
                api_settings.github_webhook_secret
            ):
                logger.warning(f"Invalid GitHub webhook signature for project {project_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )
        
        # Parse JSON payload
        try:
            webhook_data = json.loads(payload.decode())
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload"
            )
        
        # Log webhook event
        logger.info(
            f"Received GitHub webhook: event={x_github_event}, "
            f"delivery={x_github_delivery}, project={project_id}"
        )
        
        # Verify project exists
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found"
            )
        
        # Create webhook payload object
        webhook_payload = WebhookPayload(
            event=x_github_event or "unknown",
            data=webhook_data,
            source="github"
        )
        
        # Process webhook in background
        background_tasks.add_task(
            _process_github_webhook,
            project_id=project_id,
            event_type=x_github_event,
            webhook_data=webhook_data,
            delivery_id=x_github_delivery,
            project_service=project_service,
            github_service=github_service
        )
        
        # Return success response
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": f"GitHub webhook received for project '{project_id}'",
                "event": x_github_event,
                "delivery_id": x_github_delivery
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing GitHub webhook for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing GitHub webhook"
        )


@router.post("/overleaf/{project_id}")
async def overleaf_webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(validate_project_id),
    x_overleaf_event: Optional[str] = Header(None, alias="X-Overleaf-Event"),
    x_overleaf_signature: Optional[str] = Header(None, alias="X-Overleaf-Signature"),
    project_service: ProjectService = Depends(get_project_service),
    api_settings: APISettings = Depends(get_api_settings),
):
    """
    Handle Overleaf webhook events for a specific project.
    
    Supports events like:
    - project.updated: Trigger sync when Overleaf project is updated
    - project.compiled: Handle compilation events
    - project.shared: Handle sharing events
    """
    try:
        # Read request body
        payload = await request.body()
        
        # Verify webhook signature if configured
        # Note: Overleaf webhook signature verification may vary
        # This is a placeholder implementation
        if hasattr(api_settings, 'overleaf_webhook_secret') and api_settings.overleaf_webhook_secret:
            if not x_overleaf_signature:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing Overleaf signature"
                )
            
            if not verify_overleaf_signature(
                payload,
                x_overleaf_signature,
                api_settings.overleaf_webhook_secret
            ):
                logger.warning(f"Invalid Overleaf webhook signature for project {project_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )
        
        # Parse JSON payload
        try:
            webhook_data = json.loads(payload.decode())
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload"
            )
        
        # Log webhook event
        logger.info(
            f"Received Overleaf webhook: event={x_overleaf_event}, project={project_id}"
        )
        
        # Verify project exists
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found"
            )
        
        # Create webhook payload object
        webhook_payload = WebhookPayload(
            event=x_overleaf_event or "unknown",
            data=webhook_data,
            source="overleaf"
        )
        
        # Process webhook in background
        background_tasks.add_task(
            _process_overleaf_webhook,
            project_id=project_id,
            event_type=x_overleaf_event,
            webhook_data=webhook_data,
            project_service=project_service
        )
        
        # Return success response
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": f"Overleaf webhook received for project '{project_id}'",
                "event": x_overleaf_event
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Overleaf webhook for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing Overleaf webhook"
        )


@router.post("/generic")
async def generic_webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_source: Optional[str] = Header(None, alias="X-Webhook-Source"),
    x_webhook_event: Optional[str] = Header(None, alias="X-Webhook-Event"),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Handle generic webhook events from various sources.
    
    This is a catch-all endpoint for webhook events that don't
    fit into the specific GitHub or Overleaf handlers.
    """
    try:
        # Read request body
        payload = await request.body()
        
        # Parse JSON payload
        try:
            webhook_data = json.loads(payload.decode())
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload"
            )
        
        # Extract project ID from payload if available
        project_id = webhook_data.get("project_id") or webhook_data.get("projectId")
        
        # Log webhook event
        logger.info(
            f"Received generic webhook: source={x_webhook_source}, "
            f"event={x_webhook_event}, project={project_id}"
        )
        
        # Create webhook payload object
        webhook_payload = WebhookPayload(
            event=x_webhook_event or "unknown",
            data=webhook_data,
            source=x_webhook_source or "unknown"
        )
        
        # Process webhook in background
        background_tasks.add_task(
            _process_generic_webhook,
            webhook_payload=webhook_payload,
            project_service=project_service
        )
        
        # Return success response
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "Generic webhook received",
                "source": x_webhook_source,
                "event": x_webhook_event
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing generic webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing generic webhook"
        )


@router.get("/test/{project_id}")
async def test_webhook_endpoint(
    project_id: str = Depends(validate_project_id),
    source: str = "test",
    event: str = "ping",
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Test webhook endpoint for debugging and integration testing.
    
    This endpoint can be used to test webhook processing without
    requiring actual webhook events from external services.
    """
    try:
        # Verify project exists
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found"
            )
        
        # Create test webhook payload
        test_payload = {
            "test": True,
            "project_id": project_id,
            "timestamp": "2023-01-01T00:00:00Z",
            "message": "This is a test webhook"
        }
        
        # Log test webhook
        logger.info(f"Test webhook: source={source}, event={event}, project={project_id}")
        
        # Record webhook event
        await project_service.record_webhook_event(
            project_id=project_id,
            source=source,
            event=event,
            payload=test_payload,
            status="success"
        )
        
        return APIResponse(
            success=True,
            message=f"Test webhook processed for project '{project_id}'",
            data={
                "project_id": project_id,
                "source": source,
                "event": event,
                "payload": test_payload
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing test webhook for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing test webhook"
        )


# Background task functions
async def _process_github_webhook(
    project_id: str,
    event_type: Optional[str],
    webhook_data: Dict[str, Any],
    delivery_id: Optional[str],
    project_service: ProjectService,
    github_service: GitHubService
):
    """Process GitHub webhook in background."""
    try:
        logger.info(f"Processing GitHub webhook: {event_type} for project {project_id}")
        
        # Record webhook event
        await project_service.record_webhook_event(
            project_id=project_id,
            source="github",
            event=event_type or "unknown",
            payload=webhook_data,
            delivery_id=delivery_id
        )
        
        # Handle different event types
        if event_type == "push":
            await _handle_github_push_event(
                project_id, webhook_data, project_service, github_service
            )
        elif event_type == "pull_request":
            await _handle_github_pr_event(
                project_id, webhook_data, project_service, github_service
            )
        elif event_type == "release":
            await _handle_github_release_event(
                project_id, webhook_data, project_service, github_service
            )
        elif event_type == "workflow_run":
            await _handle_github_workflow_event(
                project_id, webhook_data, project_service, github_service
            )
        else:
            logger.info(f"Unhandled GitHub event type: {event_type}")
        
        # Update webhook status
        await project_service.update_webhook_event_status(
            project_id=project_id,
            delivery_id=delivery_id,
            status="processed"
        )
        
        logger.info(f"GitHub webhook processed successfully: {event_type} for project {project_id}")
        
    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {e}")
        
        # Update webhook status with error
        if delivery_id:
            await project_service.update_webhook_event_status(
                project_id=project_id,
                delivery_id=delivery_id,
                status="failed",
                error=str(e)
            )


async def _process_overleaf_webhook(
    project_id: str,
    event_type: Optional[str],
    webhook_data: Dict[str, Any],
    project_service: ProjectService
):
    """Process Overleaf webhook in background."""
    try:
        logger.info(f"Processing Overleaf webhook: {event_type} for project {project_id}")
        
        # Record webhook event
        await project_service.record_webhook_event(
            project_id=project_id,
            source="overleaf",
            event=event_type or "unknown",
            payload=webhook_data
        )
        
        # Handle different event types
        if event_type == "project.updated":
            await _handle_overleaf_project_updated(
                project_id, webhook_data, project_service
            )
        elif event_type == "project.compiled":
            await _handle_overleaf_project_compiled(
                project_id, webhook_data, project_service
            )
        else:
            logger.info(f"Unhandled Overleaf event type: {event_type}")
        
        logger.info(f"Overleaf webhook processed successfully: {event_type} for project {project_id}")
        
    except Exception as e:
        logger.error(f"Error processing Overleaf webhook: {e}")


async def _process_generic_webhook(
    webhook_payload: WebhookPayload,
    project_service: ProjectService
):
    """Process generic webhook in background."""
    try:
        logger.info(f"Processing generic webhook: {webhook_payload.event} from {webhook_payload.source}")
        
        # Extract project ID if available
        project_id = (
            webhook_payload.data.get("project_id") or 
            webhook_payload.data.get("projectId")
        )
        
        if project_id:
            # Record webhook event for specific project
            await project_service.record_webhook_event(
                project_id=project_id,
                source=webhook_payload.source,
                event=webhook_payload.event,
                payload=webhook_payload.data
            )
        
        logger.info(f"Generic webhook processed successfully: {webhook_payload.event}")
        
    except Exception as e:
        logger.error(f"Error processing generic webhook: {e}")


# Event-specific handlers
async def _handle_github_push_event(
    project_id: str,
    webhook_data: Dict[str, Any],
    project_service: ProjectService,
    github_service: GitHubService
):
    """Handle GitHub push event."""
    try:
        # Extract push information
        ref = webhook_data.get("ref", "")
        commits = webhook_data.get("commits", [])
        repository = webhook_data.get("repository", {})
        
        logger.info(f"GitHub push to {ref}: {len(commits)} commits in {repository.get('full_name')}")
        
        # Check if this push should trigger a sync
        sync_config = await project_service.get_sync_config(project_id, "github")
        if sync_config and sync_config.get("auto_sync_on_push", False):
            # Trigger automatic sync
            await project_service.trigger_auto_sync(
                project_id=project_id,
                provider="github",
                trigger="push_event",
                metadata={"ref": ref, "commits": len(commits)}
            )
        
    except Exception as e:
        logger.error(f"Error handling GitHub push event: {e}")


async def _handle_github_pr_event(
    project_id: str,
    webhook_data: Dict[str, Any],
    project_service: ProjectService,
    github_service: GitHubService
):
    """Handle GitHub pull request event."""
    try:
        action = webhook_data.get("action", "")
        pr = webhook_data.get("pull_request", {})
        
        logger.info(f"GitHub PR {action}: #{pr.get('number')} - {pr.get('title')}")
        
        # Handle different PR actions
        if action in ["opened", "synchronize"]:
            # Could trigger build/validation for PR
            pass
        elif action == "closed" and pr.get("merged"):
            # Could trigger post-merge actions
            pass
        
    except Exception as e:
        logger.error(f"Error handling GitHub PR event: {e}")


async def _handle_github_release_event(
    project_id: str,
    webhook_data: Dict[str, Any],
    project_service: ProjectService,
    github_service: GitHubService
):
    """Handle GitHub release event."""
    try:
        action = webhook_data.get("action", "")
        release = webhook_data.get("release", {})
        
        logger.info(f"GitHub release {action}: {release.get('tag_name')} - {release.get('name')}")
        
        # Could trigger actions based on releases
        if action == "published":
            # Could trigger deployment or archival
            pass
        
    except Exception as e:
        logger.error(f"Error handling GitHub release event: {e}")


async def _handle_github_workflow_event(
    project_id: str,
    webhook_data: Dict[str, Any],
    project_service: ProjectService,
    github_service: GitHubService
):
    """Handle GitHub workflow run event."""
    try:
        action = webhook_data.get("action", "")
        workflow_run = webhook_data.get("workflow_run", {})
        
        logger.info(f"GitHub workflow {action}: {workflow_run.get('name')} - {workflow_run.get('conclusion')}")
        
        # Could handle workflow results
        if action == "completed":
            conclusion = workflow_run.get("conclusion")
            if conclusion == "success":
                # Handle successful workflow
                pass
            elif conclusion == "failure":
                # Handle failed workflow
                pass
        
    except Exception as e:
        logger.error(f"Error handling GitHub workflow event: {e}")


async def _handle_overleaf_project_updated(
    project_id: str,
    webhook_data: Dict[str, Any],
    project_service: ProjectService
):
    """Handle Overleaf project updated event."""
    try:
        logger.info(f"Overleaf project updated for project {project_id}")
        
        # Check if this should trigger a sync
        sync_config = await project_service.get_sync_config(project_id, "overleaf")
        if sync_config and sync_config.get("auto_sync_on_update", False):
            # Trigger automatic sync
            await project_service.trigger_auto_sync(
                project_id=project_id,
                provider="overleaf",
                trigger="project_updated",
                metadata=webhook_data
            )
        
    except Exception as e:
        logger.error(f"Error handling Overleaf project updated event: {e}")


async def _handle_overleaf_project_compiled(
    project_id: str,
    webhook_data: Dict[str, Any],
    project_service: ProjectService
):
    """Handle Overleaf project compiled event."""
    try:
        logger.info(f"Overleaf project compiled for project {project_id}")
        
        # Could trigger actions based on compilation success/failure
        compile_status = webhook_data.get("status", "unknown")
        if compile_status == "success":
            # Handle successful compilation
            pass
        elif compile_status == "error":
            # Handle compilation errors
            pass
        
    except Exception as e:
        logger.error(f"Error handling Overleaf project compiled event: {e}")