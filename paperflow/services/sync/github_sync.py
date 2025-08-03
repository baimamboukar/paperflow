"""
GitHub synchronization service for Paperflow.

This service handles synchronization with GitHub repositories, including
repository management, branch operations, and integration with GitHub Pages.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from paperflow.config.settings import Settings
from paperflow.models.project import Project
from paperflow.models.git import GitRepository
from paperflow.utils.git_utils import GitCredentials
from paperflow.models.github import GitHubRepository, GitHubAPICredentials
from paperflow.models.sync import (
    SyncResult, SyncStatus, SyncOperationType, SyncConflict,
    ConflictResolution, SyncConfiguration, SyncMetrics
)
from paperflow.services.base import BaseService
from paperflow.services.git_service import GitService
from paperflow.services.github_service import GitHubService
from paperflow.utils.logging import setup_logging
from paperflow.utils.file_utils import FileUtils

logger = setup_logging(__name__)


class GitHubSyncConfiguration:
    """Configuration for GitHub sync operations."""
    
    def __init__(
        self,
        auto_create_repository: bool = True,
        enable_github_pages: bool = True,
        default_branch: str = "main",
        create_readme: bool = True,
        setup_branch_protection: bool = False,
        setup_webhooks: bool = False,
        webhook_url: Optional[str] = None,
        commit_message_template: str = "Sync from Overleaf: {timestamp}",
        preserve_git_history: bool = True,
        force_push_allowed: bool = False
    ):
        self.auto_create_repository = auto_create_repository
        self.enable_github_pages = enable_github_pages
        self.default_branch = default_branch
        self.create_readme = create_readme
        self.setup_branch_protection = setup_branch_protection
        self.setup_webhooks = setup_webhooks
        self.webhook_url = webhook_url
        self.commit_message_template = commit_message_template
        self.preserve_git_history = preserve_git_history
        self.force_push_allowed = force_push_allowed


class GitHubSyncService(BaseService):
    """
    GitHub synchronization service.
    
    Handles synchronization with GitHub repositories, including repository
    creation, file synchronization, and GitHub Pages configuration.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize GitHub sync service."""
        super().__init__(settings)
        
        # Service dependencies
        self.git_service: Optional[GitService] = None
        self.github_service: Optional[GitHubService] = None
        self.file_utils = FileUtils()
        
        # Configuration
        self.default_config = GitHubSyncConfiguration()
        
        # State tracking
        self.active_syncs: Dict[str, Dict[str, Any]] = {}
    
    def _perform_initialization(self) -> None:
        """Perform service-specific initialization."""
        logger.info("Initializing GitHubSyncService")
        
        # Initialize dependencies
        self.git_service = GitService(self.settings)
        self.github_service = GitHubService(self.settings)
        
        if self.settings:
            self.git_service.initialize(self.settings)
            self.github_service.initialize(self.settings)
        
        logger.info("GitHubSyncService initialized")
    
    def _perform_cleanup(self) -> None:
        """Perform service cleanup."""
        logger.info("Cleaning up GitHubSyncService")
        
        # Cleanup dependencies
        if self.git_service:
            self.git_service.cleanup()
        if self.github_service:
            self.github_service.cleanup()
        
        self.active_syncs.clear()
        
        logger.info("GitHubSyncService cleanup completed")
    
    async def sync_to_github(
        self,
        project: Project,
        source_directory: Path,
        github_repo_url: str,
        config: Optional[GitHubSyncConfiguration] = None
    ) -> SyncResult:
        """
        Sync project to GitHub repository.
        
        Args:
            project: Project to sync
            source_directory: Directory containing files to sync
            github_repo_url: GitHub repository URL
            config: Sync configuration
            
        Returns:
            SyncResult with operation details
        """
        operation_id = f"github_sync_{project.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        sync_config = config or self.default_config
        
        sync_result = SyncResult(
            operation_id=operation_id,
            operation_type=SyncOperationType.GITHUB_SYNC,
            trigger=project.last_sync or datetime.now(),
            github_repo_url=github_repo_url,
            configuration=sync_config
        )
        
        sync_result.mark_started()
        self.active_syncs[operation_id] = {"project": project, "config": sync_config}
        
        try:
            logger.info(f"Starting GitHub sync for project '{project.name}'")
            
            # Parse repository information
            repo_info = self._parse_github_url(github_repo_url)
            if not repo_info:
                raise ValueError(f"Invalid GitHub URL: {github_repo_url}")
            
            owner, repo_name = repo_info["owner"], repo_info["repo"]
            
            # Ensure GitHub repository exists
            github_repo = await self._ensure_repository_exists(
                owner, repo_name, project, sync_config, sync_result
            )
            
            if not github_repo:
                raise RuntimeError("Failed to create or access GitHub repository")
            
            # Setup local Git repository
            local_repo = await self._setup_local_repository(
                source_directory, github_repo_url, sync_config, sync_result
            )
            
            if not local_repo:
                raise RuntimeError("Failed to setup local Git repository")
            
            # Sync files and commit changes
            await self._sync_files_and_commit(
                source_directory, local_repo, project, sync_config, sync_result
            )
            
            # Push changes to GitHub
            await self._push_to_github(
                local_repo, sync_config, sync_result
            )
            
            # Setup GitHub Pages if needed
            if sync_config.enable_github_pages:
                await self._setup_github_pages(
                    owner, repo_name, sync_result
                )
            
            # Setup webhooks if needed
            if sync_config.setup_webhooks and sync_config.webhook_url:
                await self._setup_webhooks(
                    owner, repo_name, sync_config.webhook_url, sync_result
                )
            
            # Update project metadata
            project.last_sync = datetime.now()
            sync_result.deployment_url = f"https://{owner}.github.io/{repo_name}"
            
            sync_result.mark_completed(success=True)
            logger.info(f"Successfully completed GitHub sync for project '{project.name}'")
        
        except Exception as e:
            sync_result.mark_completed(success=False, error=str(e))
            logger.error(f"GitHub sync failed for project '{project.name}': {e}")
        
        finally:
            self.active_syncs.pop(operation_id, None)
        
        return sync_result
    
    async def create_github_repository(
        self,
        project: Project,
        owner: str,
        repo_name: str,
        config: Optional[GitHubSyncConfiguration] = None
    ) -> Optional[GitHubRepository]:
        """
        Create a new GitHub repository for the project.
        
        Args:
            project: Project to create repository for
            owner: GitHub username or organization
            repo_name: Repository name
            config: Repository configuration
            
        Returns:
            GitHubRepository object if successful
        """
        sync_config = config or self.default_config
        
        try:
            # Prepare repository creation parameters
            create_result = await self.github_service.create_repository(
                name=repo_name,
                description=f"Academic paper: {project.title}",
                private=False,  # Academic papers are usually public
                auto_init=True,
                has_pages=sync_config.enable_github_pages,
                topics=["academic-paper", "latex", "research", "paperflow"]
            )
            
            if create_result.success and create_result.repository:
                logger.info(f"Created GitHub repository: {owner}/{repo_name}")
                return create_result.repository
            else:
                logger.error(f"Failed to create repository: {create_result.error}")
                return None
        
        except Exception as e:
            logger.error(f"Error creating GitHub repository: {e}")
            return None
    
    async def get_repository_status(
        self,
        owner: str,
        repo_name: str
    ) -> Dict[str, Any]:
        """
        Get status of GitHub repository.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Dictionary with repository status
        """
        status = {
            "exists": False,
            "accessible": False,
            "pages_enabled": False,
            "pages_url": None,
            "last_updated": None,
            "commit_count": 0,
            "error": None
        }
        
        try:
            # Get repository information
            repo = await self.github_service.get_repository(owner, repo_name)
            
            if repo:
                status["exists"] = True
                status["accessible"] = True
                status["last_updated"] = repo.updated_at.isoformat() if repo.updated_at else None
                
                # Check GitHub Pages
                pages_config = await self.github_service.get_github_pages_config(owner, repo_name)
                if pages_config and pages_config.enabled:
                    status["pages_enabled"] = True
                    status["pages_url"] = pages_config.url
                
                logger.info(f"Retrieved status for repository {owner}/{repo_name}")
            else:
                status["error"] = "Repository not found or not accessible"
        
        except Exception as e:
            status["error"] = str(e)
            logger.error(f"Error getting repository status: {e}")
        
        return status
    
    def _parse_github_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse GitHub URL to extract owner and repository name."""
        try:
            # Handle various GitHub URL formats
            if "github.com" in url:
                # Extract from URLs like:
                # https://github.com/owner/repo
                # git@github.com:owner/repo.git
                if url.startswith("git@"):
                    # SSH format
                    parts = url.split(":")
                    if len(parts) >= 2:
                        path_part = parts[1].replace(".git", "")
                        path_parts = path_part.split("/")
                        if len(path_parts) >= 2:
                            return {"owner": path_parts[0], "repo": path_parts[1]}
                else:
                    # HTTPS format
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    path_parts = parsed.path.strip("/").split("/")
                    if len(path_parts) >= 2:
                        repo_name = path_parts[1].replace(".git", "")
                        return {"owner": path_parts[0], "repo": repo_name}
            
            return None
        except Exception:
            return None
    
    async def _ensure_repository_exists(
        self,
        owner: str,
        repo_name: str,
        project: Project,
        config: GitHubSyncConfiguration,
        sync_result: SyncResult
    ) -> Optional[GitHubRepository]:
        """Ensure GitHub repository exists, create if needed."""
        try:
            # Try to get existing repository
            repo = await self.github_service.get_repository(owner, repo_name)
            
            if repo:
                logger.info(f"Found existing repository: {owner}/{repo_name}")
                return repo
            
            # Repository doesn't exist, create if auto-create is enabled
            if config.auto_create_repository:
                logger.info(f"Creating new repository: {owner}/{repo_name}")
                repo = await self.create_github_repository(
                    project, owner, repo_name, config
                )
                
                if repo:
                    sync_result.add_warning(f"Created new repository: {owner}/{repo_name}")
                    return repo
                else:
                    sync_result.add_warning("Failed to create repository")
            else:
                sync_result.add_warning("Repository does not exist and auto-create is disabled")
            
            return None
        
        except Exception as e:
            logger.error(f"Error ensuring repository exists: {e}")
            return None
    
    async def _setup_local_repository(
        self,
        source_directory: Path,
        github_url: str,
        config: GitHubSyncConfiguration,
        sync_result: SyncResult
    ) -> Optional[GitRepository]:
        """Setup local Git repository for sync."""
        try:
            # Check if directory already has a Git repository
            if (source_directory / ".git").exists():
                # Load existing repository
                repo = await self.git_service.load_repository(source_directory)
                
                if repo:
                    # Check if GitHub remote exists
                    github_remote = None
                    for remote in repo.remotes:
                        if github_url in remote.url:
                            github_remote = remote
                            break
                    
                    # Add GitHub remote if not exists
                    if not github_remote:
                        await self.git_service.add_remote(
                            repo, "origin", github_url
                        )
                        logger.info("Added GitHub remote to existing repository")
                    
                    return repo
            
            # Initialize new Git repository
            from pathlib import Path
            import subprocess
            
            # Initialize git repository
            result = subprocess.run(
                ["git", "init"],
                cwd=source_directory,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to initialize Git repository: {result.stderr}")
            
            # Load the newly initialized repository
            repo = await self.git_service.load_repository(source_directory)
            
            if repo:
                # Add GitHub remote
                await self.git_service.add_remote(repo, "origin", github_url)
                logger.info("Initialized new Git repository with GitHub remote")
                return repo
            
            return None
        
        except Exception as e:
            logger.error(f"Error setting up local repository: {e}")
            return None
    
    async def _sync_files_and_commit(
        self,
        source_directory: Path,
        repo: GitRepository,
        project: Project,
        config: GitHubSyncConfiguration,
        sync_result: SyncResult
    ) -> None:
        """Sync files and create commit."""
        try:
            # Add all files (Git will handle what's actually changed)
            add_result = await self.git_service.add_files(repo, ".")
            
            if not add_result.success:
                raise RuntimeError(f"Failed to add files: {add_result.error}")
            
            # Check if there are changes to commit
            status = await self.git_service.get_repository_status(repo)
            
            if status.has_staged_changes:
                # Create commit message
                commit_message = config.commit_message_template.format(
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    project_name=project.name,
                    project_title=project.title
                )
                
                # Commit changes
                commit_result = await self.git_service.commit_changes(
                    repo, commit_message
                )
                
                if commit_result.success:
                    sync_result.target_commit_hash = commit_result.commit_hash
                    sync_result.metrics.files_modified = commit_result.files_changed
                    logger.info(f"Created commit: {commit_result.commit_hash}")
                else:
                    raise RuntimeError(f"Failed to commit changes: {commit_result.error}")
            else:
                sync_result.add_warning("No changes to commit")
                logger.info("No changes detected, skipping commit")
        
        except Exception as e:
            logger.error(f"Error syncing files and committing: {e}")
            raise
    
    async def _push_to_github(
        self,
        repo: GitRepository,
        config: GitHubSyncConfiguration,
        sync_result: SyncResult
    ) -> None:
        """Push changes to GitHub."""
        try:
            # Determine branch to push
            branch_name = config.default_branch
            if repo.current_branch:
                branch_name = repo.current_branch.name
            
            # Push changes
            push_result = await self.git_service.push_changes(
                repo,
                remote="origin",
                branch=branch_name,
                force=config.force_push_allowed,
                set_upstream=True
            )
            
            if push_result.success:
                sync_result.metrics.files_pushed = push_result.commits_pushed or 0
                logger.info(f"Successfully pushed to GitHub: {push_result.commits_pushed} commits")
            else:
                if push_result.rejected and not config.force_push_allowed:
                    # Try to pull and merge first
                    logger.info("Push rejected, attempting to pull and merge")
                    
                    pull_result = await self.git_service.pull_changes(repo, "origin", branch_name)
                    
                    if pull_result.success:
                        # Retry push
                        retry_push = await self.git_service.push_changes(
                            repo, "origin", branch_name
                        )
                        
                        if retry_push.success:
                            sync_result.metrics.files_pushed = retry_push.commits_pushed or 0
                            logger.info("Successfully pushed after pull and merge")
                        else:
                            raise RuntimeError(f"Failed to push after merge: {retry_push.error}")
                    else:
                        if pull_result.had_conflicts:
                            # Handle merge conflicts
                            sync_result.status = SyncStatus.CONFLICT
                            for file_path in pull_result.conflict_files or []:
                                conflict = SyncConflict(
                                    file_path=file_path,
                                    conflict_type="merge_conflict",
                                    details={"error": "Merge conflict during pull"}
                                )
                                sync_result.add_conflict(conflict)
                            
                            logger.warning(f"Merge conflicts detected: {len(pull_result.conflict_files or [])}")
                        else:
                            raise RuntimeError(f"Failed to pull before push: {pull_result.error}")
                else:
                    raise RuntimeError(f"Failed to push to GitHub: {push_result.error}")
        
        except Exception as e:
            logger.error(f"Error pushing to GitHub: {e}")
            raise
    
    async def _setup_github_pages(
        self,
        owner: str,
        repo_name: str,
        sync_result: SyncResult
    ) -> None:
        """Setup GitHub Pages for the repository."""
        try:
            # Check if Pages is already enabled
            pages_config = await self.github_service.get_github_pages_config(owner, repo_name)
            
            if pages_config and pages_config.enabled:
                sync_result.deployment_url = pages_config.url
                logger.info(f"GitHub Pages already enabled: {pages_config.url}")
                return
            
            # Setup GitHub Pages
            pages_result = await self.github_service.setup_github_pages(
                owner=owner,
                repo=repo_name,
                source_branch="main",  # Use main branch
                source_path="root"  # Use root directory
            )
            
            if pages_result.success:
                sync_result.deployment_url = pages_result.pages_url
                sync_result.deployment_status = "enabled"
                logger.info(f"Successfully enabled GitHub Pages: {pages_result.pages_url}")
            else:
                sync_result.add_warning(f"Failed to enable GitHub Pages: {pages_result.error}")
        
        except Exception as e:
            logger.warning(f"Error setting up GitHub Pages: {e}")
            sync_result.add_warning(f"Failed to setup GitHub Pages: {e}")
    
    async def _setup_webhooks(
        self,
        owner: str,
        repo_name: str,
        webhook_url: str,
        sync_result: SyncResult
    ) -> None:
        """Setup webhooks for the repository."""
        try:
            from paperflow.models.github import GitHubWebhookEvent
            
            # Setup webhook for push events
            webhook_result = await self.github_service.create_webhook(
                owner=owner,
                repo=repo_name,
                webhook_url=webhook_url,
                events=[GitHubWebhookEvent.PUSH, GitHubWebhookEvent.PULL_REQUEST]
            )
            
            if webhook_result.success:
                logger.info(f"Successfully created webhook: {webhook_result.webhook_id}")
            else:
                sync_result.add_warning(f"Failed to create webhook: {webhook_result.error}")
        
        except Exception as e:
            logger.warning(f"Error setting up webhooks: {e}")
            sync_result.add_warning(f"Failed to setup webhooks: {e}")
    
    async def clone_github_repository(
        self,
        github_url: str,
        destination: Path,
        credentials: Optional[GitCredentials] = None
    ) -> SyncResult:
        """
        Clone a GitHub repository.
        
        Args:
            github_url: GitHub repository URL
            destination: Local destination path
            credentials: Git credentials if needed
            
        Returns:
            SyncResult with operation details
        """
        operation_id = f"github_clone_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        sync_result = SyncResult(
            operation_id=operation_id,
            operation_type=SyncOperationType.PULL_ONLY,
            trigger=datetime.now(),
            github_repo_url=github_url
        )
        
        sync_result.mark_started()
        
        try:
            clone_result = await self.git_service.clone_repository(
                url=github_url,
                destination=destination,
                credentials=credentials
            )
            
            if clone_result.success:
                sync_result.mark_completed(success=True)
                logger.info(f"Successfully cloned repository to {destination}")
            else:
                sync_result.mark_completed(success=False, error=clone_result.error)
                logger.error(f"Failed to clone repository: {clone_result.error}")
        
        except Exception as e:
            sync_result.mark_completed(success=False, error=str(e))
            logger.error(f"Error cloning repository: {e}")
        
        return sync_result
    
    def get_sync_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get status of active sync operation."""
        if operation_id in self.active_syncs:
            return self.active_syncs[operation_id]
        return None
    
    def cancel_sync(self, operation_id: str) -> bool:
        """Cancel active sync operation."""
        if operation_id in self.active_syncs:
            self.active_syncs.pop(operation_id)
            logger.info(f"Cancelled sync operation: {operation_id}")
            return True
        return False