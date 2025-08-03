"""
GitHub data models for Paperflow.

This module defines GitHub-related models including repositories, webhooks,
GitHub Pages configuration, releases, and operation results for managing
GitHub operations in the Paperflow ecosystem.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class GitHubRepositoryType(str, Enum):
    """GitHub repository type enumeration."""

    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"


class GitHubRepositoryState(str, Enum):
    """GitHub repository state enumeration."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DISABLED = "disabled"
    TEMPLATE = "template"


class GitHubWebhookEvent(str, Enum):
    """GitHub webhook event types."""

    PUSH = "push"
    PULL_REQUEST = "pull_request"
    ISSUES = "issues"
    ISSUE_COMMENT = "issue_comment"
    COMMIT_COMMENT = "commit_comment"
    CREATE = "create"
    DELETE = "delete"
    RELEASE = "release"
    DEPLOYMENT = "deployment"
    DEPLOYMENT_STATUS = "deployment_status"
    FORK = "fork"
    GOLLUM = "gollum"
    MEMBER = "member"
    PING = "ping"
    PUBLIC = "public"
    REPOSITORY = "repository"
    STAR = "star"
    WATCH = "watch"
    WORKFLOW_RUN = "workflow_run"


class GitHubPagesSource(str, Enum):
    """GitHub Pages source configuration."""

    ROOT = "/"
    DOCS = "/docs"
    BRANCH = "gh-pages"


class GitHubPagesBuildStatus(str, Enum):
    """GitHub Pages build status."""

    BUILT = "built"
    BUILDING = "building"
    ERRORED = "errored"
    NULL = "null"


