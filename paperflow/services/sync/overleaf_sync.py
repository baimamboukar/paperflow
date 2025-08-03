"""
Overleaf synchronization service for Paperflow.

This service handles synchronization with Overleaf Git repositories,
including authentication, conflict detection, and file management.
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
from urllib.parse import urlparse

from paperflow.config.settings import Settings
from paperflow.models.project import Project
from paperflow.models.git import GitRepository
from paperflow.utils.git_utils import GitCredentials
from paperflow.models.sync import (
    SyncResult, SyncStatus, SyncOperationType, SyncConflict, 
    ConflictResolution, SyncConfiguration, SyncMetrics
)
from paperflow.services.base import BaseService
from paperflow.services.git_service import GitService
from paperflow.utils.logging import setup_logging
from paperflow.utils.file_utils import FileUtils

logger = setup_logging(__name__)


class OverleafCredentials:
    """Credentials for Overleaf Git access."""
    
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssh_key_path: Optional[Path] = None,
        ssh_key_passphrase: Optional[str] = None
    ):
        self.username = username
        self.password = password
        self.ssh_key_path = ssh_key_path
        self.ssh_key_passphrase = ssh_key_passphrase
    
    def to_git_credentials(self) -> GitCredentials:
        """Convert to GitCredentials object."""
        return GitCredentials(
            username=self.username,
            password=self.password,
            ssh_key_path=self.ssh_key_path,
            ssh_key_passphrase=self.ssh_key_passphrase
        )
    
    @property
    def is_valid(self) -> bool:
        """Check if credentials are valid."""
        has_password_auth = self.username and self.password
        has_ssh_auth = self.ssh_key_path and self.ssh_key_path.exists()
        return has_password_auth or has_ssh_auth


class OverleafProject:
    """Represents an Overleaf project."""
    
    def __init__(
        self,
        project_id: str,
        name: str,
        git_url: str,
        owner_id: Optional[str] = None,
        collaborators: Optional[List[str]] = None,
        last_modified: Optional[datetime] = None
    ):
        self.project_id = project_id
        self.name = name
        self.git_url = git_url
        self.owner_id = owner_id
        self.collaborators = collaborators or []
        self.last_modified = last_modified
    
    def get_read_only_url(self) -> str:
        """Get read-only Git URL."""
        return self.git_url.replace("/project/", "/project/read-only/")
    
    def extract_project_id_from_url(self, url: str) -> Optional[str]:
        """Extract project ID from Overleaf Git URL."""
        try:
            parsed = urlparse(url)
            if "overleaf.com" in parsed.netloc or "git.overleaf.com" in parsed.netloc:
                # URLs like: https://git.overleaf.com/PROJECT_ID
                path_parts = parsed.path.strip("/").split("/")
                if path_parts:
                    return path_parts[-1]  # Last part should be project ID
            return None
        except Exception:
            return None


class OverleafFileManager:
    """Manages file operations for Overleaf sync."""
    
    def __init__(self):
        self.file_utils = FileUtils()
        # File patterns that are typically safe to sync from Overleaf
        self.allowed_patterns = {
            "*.tex", "*.bib", "*.cls", "*.sty", "*.bst",
            "*.png", "*.jpg", "*.jpeg", "*.pdf", "*.eps", "*.svg",
            "*.txt", "*.md", "*.json", "*.yaml", "*.yml"
        }
        # Patterns to exclude from sync
        self.excluded_patterns = {
            "*.aux", "*.log", "*.out", "*.toc", "*.lof", "*.lot",
            "*.fdb_latexmk", "*.fls", "*.synctex.gz", "*.bbl", "*.blg",
            ".git/*", "*.tmp", "*.temp", "*.backup"
        }
    
    def should_sync_file(self, file_path: Path) -> bool:
        """Determine if a file should be synced."""
        file_name = file_path.name
        
        # Check excluded patterns first
        for pattern in self.excluded_patterns:
            if self.file_utils.matches_pattern(file_name, pattern):
                return False
        
        # Check allowed patterns
        for pattern in self.allowed_patterns:
            if self.file_utils.matches_pattern(file_name, pattern):
                return True
        
        return False
    
    def detect_file_conflicts(
        self,
        local_files: Dict[str, datetime],
        remote_files: Dict[str, datetime]
    ) -> List[SyncConflict]:
        """Detect conflicts between local and remote files."""
        conflicts = []
        
        for file_path, remote_time in remote_files.items():
            if file_path in local_files:
                local_time = local_files[file_path]
                
                # Check if files have diverged (both modified since last sync)
                if abs((remote_time - local_time).total_seconds()) > 60:  # 1 minute tolerance
                    conflict = SyncConflict(
                        file_path=file_path,
                        conflict_type="modification_conflict",
                        details={
                            "local_modified": local_time.isoformat(),
                            "remote_modified": remote_time.isoformat(),
                            "time_diff_seconds": (remote_time - local_time).total_seconds()
                        }
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def get_file_inventory(self, directory: Path) -> Dict[str, datetime]:
        """Get inventory of files with modification times."""
        inventory = {}
        
        for file_path in directory.rglob("*"):
            if file_path.is_file() and self.should_sync_file(file_path):
                relative_path = file_path.relative_to(directory)
                modification_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                inventory[str(relative_path)] = modification_time
        
        return inventory


class OverleafSync(BaseService):
    """
    Overleaf synchronization service.
    
    Handles synchronization with Overleaf Git repositories, including
    authentication, conflict detection, and file management.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize Overleaf sync service."""
        super().__init__(settings)
        
        # Service dependencies
        self.git_service: Optional[GitService] = None
        self.file_manager = OverleafFileManager()
        
        # Credentials and configuration
        self.credentials: Optional[OverleafCredentials] = None
        self.temp_dir_base: Optional[Path] = None
        
        # Active sync operations
        self.active_syncs: Dict[str, Path] = {}  # operation_id -> temp_path
    
    def _perform_initialization(self) -> None:
        """Perform service-specific initialization."""
        logger.info("Initializing OverleafSync service")
        
        # Initialize Git service
        self.git_service = GitService(self.settings)
        if self.settings:
            self.git_service.initialize(self.settings)
        
        # Setup temporary directory
        self.temp_dir_base = Path(tempfile.gettempdir()) / "paperflow_overleaf"
        self.temp_dir_base.mkdir(exist_ok=True)
        
        # Load credentials from settings
        self._load_credentials_from_settings()
        
        logger.info("OverleafSync service initialized")
    
    def _perform_cleanup(self) -> None:
        """Perform service cleanup."""
        logger.info("Cleaning up OverleafSync service")
        
        # Cleanup temporary directories
        for temp_path in self.active_syncs.values():
            try:
                if temp_path.exists():
                    self.file_manager.file_utils.remove_directory(temp_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory {temp_path}: {e}")
        
        self.active_syncs.clear()
        
        # Cleanup Git service
        if self.git_service:
            self.git_service.cleanup()
        
        logger.info("OverleafSync service cleanup completed")
    
    def _load_credentials_from_settings(self) -> None:
        """Load Overleaf credentials from settings."""
        if not self.settings:
            return
        
        # Try to load credentials from settings
        overleaf_username = getattr(self.settings, 'overleaf_username', None)
        overleaf_password = getattr(self.settings, 'overleaf_password', None)
        overleaf_ssh_key = getattr(self.settings, 'overleaf_ssh_key_path', None)
        
        if overleaf_username or overleaf_ssh_key:
            self.credentials = OverleafCredentials(
                username=overleaf_username,
                password=overleaf_password,
                ssh_key_path=Path(overleaf_ssh_key) if overleaf_ssh_key else None
            )
            logger.info("Loaded Overleaf credentials from settings")
    
    def set_credentials(self, credentials: OverleafCredentials) -> None:
        """Set Overleaf credentials."""
        self.credentials = credentials
        logger.info("Updated Overleaf credentials")
    
    def validate_overleaf_url(self, url: str) -> bool:
        """Validate Overleaf Git URL format."""
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ['https', 'http'] and
                ('overleaf.com' in parsed.netloc or 'git.overleaf.com' in parsed.netloc) and
                len(parsed.path.strip('/')) > 0
            )
        except Exception:
            return False
    
    async def test_connection(self, project_url: str) -> Dict[str, Any]:
        """
        Test connection to Overleaf project.
        
        Args:
            project_url: Overleaf Git URL
            
        Returns:
            Dictionary with connection test results
        """
        result = {
            "success": False,
            "accessible": False,
            "project_info": None,
            "error": None
        }
        
        try:
            if not self.validate_overleaf_url(project_url):
                result["error"] = "Invalid Overleaf URL format"
                return result
            
            if not self.credentials or not self.credentials.is_valid:
                result["error"] = "No valid Overleaf credentials configured"
                return result
            
            # Create temporary directory for test
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "test_clone"
                
                # Attempt to clone (shallow)
                clone_result = await self.git_service.clone_repository(
                    url=project_url,
                    destination=temp_path,
                    depth=1,
                    credentials=self.credentials.to_git_credentials()
                )
                
                if clone_result.success:
                    result["success"] = True
                    result["accessible"] = True
                    
                    # Get basic project info
                    project_info = await self._extract_project_info(temp_path)
                    result["project_info"] = project_info
                    
                    logger.info(f"Successfully tested connection to Overleaf project")
                else:
                    result["error"] = clone_result.error
                    logger.warning(f"Failed to connect to Overleaf project: {clone_result.error}")
        
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error testing Overleaf connection: {e}")
        
        return result
    
    async def sync_from_overleaf(
        self,
        project: Project,
        overleaf_url: str,
        target_directory: Path,
        config: Optional[SyncConfiguration] = None
    ) -> SyncResult:
        """
        Sync project from Overleaf.
        
        Args:
            project: Target project
            overleaf_url: Overleaf Git URL
            target_directory: Local directory to sync to
            config: Sync configuration
            
        Returns:
            SyncResult with operation details
        """
        operation_id = f"overleaf_sync_{project.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        sync_result = SyncResult(
            operation_id=operation_id,
            operation_type=SyncOperationType.OVERLEAF_SYNC,
            trigger=project.last_sync or datetime.now(),
            overleaf_repo_url=overleaf_url,
            configuration=config
        )
        
        sync_result.mark_started()
        
        try:
            # Validate inputs
            if not self.validate_overleaf_url(overleaf_url):
                raise ValueError("Invalid Overleaf URL")
            
            if not self.credentials or not self.credentials.is_valid:
                raise ValueError("No valid Overleaf credentials configured")
            
            # Create temporary working directory
            temp_dir = self.temp_dir_base / operation_id
            temp_dir.mkdir(exist_ok=True)
            self.active_syncs[operation_id] = temp_dir
            
            logger.info(f"Starting Overleaf sync for project '{project.name}'")
            
            # Clone Overleaf repository
            clone_result = await self._clone_overleaf_repo(
                overleaf_url, temp_dir, sync_result
            )
            
            if not clone_result:
                raise RuntimeError("Failed to clone Overleaf repository")
            
            # Detect and handle conflicts
            await self._detect_conflicts(
                target_directory, temp_dir, sync_result, config
            )
            
            # Handle conflicts if any
            if sync_result.has_unresolved_conflicts():
                if config and config.auto_resolve_conflicts:
                    await self._auto_resolve_conflicts(
                        sync_result, config.conflict_resolution_strategy
                    )
                else:
                    sync_result.status = SyncStatus.CONFLICT
                    logger.warning(f"Sync has unresolved conflicts: {len(sync_result.conflicts)}")
                    return sync_result
            
            # Sync files to target directory
            await self._sync_files_to_target(
                temp_dir, target_directory, sync_result
            )
            
            # Update project metadata
            project.last_sync = datetime.now()
            sync_result.target_commit_hash = clone_result.get("commit_hash")
            
            sync_result.mark_completed(success=True)
            logger.info(f"Successfully completed Overleaf sync for project '{project.name}'")
        
        except Exception as e:
            sync_result.mark_completed(success=False, error=str(e))
            logger.error(f"Overleaf sync failed for project '{project.name}': {e}")
        
        finally:
            # Cleanup temporary directory
            if operation_id in self.active_syncs:
                temp_path = self.active_syncs.pop(operation_id)
                try:
                    if temp_path.exists():
                        self.file_manager.file_utils.remove_directory(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")
        
        return sync_result
    
    async def _clone_overleaf_repo(
        self,
        overleaf_url: str,
        temp_dir: Path,
        sync_result: SyncResult
    ) -> Optional[Dict[str, Any]]:
        """Clone Overleaf repository to temporary directory."""
        try:
            clone_result = await self.git_service.clone_repository(
                url=overleaf_url,
                destination=temp_dir / "overleaf_repo",
                credentials=self.credentials.to_git_credentials()
            )
            
            if clone_result.success:
                # Load repository to get commit info
                repo = await self.git_service.load_repository(temp_dir / "overleaf_repo")
                if repo and repo.recent_commits:
                    latest_commit = repo.recent_commits[0]
                    sync_result.source_commit_hash = latest_commit.hash
                    
                    return {
                        "commit_hash": latest_commit.hash,
                        "commit_message": latest_commit.message,
                        "author": latest_commit.author_name,
                        "date": latest_commit.commit_date
                    }
                
                return {"success": True}
            else:
                sync_result.add_warning(f"Failed to clone Overleaf repository: {clone_result.error}")
                return None
        
        except Exception as e:
            logger.error(f"Error cloning Overleaf repository: {e}")
            return None
    
    async def _detect_conflicts(
        self,
        local_dir: Path,
        remote_dir: Path,
        sync_result: SyncResult,
        config: Optional[SyncConfiguration]
    ) -> None:
        """Detect conflicts between local and remote files."""
        try:
            overleaf_repo_dir = remote_dir / "overleaf_repo"
            
            if not local_dir.exists() or not overleaf_repo_dir.exists():
                return
            
            # Get file inventories
            local_files = self.file_manager.get_file_inventory(local_dir)
            remote_files = self.file_manager.get_file_inventory(overleaf_repo_dir)
            
            # Detect conflicts
            conflicts = self.file_manager.detect_file_conflicts(local_files, remote_files)
            
            for conflict in conflicts:
                sync_result.add_conflict(conflict)
            
            # Update metrics
            sync_result.metrics.files_pulled = len(remote_files)
            sync_result.metrics.conflicts_detected = len(conflicts)
            
            if conflicts:
                logger.info(f"Detected {len(conflicts)} file conflicts")
        
        except Exception as e:
            logger.error(f"Error detecting conflicts: {e}")
            sync_result.add_warning(f"Failed to detect conflicts: {e}")
    
    async def _auto_resolve_conflicts(
        self,
        sync_result: SyncResult,
        strategy: ConflictResolution
    ) -> None:
        """Automatically resolve conflicts based on strategy."""
        resolved_count = 0
        
        for conflict in sync_result.conflicts:
            if conflict.resolution:
                continue  # Already resolved
            
            try:
                if strategy == ConflictResolution.OVERLEAF_WINS:
                    # Use Overleaf version
                    conflict.resolution = ConflictResolution.OVERLEAF_WINS
                    conflict.resolved_at = datetime.now()
                    resolved_count += 1
                    
                elif strategy == ConflictResolution.GITHUB_WINS:
                    # Keep local version
                    conflict.resolution = ConflictResolution.GITHUB_WINS
                    conflict.resolved_at = datetime.now()
                    resolved_count += 1
                    
                elif strategy == ConflictResolution.SKIP_CONFLICTED:
                    # Skip conflicted files
                    conflict.resolution = ConflictResolution.SKIP_CONFLICTED
                    conflict.resolved_at = datetime.now()
                    resolved_count += 1
            
            except Exception as e:
                logger.warning(f"Failed to auto-resolve conflict for {conflict.file_path}: {e}")
        
        sync_result.metrics.conflicts_resolved = resolved_count
        logger.info(f"Auto-resolved {resolved_count} conflicts using strategy: {strategy.value}")
    
    async def _sync_files_to_target(
        self,
        source_dir: Path,
        target_dir: Path,
        sync_result: SyncResult
    ) -> None:
        """Sync files from source to target directory."""
        try:
            overleaf_repo_dir = source_dir / "overleaf_repo"
            
            if not overleaf_repo_dir.exists():
                raise RuntimeError("Overleaf repository directory not found")
            
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)
            
            files_copied = 0
            files_modified = 0
            files_added = 0
            
            # Process each file in the Overleaf repository
            for file_path in overleaf_repo_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                
                # Skip git files
                if ".git" in file_path.parts:
                    continue
                
                # Check if file should be synced
                if not self.file_manager.should_sync_file(file_path):
                    continue
                
                # Calculate relative path
                relative_path = file_path.relative_to(overleaf_repo_dir)
                target_file_path = target_dir / relative_path
                
                # Check for conflicts
                skip_file = False
                for conflict in sync_result.conflicts:
                    if (
                        str(relative_path) == conflict.file_path and
                        conflict.resolution == ConflictResolution.SKIP_CONFLICTED
                    ):
                        skip_file = True
                        break
                    elif (
                        str(relative_path) == conflict.file_path and
                        conflict.resolution == ConflictResolution.GITHUB_WINS
                    ):
                        skip_file = True
                        break
                
                if skip_file:
                    continue
                
                # Create parent directories
                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Determine if file is new or modified
                if target_file_path.exists():
                    files_modified += 1
                else:
                    files_added += 1
                
                # Copy file
                self.file_manager.file_utils.copy_file(file_path, target_file_path)
                files_copied += 1
            
            # Update metrics
            sync_result.metrics.files_pulled = files_copied
            sync_result.metrics.files_modified = files_modified
            sync_result.metrics.files_added = files_added
            
            logger.info(f"Synced {files_copied} files from Overleaf to target directory")
        
        except Exception as e:
            logger.error(f"Error syncing files to target: {e}")
            raise
    
    async def _extract_project_info(self, repo_path: Path) -> Dict[str, Any]:
        """Extract basic project information from cloned repository."""
        info = {
            "name": repo_path.name,
            "file_count": 0,
            "latex_files": [],
            "has_main_tex": False,
            "has_bibliography": False
        }
        
        try:
            # Count files and identify LaTeX files
            for file_path in repo_path.rglob("*"):
                if file_path.is_file() and ".git" not in file_path.parts:
                    info["file_count"] += 1
                    
                    if file_path.suffix == ".tex":
                        info["latex_files"].append(file_path.name)
                        if file_path.name == "main.tex":
                            info["has_main_tex"] = True
                    
                    elif file_path.suffix == ".bib":
                        info["has_bibliography"] = True
        
        except Exception as e:
            logger.warning(f"Error extracting project info: {e}")
        
        return info
    
    async def get_project_status(self, project_url: str) -> Dict[str, Any]:
        """
        Get status information for an Overleaf project.
        
        Args:
            project_url: Overleaf Git URL
            
        Returns:
            Dictionary with project status
        """
        status = {
            "accessible": False,
            "last_modified": None,
            "commit_count": 0,
            "recent_commits": [],
            "file_count": 0,
            "error": None
        }
        
        try:
            # Test connection first
            connection_test = await self.test_connection(project_url)
            
            if not connection_test["success"]:
                status["error"] = connection_test["error"]
                return status
            
            status["accessible"] = True
            
            # Get more detailed information if accessible
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "status_check"
                
                clone_result = await self.git_service.clone_repository(
                    url=project_url,
                    destination=temp_path,
                    credentials=self.credentials.to_git_credentials()
                )
                
                if clone_result.success:
                    repo = await self.git_service.load_repository(temp_path)
                    
                    if repo:
                        status["commit_count"] = len(repo.recent_commits)
                        status["recent_commits"] = [
                            {
                                "hash": commit.short_hash,
                                "message": commit.message,
                                "author": commit.author_name,
                                "date": commit.commit_date.isoformat()
                            }
                            for commit in repo.recent_commits[:5]
                        ]
                        
                        if repo.recent_commits:
                            status["last_modified"] = repo.recent_commits[0].commit_date.isoformat()
                        
                        # Count files
                        file_count = 0
                        for file_path in temp_path.rglob("*"):
                            if file_path.is_file() and ".git" not in file_path.parts:
                                file_count += 1
                        status["file_count"] = file_count
        
        except Exception as e:
            status["error"] = str(e)
            logger.error(f"Error getting Overleaf project status: {e}")
        
        return status
    
    def get_supported_file_types(self) -> List[str]:
        """Get list of supported file types for sync."""
        return list(self.file_manager.allowed_patterns)
    
    def get_excluded_file_types(self) -> List[str]:
        """Get list of excluded file types."""
        return list(self.file_manager.excluded_patterns)