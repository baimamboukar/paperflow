"""
GitHub service for Paperflow.

This service provides comprehensive GitHub API operations for managing repositories,
GitHub Pages, webhooks, releases, and deploy keys with proper authentication,
rate limiting, and error handling.
"""

import asyncio
import secrets
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
import tempfile
import base64

from paperflow.services.base import BaseService
from paperflow.models.github import (
    GitHubRepository, GitHubPages, GitHubWebhook, GitHubRelease, 
    GitHubDeployKey, GitHubUser, GitHubAPICredentials, GitHubWebhookEvent,
    GitHubPagesSource, GitHubPagesBuildStatus, GitHubOperationStatus,
    GitHubOperationResult, RepositoryCreateResult, PagesConfigResult,
    WebhookCreateResult, ReleaseCreateResult, DeployKeyCreateResult
)
from paperflow.utils.github_utils import (
    GitHubAPIClient, GitHubAPIError, GitHubRateLimitError,
    GitHubAuthenticationError, GitHubValidationError,
    GitHubRepositoryValidator, GitHubWebhookValidator,
    GitHubPagesUtils, GitHubAPIUtils, GitHubRetryStrategy
)
from paperflow.utils.logging import setup_logging
from paperflow.config.settings import Settings

logger = setup_logging(__name__)


