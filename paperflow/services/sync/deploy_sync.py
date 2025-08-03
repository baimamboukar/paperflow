"""
Deployment synchronization service for Paperflow.

This service handles deployment of built websites to various platforms,
with primary focus on GitHub Pages deployment.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from paperflow.config.settings import Settings
from paperflow.models.project import Project
from paperflow.models.github import GitHubRepository, GitHubPages, GitHubPagesSource
from paperflow.models.git import GitRepository
from paperflow.models.sync import (
    SyncResult, SyncStatus, SyncOperationType, SyncConfiguration,
    SyncMetrics, SyncStage
)
from paperflow.services.base import BaseService
from paperflow.services.git_service import GitService
from paperflow.services.github_service import GitHubService
from paperflow.utils.logging import setup_logging
from paperflow.utils.file_utils import FileUtils

logger = setup_logging(__name__)


class DeploymentTarget:
    """Represents a deployment target."""
    
    def __init__(
        self,
        name: str,
        target_type: str,
        url: str,
        configuration: Dict[str, Any]
    ):
        self.name = name
        self.target_type = target_type  # 'github_pages', 'netlify', 'vercel', etc.
        self.url = url
        self.configuration = configuration


class DeploymentConfiguration:
    """Configuration for deployment operations."""
    
    def __init__(
        self,
        target_branch: str = "gh-pages",
        custom_domain: Optional[str] = None,
        enforce_https: bool = True,
        cleanup_old_deployments: bool = True,
        deployment_timeout_seconds: int = 600,
        verify_deployment: bool = True,
        rollback_on_failure: bool = True,
        preserve_deployment_history: bool = True,
        max_deployment_history: int = 10,
        deployment_message_template: str = "Deploy website: {timestamp}",
        pre_deploy_commands: Optional[List[str]] = None,
        post_deploy_commands: Optional[List[str]] = None
    ):
        self.target_branch = target_branch
        self.custom_domain = custom_domain
        self.enforce_https = enforce_https
        self.cleanup_old_deployments = cleanup_old_deployments
        self.deployment_timeout_seconds = deployment_timeout_seconds
        self.verify_deployment = verify_deployment
        self.rollback_on_failure = rollback_on_failure
        self.preserve_deployment_history = preserve_deployment_history
        self.max_deployment_history = max_deployment_history
        self.deployment_message_template = deployment_message_template
        self.pre_deploy_commands = pre_deploy_commands or []
        self.post_deploy_commands = post_deploy_commands or []


class DeploymentHistory:
    """Tracks deployment history."""
    
    def __init__(self):
        self.deployments: List[Dict[str, Any]] = []
    
    def add_deployment(
        self,
        deployment_id: str,
        target: str,
        status: str,
        url: Optional[str] = None,
        commit_hash: Optional[str] = None,
        deployment_time: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add deployment record."""
        deployment_record = {
            "id": deployment_id,
            "target": target,
            "status": status,
            "url": url,
            "commit_hash": commit_hash,
            "deployment_time": (deployment_time or datetime.now()).isoformat(),
            "metadata": metadata or {}
        }
        
        self.deployments.append(deployment_record)
        
        # Keep only recent deployments
        if len(self.deployments) > 50:
            self.deployments = self.deployments[-25:]
    
    def get_latest_deployment(self, target: str) -> Optional[Dict[str, Any]]:
        """Get latest deployment for target."""
        for deployment in reversed(self.deployments):
            if deployment["target"] == target:
                return deployment
        return None
    
    def get_successful_deployments(self, target: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent successful deployments."""
        successful = []
        for deployment in reversed(self.deployments):
            if deployment["target"] == target and deployment["status"] == "success":
                successful.append(deployment)
                if len(successful) >= limit:
                    break
        return successful


class GitHubPagesDeployer:
    """Handles GitHub Pages deployments."""
    
    def __init__(self, git_service: GitService, github_service: GitHubService):
        self.git_service = git_service
        self.github_service = github_service
        self.file_utils = FileUtils()
    
    async def deploy_to_github_pages(
        self,
        source_directory: Path,
        github_repo_url: str,
        config: DeploymentConfiguration,
        sync_result: SyncResult
    ) -> bool:
        """Deploy to GitHub Pages."""
        try:
            # Parse repository information
            repo_info = self._parse_github_url(github_repo_url)
            if not repo_info:
                raise ValueError(f"Invalid GitHub URL: {github_repo_url}")
            
            owner, repo_name = repo_info["owner"], repo_info["repo"]
            
            # Setup deployment branch
            deploy_success = await self._setup_deployment_branch(
                source_directory, github_repo_url, config, sync_result
            )
            
            if not deploy_success:
                return False
            
            # Configure GitHub Pages
            pages_success = await self._configure_github_pages(
                owner, repo_name, config, sync_result
            )
            
            if not pages_success:
                sync_result.add_warning("Failed to configure GitHub Pages settings")
            
            # Verify deployment
            if config.verify_deployment:
                await self._verify_deployment(
                    owner, repo_name, config, sync_result
                )
            
            return True
        
        except Exception as e:
            logger.error(f"GitHub Pages deployment failed: {e}")
            return False
    
    async def _setup_deployment_branch(
        self,
        source_directory: Path,
        github_repo_url: str,
        config: DeploymentConfiguration,
        sync_result: SyncResult
    ) -> bool:
        """Setup deployment branch with built files."""
        try:
            # Clone repository to temporary location
            import tempfile
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_repo_path = Path(temp_dir) / "repo"
                
                # Clone repository
                clone_result = await self.git_service.clone_repository(
                    url=github_repo_url,
                    destination=temp_repo_path
                )
                
                if not clone_result.success:
                    raise RuntimeError(f"Failed to clone repository: {clone_result.error}")
                
                # Load repository
                repo = await self.git_service.load_repository(temp_repo_path)
                if not repo:
                    raise RuntimeError("Failed to load cloned repository")
                
                # Check if deployment branch exists
                branch_exists = False
                for branch in repo.branches:
                    if branch.name == config.target_branch:
                        branch_exists = True
                        break
                
                if branch_exists:
                    # Checkout existing deployment branch
                    checkout_result = await self.git_service.checkout_branch(
                        repo, config.target_branch
                    )
                    if not checkout_result.success:
                        raise RuntimeError(f"Failed to checkout branch: {checkout_result.error}")
                else:
                    # Create new deployment branch
                    create_result = await self.git_service.create_branch(
                        repo, config.target_branch, checkout=True
                    )
                    if not create_result.success:
                        raise RuntimeError(f"Failed to create branch: {create_result.error}")
                
                # Clear existing files in deployment branch (except .git)
                await self._clear_deployment_files(temp_repo_path)
                
                # Copy built files to deployment branch
                await self._copy_built_files(source_directory, temp_repo_path, config)
                
                # Create CNAME file if custom domain is specified
                if config.custom_domain:
                    cname_file = temp_repo_path / "CNAME"
                    cname_file.write_text(config.custom_domain, encoding='utf-8')
                
                # Add and commit changes
                add_result = await self.git_service.add_files(repo, ".")
                if not add_result.success:
                    raise RuntimeError(f"Failed to add files: {add_result.error}")
                
                commit_message = config.deployment_message_template.format(
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
                commit_result = await self.git_service.commit_changes(
                    repo, commit_message
                )
                
                if commit_result.success:
                    sync_result.target_commit_hash = commit_result.commit_hash
                    
                    # Push to GitHub
                    push_result = await self.git_service.push_changes(
                        repo, "origin", config.target_branch, set_upstream=True
                    )
                    
                    if push_result.success:
                        logger.info(f"Successfully pushed to {config.target_branch} branch")
                        return True
                    else:
                        raise RuntimeError(f"Failed to push: {push_result.error}")
                else:
                    logger.info("No changes to deploy")
                    return True
        
        except Exception as e:
            logger.error(f"Error setting up deployment branch: {e}")
            return False
    
    async def _clear_deployment_files(self, repo_path: Path) -> None:
        """Clear existing files in deployment directory."""
        for item in repo_path.iterdir():
            if item.name == ".git":
                continue  # Preserve .git directory
            
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                self.file_utils.remove_directory(item)
    
    async def _copy_built_files(
        self,
        source_dir: Path,
        target_dir: Path,
        config: DeploymentConfiguration
    ) -> None:
        """Copy built files to deployment directory."""
        # Copy all files from source to target
        for item in source_dir.iterdir():
            if item.name.startswith('.'):
                continue  # Skip hidden files
            
            target_item = target_dir / item.name
            
            if item.is_file():
                self.file_utils.copy_file(item, target_item)
            elif item.is_dir():
                self.file_utils.copy_directory(item, target_item)
    
    async def _configure_github_pages(
        self,
        owner: str,
        repo_name: str,
        config: DeploymentConfiguration,
        sync_result: SyncResult
    ) -> bool:
        """Configure GitHub Pages settings."""
        try:
            # Setup GitHub Pages
            pages_result = await self.github_service.setup_github_pages(
                owner=owner,
                repo=repo_name,
                source_branch=config.target_branch,
                source_path=GitHubPagesSource.ROOT,
                custom_domain=config.custom_domain,
                enforce_https=config.enforce_https
            )
            
            if pages_result.success:
                sync_result.deployment_url = pages_result.pages_url
                sync_result.deployment_status = "configured"
                logger.info(f"Configured GitHub Pages: {pages_result.pages_url}")
                return True
            else:
                logger.error(f"Failed to configure GitHub Pages: {pages_result.error}")
                return False
        
        except Exception as e:
            logger.error(f"Error configuring GitHub Pages: {e}")
            return False
    
    async def _verify_deployment(
        self,
        owner: str,
        repo_name: str,
        config: DeploymentConfiguration,
        sync_result: SyncResult
    ) -> None:
        """Verify deployment is successful."""
        try:
            # Wait a bit for GitHub Pages to process
            await asyncio.sleep(10)
            
            # Check GitHub Pages status
            pages_config = await self.github_service.get_github_pages_config(owner, repo_name)
            
            if pages_config and pages_config.enabled:
                sync_result.deployment_url = pages_config.url
                sync_result.deployment_status = "verified"
                logger.info(f"Deployment verified: {pages_config.url}")
            else:
                sync_result.add_warning("Could not verify deployment status")
        
        except Exception as e:
            logger.warning(f"Error verifying deployment: {e}")
            sync_result.add_warning(f"Deployment verification failed: {e}")
    
    def _parse_github_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse GitHub URL to extract owner and repository name."""
        try:
            if "github.com" in url:
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
                    parsed = urlparse(url)
                    path_parts = parsed.path.strip("/").split("/")
                    if len(path_parts) >= 2:
                        repo_name = path_parts[1].replace(".git", "")
                        return {"owner": path_parts[0], "repo": repo_name}
            
            return None
        except Exception:
            return None


class DeploySync(BaseService):
    """
    Deployment synchronization service.
    
    Handles deployment of built websites to various platforms,
    with primary focus on GitHub Pages.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize deploy sync service."""
        super().__init__(settings)
        
        # Service dependencies
        self.git_service: Optional[GitService] = None
        self.github_service: Optional[GitHubService] = None
        
        # Deployers
        self.github_pages_deployer: Optional[GitHubPagesDeployer] = None
        
        # Configuration
        self.default_config = DeploymentConfiguration()
        
        # State tracking
        self.active_deployments: Dict[str, Dict[str, Any]] = {}
        self.deployment_history = DeploymentHistory()
    
    def _perform_initialization(self) -> None:
        """Perform service-specific initialization."""
        logger.info("Initializing DeploySync service")
        
        # Initialize dependencies
        self.git_service = GitService(self.settings)
        self.github_service = GitHubService(self.settings)
        
        if self.settings:
            self.git_service.initialize(self.settings)
            self.github_service.initialize(self.settings)
        
        # Initialize deployers
        self.github_pages_deployer = GitHubPagesDeployer(
            self.git_service, self.github_service
        )
        
        logger.info("DeploySync service initialized")
    
    def _perform_cleanup(self) -> None:
        """Perform service cleanup."""
        logger.info("Cleaning up DeploySync service")
        
        # Cleanup dependencies
        if self.git_service:
            self.git_service.cleanup()
        if self.github_service:
            self.github_service.cleanup()
        
        self.active_deployments.clear()
        
        logger.info("DeploySync service cleanup completed")
    
    async def deploy_to_github_pages(
        self,
        project: Project,
        build_output_directory: Path,
        github_repo_url: str,
        config: Optional[DeploymentConfiguration] = None
    ) -> SyncResult:
        """
        Deploy project to GitHub Pages.
        
        Args:
            project: Project to deploy
            build_output_directory: Directory containing built website
            github_repo_url: GitHub repository URL
            config: Deployment configuration
            
        Returns:
            SyncResult with deployment details
        """
        operation_id = f"deploy_{project.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        deploy_config = config or self.default_config
        
        sync_result = SyncResult(
            operation_id=operation_id,
            operation_type=SyncOperationType.DEPLOY_ONLY,
            trigger=datetime.now(),
            github_repo_url=github_repo_url,
            configuration=deploy_config
        )
        
        sync_result.mark_started()
        sync_result.progress.stage = SyncStage.DEPLOYING
        
        self.active_deployments[operation_id] = {
            "project": project,
            "config": deploy_config,
            "start_time": datetime.now()
        }
        
        try:
            logger.info(f"Starting GitHub Pages deployment for project '{project.name}'")
            
            # Validate build output directory
            if not build_output_directory.exists():
                raise RuntimeError(f"Build output directory does not exist: {build_output_directory}")
            
            # Check for required files
            index_file = build_output_directory / "index.html"
            if not index_file.exists():
                raise RuntimeError("No index.html found in build output")
            
            # Run pre-deploy commands
            if deploy_config.pre_deploy_commands:
                await self._run_commands(
                    deploy_config.pre_deploy_commands, 
                    build_output_directory,
                    "Pre-deploy"
                )
            
            # Deploy to GitHub Pages
            deploy_start = datetime.now()
            
            deployment_success = await self.github_pages_deployer.deploy_to_github_pages(
                source_directory=build_output_directory,
                github_repo_url=github_repo_url,
                config=deploy_config,
                sync_result=sync_result
            )
            
            deploy_end = datetime.now()
            sync_result.metrics.deploy_time_seconds = (deploy_end - deploy_start).total_seconds()
            
            if not deployment_success:
                raise RuntimeError("GitHub Pages deployment failed")
            
            # Run post-deploy commands
            if deploy_config.post_deploy_commands:
                await self._run_commands(
                    deploy_config.post_deploy_commands,
                    build_output_directory,
                    "Post-deploy"
                )
            
            # Record deployment in history
            self.deployment_history.add_deployment(
                deployment_id=operation_id,
                target="github_pages",
                status="success",
                url=sync_result.deployment_url,
                commit_hash=sync_result.target_commit_hash,
                deployment_time=datetime.now(),
                metadata={
                    "project_name": project.name,
                    "custom_domain": deploy_config.custom_domain,
                    "target_branch": deploy_config.target_branch
                }
            )
            
            sync_result.mark_completed(success=True)
            logger.info(f"Successfully deployed project '{project.name}' to GitHub Pages")
        
        except Exception as e:
            # Record failed deployment
            self.deployment_history.add_deployment(
                deployment_id=operation_id,
                target="github_pages",
                status="failed",
                deployment_time=datetime.now(),
                metadata={"error": str(e), "project_name": project.name}
            )
            
            sync_result.mark_completed(success=False, error=str(e))
            logger.error(f"GitHub Pages deployment failed for project '{project.name}': {e}")
            
            # Attempt rollback if configured
            if deploy_config.rollback_on_failure:
                await self._attempt_rollback(project, github_repo_url, deploy_config)
        
        finally:
            self.active_deployments.pop(operation_id, None)
        
        return sync_result
    
    async def _run_commands(
        self,
        commands: List[str],
        working_directory: Path,
        command_type: str
    ) -> None:
        """Run shell commands."""
        try:
            import subprocess
            
            for command in commands:
                logger.info(f"Running {command_type} command: {command}")
                
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=working_directory,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout per command
                )
                
                if result.returncode != 0:
                    logger.warning(f"{command_type} command failed: {result.stderr}")
                else:
                    logger.info(f"{command_type} command completed successfully")
        
        except Exception as e:
            logger.error(f"Error running {command_type} commands: {e}")
            raise
    
    async def _attempt_rollback(
        self,
        project: Project,
        github_repo_url: str,
        config: DeploymentConfiguration
    ) -> None:
        """Attempt to rollback to previous deployment."""
        try:
            # Get last successful deployment
            last_deployment = self.deployment_history.get_latest_deployment("github_pages")
            
            if last_deployment and last_deployment["status"] == "success":
                logger.info(f"Attempting rollback to deployment: {last_deployment['id']}")
                
                # Implementation would restore previous deployment
                # This is a simplified version
                logger.info("Rollback mechanism would be implemented here")
            else:
                logger.warning("No previous successful deployment found for rollback")
        
        except Exception as e:
            logger.error(f"Rollback attempt failed: {e}")
    
    async def get_deployment_status(
        self,
        owner: str,
        repo_name: str
    ) -> Dict[str, Any]:
        """
        Get deployment status for GitHub Pages.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Dictionary with deployment status
        """
        status = {
            "enabled": False,
            "url": None,
            "custom_domain": None,
            "https_enforced": False,
            "last_deployment": None,
            "build_status": None,
            "error": None
        }
        
        try:
            # Get GitHub Pages configuration
            pages_config = await self.github_service.get_github_pages_config(owner, repo_name)
            
            if pages_config:
                status["enabled"] = pages_config.enabled
                status["url"] = pages_config.url
                status["custom_domain"] = pages_config.custom_domain
                status["https_enforced"] = pages_config.https_enforced
                status["build_status"] = pages_config.status.value if pages_config.status else None
            
            # Get last deployment from history
            last_deployment = self.deployment_history.get_latest_deployment("github_pages")
            if last_deployment:
                status["last_deployment"] = last_deployment
            
        except Exception as e:
            status["error"] = str(e)
            logger.error(f"Error getting deployment status: {e}")
        
        return status
    
    async def list_deployments(
        self,
        target: str = "github_pages",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List recent deployments.
        
        Args:
            target: Deployment target
            limit: Maximum number of deployments to return
            
        Returns:
            List of deployment records
        """
        deployments = []
        
        for deployment in reversed(self.deployment_history.deployments):
            if deployment["target"] == target:
                deployments.append(deployment)
                if len(deployments) >= limit:
                    break
        
        return deployments
    
    def get_deployment_targets(self) -> List[DeploymentTarget]:
        """Get list of available deployment targets."""
        return [
            DeploymentTarget(
                name="GitHub Pages",
                target_type="github_pages",
                url="https://pages.github.com",
                configuration={
                    "supported_branches": ["gh-pages", "main", "master"],
                    "custom_domain_support": True,
                    "https_enforcement": True
                }
            )
        ]
    
    def get_active_deployments(self) -> List[Dict[str, Any]]:
        """Get currently active deployments."""
        active = []
        
        for operation_id, deployment_info in self.active_deployments.items():
            info = deployment_info.copy()
            info["operation_id"] = operation_id
            info["elapsed_time"] = (
                datetime.now() - deployment_info["start_time"]
            ).total_seconds()
            active.append(info)
        
        return active
    
    def cancel_deployment(self, operation_id: str) -> bool:
        """Cancel active deployment operation."""
        if operation_id in self.active_deployments:
            self.active_deployments.pop(operation_id)
            
            # Record cancelled deployment
            self.deployment_history.add_deployment(
                deployment_id=operation_id,
                target="github_pages",
                status="cancelled",
                deployment_time=datetime.now()
            )
            
            logger.info(f"Cancelled deployment operation: {operation_id}")
            return True
        
        return False