"""
GitHub-related schemas for Paperflow API.

This module provides request and response models for GitHub
integration and repository management.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .base import APIResponse, TaskInfo


class GitHubPermission(str, Enum):
    """GitHub repository permission levels."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class GitHubVisibility(str, Enum):
    """GitHub repository visibility."""

    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"


class WebhookEvent(str, Enum):
    """GitHub webhook events."""

    PUSH = "push"
    PULL_REQUEST = "pull_request"
    ISSUES = "issues"
    RELEASE = "release"
    WORKFLOW_RUN = "workflow_run"


class GitHubUser(BaseModel):
    """GitHub user information."""

    login: str = Field(..., description="GitHub username")
    id: int = Field(..., description="GitHub user ID")
    name: Optional[str] = Field(None, description="Display name")
    email: Optional[str] = Field(None, description="Email address")
    avatar_url: str = Field(..., description="Avatar URL")
    html_url: str = Field(..., description="Profile URL")
    type: str = Field(..., description="User type")
    site_admin: bool = Field(False, description="Whether user is site admin")


class GitHubRepository(BaseModel):
    """GitHub repository information."""

    id: int = Field(..., description="Repository ID")
    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name (owner/repo)")
    description: Optional[str] = Field(None, description="Repository description")
    html_url: str = Field(..., description="Repository URL")
    clone_url: str = Field(..., description="Clone URL")
    ssh_url: str = Field(..., description="SSH URL")
    default_branch: str = Field(..., description="Default branch")
    visibility: GitHubVisibility = Field(..., description="Repository visibility")
    private: bool = Field(..., description="Whether repository is private")
    
    # Statistics
    size: int = Field(..., description="Repository size in KB")
    stargazers_count: int = Field(..., description="Number of stars")
    watchers_count: int = Field(..., description="Number of watchers")
    forks_count: int = Field(..., description="Number of forks")
    open_issues_count: int = Field(..., description="Number of open issues")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    pushed_at: Optional[datetime] = Field(None, description="Last push timestamp")
    
    # Features
    has_issues: bool = Field(..., description="Whether issues are enabled")
    has_projects: bool = Field(..., description="Whether projects are enabled")
    has_wiki: bool = Field(..., description="Whether wiki is enabled")
    has_pages: bool = Field(..., description="Whether pages are enabled")
    has_downloads: bool = Field(..., description="Whether downloads are enabled")
    
    # Owner
    owner: GitHubUser = Field(..., description="Repository owner")
    
    # Permissions
    permissions: Optional[Dict[str, bool]] = Field(
        None, description="User permissions"
    )


class RepositoryCreate(BaseModel):
    """Schema for creating a GitHub repository."""

    name: str = Field(..., description="Repository name")
    description: Optional[str] = Field(None, description="Repository description")
    private: bool = Field(False, description="Whether repository should be private")
    auto_init: bool = Field(True, description="Initialize with README")
    gitignore_template: Optional[str] = Field(
        None, description="Gitignore template name"
    )
    license_template: Optional[str] = Field(None, description="License template name")
    allow_squash_merge: bool = Field(True, description="Allow squash merging")
    allow_merge_commit: bool = Field(True, description="Allow merge commits")
    allow_rebase_merge: bool = Field(True, description="Allow rebase merging")
    delete_branch_on_merge: bool = Field(
        False, description="Delete head branches on merge"
    )
    has_issues: bool = Field(True, description="Enable issues")
    has_projects: bool = Field(True, description="Enable projects")
    has_wiki: bool = Field(True, description="Enable wiki")

    @validator("name")
    def validate_name(cls, v):
        """Validate repository name."""
        if not v or len(v.strip()) < 1:
            raise ValueError("Repository name cannot be empty")
        
        if len(v) > 100:
            raise ValueError("Repository name cannot exceed 100 characters")
        
        # GitHub repository name rules
        import re
        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError(
                "Repository name can only contain alphanumeric characters, "
                "periods, hyphens, and underscores"
            )
        
        return v.strip()