class GitHubService(BaseService):
    """
    Comprehensive GitHub service for API operations.
    
    Provides async GitHub operations with authentication, rate limiting,
    and comprehensive error handling for the Paperflow ecosystem.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize GitHub service.
        
        Args:
            settings: Service configuration settings
        """
        super().__init__(settings)
        self._api_client: Optional[GitHubAPIClient] = None
        self._credentials: Optional[GitHubAPICredentials] = None
        self._retry_strategy = GitHubRetryStrategy()
    
    def _perform_initialization(self) -> None:
        """Perform GitHub service initialization."""
        # Load GitHub credentials from settings if available
        if self.settings:
            github_token = getattr(self.settings, 'github_token', None)
            github_username = getattr(self.settings, 'github_username', None)
            
            if github_token:
                self._credentials = GitHubAPICredentials(
                    token=github_token,
                    username=github_username
                )
                logger.info("GitHub service initialized with token authentication")
            else:
                logger.warning("GitHub service initialized without credentials")
        else:
            logger.warning("GitHub service initialized without settings")
    
    def _perform_cleanup(self) -> None:
        """Perform GitHub service cleanup."""
        if self._api_client:
            asyncio.create_task(self._api_client.close())
            self._api_client = None
        logger.info("GitHub service cleaned up")
    
    async def _get_api_client(self) -> GitHubAPIClient:
        """Get or create GitHub API client."""
        if not self._credentials:
            raise GitHubAuthenticationError("No GitHub credentials configured")
        
        if not self._api_client:
            self._api_client = GitHubAPIClient(self._credentials)
        
        return self._api_client
    
    def set_credentials(self, credentials: GitHubAPICredentials) -> None:
        """
        Set GitHub API credentials.
        
        Args:
            credentials: GitHub API credentials
        """
        self._credentials = credentials
        
        # Close existing client to force recreation with new credentials
        if self._api_client:
            asyncio.create_task(self._api_client.close())
            self._api_client = None
        
        logger.info(f"GitHub credentials updated for user: {credentials.username or 'unknown'}")
    
    async def test_authentication(self) -> GitHubOperationResult:
        """
        Test GitHub API authentication.
        
        Returns:
            GitHubOperationResult with authentication test results
        """
        result = GitHubOperationResult(
            operation="test_auth",
            status=GitHubOperationStatus.PENDING,
            success=False
        )
        
        try:
            client = await self._get_api_client()
            
            async with client:
                user = await client.get_authenticated_user()
                
                result.mark_completed(
                    True, 
                    f"Authentication successful for user: {user.login}"
                )
                result.response_data = {
                    "user": user.dict(),
                    "authenticated": True
                }
                
                logger.info(f"GitHub authentication test successful for: {user.login}")
                
        except GitHubAuthenticationError as e:
            result.error = str(e)
            result.status = GitHubOperationStatus.UNAUTHORIZED
            result.mark_completed(False, "Authentication failed")
            logger.error(f"GitHub authentication failed: {e}")
            
        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Authentication test failed: {e}")
            logger.error(f"GitHub authentication test error: {e}")
        
        return result
    
    # Repository Management
    
    async def create_repository(
        self,
        name: str,
        description: Optional[str] = None,
        private: bool = False,
        auto_init: bool = True,
        gitignore_template: Optional[str] = None,
        license_template: Optional[str] = None,
        homepage: Optional[str] = None,
        has_issues: bool = True,
        has_projects: bool = True,
        has_wiki: bool = True,
        has_pages: bool = False,
        is_template: bool = False,
        org_name: Optional[str] = None,
        topics: Optional[List[str]] = None
    ) -> RepositoryCreateResult:
        """
        Create a new GitHub repository.
        
        Args:
            name: Repository name
            description: Repository description
            private: Whether repository should be private
            auto_init: Initialize with README
            gitignore_template: Gitignore template name
            license_template: License template name
            homepage: Repository homepage URL
            has_issues: Enable issues
            has_projects: Enable projects
            has_wiki: Enable wiki
            has_pages: Enable GitHub Pages
            is_template: Mark as template repository
            org_name: Organization name (if creating in org)
            topics: Repository topics
            
        Returns:
            RepositoryCreateResult with operation details
        """
        result = RepositoryCreateResult(
            operation="create_repository",
            status=GitHubOperationStatus.PENDING,
            success=False
        )
        
        try:
            # Validate repository name
            is_valid, error_msg = GitHubRepositoryValidator.validate_repository_name(name)
            if not is_valid:
                result.error = error_msg
                result.mark_completed(False, f"Invalid repository name: {error_msg}")
                return result
            
            # Validate topics if provided
            if topics:
                for topic in topics:
                    is_valid, error_msg = GitHubRepositoryValidator.validate_topic(topic)
                    if not is_valid:
                        result.error = f"Invalid topic '{topic}': {error_msg}"
                        result.mark_completed(False, result.error)
                        return result
            
            client = await self._get_api_client()
            
            async with client:
                # Create repository
                repository = await client.create_repository(
                    name=name,
                    description=description,
                    private=private,
                    auto_init=auto_init,
                    gitignore_template=gitignore_template,
                    license_template=license_template,
                    homepage=homepage,
                    has_issues=has_issues,
                    has_projects=has_projects,
                    has_wiki=has_wiki,
                    is_template=is_template,
                    org_name=org_name
                )
                
                # Add topics if provided
                if topics:
                    await self._update_repository_topics(
                        repository.owner.login, 
                        repository.name, 
                        topics,
                        client
                    )
                
                # Enable GitHub Pages if requested
                if has_pages:
                    await self._enable_github_pages(
                        repository.owner.login,
                        repository.name,
                        client
                    )
                
                result.repository = repository
                result.repository_url = repository.html_url
                result.clone_url = repository.clone_url
                
                result.mark_completed(
                    True, 
                    f"Successfully created repository: {repository.full_name}"
                )
                
                logger.info(f"Created GitHub repository: {repository.full_name}")
                
        except GitHubValidationError as e:
            result.error = f"Validation error: {e.message}"
            result.mark_completed(False, result.error)
            logger.error(f"Repository creation validation error: {e}")
            
        except GitHubAPIError as e:
            result.error = str(e)
            result.http_status = e.status_code
            result.mark_completed(False, f"Repository creation failed: {e}")
            logger.error(f"Repository creation API error: {e}")
            
        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Repository creation failed: {e}")
            logger.error(f"Repository creation error: {e}")
        
        return result
    
    async def get_repository(self, owner: str, repo: str) -> Optional[GitHubRepository]:
        """
        Get repository information.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            GitHubRepository object or None if not found
        """
        try:
            client = await self._get_api_client()
            
            async with client:
                repository = await client.get_repository(owner, repo)
                logger.info(f"Retrieved repository info: {repository.full_name}")
                return repository
                
        except GitHubAPIError as e:
            if e.status_code == 404:
                logger.warning(f"Repository not found: {owner}/{repo}")
            else:
                logger.error(f"Failed to get repository {owner}/{repo}: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting repository {owner}/{repo}: {e}")
            return None
    
    async def list_repositories(
        self,
        username: Optional[str] = None,
        org_name: Optional[str] = None,
        repo_type: str = "all",
        sort: str = "updated",
        per_page: int = 30
    ) -> List[GitHubRepository]:
        """
        List repositories for user or organization.
        
        Args:
            username: Username to list repos for (None for authenticated user)
            org_name: Organization name to list repos for
            repo_type: Repository type filter
            sort: Sort order
            per_page: Results per page
            
        Returns:
            List of GitHubRepository objects
        """
        try:
            client = await self._get_api_client()
            
            async with client:
                if org_name:
                    repositories = await client.list_organization_repositories(
                        org_name=org_name,
                        repo_type=repo_type,
                        sort=sort,
                        per_page=per_page
                    )
                    logger.info(f"Listed {len(repositories)} repositories for org: {org_name}")
                else:
                    repositories = await client.list_user_repositories(
                        username=username,
                        repo_type=repo_type,
                        sort=sort,
                        per_page=per_page
                    )
                    user_desc = username or "authenticated user"
                    logger.info(f"Listed {len(repositories)} repositories for user: {user_desc}")
                
                return repositories
                
        except Exception as e:
            logger.error(f"Error listing repositories: {e}")
            return []
    
    async def delete_repository(self, owner: str, repo: str) -> GitHubOperationResult:
        """
        Delete a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            GitHubOperationResult with operation details
        """
        result = GitHubOperationResult(
            operation="delete_repository",
            status=GitHubOperationStatus.PENDING,
            success=False
        )
        
        try:
            client = await self._get_api_client()
            
            async with client:
                success = await client.delete_repository(owner, repo)
                
                if success:
                    result.mark_completed(True, f"Successfully deleted repository: {owner}/{repo}")
                    logger.info(f"Deleted repository: {owner}/{repo}")
                else:
                    result.error = "Repository deletion failed"
                    result.mark_completed(False, result.error)
                    logger.error(f"Failed to delete repository: {owner}/{repo}")
                
        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Repository deletion failed: {e}")
            logger.error(f"Repository deletion error: {e}")
        
        return result
    
    # GitHub Pages Management
    
    async def setup_github_pages(
        self,
        owner: str,
        repo: str,
        source_branch: str = "gh-pages",
        source_path: GitHubPagesSource = GitHubPagesSource.ROOT,
        custom_domain: Optional[str] = None,
        enforce_https: bool = True
    ) -> PagesConfigResult:
        """
        Setup GitHub Pages for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            source_branch: Source branch for Pages
            source_path: Source path in branch
            custom_domain: Custom domain name
            enforce_https: Whether to enforce HTTPS
            
        Returns:
            PagesConfigResult with operation details
        """
        result = PagesConfigResult(
            operation="setup_pages",
            status=GitHubOperationStatus.PENDING,
            success=False
        )
        
        try:
            # Validate custom domain if provided
            if custom_domain:
                is_valid, error_msg = GitHubPagesUtils.validate_custom_domain(custom_domain)
                if not is_valid:
                    result.error = error_msg
                    result.mark_completed(False, f"Invalid custom domain: {error_msg}")
                    return result
            
            client = await self._get_api_client()
            
            async with client:
                # Enable GitHub Pages
                pages_data = {
                    "source": {
                        "branch": source_branch,
                        "path": source_path.value
                    }
                }
                
                if custom_domain:
                    pages_data["cname"] = custom_domain
                
                if enforce_https:
                    pages_data["https_enforced"] = True
                
                # Make API call to enable Pages
                status_code, response_data, headers = await client._make_request(
                    "POST",
                    f"/repos/{owner}/{repo}/pages",
                    data=pages_data
                )
                
                # Get Pages configuration
                pages_config = await self.get_github_pages_config(owner, repo)
                
                result.pages_config = pages_config
                result.pages_url = GitHubPagesUtils.get_default_pages_url(owner, repo)
                result.deployment_status = "enabled"
                
                # Create CNAME file if custom domain is set
                if custom_domain and pages_config:
                    await self._create_cname_file(owner, repo, custom_domain, client)
                
                result.mark_completed(
                    True,
                    f"Successfully set up GitHub Pages for {owner}/{repo}"
                )
                
                logger.info(f"Set up GitHub Pages for {owner}/{repo}")
                
        except GitHubAPIError as e:
            result.error = str(e)
            result.http_status = e.status_code
            result.mark_completed(False, f"Pages setup failed: {e}")
            logger.error(f"GitHub Pages setup error: {e}")
            
        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Pages setup failed: {e}")
            logger.error(f"GitHub Pages setup error: {e}")
        
        return result
    
    async def get_github_pages_config(self, owner: str, repo: str) -> Optional[GitHubPages]:
        """
        Get GitHub Pages configuration for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            GitHubPages configuration or None if not enabled
        """
        try:
            client = await self._get_api_client()
            
            async with client:
                status_code, data, _ = await client._make_request(
                    "GET",
                    f"/repos/{owner}/{repo}/pages"
                )
                
                if status_code == 200:
                    # Parse GitHub Pages data
                    pages_config = GitHubPages(
                        enabled=True,
                        url=data.get("html_url"),
                        custom_domain=data.get("cname"),
                        source_branch=data.get("source", {}).get("branch", "gh-pages"),
                        source_path=GitHubPagesSource(data.get("source", {}).get("path", "/")),
                        status=GitHubPagesBuildStatus(data.get("status", "null")),
                        https_enforced=data.get("https_enforced", False)
                    )
                    
                    logger.info(f"Retrieved GitHub Pages config for {owner}/{repo}")
                    return pages_config
                
                return None
                
        except GitHubAPIError as e:
            if e.status_code == 404:
                logger.info(f"GitHub Pages not enabled for {owner}/{repo}")
            else:
                logger.error(f"Failed to get Pages config for {owner}/{repo}: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting Pages config for {owner}/{repo}: {e}")
            return None
    
    # Webhook Management
    
    async def create_webhook(
        self,
        owner: str,
        repo: str,
        webhook_url: str,
        events: List[GitHubWebhookEvent],
        secret: Optional[str] = None,
        content_type: str = "json",
        insecure_ssl: bool = False,
        active: bool = True
    ) -> WebhookCreateResult:
        """
        Create a webhook for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            webhook_url: Webhook payload URL
            events: List of events to subscribe to
            secret: Webhook secret for signature verification
            content_type: Content type for webhook payloads
            insecure_ssl: Whether to verify SSL certificates
            active: Whether webhook is active
            
        Returns:
            WebhookCreateResult with operation details
        """
        result = WebhookCreateResult(
            operation="create_webhook",
            status=GitHubOperationStatus.PENDING,
            success=False
        )
        
        try:
            # Generate secret if not provided
            if not secret:
                secret = secrets.token_urlsafe(32)
            
            client = await self._get_api_client()
            
            async with client:
                webhook_data = {
                    "name": "web",
                    "config": {
                        "url": webhook_url,
                        "content_type": content_type,
                        "secret": secret,
                        "insecure_ssl": "1" if insecure_ssl else "0"
                    },
                    "events": [event.value for event in events],
                    "active": active
                }
                
                status_code, response_data, _ = await client._make_request(
                    "POST",
                    f"/repos/{owner}/{repo}/hooks",
                    data=webhook_data
                )
                
                if status_code == 201:
                    # Create webhook object
                    webhook = GitHubWebhook(
                        id=response_data["id"],
                        url=webhook_url,
                        events=events,
                        active=active,
                        content_type=content_type,
                        insecure_ssl=insecure_ssl,
                        secret=secret,
                        created_at=datetime.fromisoformat(response_data["created_at"].replace("Z", "+00:00")),
                        updated_at=datetime.fromisoformat(response_data["updated_at"].replace("Z", "+00:00"))
                    )
                    
                    result.webhook = webhook
                    result.webhook_id = webhook.id
                    
                    # Test webhook with ping
                    ping_result = await self._ping_webhook(owner, repo, webhook.id, client)
                    result.ping_successful = ping_result
                    
                    result.mark_completed(
                        True,
                        f"Successfully created webhook for {owner}/{repo}"
                    )
                    
                    logger.info(f"Created webhook for {owner}/{repo}: {webhook.id}")
                
        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Webhook creation failed: {e}")
            logger.error(f"Webhook creation error: {e}")
        
        return result
    
    async def list_webhooks(self, owner: str, repo: str) -> List[GitHubWebhook]:
        """
        List webhooks for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            List of GitHubWebhook objects
        """
        try:
            client = await self._get_api_client()
            
            async with client:
                status_code, data, _ = await client._make_request(
                    "GET",
                    f"/repos/{owner}/{repo}/hooks"
                )
                
                if status_code == 200:
                    webhooks = []
                    for hook_data in data:
                        webhook = GitHubWebhook(
                            id=hook_data["id"],
                            name=hook_data.get("name", "web"),
                            url=hook_data["config"]["url"],
                            events=[GitHubWebhookEvent(event) for event in hook_data["events"]],
                            active=hook_data["active"],
                            content_type=hook_data["config"].get("content_type", "json"),
                            insecure_ssl=hook_data["config"].get("insecure_ssl") == "1",
                            created_at=datetime.fromisoformat(hook_data["created_at"].replace("Z", "+00:00")),
                            updated_at=datetime.fromisoformat(hook_data["updated_at"].replace("Z", "+00:00"))
                        )
                        webhooks.append(webhook)
                    
                    logger.info(f"Listed {len(webhooks)} webhooks for {owner}/{repo}")
                    return webhooks
                
                return []
                
        except Exception as e:
            logger.error(f"Error listing webhooks for {owner}/{repo}: {e}")
            return []
    
    async def delete_webhook(self, owner: str, repo: str, webhook_id: int) -> GitHubOperationResult:
        """
        Delete a webhook.
        
        Args:
            owner: Repository owner
            repo: Repository name
            webhook_id: Webhook ID to delete
            
        Returns:
            GitHubOperationResult with operation details
        """
        result = GitHubOperationResult(
            operation="delete_webhook",
            status=GitHubOperationStatus.PENDING,
            success=False
        )
        
        try:
            client = await self._get_api_client()
            
            async with client:
                status_code, _, _ = await client._make_request(
                    "DELETE",
                    f"/repos/{owner}/{repo}/hooks/{webhook_id}"
                )
                
                if status_code == 204:
                    result.mark_completed(True, f"Successfully deleted webhook {webhook_id}")
                    logger.info(f"Deleted webhook {webhook_id} for {owner}/{repo}")
                else:
                    result.error = f"Failed to delete webhook (status: {status_code})"
                    result.mark_completed(False, result.error)
                
        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Webhook deletion failed: {e}")
            logger.error(f"Webhook deletion error: {e}")
        
        return result
    
    # Release Management
    
    async def create_release(
        self,
        owner: str,
        repo: str,
        tag_name: str,
        target_commitish: str = "main",
        name: Optional[str] = None,
        body: Optional[str] = None,
        draft: bool = False,
        prerelease: bool = False,
        assets: Optional[List[Path]] = None
    ) -> ReleaseCreateResult:
        """
        Create a release for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            tag_name: Git tag name for the release
            target_commitish: Target branch or commit
            name: Release name
            body: Release description
            draft: Whether release is a draft
            prerelease: Whether release is a prerelease
            assets: List of asset file paths to upload
            
        Returns:
            ReleaseCreateResult with operation details
        """
        result = ReleaseCreateResult(
            operation="create_release",
            status=GitHubOperationStatus.PENDING,
            success=False
        )
        
        try:
            client = await self._get_api_client()
            
            async with client:
                release_data = {
                    "tag_name": tag_name,
                    "target_commitish": target_commitish,
                    "draft": draft,
                    "prerelease": prerelease
                }
                
                if name:
                    release_data["name"] = name
                if body:
                    release_data["body"] = body
                
                status_code, response_data, _ = await client._make_request(
                    "POST",
                    f"/repos/{owner}/{repo}/releases",
                    data=release_data
                )
                
                if status_code == 201:
                    # Create release object
                    release = GitHubRelease(
                        id=response_data["id"],
                        node_id=response_data["node_id"],
                        tag_name=response_data["tag_name"],
                        target_commitish=response_data["target_commitish"],
                        name=response_data.get("name"),
                        body=response_data.get("body"),
                        draft=response_data["draft"],
                        prerelease=response_data["prerelease"],
                        html_url=response_data["html_url"],
                        upload_url=response_data["upload_url"],
                        tarball_url=response_data["tarball_url"],
                        zipball_url=response_data["zipball_url"],
                        author=GitHubUser(**response_data["author"]),
                        assets_url=response_data["assets_url"],
                        created_at=datetime.fromisoformat(response_data["created_at"].replace("Z", "+00:00")),
                        published_at=datetime.fromisoformat(response_data["published_at"].replace("Z", "+00:00")) if response_data.get("published_at") else None
                    )
                    
                    result.release = release
                    result.release_id = release.id
                    result.release_url = release.html_url
                    
                    # Upload assets if provided
                    if assets:
                        uploaded_count = await self._upload_release_assets(
                            release, assets, client
                        )
                        result.assets_uploaded = uploaded_count
                    
                    result.mark_completed(
                        True,
                        f"Successfully created release {tag_name} for {owner}/{repo}"
                    )
                    
                    logger.info(f"Created release {tag_name} for {owner}/{repo}")
                
        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Release creation failed: {e}")
            logger.error(f"Release creation error: {e}")
        
        return result
    
    # Deploy Key Management
    
    async def create_deploy_key(
        self,
        owner: str,
        repo: str,
        title: str,
        key: str,
        read_only: bool = True
    ) -> DeployKeyCreateResult:
        """
        Create a deploy key for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            title: Deploy key title
            key: SSH public key
            read_only: Whether key is read-only
            
        Returns:
            DeployKeyCreateResult with operation details
        """
        result = DeployKeyCreateResult(
            operation="create_deploy_key",
            status=GitHubOperationStatus.PENDING,
            success=False
        )
        
        try:
            client = await self._get_api_client()
            
            async with client:
                key_data = {
                    "title": title,
                    "key": key,
                    "read_only": read_only
                }
                
                status_code, response_data, _ = await client._make_request(
                    "POST",
                    f"/repos/{owner}/{repo}/keys",
                    data=key_data
                )
                
                if status_code == 201:
                    # Create deploy key object
                    deploy_key = GitHubDeployKey(
                        id=response_data["id"],
                        title=response_data["title"],
                        key=response_data["key"],
                        read_only=response_data["read_only"],
                        verified=response_data.get("verified", False),
                        url=response_data["url"],
                        created_at=datetime.fromisoformat(response_data["created_at"].replace("Z", "+00:00"))
                    )
                    
                    result.deploy_key = deploy_key
                    result.key_id = deploy_key.id
                    
                    result.mark_completed(
                        True,
                        f"Successfully created deploy key '{title}' for {owner}/{repo}"
                    )
                    
                    logger.info(f"Created deploy key '{title}' for {owner}/{repo}")
                
        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Deploy key creation failed: {e}")
            logger.error(f"Deploy key creation error: {e}")
        
        return result
    
    # Branch Protection
    
    async def setup_branch_protection(
        self,
        owner: str,
        repo: str,
        branch: str,
        required_status_checks: Optional[List[str]] = None,
        enforce_admins: bool = False,
        required_pull_request_reviews: bool = True,
        dismiss_stale_reviews: bool = True,
        require_code_owner_reviews: bool = False,
        required_approving_review_count: int = 1
    ) -> GitHubOperationResult:
        """
        Setup branch protection rules.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name to protect
            required_status_checks: List of required status checks
            enforce_admins: Whether to enforce rules for admins
            required_pull_request_reviews: Require PR reviews
            dismiss_stale_reviews: Dismiss stale reviews
            require_code_owner_reviews: Require code owner reviews
            required_approving_review_count: Number of required reviews
            
        Returns:
            GitHubOperationResult with operation details
        """
        result = GitHubOperationResult(
            operation="setup_branch_protection",
            status=GitHubOperationStatus.PENDING,
            success=False
        )
        
        try:
            client = await self._get_api_client()
            
            async with client:
                protection_data = {
                    "required_status_checks": {
                        "strict": True,
                        "contexts": required_status_checks or []
                    } if required_status_checks else None,
                    "enforce_admins": enforce_admins,
                    "required_pull_request_reviews": {
                        "dismiss_stale_reviews": dismiss_stale_reviews,
                        "require_code_owner_reviews": require_code_owner_reviews,
                        "required_approving_review_count": required_approving_review_count
                    } if required_pull_request_reviews else None,
                    "restrictions": None  # No restrictions on who can push
                }
                
                status_code, _, _ = await client._make_request(
                    "PUT",
                    f"/repos/{owner}/{repo}/branches/{branch}/protection",
                    data=protection_data
                )
                
                if status_code == 200:
                    result.mark_completed(
                        True,
                        f"Successfully set up branch protection for {branch}"
                    )
                    logger.info(f"Set up branch protection for {owner}/{repo}:{branch}")
                else:
                    result.error = f"Failed to set up branch protection (status: {status_code})"
                    result.mark_completed(False, result.error)
                
        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Branch protection setup failed: {e}")
            logger.error(f"Branch protection setup error: {e}")
        
        return result
    
    # Helper Methods
    
    async def _update_repository_topics(
        self,
        owner: str,
        repo: str,
        topics: List[str],
        client: GitHubAPIClient
    ) -> bool:
        """Update repository topics."""
        try:
            status_code, _, _ = await client._make_request(
                "PUT",
                f"/repos/{owner}/{repo}/topics",
                data={"names": topics}
            )
            return status_code == 200
        except Exception as e:
            logger.warning(f"Failed to update topics for {owner}/{repo}: {e}")
            return False
    
    async def _enable_github_pages(
        self,
        owner: str,
        repo: str,
        client: GitHubAPIClient
    ) -> bool:
        """Enable GitHub Pages for repository."""
        try:
            pages_data = {
                "source": {
                    "branch": "gh-pages",
                    "path": "/"
                }
            }
            
            status_code, _, _ = await client._make_request(
                "POST",
                f"/repos/{owner}/{repo}/pages",
                data=pages_data
            )
            return status_code == 201
        except Exception as e:
            logger.warning(f"Failed to enable Pages for {owner}/{repo}: {e}")
            return False
    
    async def _create_cname_file(
        self,
        owner: str,
        repo: str,
        domain: str,
        client: GitHubAPIClient
    ) -> bool:
        """Create CNAME file for custom domain."""
        try:
            cname_content = GitHubPagesUtils.generate_cname_content(domain)
            encoded_content = base64.b64encode(cname_content.encode()).decode()
            
            file_data = {
                "message": f"Add CNAME for {domain}",
                "content": encoded_content,
                "branch": "gh-pages"
            }
            
            status_code, _, _ = await client._make_request(
                "PUT",
                f"/repos/{owner}/{repo}/contents/CNAME",
                data=file_data
            )
            return status_code == 201
        except Exception as e:
            logger.warning(f"Failed to create CNAME file for {owner}/{repo}: {e}")
            return False
    
    async def _ping_webhook(
        self,
        owner: str,
        repo: str,
        webhook_id: int,
        client: GitHubAPIClient
    ) -> bool:
        """Ping webhook to test connectivity."""
        try:
            status_code, _, _ = await client._make_request(
                "POST",
                f"/repos/{owner}/{repo}/hooks/{webhook_id}/pings"
            )
            return status_code == 204
        except Exception as e:
            logger.warning(f"Failed to ping webhook {webhook_id}: {e}")
            return False
    
    async def _upload_release_assets(
        self,
        release: GitHubRelease,
        asset_paths: List[Path],
        client: GitHubAPIClient
    ) -> int:
        """Upload assets to a release."""
        uploaded_count = 0
        
        for asset_path in asset_paths:
            try:
                if not asset_path.exists():
                    logger.warning(f"Asset file not found: {asset_path}")
                    continue
                
                # Read file content
                with open(asset_path, 'rb') as f:
                    asset_data = f.read()
                
                # Prepare upload URL
                upload_url = release.upload_url.replace("{?name,label}", f"?name={asset_path.name}")
                
                # Upload asset
                status_code, _, _ = await client._make_request(
                    "POST",
                    upload_url,
                    data=asset_data,
                    headers={"Content-Type": "application/octet-stream"}
                )
                
                if status_code == 201:
                    uploaded_count += 1
                    logger.info(f"Uploaded release asset: {asset_path.name}")
                else:
                    logger.warning(f"Failed to upload asset {asset_path.name}: status {status_code}")
                    
            except Exception as e:
                logger.error(f"Error uploading asset {asset_path}: {e}")
        
        return uploaded_count
    
    # Utility Methods
    
    async def validate_webhook_payload(
        self,
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """
        Validate webhook payload signature.
        
        Args:
            payload: Webhook payload bytes
            signature: Signature header value
            secret: Webhook secret
            
        Returns:
            True if signature is valid
        """
        return GitHubWebhookValidator.validate_webhook_signature(
            payload, signature, secret
        )
    
    def parse_webhook_payload(self, payload: str) -> Dict[str, Any]:
        """
        Parse webhook payload JSON.
        
        Args:
            payload: JSON payload string
            
        Returns:
            Parsed payload data
        """
        return GitHubWebhookValidator.parse_webhook_payload(payload)
    
    async def get_rate_limit_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current API rate limit information.
        
        Returns:
            Rate limit information or None if unavailable
        """
        try:
            client = await self._get_api_client()
            
            async with client:
                rate_limit_info = await client.get_rate_limit_info()
                
                if rate_limit_info:
                    return {
                        "core": {
                            "limit": rate_limit_info.core_limit,
                            "remaining": rate_limit_info.core_remaining,
                            "reset": rate_limit_info.core_reset.isoformat(),
                            "used": rate_limit_info.core_used
                        },
                        "search": {
                            "limit": rate_limit_info.search_limit,
                            "remaining": rate_limit_info.search_remaining,
                            "reset": rate_limit_info.search_reset.isoformat(),
                            "used": rate_limit_info.search_used
                        }
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting rate limit info: {e}")
            return None
    
    def extract_repo_info_from_url(self, github_url: str) -> Optional[Dict[str, str]]:
        """
        Extract repository information from GitHub URL.
        
        Args:
            github_url: GitHub repository URL
            
        Returns:
            Dictionary with repository info or None if invalid
        """
        return GitHubAPIUtils.extract_repo_info_from_remote(github_url)