class GitHubOperationStatus(str, Enum):
    """GitHub operation status enumeration."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"


class GitHubReleaseType(str, Enum):
    """GitHub release type enumeration."""

    RELEASE = "release"
    PRERELEASE = "prerelease"
    DRAFT = "draft"


class GitHubPermissionLevel(str, Enum):
    """GitHub permission levels."""

    READ = "read"
    TRIAGE = "triage"
    WRITE = "write"
    MAINTAIN = "maintain"
    ADMIN = "admin"


class GitHubUser(BaseModel):
    """
    GitHub user or organization model.

    Represents a GitHub user account or organization with basic information.
    """

    login: str = Field(..., description="GitHub username/login")
    id: int = Field(..., description="GitHub user ID")
    node_id: str = Field(..., description="GitHub node ID")
    avatar_url: Optional[str] = Field(default=None, description="Avatar URL")
    html_url: Optional[str] = Field(default=None, description="Profile URL")

    # User details
    name: Optional[str] = Field(default=None, description="Display name")
    email: Optional[str] = Field(default=None, description="Email address")
    bio: Optional[str] = Field(default=None, description="User bio")
    location: Optional[str] = Field(default=None, description="User location")
    company: Optional[str] = Field(default=None, description="User company")
    blog: Optional[str] = Field(default=None, description="User blog URL")
    twitter_username: Optional[str] = Field(
        default=None, description="Twitter username"
    )

    # Account type and status
    type: str = Field(default="User", description="Account type (User/Organization)")
    site_admin: bool = Field(default=False, description="Whether user is site admin")

    # Statistics
    public_repos: Optional[int] = Field(
        default=None, description="Number of public repositories"
    )
    public_gists: Optional[int] = Field(
        default=None, description="Number of public gists"
    )
    followers: Optional[int] = Field(default=None, description="Number of followers")
    following: Optional[int] = Field(default=None, description="Number of following")

    # Timestamps
    created_at: Optional[datetime] = Field(
        default=None, description="Account creation date"
    )
    updated_at: Optional[datetime] = Field(default=None, description="Last update date")

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    @validator("login")
    def validate_login(cls, v):
        """Validate GitHub login format."""
        if not v or not v.strip():
            raise ValueError("GitHub login cannot be empty")

        # Basic GitHub username validation
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("GitHub login contains invalid characters")

        if len(v) > 39:
            raise ValueError("GitHub login cannot exceed 39 characters")

        return v.strip()

    def is_organization(self) -> bool:
        """Check if this is an organization account."""
        return self.type.lower() == "organization"

    def get_profile_url(self) -> str:
        """Get GitHub profile URL."""
        return self.html_url or f"https://github.com/{self.login}"


class GitHubRepository(BaseModel):
    """
    GitHub repository model.

    Represents a GitHub repository with comprehensive metadata and configuration.
    """

    # Basic repository information
    id: int = Field(..., description="GitHub repository ID")
    node_id: str = Field(..., description="GitHub node ID")
    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name (owner/repo)")
    owner: GitHubUser = Field(..., description="Repository owner")

    # Repository URLs
    html_url: str = Field(..., description="Repository web URL")
    clone_url: str = Field(..., description="HTTPS clone URL")
    ssh_url: str = Field(..., description="SSH clone URL")
    git_url: str = Field(..., description="Git protocol URL")

    # Repository settings
    private: bool = Field(default=False, description="Whether repository is private")
    description: Optional[str] = Field(
        default=None, description="Repository description"
    )
    homepage: Optional[str] = Field(default=None, description="Repository homepage URL")
    language: Optional[str] = Field(default=None, description="Primary language")
    topics: List[str] = Field(default_factory=list, description="Repository topics")

    # Repository state
    archived: bool = Field(default=False, description="Whether repository is archived")
    disabled: bool = Field(default=False, description="Whether repository is disabled")
    fork: bool = Field(default=False, description="Whether repository is a fork")
    template: bool = Field(
        default=False, description="Whether repository is a template"
    )

    # Branch information
    default_branch: str = Field(default="main", description="Default branch name")

    # Repository permissions
    permissions: Dict[str, bool] = Field(
        default_factory=dict, description="Repository permissions"
    )
    allow_forking: bool = Field(default=True, description="Whether forking is allowed")

    # Repository features
    has_issues: bool = Field(default=True, description="Whether issues are enabled")
    has_projects: bool = Field(default=True, description="Whether projects are enabled")
    has_wiki: bool = Field(default=True, description="Whether wiki is enabled")
    has_pages: bool = Field(default=False, description="Whether Pages is enabled")
    has_downloads: bool = Field(
        default=True, description="Whether downloads are enabled"
    )
    has_discussions: bool = Field(
        default=False, description="Whether discussions are enabled"
    )

    # Statistics
    size: int = Field(default=0, description="Repository size in KB")
    stargazers_count: int = Field(default=0, description="Number of stars")
    watchers_count: int = Field(default=0, description="Number of watchers")
    forks_count: int = Field(default=0, description="Number of forks")
    open_issues_count: int = Field(default=0, description="Number of open issues")

    # Timestamps
    created_at: datetime = Field(..., description="Repository creation date")
    updated_at: datetime = Field(..., description="Last update date")
    pushed_at: Optional[datetime] = Field(default=None, description="Last push date")

    # License
    license: Optional[Dict[str, Any]] = Field(
        default=None, description="Repository license"
    )

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    @validator("name")
    def validate_name(cls, v):
        """Validate repository name format."""
        if not v or not v.strip():
            raise ValueError("Repository name cannot be empty")

        # GitHub repository name restrictions
        if len(v) > 100:
            raise ValueError("Repository name cannot exceed 100 characters")

        # Basic validation for special characters
        invalid_chars = ' <>:"|?*'
        if any(char in v for char in invalid_chars):
            raise ValueError(
                f"Repository name contains invalid characters: {invalid_chars}"
            )

        return v.strip()

    def get_api_url(self) -> str:
        """Get GitHub API URL for this repository."""
        return f"https://api.github.com/repos/{self.full_name}"

    def get_pages_url(self) -> Optional[str]:
        """Get GitHub Pages URL if enabled."""
        if not self.has_pages:
            return None

        # Standard GitHub Pages URL format
        if self.owner.login.endswith(".github.io") and self.name == self.owner.login:
            return f"https://{self.owner.login}"
        else:
            return f"https://{self.owner.login}.github.io/{self.name}"

    def can_admin(self) -> bool:
        """Check if current user has admin permissions."""
        return self.permissions.get("admin", False)

    def can_write(self) -> bool:
        """Check if current user has write permissions."""
        return self.permissions.get("push", False) or self.can_admin()

    def is_paperflow_project(self) -> bool:
        """Check if repository appears to be a Paperflow project."""
        return "paperflow" in self.topics or "academic-paper" in self.topics


class GitHubPages(BaseModel):
    """
    GitHub Pages configuration and status model.

    Represents GitHub Pages settings and deployment status.
    """

    # Pages configuration
    enabled: bool = Field(default=False, description="Whether Pages is enabled")
    url: Optional[str] = Field(default=None, description="Pages site URL")
    custom_domain: Optional[str] = Field(default=None, description="Custom domain")
    cname: Optional[str] = Field(default=None, description="CNAME record")

    # Source configuration
    source_branch: str = Field(default="gh-pages", description="Source branch")
    source_path: GitHubPagesSource = Field(
        default=GitHubPagesSource.ROOT, description="Source path"
    )

    # Build status
    status: GitHubPagesBuildStatus = Field(
        default=GitHubPagesBuildStatus.NULL, description="Build status"
    )
    build_type: Optional[str] = Field(
        default=None, description="Build type (legacy/workflow)"
    )

    # HTTPS settings
    https_enforced: bool = Field(default=False, description="Whether HTTPS is enforced")
    https_certificate: Optional[Dict[str, Any]] = Field(
        default=None, description="HTTPS certificate info"
    )

    # Build information
    last_build_time: Optional[datetime] = Field(
        default=None, description="Last build time"
    )
    last_build_commit: Optional[str] = Field(
        default=None, description="Last build commit hash"
    )
    last_build_message: Optional[str] = Field(
        default=None, description="Last build message"
    )

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    def is_building(self) -> bool:
        """Check if Pages is currently building."""
        return self.status == GitHubPagesBuildStatus.BUILDING

    def is_ready(self) -> bool:
        """Check if Pages is ready and accessible."""
        return self.enabled and self.status == GitHubPagesBuildStatus.BUILT

    def has_errors(self) -> bool:
        """Check if last build had errors."""
        return self.status == GitHubPagesBuildStatus.ERRORED

    def get_deployment_url(self) -> Optional[str]:
        """Get the deployment URL (custom domain or default)."""
        return self.custom_domain or self.url


class GitHubWebhook(BaseModel):
    """
    GitHub webhook model.

    Represents a GitHub webhook configuration and metadata.
    """

    # Webhook identification
    id: int = Field(..., description="Webhook ID")
    name: str = Field(default="web", description="Webhook name")
    url: str = Field(..., description="Webhook URL")

    # Webhook configuration
    events: List[GitHubWebhookEvent] = Field(..., description="Webhook events")
    active: bool = Field(default=True, description="Whether webhook is active")
    content_type: str = Field(default="json", description="Content type (json/form)")
    insecure_ssl: bool = Field(default=False, description="Whether to verify SSL")

    # Security
    secret: Optional[str] = Field(default=None, description="Webhook secret")

    # Metadata
    created_at: datetime = Field(..., description="Webhook creation date")
    updated_at: datetime = Field(..., description="Last update date")

    # Delivery statistics
    last_response: Optional[Dict[str, Any]] = Field(
        default=None, description="Last delivery response"
    )
    ping_url: Optional[str] = Field(default=None, description="Ping URL")
    test_url: Optional[str] = Field(default=None, description="Test URL")

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    @validator("url")
    def validate_url(cls, v):
        """Validate webhook URL format."""
        if not v or not v.strip():
            raise ValueError("Webhook URL cannot be empty")

        # Basic URL validation
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Webhook URL must start with http:// or https://")

        return v.strip()

    def handles_event(self, event: GitHubWebhookEvent) -> bool:
        """Check if webhook handles a specific event."""
        return event in self.events

    def is_secure(self) -> bool:
        """Check if webhook has security configured."""
        return bool(self.secret and not self.insecure_ssl)


class GitHubRelease(BaseModel):
    """
    GitHub release model.

    Represents a GitHub release with assets and metadata.
    """

    # Release identification
    id: int = Field(..., description="Release ID")
    node_id: str = Field(..., description="Release node ID")
    tag_name: str = Field(..., description="Git tag name")
    target_commitish: str = Field(default="main", description="Target branch/commit")
    name: Optional[str] = Field(default=None, description="Release name/title")

    # Release content
    body: Optional[str] = Field(default=None, description="Release description")
    draft: bool = Field(default=False, description="Whether release is a draft")
    prerelease: bool = Field(
        default=False, description="Whether release is a prerelease"
    )

    # URLs
    html_url: str = Field(..., description="Release web URL")
    upload_url: str = Field(..., description="Asset upload URL")
    tarball_url: str = Field(..., description="Tarball download URL")
    zipball_url: str = Field(..., description="Zipball download URL")

    # Release author
    author: GitHubUser = Field(..., description="Release author")

    # Assets
    assets: List[Dict[str, Any]] = Field(
        default_factory=list, description="Release assets"
    )
    assets_url: str = Field(..., description="Assets API URL")

    # Timestamps
    created_at: datetime = Field(..., description="Release creation date")
    published_at: Optional[datetime] = Field(
        default=None, description="Release publication date"
    )

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    @validator("tag_name")
    def validate_tag_name(cls, v):
        """Validate Git tag name format."""
        if not v or not v.strip():
            raise ValueError("Tag name cannot be empty")

        # Basic Git tag validation
        invalid_chars = " ~^:?*[]\\@{"
        if any(char in v for char in invalid_chars):
            raise ValueError(f"Tag name contains invalid characters: {invalid_chars}")

        return v.strip()

    def is_published(self) -> bool:
        """Check if release is published."""
        return not self.draft and self.published_at is not None

    def get_version(self) -> str:
        """Get semantic version from tag name."""
        # Remove common prefixes
        version = self.tag_name
        for prefix in ["v", "version-", "release-"]:
            if version.lower().startswith(prefix):
                version = version[len(prefix) :]
                break
        return version

    def get_download_count(self) -> int:
        """Get total download count for all assets."""
        return sum(asset.get("download_count", 0) for asset in self.assets)


class GitHubDeployKey(BaseModel):
    """
    GitHub deploy key model.

    Represents a deploy key for repository access.
    """

    # Key identification
    id: int = Field(..., description="Deploy key ID")
    title: str = Field(..., description="Deploy key title")
    key: str = Field(..., description="SSH public key")

    # Key permissions
    read_only: bool = Field(default=True, description="Whether key is read-only")
    verified: bool = Field(default=False, description="Whether key is verified")

    # URLs
    url: str = Field(..., description="Deploy key API URL")

    # Timestamps
    created_at: datetime = Field(..., description="Key creation date")
    last_used: Optional[datetime] = Field(default=None, description="Last usage date")

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    @validator("key")
    def validate_key(cls, v):
        """Validate SSH public key format."""
        if not v or not v.strip():
            raise ValueError("SSH key cannot be empty")

        # Basic SSH key validation
        key_prefixes = ["ssh-rsa", "ssh-dss", "ssh-ed25519", "ecdsa-sha2-"]
        if not any(v.startswith(prefix) for prefix in key_prefixes):
            raise ValueError("Invalid SSH public key format")

        return v.strip()

    def can_write(self) -> bool:
        """Check if deploy key has write access."""
        return not self.read_only

    def get_fingerprint(self) -> Optional[str]:
        """Get SSH key fingerprint (if available)."""
        # This would typically be computed from the key
        # For now, we'll return None as it's not always available
        return None


class GitHubOperationResult(BaseModel):
    """
    Base class for GitHub operation results.

    Represents the result of a GitHub API operation with status and metadata.
    """

    operation: str = Field(..., description="Operation name")
    status: GitHubOperationStatus = Field(..., description="Operation status")
    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(default="", description="Operation message")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    # API information
    api_endpoint: Optional[str] = Field(
        default=None, description="GitHub API endpoint used"
    )
    http_status: Optional[int] = Field(default=None, description="HTTP status code")
    rate_limit_remaining: Optional[int] = Field(
        default=None, description="API rate limit remaining"
    )
    rate_limit_reset: Optional[datetime] = Field(
        default=None, description="Rate limit reset time"
    )

    # Timing information
    started_at: datetime = Field(
        default_factory=datetime.now, description="Operation start time"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Operation completion time"
    )
    duration_seconds: Optional[float] = Field(
        default=None, description="Operation duration"
    )

    # Response data
    response_data: Optional[Dict[str, Any]] = Field(
        default=None, description="API response data"
    )

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    def mark_completed(self, success: bool = True, message: str = "") -> None:
        """Mark operation as completed."""
        self.completed_at = datetime.now()
        self.success = success
        self.status = (
            GitHubOperationStatus.SUCCESS if success else GitHubOperationStatus.FAILED
        )
        if message:
            self.message = message

        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()

    def is_rate_limited(self) -> bool:
        """Check if operation failed due to rate limiting."""
        return self.status == GitHubOperationStatus.RATE_LIMITED

    def is_unauthorized(self) -> bool:
        """Check if operation failed due to authorization."""
        return self.status == GitHubOperationStatus.UNAUTHORIZED


class RepositoryCreateResult(GitHubOperationResult):
    """Result of a repository creation operation."""

    repository: Optional[GitHubRepository] = Field(
        default=None, description="Created repository"
    )
    repository_url: Optional[str] = Field(default=None, description="Repository URL")
    clone_url: Optional[str] = Field(default=None, description="Repository clone URL")


class PagesConfigResult(GitHubOperationResult):
    """Result of a GitHub Pages configuration operation."""

    pages_config: Optional[GitHubPages] = Field(
        default=None, description="Pages configuration"
    )
    pages_url: Optional[str] = Field(default=None, description="Pages site URL")
    deployment_status: Optional[str] = Field(
        default=None, description="Deployment status"
    )


class WebhookCreateResult(GitHubOperationResult):
    """Result of a webhook creation operation."""

    webhook: Optional[GitHubWebhook] = Field(
        default=None, description="Created webhook"
    )
    webhook_id: Optional[int] = Field(default=None, description="Webhook ID")
    ping_successful: bool = Field(
        default=False, description="Whether ping test succeeded"
    )


class ReleaseCreateResult(GitHubOperationResult):
    """Result of a release creation operation."""

    release: Optional[GitHubRelease] = Field(
        default=None, description="Created release"
    )
    release_id: Optional[int] = Field(default=None, description="Release ID")
    release_url: Optional[str] = Field(default=None, description="Release URL")
    assets_uploaded: int = Field(default=0, description="Number of assets uploaded")


class DeployKeyCreateResult(GitHubOperationResult):
    """Result of a deploy key creation operation."""

    deploy_key: Optional[GitHubDeployKey] = Field(
        default=None, description="Created deploy key"
    )
    key_id: Optional[int] = Field(default=None, description="Deploy key ID")
    key_fingerprint: Optional[str] = Field(default=None, description="Key fingerprint")


class GitHubAPICredentials(BaseModel):
    """
    GitHub API credentials model.

    Represents authentication credentials for GitHub API access.
    """

    # Token authentication
    token: str = Field(..., description="GitHub Personal Access Token")
    token_type: str = Field(default="token", description="Token type (token/Bearer)")

    # Token metadata
    token_name: Optional[str] = Field(
        default=None, description="Token name/description"
    )
    scopes: List[str] = Field(default_factory=list, description="Token scopes")
    expires_at: Optional[datetime] = Field(
        default=None, description="Token expiration date"
    )

    # User information
    username: Optional[str] = Field(default=None, description="GitHub username")
    user_id: Optional[int] = Field(default=None, description="GitHub user ID")

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    @validator("token")
    def validate_token(cls, v):
        """Validate GitHub token format."""
        if not v or not v.strip():
            raise ValueError("GitHub token cannot be empty")

        # Basic GitHub token validation
        if len(v) < 20:
            raise ValueError("GitHub token appears to be too short")

        # GitHub tokens typically start with specific prefixes
        valid_prefixes = ["ghp_", "gho_", "ghu_", "ghs_", "ghr_"]
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            # Legacy tokens might not have prefixes, so just warn
            pass

        return v.strip()

    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

    def has_scope(self, scope: str) -> bool:
        """Check if token has a specific scope."""
        return scope in self.scopes

    def get_auth_header(self) -> Dict[str, str]:
        """Get authorization header for API requests."""
        return {"Authorization": f"{self.token_type} {self.token}"}


class GitHubRateLimitInfo(BaseModel):
    """
    GitHub API rate limit information.

    Represents current rate limit status and usage.
    """

    # Core API limits
    core_limit: int = Field(..., description="Core API rate limit")
    core_remaining: int = Field(..., description="Core API requests remaining")
    core_reset: datetime = Field(..., description="Core API reset time")
    core_used: int = Field(..., description="Core API requests used")

    # Search API limits
    search_limit: int = Field(..., description="Search API rate limit")
    search_remaining: int = Field(..., description="Search API requests remaining")
    search_reset: datetime = Field(..., description="Search API reset time")
    search_used: int = Field(..., description="Search API requests used")

    # GraphQL API limits
    graphql_limit: int = Field(..., description="GraphQL API rate limit")
    graphql_remaining: int = Field(..., description="GraphQL API requests remaining")
    graphql_reset: datetime = Field(..., description="GraphQL API reset time")
    graphql_used: int = Field(..., description="GraphQL API requests used")

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    def is_rate_limited(self, api_type: str = "core") -> bool:
        """Check if API is rate limited."""
        if api_type == "core":
            return self.core_remaining <= 0
        elif api_type == "search":
            return self.search_remaining <= 0
        elif api_type == "graphql":
            return self.graphql_remaining <= 0
        return False

    def time_until_reset(self, api_type: str = "core") -> int:
        """Get seconds until rate limit reset."""
        now = datetime.now()
        if api_type == "core":
            return max(0, int((self.core_reset - now).total_seconds()))
        elif api_type == "search":
            return max(0, int((self.search_reset - now).total_seconds()))
        elif api_type == "graphql":
            return max(0, int((self.graphql_reset - now).total_seconds()))
        return 0

    def get_usage_percentage(self, api_type: str = "core") -> float:
        """Get usage percentage for API type."""
        if api_type == "core":
            return (
                (self.core_used / self.core_limit) * 100 if self.core_limit > 0 else 0
            )
        elif api_type == "search":
            return (
                (self.search_used / self.search_limit) * 100
                if self.search_limit > 0
                else 0
            )
        elif api_type == "graphql":
            return (
                (self.graphql_used / self.graphql_limit) * 100
                if self.graphql_limit > 0
                else 0
            )
        return 0
