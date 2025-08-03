"""
GitHub utilities for Paperflow.

This module provides utility functions and classes for GitHub API operations,
including authentication, rate limiting, error handling, and webhook validation.
"""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from urllib.parse import urljoin, urlparse
import re

import httpx
from pydantic import BaseModel, Field, validator

from paperflow.models.github import (
    GitHubAPICredentials, GitHubRateLimitInfo, GitHubOperationStatus,
    GitHubUser, GitHubRepository, GitHubPages, GitHubWebhook,
    GitHubRelease, GitHubDeployKey
)
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class GitHubRateLimitError(GitHubAPIError):
    """Exception raised when GitHub API rate limit is exceeded."""
    
    def __init__(self, reset_time: Optional[datetime] = None):
        self.reset_time = reset_time
        message = "GitHub API rate limit exceeded"
        if reset_time:
            message += f". Resets at {reset_time.isoformat()}"
        super().__init__(message, status_code=403)


class GitHubAuthenticationError(GitHubAPIError):
    """Exception raised for GitHub authentication errors."""
    
    def __init__(self, message: str = "GitHub authentication failed"):
        super().__init__(message, status_code=401)


class GitHubValidationError(GitHubAPIError):
    """Exception raised for GitHub API validation errors."""
    
    def __init__(self, message: str, errors: Optional[List[Dict]] = None):
        super().__init__(message, status_code=422)
        self.errors = errors or []


