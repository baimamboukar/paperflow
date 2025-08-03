"""
GitHub router for Paperflow API.

This module provides endpoints for GitHub integration,
repository management, and GitHub Pages setup.
"""

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
    get_github_credentials,
    get_github_service,
    require_authentication,
)
from paperflow.api.schemas.base import APIResponse
from paperflow.api.schemas.github import (
    GitHubIntegrationResponse,
    PagesResponse,
    PagesSetup,
    PullRequestCreate,
    PullRequestListResponse,
    PullRequestResponse,
    ReleaseListResponse,
    ReleaseResponse,
    RepositoryCreate,
    RepositoryListResponse,
    RepositoryResponse,
    RepositoryUpdate,
    WebhookCreate,
    WebhookListResponse,
    WebhookResponse,
    GitHubUserResponse,
)
from paperflow.services.github_service import GitHubService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter()


@router.get("/user", response_model=GitHubUserResponse)
async def get_github_user(
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Get authenticated GitHub user information."""
    try:
        logger.info("Getting GitHub user information")
        
        # Get user info from GitHub
        user_info = await github_service.get_authenticated_user(
            credentials=github_credentials
        )
        
        return GitHubUserResponse(
            success=True,
            message="GitHub user information retrieved",
            data=user_info
        )
        
    except Exception as e:
        logger.error(f"Error getting GitHub user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving GitHub user information: {str(e)}"
        )


@router.get("/repositories", response_model=RepositoryListResponse)
async def list_repositories(
    type: str = Query("owner", description="Repository type: owner, public, private"),
    sort: str = Query("updated", description="Sort by: created, updated, pushed, full_name"),
    direction: str = Query("desc", description="Sort direction: asc, desc"),
    per_page: int = Query(30, ge=1, le=100, description="Results per page"),
    page: int = Query(1, ge=1, description="Page number"),
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """List GitHub repositories for the authenticated user."""
    try:
        logger.info(f"Listing GitHub repositories: type={type}, sort={sort}")
        
        # List repositories
        repositories = await github_service.list_repositories(
            credentials=github_credentials,
            type=type,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page
        )
        
        return RepositoryListResponse(
            success=True,
            message=f"Found {len(repositories)} repositories",
            data=repositories
        )
        
    except Exception as e:
        logger.error(f"Error listing GitHub repositories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing repositories: {str(e)}"
        )


@router.post("/repositories", response_model=RepositoryResponse)
async def create_repository(
    repository_data: RepositoryCreate,
    background_tasks: BackgroundTasks,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Create a new GitHub repository."""
    try:
        logger.info(f"Creating GitHub repository: {repository_data.name}")
        
        # Check if repository already exists
        try:
            existing_repo = await github_service.get_repository(
                credentials=github_credentials,
                owner=current_user.get("username", ""),
                repo=repository_data.name
            )
            if existing_repo:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Repository '{repository_data.name}' already exists"
                )
        except HTTPException as e:
            if e.status_code != status.HTTP_404_NOT_FOUND:
                raise
        
        # Create repository
        repository = await github_service.create_repository(
            credentials=github_credentials,
            repository_data=repository_data.dict()
        )
        
        logger.info(f"Successfully created GitHub repository: {repository_data.name}")
        
        return RepositoryResponse(
            success=True,
            message=f"Repository '{repository_data.name}' created successfully",
            data=repository
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating GitHub repository: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating repository: {str(e)}"
        )