class RepositoryUpdate(BaseModel):
    """Schema for updating a GitHub repository."""

    name: Optional[str] = Field(None, description="Repository name")
    description: Optional[str] = Field(None, description="Repository description")
    private: Optional[bool] = Field(None, description="Repository visibility")
    default_branch: Optional[str] = Field(None, description="Default branch")
    allow_squash_merge: Optional[bool] = Field(
        None, description="Allow squash merging"
    )
    allow_merge_commit: Optional[bool] = Field(None, description="Allow merge commits")
    allow_rebase_merge: Optional[bool] = Field(None, description="Allow rebase merging")
    delete_branch_on_merge: Optional[bool] = Field(
        None, description="Delete head branches on merge"
    )
    has_issues: Optional[bool] = Field(None, description="Enable issues")
    has_projects: Optional[bool] = Field(None, description="Enable projects")
    has_wiki: Optional[bool] = Field(None, description="Enable wiki")


class GitHubPages(BaseModel):
    """GitHub Pages information."""

    url: str = Field(..., description="Pages URL")
    status: str = Field(..., description="Pages status")
    cname: Optional[str] = Field(None, description="Custom domain")
    custom_404: bool = Field(..., description="Whether custom 404 page exists")
    html_url: str = Field(..., description="Pages HTML URL")
    
    # Source configuration
    source: Dict[str, Any] = Field(..., description="Pages source configuration")
    
    # Build information
    public: bool = Field(..., description="Whether pages are public")
    https_enforced: bool = Field(..., description="Whether HTTPS is enforced")
    https_certificate: Optional[Dict[str, Any]] = Field(
        None, description="HTTPS certificate info"
    )


class PagesSetup(BaseModel):
    """Schema for setting up GitHub Pages."""

    source: str = Field(..., description="Pages source: gh-pages, main, docs")
    path: str = Field("/", description="Source path within branch")
    cname: Optional[str] = Field(None, description="Custom domain")
    enforce_https: bool = Field(True, description="Enforce HTTPS")

    @validator("source")
    def validate_source(cls, v):
        """Validate pages source."""
        allowed_sources = ["gh-pages", "main", "master", "docs"]
        if v not in allowed_sources:
            raise ValueError(f"Invalid source. Allowed: {allowed_sources}")
        return v


class WebhookConfig(BaseModel):
    """Webhook configuration."""

    url: str = Field(..., description="Webhook URL")
    content_type: str = Field("json", description="Content type")
    secret: Optional[str] = Field(None, description="Webhook secret")
    insecure_ssl: bool = Field(False, description="Accept insecure SSL")


class Webhook(BaseModel):
    """GitHub webhook information."""

    id: int = Field(..., description="Webhook ID")
    name: str = Field(..., description="Webhook name")
    active: bool = Field(..., description="Whether webhook is active")
    events: List[WebhookEvent] = Field(..., description="Webhook events")
    config: WebhookConfig = Field(..., description="Webhook configuration")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    url: str = Field(..., description="Webhook API URL")
    test_url: str = Field(..., description="Test URL")
    ping_url: str = Field(..., description="Ping URL")
    deliveries_url: str = Field(..., description="Deliveries URL")
    last_response: Optional[Dict[str, Any]] = Field(
        None, description="Last delivery response"
    )


class WebhookCreate(BaseModel):
    """Schema for creating a webhook."""

    name: str = Field("web", description="Webhook name")
    events: List[WebhookEvent] = Field(
        default_factory=lambda: [WebhookEvent.PUSH], description="Webhook events"
    )
    active: bool = Field(True, description="Whether webhook is active")
    config: WebhookConfig = Field(..., description="Webhook configuration")