class GitHubAPIClient:
    """
    Async GitHub API client with authentication and rate limiting.
    
    Provides a comprehensive interface to the GitHub REST API v4 with
    automatic retry logic, rate limit handling, and proper authentication.
    """
    
    BASE_URL = "https://api.github.com"
    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    
    def __init__(self, credentials: GitHubAPICredentials, timeout: float = DEFAULT_TIMEOUT):
        """
        Initialize GitHub API client.
        
        Args:
            credentials: GitHub API credentials
            timeout: Request timeout in seconds
        """
        self.credentials = credentials
        self.timeout = timeout
        self._session: Optional[httpx.AsyncClient] = None
        self._rate_limit_info: Optional[GitHubRateLimitInfo] = None
        self._last_rate_limit_check = datetime.now()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self) -> None:
        """Ensure HTTP session is initialized."""
        if not self._session:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Paperflow/1.0",
                **self.credentials.get_auth_header()
            }
            
            self._session = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True
            )
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.aclose()
            self._session = None
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        """
        Make HTTP request to GitHub API with retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base URL)
            params: Query parameters
            data: Request body data
            files: File uploads
            headers: Additional headers
            
        Returns:
            Tuple of (status_code, response_data, response_headers)
            
        Raises:
            GitHubAPIError: For API errors
            GitHubRateLimitError: For rate limit errors
            GitHubAuthenticationError: For auth errors
        """
        await self._ensure_session()
        
        # Check rate limits before making request
        await self._check_rate_limits()
        
        # Prepare request
        url = endpoint if endpoint.startswith("http") else f"/{endpoint.lstrip('/')}"
        request_headers = headers or {}
        
        # Prepare request data
        request_kwargs = {
            "method": method,
            "url": url,
            "params": params or {},
            "headers": request_headers
        }
        
        if data:
            if files:
                # Multipart form data
                request_kwargs["data"] = data
                request_kwargs["files"] = files
            else:
                # JSON data
                request_kwargs["json"] = data
        
        # Retry logic
        last_exception = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = await self._session.request(**request_kwargs)
                
                # Update rate limit info
                self._update_rate_limit_info(response.headers)
                
                # Parse response
                try:
                    response_data = response.json() if response.content else {}
                except json.JSONDecodeError:
                    response_data = {"content": response.text}
                
                # Handle different status codes
                if response.status_code == 200 or response.status_code == 201:
                    logger.debug(f"GitHub API request successful: {method} {url}")
                    return response.status_code, response_data, dict(response.headers)
                
                elif response.status_code == 204:
                    # No content
                    return response.status_code, {}, dict(response.headers)
                
                elif response.status_code == 401:
                    raise GitHubAuthenticationError("Invalid GitHub credentials")
                
                elif response.status_code == 403:
                    # Check if it's a rate limit error
                    if "rate limit" in response_data.get("message", "").lower():
                        reset_time = self._parse_rate_limit_reset(response.headers)
                        raise GitHubRateLimitError(reset_time)
                    else:
                        raise GitHubAPIError(
                            f"GitHub API access forbidden: {response_data.get('message', 'Unknown error')}",
                            status_code=403,
                            response_data=response_data
                        )
                
                elif response.status_code == 404:
                    raise GitHubAPIError(
                        f"GitHub resource not found: {response_data.get('message', 'Not found')}",
                        status_code=404,
                        response_data=response_data
                    )
                
                elif response.status_code == 422:
                    errors = response_data.get("errors", [])
                    message = response_data.get("message", "Validation failed")
                    raise GitHubValidationError(message, errors)
                
                elif response.status_code >= 500:
                    # Server error - retry
                    error_msg = f"GitHub API server error: {response.status_code}"
                    logger.warning(f"{error_msg} (attempt {attempt + 1}/{self.MAX_RETRIES + 1})")
                    
                    if attempt < self.MAX_RETRIES:
                        await asyncio.sleep(self.RETRY_DELAY * (2 ** attempt))
                        continue
                    else:
                        raise GitHubAPIError(error_msg, status_code=response.status_code)
                
                else:
                    # Other client errors
                    raise GitHubAPIError(
                        f"GitHub API error: {response_data.get('message', 'Unknown error')}",
                        status_code=response.status_code,
                        response_data=response_data
                    )
            
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exception = e
                logger.warning(f"GitHub API request failed (attempt {attempt + 1}/{self.MAX_RETRIES + 1}): {e}")
                
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY * (2 ** attempt))
                    continue
        
        # All retries failed
        raise GitHubAPIError(f"GitHub API request failed after {self.MAX_RETRIES + 1} attempts: {last_exception}")
    
    def _update_rate_limit_info(self, headers: Dict[str, str]) -> None:
        """Update rate limit information from response headers."""
        try:
            # Core API limits
            core_limit = int(headers.get("x-ratelimit-limit", 5000))
            core_remaining = int(headers.get("x-ratelimit-remaining", 5000))
            core_reset = datetime.fromtimestamp(int(headers.get("x-ratelimit-reset", time.time())))
            core_used = int(headers.get("x-ratelimit-used", 0))
            
            # Search API limits (if available)
            search_limit = int(headers.get("x-ratelimit-limit-search", 30))
            search_remaining = int(headers.get("x-ratelimit-remaining-search", 30))
            search_reset = datetime.fromtimestamp(int(headers.get("x-ratelimit-reset-search", time.time())))
            search_used = int(headers.get("x-ratelimit-used-search", 0))
            
            # GraphQL API limits (default values)
            graphql_limit = 5000
            graphql_remaining = 5000
            graphql_reset = datetime.now() + timedelta(hours=1)
            graphql_used = 0
            
            self._rate_limit_info = GitHubRateLimitInfo(
                core_limit=core_limit,
                core_remaining=core_remaining,
                core_reset=core_reset,
                core_used=core_used,
                search_limit=search_limit,
                search_remaining=search_remaining,
                search_reset=search_reset,
                search_used=search_used,
                graphql_limit=graphql_limit,
                graphql_remaining=graphql_remaining,
                graphql_reset=graphql_reset,
                graphql_used=graphql_used
            )
            
            logger.debug(f"Updated rate limit info: {core_remaining}/{core_limit} requests remaining")
            
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse rate limit headers: {e}")
    
    def _parse_rate_limit_reset(self, headers: Dict[str, str]) -> Optional[datetime]:
        """Parse rate limit reset time from headers."""
        try:
            reset_timestamp = int(headers.get("x-ratelimit-reset", 0))
            return datetime.fromtimestamp(reset_timestamp) if reset_timestamp else None
        except (ValueError, KeyError):
            return None
    
    async def _check_rate_limits(self) -> None:
        """Check if we're approaching rate limits and wait if necessary."""
        if not self._rate_limit_info:
            return
        
        # Check if we need to wait for rate limit reset
        now = datetime.now()
        
        # Core API check
        if self._rate_limit_info.core_remaining < 10:  # Conservative threshold
            wait_time = self._rate_limit_info.time_until_reset("core")
            if wait_time > 0:
                logger.warning(f"Approaching GitHub API rate limit. Waiting {wait_time} seconds.")
                await asyncio.sleep(min(wait_time, 60))  # Max 1 minute wait
    
    async def get_rate_limit_info(self) -> Optional[GitHubRateLimitInfo]:
        """Get current rate limit information."""
        try:
            status_code, data, headers = await self._make_request("GET", "/rate_limit")
            if status_code == 200:
                # Update our cached info with fresh data
                self._update_rate_limit_info(headers)
                return self._rate_limit_info
        except Exception as e:
            logger.warning(f"Failed to fetch rate limit info: {e}")
        
        return self._rate_limit_info
    
    # User and Organization Methods
    
    async def get_authenticated_user(self) -> GitHubUser:
        """Get information about the authenticated user."""
        status_code, data, _ = await self._make_request("GET", "/user")
        return GitHubUser(**data)
    
    async def get_user(self, username: str) -> GitHubUser:
        """Get information about a specific user."""
        status_code, data, _ = await self._make_request("GET", f"/users/{username}")
        return GitHubUser(**data)
    
    async def get_organization(self, org_name: str) -> GitHubUser:
        """Get information about an organization."""
        status_code, data, _ = await self._make_request("GET", f"/orgs/{org_name}")
        return GitHubUser(**data)
    
    # Repository Methods
    
    async def get_repository(self, owner: str, repo: str) -> GitHubRepository:
        """Get repository information."""
        status_code, data, _ = await self._make_request("GET", f"/repos/{owner}/{repo}")
        return GitHubRepository(**data)
    
    async def list_user_repositories(
        self,
        username: Optional[str] = None,
        repo_type: str = "all",
        sort: str = "updated",
        per_page: int = 30
    ) -> List[GitHubRepository]:
        """List repositories for a user."""
        endpoint = f"/users/{username}/repos" if username else "/user/repos"
        params = {
            "type": repo_type,
            "sort": sort,
            "per_page": per_page
        }
        
        status_code, data, _ = await self._make_request("GET", endpoint, params=params)
        return [GitHubRepository(**repo_data) for repo_data in data]
    
    async def list_organization_repositories(
        self,
        org_name: str,
        repo_type: str = "all",
        sort: str = "updated",
        per_page: int = 30
    ) -> List[GitHubRepository]:
        """List repositories for an organization."""
        params = {
            "type": repo_type,
            "sort": sort,
            "per_page": per_page
        }
        
        status_code, data, _ = await self._make_request("GET", f"/orgs/{org_name}/repos", params=params)
        return [GitHubRepository(**repo_data) for repo_data in data]
    
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
        is_template: bool = False,
        org_name: Optional[str] = None
    ) -> GitHubRepository:
        """Create a new repository."""
        data = {
            "name": name,
            "private": private,
            "auto_init": auto_init,
            "has_issues": has_issues,
            "has_projects": has_projects,
            "has_wiki": has_wiki,
            "is_template": is_template
        }
        
        if description:
            data["description"] = description
        if homepage:
            data["homepage"] = homepage
        if gitignore_template:
            data["gitignore_template"] = gitignore_template
        if license_template:
            data["license_template"] = license_template
        
        endpoint = f"/orgs/{org_name}/repos" if org_name else "/user/repos"
        status_code, response_data, _ = await self._make_request("POST", endpoint, data=data)
        
        return GitHubRepository(**response_data)
    
    async def delete_repository(self, owner: str, repo: str) -> bool:
        """Delete a repository."""
        try:
            status_code, _, _ = await self._make_request("DELETE", f"/repos/{owner}/{repo}")
            return status_code == 204
        except GitHubAPIError:
            return False