@router.get("/repositories/{owner}/{repo}", response_model=RepositoryResponse)
async def get_repository(
    owner: str,
    repo: str,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Get a specific GitHub repository."""
    try:
        logger.info(f"Getting GitHub repository: {owner}/{repo}")
        
        # Get repository
        repository = await github_service.get_repository(
            credentials=github_credentials,
            owner=owner,
            repo=repo
        )
        
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository '{owner}/{repo}' not found"
            )
        
        return RepositoryResponse(
            success=True,
            message=f"Repository '{owner}/{repo}' retrieved successfully",
            data=repository
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GitHub repository {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving repository: {str(e)}"
        )


@router.patch("/repositories/{owner}/{repo}", response_model=RepositoryResponse)
async def update_repository(
    owner: str,
    repo: str,
    repository_update: RepositoryUpdate,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Update a GitHub repository."""
    try:
        logger.info(f"Updating GitHub repository: {owner}/{repo}")
        
        # Update repository
        repository = await github_service.update_repository(
            credentials=github_credentials,
            owner=owner,
            repo=repo,
            update_data=repository_update.dict(exclude_unset=True)
        )
        
        logger.info(f"Successfully updated GitHub repository: {owner}/{repo}")
        
        return RepositoryResponse(
            success=True,
            message=f"Repository '{owner}/{repo}' updated successfully",
            data=repository
        )
        
    except Exception as e:
        logger.error(f"Error updating GitHub repository {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating repository: {str(e)}"
        )


@router.delete("/repositories/{owner}/{repo}")
async def delete_repository(
    owner: str,
    repo: str,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Delete a GitHub repository."""
    try:
        logger.info(f"Deleting GitHub repository: {owner}/{repo}")
        
        # Delete repository
        await github_service.delete_repository(
            credentials=github_credentials,
            owner=owner,
            repo=repo
        )
        
        logger.info(f"Successfully deleted GitHub repository: {owner}/{repo}")
        
        return APIResponse(
            success=True,
            message=f"Repository '{owner}/{repo}' deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Error deleting GitHub repository {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting repository: {str(e)}"
        )


@router.get("/repositories/{owner}/{repo}/pages", response_model=PagesResponse)
async def get_github_pages(
    owner: str,
    repo: str,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Get GitHub Pages information for a repository."""
    try:
        logger.info(f"Getting GitHub Pages info for: {owner}/{repo}")
        
        # Get pages info
        pages_info = await github_service.get_pages(
            credentials=github_credentials,
            owner=owner,
            repo=repo
        )
        
        if not pages_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GitHub Pages not configured for '{owner}/{repo}'"
            )
        
        return PagesResponse(
            success=True,
            message=f"GitHub Pages info retrieved for '{owner}/{repo}'",
            data=pages_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GitHub Pages for {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving GitHub Pages info: {str(e)}"
        )


@router.post("/repositories/{owner}/{repo}/pages", response_model=PagesResponse)
async def setup_github_pages(
    owner: str,
    repo: str,
    pages_setup: PagesSetup,
    background_tasks: BackgroundTasks,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Setup GitHub Pages for a repository."""
    try:
        logger.info(f"Setting up GitHub Pages for: {owner}/{repo}")
        
        # Setup pages
        pages_info = await github_service.setup_pages(
            credentials=github_credentials,
            owner=owner,
            repo=repo,
            pages_config=pages_setup.dict()
        )
        
        # Schedule background task to verify pages deployment
        background_tasks.add_task(
            _verify_pages_deployment,
            github_service=github_service,
            credentials=github_credentials,
            owner=owner,
            repo=repo
        )
        
        logger.info(f"Successfully setup GitHub Pages for: {owner}/{repo}")
        
        return PagesResponse(
            success=True,
            message=f"GitHub Pages setup for '{owner}/{repo}' initiated",
            data=pages_info
        )
        
    except Exception as e:
        logger.error(f"Error setting up GitHub Pages for {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting up GitHub Pages: {str(e)}"
        )


@router.get("/repositories/{owner}/{repo}/webhooks", response_model=WebhookListResponse)
async def list_webhooks(
    owner: str,
    repo: str,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """List webhooks for a repository."""
    try:
        logger.info(f"Listing webhooks for: {owner}/{repo}")
        
        # List webhooks
        webhooks = await github_service.list_webhooks(
            credentials=github_credentials,
            owner=owner,
            repo=repo
        )
        
        return WebhookListResponse(
            success=True,
            message=f"Found {len(webhooks)} webhooks for '{owner}/{repo}'",
            data=webhooks
        )
        
    except Exception as e:
        logger.error(f"Error listing webhooks for {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing webhooks: {str(e)}"
        )


@router.post("/repositories/{owner}/{repo}/webhooks", response_model=WebhookResponse)
async def create_webhook(
    owner: str,
    repo: str,
    webhook_data: WebhookCreate,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Create a webhook for a repository."""
    try:
        logger.info(f"Creating webhook for: {owner}/{repo}")
        
        # Create webhook
        webhook = await github_service.create_webhook(
            credentials=github_credentials,
            owner=owner,
            repo=repo,
            webhook_config=webhook_data.dict()
        )
        
        logger.info(f"Successfully created webhook for: {owner}/{repo}")
        
        return WebhookResponse(
            success=True,
            message=f"Webhook created for '{owner}/{repo}'",
            data=webhook
        )
        
    except Exception as e:
        logger.error(f"Error creating webhook for {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating webhook: {str(e)}"
        )


@router.delete("/repositories/{owner}/{repo}/webhooks/{webhook_id}")
async def delete_webhook(
    owner: str,
    repo: str,
    webhook_id: int,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Delete a webhook from a repository."""
    try:
        logger.info(f"Deleting webhook {webhook_id} from: {owner}/{repo}")
        
        # Delete webhook
        await github_service.delete_webhook(
            credentials=github_credentials,
            owner=owner,
            repo=repo,
            webhook_id=webhook_id
        )
        
        logger.info(f"Successfully deleted webhook {webhook_id} from: {owner}/{repo}")
        
        return APIResponse(
            success=True,
            message=f"Webhook {webhook_id} deleted from '{owner}/{repo}'"
        )
        
    except Exception as e:
        logger.error(f"Error deleting webhook {webhook_id} from {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting webhook: {str(e)}"
        )


@router.get("/repositories/{owner}/{repo}/pulls", response_model=PullRequestListResponse)
async def list_pull_requests(
    owner: str,
    repo: str,
    state: str = Query("open", description="Pull request state: open, closed, all"),
    sort: str = Query("created", description="Sort by: created, updated, popularity"),
    direction: str = Query("desc", description="Sort direction: asc, desc"),
    per_page: int = Query(30, ge=1, le=100, description="Results per page"),
    page: int = Query(1, ge=1, description="Page number"),
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """List pull requests for a repository."""
    try:
        logger.info(f"Listing pull requests for: {owner}/{repo}")
        
        # List pull requests
        pull_requests = await github_service.list_pull_requests(
            credentials=github_credentials,
            owner=owner,
            repo=repo,
            state=state,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page
        )
        
        return PullRequestListResponse(
            success=True,
            message=f"Found {len(pull_requests)} pull requests for '{owner}/{repo}'",
            data=pull_requests
        )
        
    except Exception as e:
        logger.error(f"Error listing pull requests for {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing pull requests: {str(e)}"
        )


@router.post("/repositories/{owner}/{repo}/pulls", response_model=PullRequestResponse)
async def create_pull_request(
    owner: str,
    repo: str,
    pr_data: PullRequestCreate,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Create a pull request for a repository."""
    try:
        logger.info(f"Creating pull request for: {owner}/{repo}")
        
        # Create pull request
        pull_request = await github_service.create_pull_request(
            credentials=github_credentials,
            owner=owner,
            repo=repo,
            pr_data=pr_data.dict()
        )
        
        logger.info(f"Successfully created pull request for: {owner}/{repo}")
        
        return PullRequestResponse(
            success=True,
            message=f"Pull request created for '{owner}/{repo}'",
            data=pull_request
        )
        
    except Exception as e:
        logger.error(f"Error creating pull request for {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating pull request: {str(e)}"
        )


@router.get("/repositories/{owner}/{repo}/releases", response_model=ReleaseListResponse)
async def list_releases(
    owner: str,
    repo: str,
    per_page: int = Query(30, ge=1, le=100, description="Results per page"),
    page: int = Query(1, ge=1, description="Page number"),
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """List releases for a repository."""
    try:
        logger.info(f"Listing releases for: {owner}/{repo}")
        
        # List releases
        releases = await github_service.list_releases(
            credentials=github_credentials,
            owner=owner,
            repo=repo,
            per_page=per_page,
            page=page
        )
        
        return ReleaseListResponse(
            success=True,
            message=f"Found {len(releases)} releases for '{owner}/{repo}'",
            data=releases
        )
        
    except Exception as e:
        logger.error(f"Error listing releases for {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing releases: {str(e)}"
        )


@router.get("/repositories/{owner}/{repo}/releases/latest", response_model=ReleaseResponse)
async def get_latest_release(
    owner: str,
    repo: str,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Get the latest release for a repository."""
    try:
        logger.info(f"Getting latest release for: {owner}/{repo}")
        
        # Get latest release
        release = await github_service.get_latest_release(
            credentials=github_credentials,
            owner=owner,
            repo=repo
        )
        
        if not release:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No releases found for '{owner}/{repo}'"
            )
        
        return ReleaseResponse(
            success=True,
            message=f"Latest release retrieved for '{owner}/{repo}'",
            data=release
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest release for {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving latest release: {str(e)}"
        )


@router.get("/integration", response_model=GitHubIntegrationResponse)
async def get_integration_status(
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Get GitHub integration status for the current user."""
    try:
        logger.info("Getting GitHub integration status")
        
        # Get integration status
        integration_status = await github_service.get_integration_status(
            credentials=github_credentials
        )
        
        return GitHubIntegrationResponse(
            success=True,
            message="GitHub integration status retrieved",
            data=integration_status
        )
        
    except Exception as e:
        logger.error(f"Error getting GitHub integration status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving integration status: {str(e)}"
        )


@router.post("/repositories/{owner}/{repo}/sync-project/{project_id}")
async def sync_project_to_repository(
    owner: str,
    repo: str,
    project_id: str,
    branch: str = Query("main", description="Target branch"),
    commit_message: Optional[str] = Query(None, description="Custom commit message"),
    create_pr: bool = Query(False, description="Create pull request"),
    background_tasks: BackgroundTasks,
    github_service: GitHubService = Depends(get_github_service),
    github_credentials: Dict[str, str] = Depends(get_github_credentials),
    current_user: Dict[str, Any] = Depends(require_authentication),
):
    """Sync a Paperflow project to a GitHub repository."""
    try:
        logger.info(f"Syncing project {project_id} to {owner}/{repo}")
        
        # Schedule background sync
        background_tasks.add_task(
            _sync_project_to_repo,
            github_service=github_service,
            credentials=github_credentials,
            owner=owner,
            repo=repo,
            project_id=project_id,
            branch=branch,
            commit_message=commit_message,
            create_pr=create_pr,
            user_id=current_user.get("user_id")
        )
        
        return APIResponse(
            success=True,
            message=f"Project sync initiated for '{project_id}' to '{owner}/{repo}'"
        )
        
    except Exception as e:
        logger.error(f"Error syncing project {project_id} to {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing project: {str(e)}"
        )


# Background task functions
async def _verify_pages_deployment(
    github_service: GitHubService,
    credentials: Dict[str, str],
    owner: str,
    repo: str
):
    """Verify GitHub Pages deployment in background."""
    try:
        import asyncio
        
        # Wait for deployment to complete (GitHub needs time)
        await asyncio.sleep(30)
        
        # Check pages status
        pages_info = await github_service.get_pages(
            credentials=credentials,
            owner=owner,
            repo=repo
        )
        
        if pages_info and pages_info.get("status") == "built":
            logger.info(f"GitHub Pages successfully deployed for {owner}/{repo}")
        else:
            logger.warning(f"GitHub Pages deployment may have failed for {owner}/{repo}")
            
    except Exception as e:
        logger.error(f"Error verifying pages deployment for {owner}/{repo}: {e}")


async def _sync_project_to_repo(
    github_service: GitHubService,
    credentials: Dict[str, str],
    owner: str,
    repo: str,
    project_id: str,
    branch: str,
    commit_message: Optional[str],
    create_pr: bool,
    user_id: Optional[str]
):
    """Sync project to repository in background."""
    try:
        logger.info(f"Executing project sync: {project_id} -> {owner}/{repo}")
        
        # Perform the sync
        result = await github_service.sync_project_to_repository(
            credentials=credentials,
            owner=owner,
            repo=repo,
            project_id=project_id,
            branch=branch,
            commit_message=commit_message,
            create_pr=create_pr
        )
        
        logger.info(f"Project sync completed: {project_id} -> {owner}/{repo}")
        
    except Exception as e:
        logger.error(f"Project sync failed: {project_id} -> {owner}/{repo}: {e}")