class PullRequest(BaseModel):
    """Pull request information."""

    id: int = Field(..., description="Pull request ID")
    number: int = Field(..., description="Pull request number")
    title: str = Field(..., description="Pull request title")
    body: Optional[str] = Field(None, description="Pull request description")
    state: str = Field(..., description="Pull request state")
    html_url: str = Field(..., description="Pull request URL")
    diff_url: str = Field(..., description="Diff URL")
    patch_url: str = Field(..., description="Patch URL")
    
    # Branches
    head: Dict[str, Any] = Field(..., description="Head branch information")
    base: Dict[str, Any] = Field(..., description="Base branch information")
    
    # Users
    user: GitHubUser = Field(..., description="Pull request author")
    assignee: Optional[GitHubUser] = Field(None, description="Assignee")
    assignees: List[GitHubUser] = Field(
        default_factory=list, description="Assignees"
    )
    
    # Status
    mergeable: Optional[bool] = Field(None, description="Whether PR is mergeable")
    mergeable_state: str = Field(..., description="Mergeable state")
    merged: bool = Field(..., description="Whether PR is merged")
    merged_at: Optional[datetime] = Field(None, description="Merge timestamp")
    merged_by: Optional[GitHubUser] = Field(None, description="User who merged")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    closed_at: Optional[datetime] = Field(None, description="Close timestamp")
    
    # Statistics
    comments: int = Field(..., description="Number of comments")
    review_comments: int = Field(..., description="Number of review comments")
    commits: int = Field(..., description="Number of commits")
    additions: int = Field(..., description="Number of additions")
    deletions: int = Field(..., description="Number of deletions")
    changed_files: int = Field(..., description="Number of changed files")


class PullRequestCreate(BaseModel):
    """Schema for creating a pull request."""

    title: str = Field(..., description="Pull request title")
    body: Optional[str] = Field(None, description="Pull request description")
    head: str = Field(..., description="Head branch")
    base: str = Field(..., description="Base branch")
    draft: bool = Field(False, description="Create as draft")
    maintainer_can_modify: bool = Field(
        True, description="Allow maintainer modifications"
    )


class Release(BaseModel):
    """GitHub release information."""

    id: int = Field(..., description="Release ID")
    tag_name: str = Field(..., description="Tag name")
    name: str = Field(..., description="Release name")
    body: Optional[str] = Field(None, description="Release description")
    draft: bool = Field(..., description="Whether release is draft")
    prerelease: bool = Field(..., description="Whether release is prerelease")
    created_at: datetime = Field(..., description="Creation timestamp")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")
    author: GitHubUser = Field(..., description="Release author")
    assets: List[Dict[str, Any]] = Field(
        default_factory=list, description="Release assets"
    )
    html_url: str = Field(..., description="Release URL")
    tarball_url: str = Field(..., description="Tarball URL")
    zipball_url: str = Field(..., description="Zipball URL")


class GitHubIntegration(BaseModel):
    """GitHub integration status."""

    enabled: bool = Field(..., description="Whether integration is enabled")
    authenticated: bool = Field(..., description="Whether user is authenticated")
    username: Optional[str] = Field(None, description="GitHub username")
    scopes: List[str] = Field(default_factory=list, description="OAuth scopes")
    rate_limit: Optional[Dict[str, Any]] = Field(
        None, description="Rate limit information"
    )
    
    # Connected repositories
    repositories: List[GitHubRepository] = Field(
        default_factory=list, description="Connected repositories"
    )
    
    # Statistics
    total_repositories: int = Field(0, description="Total repository count")
    private_repositories: int = Field(0, description="Private repository count")
    public_repositories: int = Field(0, description="Public repository count")


# Response schemas
class GitHubUserResponse(APIResponse):
    """Response for GitHub user information."""

    data: GitHubUser


class RepositoryResponse(APIResponse):
    """Response for repository operations."""

    data: GitHubRepository


class RepositoryListResponse(APIResponse):
    """Response for repository listing."""

    data: List[GitHubRepository]


class PagesResponse(APIResponse):
    """Response for GitHub Pages operations."""

    data: GitHubPages


class WebhookResponse(APIResponse):
    """Response for webhook operations."""

    data: Webhook


class WebhookListResponse(APIResponse):
    """Response for webhook listing."""

    data: List[Webhook]


class PullRequestResponse(APIResponse):
    """Response for pull request operations."""

    data: PullRequest


class PullRequestListResponse(APIResponse):
    """Response for pull request listing."""

    data: List[PullRequest]


class ReleaseResponse(APIResponse):
    """Response for release operations."""

    data: Release


class ReleaseListResponse(APIResponse):
    """Response for release listing."""

    data: List[Release]


class GitHubIntegrationResponse(APIResponse):
    """Response for GitHub integration status."""

    data: GitHubIntegration