class GitHubRepositoryValidator:
    """Utility class for validating GitHub repository names and configurations."""
    
    @staticmethod
    def validate_repository_name(name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GitHub repository name.
        
        Args:
            name: Repository name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, "Repository name cannot be empty"
        
        name = name.strip()
        
        # Length check
        if len(name) > 100:
            return False, "Repository name cannot exceed 100 characters"
        
        # Character validation
        if not re.match(r'^[a-zA-Z0-9._-]+$', name):
            return False, "Repository name can only contain alphanumeric characters, periods, hyphens, and underscores"
        
        # Cannot start or end with special characters
        if name.startswith('.') or name.endswith('.'):
            return False, "Repository name cannot start or end with a period"
        
        if name.startswith('-') or name.endswith('-'):
            return False, "Repository name cannot start or end with a hyphen"
        
        # Reserved names
        reserved_names = {
            ".", "..", ".git", ".github", "admin", "api", "www", "help", "blog",
            "status", "security", "support", "about", "enterprise", "downloads",
            "marketplace", "explore", "integration", "integrations", "features",
            "contact", "pricing", "plans", "jobs", "login", "join", "signup",
            "settings", "notifications", "watching", "organizations", "orgs",
            "repositories", "repos", "topics", "trending", "stars", "gist",
            "gists", "new", "issues", "pulls", "milestones", "wiki", "forks",
            "branches", "tags", "releases", "contributors", "graphs", "pulse",
            "network", "commits", "commit", "compare", "blame", "blob", "tree",
            "raw", "edit", "create", "upload", "find", "delete", "history"
        }
        
        if name.lower() in reserved_names:
            return False, f"Repository name '{name}' is reserved"
        
        return True, None
    
    @staticmethod
    def validate_topic(topic: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GitHub repository topic.
        
        Args:
            topic: Topic to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not topic or not topic.strip():
            return False, "Topic cannot be empty"
        
        topic = topic.strip().lower()
        
        # Length check
        if len(topic) > 50:
            return False, "Topic cannot exceed 50 characters"
        
        # Character validation - only lowercase letters, numbers, and hyphens
        if not re.match(r'^[a-z0-9-]+$', topic):
            return False, "Topic can only contain lowercase letters, numbers, and hyphens"
        
        # Cannot start or end with hyphen
        if topic.startswith('-') or topic.endswith('-'):
            return False, "Topic cannot start or end with a hyphen"
        
        # Cannot have consecutive hyphens
        if '--' in topic:
            return False, "Topic cannot contain consecutive hyphens"
        
        return True, None


class GitHubWebhookValidator:
    """Utility class for validating GitHub webhooks and their signatures."""
    
    @staticmethod
    def validate_webhook_signature(
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """
        Validate GitHub webhook signature.
        
        Args:
            payload: Webhook payload bytes
            signature: Signature from X-Hub-Signature-256 header
            secret: Webhook secret
            
        Returns:
            True if signature is valid
        """
        if not signature or not secret:
            return False
        
        # GitHub uses SHA-256 HMAC
        if not signature.startswith('sha256='):
            return False
        
        try:
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            received_signature = signature[7:]  # Remove 'sha256=' prefix
            
            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(expected_signature, received_signature)
            
        except Exception as e:
            logger.warning(f"Failed to validate webhook signature: {e}")
            return False
    
    @staticmethod
    def parse_webhook_payload(payload: str) -> Dict[str, Any]:
        """
        Parse GitHub webhook payload.
        
        Args:
            payload: JSON payload string
            
        Returns:
            Parsed payload data
            
        Raises:
            ValueError: If payload is invalid JSON
        """
        try:
            return json.loads(payload)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid webhook payload JSON: {e}")
    
    @staticmethod
    def extract_webhook_event(headers: Dict[str, str]) -> Optional[str]:
        """
        Extract webhook event type from headers.
        
        Args:
            headers: Request headers
            
        Returns:
            Event type or None if not found
        """
        return headers.get('X-GitHub-Event') or headers.get('x-github-event')
    
    @staticmethod
    def is_ping_event(payload: Dict[str, Any]) -> bool:
        """Check if webhook payload is a ping event."""
        return payload.get('zen') is not None and payload.get('hook_id') is not None


class GitHubPagesUtils:
    """Utility functions for GitHub Pages operations."""
    
    @staticmethod
    def validate_custom_domain(domain: str) -> Tuple[bool, Optional[str]]:
        """
        Validate custom domain for GitHub Pages.
        
        Args:
            domain: Domain name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not domain or not domain.strip():
            return False, "Domain cannot be empty"
        
        domain = domain.strip().lower()
        
        # Remove protocol if present
        if domain.startswith('http://') or domain.startswith('https://'):
            return False, "Domain should not include protocol (http/https)"
        
        # Remove path if present
        if '/' in domain:
            return False, "Domain should not include path"
        
        # Basic domain validation
        if not re.match(r'^[a-z0-9.-]+$', domain):
            return False, "Domain contains invalid characters"
        
        # Length check
        if len(domain) > 253:
            return False, "Domain name too long"
        
        # Check domain parts
        parts = domain.split('.')
        if len(parts) < 2:
            return False, "Domain must have at least two parts"
        
        for part in parts:
            if not part:
                return False, "Domain cannot have empty parts"
            if len(part) > 63:
                return False, "Domain part cannot exceed 63 characters"
            if part.startswith('-') or part.endswith('-'):
                return False, "Domain parts cannot start or end with hyphens"
        
        # Reserved domains
        reserved_domains = {
            'github.com', 'githubusercontent.com', 'github.io',
            'localhost', '127.0.0.1', '0.0.0.0'
        }
        
        if domain in reserved_domains:
            return False, f"Domain '{domain}' is reserved"
        
        return True, None
    
    @staticmethod
    def generate_cname_content(domain: str) -> str:
        """Generate CNAME file content for custom domain."""
        return domain.strip().lower()
    
    @staticmethod
    def get_default_pages_url(owner: str, repo: str) -> str:
        """Get default GitHub Pages URL for a repository."""
        if repo.lower() == f"{owner.lower()}.github.io":
            return f"https://{owner.lower()}.github.io"
        else:
            return f"https://{owner.lower()}.github.io/{repo}"


class GitHubAPIUtils:
    """General utility functions for GitHub API operations."""
    
    @staticmethod
    def parse_github_url(url: str) -> Optional[Tuple[str, str]]:
        """
        Parse GitHub repository URL to extract owner and repo name.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo) or None if invalid
        """
        if not url:
            return None
        
        # Handle different URL formats
        patterns = [
            r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$',
            r'ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, url.strip())
            if match:
                owner, repo = match.groups()
                return owner, repo
        
        return None
    
    @staticmethod
    def build_github_url(owner: str, repo: str, url_type: str = "https") -> str:
        """
        Build GitHub repository URL.
        
        Args:
            owner: Repository owner
            repo: Repository name
            url_type: URL type ("https", "ssh", "git")
            
        Returns:
            GitHub repository URL
        """
        if url_type == "ssh":
            return f"git@github.com:{owner}/{repo}.git"
        elif url_type == "git":
            return f"git://github.com/{owner}/{repo}.git"
        else:  # https
            return f"https://github.com/{owner}/{repo}.git"
    
    @staticmethod
    def is_github_url(url: str) -> bool:
        """Check if URL is a GitHub repository URL."""
        if not url:
            return False
        
        parsed = urlparse(url)
        return parsed.hostname in ['github.com', 'www.github.com']
    
    @staticmethod
    def extract_repo_info_from_remote(remote_url: str) -> Optional[Dict[str, str]]:
        """
        Extract repository information from Git remote URL.
        
        Args:
            remote_url: Git remote URL
            
        Returns:
            Dictionary with repo info or None if not a GitHub URL
        """
        if not GitHubAPIUtils.is_github_url(remote_url):
            return None
        
        parsed = GitHubAPIUtils.parse_github_url(remote_url)
        if not parsed:
            return None
        
        owner, repo = parsed
        return {
            "owner": owner,
            "repo": repo,
            "full_name": f"{owner}/{repo}",
            "html_url": f"https://github.com/{owner}/{repo}",
            "clone_url": f"https://github.com/{owner}/{repo}.git",
            "ssh_url": f"git@github.com:{owner}/{repo}.git"
        }
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """Truncate text to specified length with suffix."""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix


class GitHubRetryStrategy:
    """Retry strategy for GitHub API operations."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determine if operation should be retried."""
        if attempt >= self.max_retries:
            return False
        
        # Don't retry authentication errors
        if isinstance(exception, GitHubAuthenticationError):
            return False
        
        # Don't retry validation errors
        if isinstance(exception, GitHubValidationError):
            return False
        
        # Retry rate limit errors after waiting
        if isinstance(exception, GitHubRateLimitError):
            return True
        
        # Retry server errors and network errors
        if isinstance(exception, (GitHubAPIError, httpx.RequestError)):
            return True
        
        return False
    
    def get_delay(self, attempt: int) -> float:
        """Get delay before next retry attempt."""
        delay = self.base_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)
    
    async def execute_with_retry(self, operation, *args, **kwargs):
        """Execute operation with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if not self.should_retry(attempt, e):
                    raise
                
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    logger.warning(f"Operation failed (attempt {attempt + 1}), retrying in {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        raise last_exception