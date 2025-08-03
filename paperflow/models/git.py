"""
Git data models for Paperflow.

This module defines Git-related models including repositories, commits,
branches, and operation results for managing Git operations in Paperflow.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class GitRemoteType(str, Enum):
    """Git remote type enumeration."""
    ORIGIN = "origin"
    UPSTREAM = "upstream"
    FORK = "fork"
    OVERLEAF = "overleaf"
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class GitOperationStatus(str, Enum):
    """Git operation status enumeration."""
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"
    PENDING = "pending"
    CANCELLED = "cancelled"


class GitConflictType(str, Enum):
    """Git conflict type enumeration."""
    MERGE = "merge"
    REBASE = "rebase"
    CHERRY_PICK = "cherry_pick"
    PULL = "pull"


class GitBranchType(str, Enum):
    """Git branch type enumeration."""
    LOCAL = "local"
    REMOTE = "remote"
    TRACKING = "tracking"


class GitRemote(BaseModel):
    """
    Git remote repository model.
    
    Represents a remote repository configuration with URL and metadata.
    """
    
    name: str = Field(..., description="Remote name (e.g., 'origin', 'upstream')")
    url: str = Field(..., description="Remote repository URL")
    remote_type: GitRemoteType = Field(default=GitRemoteType.ORIGIN, description="Type of remote")
    fetch_url: Optional[str] = Field(default=None, description="Fetch URL if different from push URL")
    is_default: bool = Field(default=False, description="Whether this is the default remote")
    
    # Authentication info
    requires_auth: bool = Field(default=False, description="Whether remote requires authentication")
    username: Optional[str] = Field(default=None, description="Username for authentication")
    
    # Metadata
    description: Optional[str] = Field(default=None, description="Remote description")
    created_at: datetime = Field(default_factory=datetime.now, description="When remote was added")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator("url")
    def validate_url(cls, v):
        """Validate Git URL format."""
        if not v:
            raise ValueError("Remote URL cannot be empty")
        
        # Basic URL validation for common Git URL formats
        valid_patterns = [
            v.startswith("https://"),
            v.startswith("http://"),
            v.startswith("git@"),
            v.startswith("ssh://"),
            v.startswith("file://")
        ]
        
        if not any(valid_patterns):
            raise ValueError("Invalid Git URL format")
        
        return v
    
    @validator("name")
    def validate_name(cls, v):
        """Validate remote name."""
        if not v or not v.strip():
            raise ValueError("Remote name cannot be empty")
        
        # Git remote names cannot contain spaces or special characters
        invalid_chars = " \t\n\r/*?[]{}()$&|;#"
        if any(char in v for char in invalid_chars):
            raise ValueError(f"Remote name contains invalid characters: {invalid_chars}")
        
        return v.strip()
    
    def get_host(self) -> Optional[str]:
        """Extract hostname from URL."""
        if self.url.startswith("https://") or self.url.startswith("http://"):
            # HTTP(S) URL
            from urllib.parse import urlparse
            parsed = urlparse(self.url)
            return parsed.hostname
        elif self.url.startswith("git@"):
            # SSH URL like git@github.com:user/repo.git
            if ":" in self.url:
                host_part = self.url.split("@")[1].split(":")[0]
                return host_part
        
        return None
    
    def is_github(self) -> bool:
        """Check if remote is a GitHub repository."""
        host = self.get_host()
        return host == "github.com" if host else False
    
    def is_gitlab(self) -> bool:
        """Check if remote is a GitLab repository."""
        host = self.get_host()
        return host == "gitlab.com" if host else False
    
    def is_overleaf(self) -> bool:
        """Check if remote is an Overleaf repository."""
        host = self.get_host()
        return host and "overleaf.com" in host


class GitBranch(BaseModel):
    """
    Git branch model.
    
    Represents a Git branch with its metadata and tracking information.
    """
    
    name: str = Field(..., description="Branch name")
    branch_type: GitBranchType = Field(default=GitBranchType.LOCAL, description="Type of branch")
    is_current: bool = Field(default=False, description="Whether this is the current branch")
    is_default: bool = Field(default=False, description="Whether this is the default branch")
    
    # Tracking information
    upstream_branch: Optional[str] = Field(default=None, description="Upstream branch name")
    upstream_remote: Optional[str] = Field(default=None, description="Upstream remote name")
    ahead_count: int = Field(default=0, description="Commits ahead of upstream")
    behind_count: int = Field(default=0, description="Commits behind upstream")
    
    # Commit information
    last_commit_hash: Optional[str] = Field(default=None, description="Last commit hash")
    last_commit_message: Optional[str] = Field(default=None, description="Last commit message")
    last_commit_date: Optional[datetime] = Field(default=None, description="Last commit date")
    last_commit_author: Optional[str] = Field(default=None, description="Last commit author")
    
    # Metadata
    created_at: Optional[datetime] = Field(default=None, description="Branch creation date")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator("name")
    def validate_name(cls, v):
        """Validate branch name."""
        if not v or not v.strip():
            raise ValueError("Branch name cannot be empty")
        
        # Git branch name restrictions
        invalid_chars = " ~^:?*[]\\"
        if any(char in v for char in invalid_chars):
            raise ValueError(f"Branch name contains invalid characters: {invalid_chars}")
        
        if v.startswith("-") or v.endswith(".") or ".." in v:
            raise ValueError("Invalid branch name format")
        
        return v.strip()
    
    def get_full_upstream_name(self) -> Optional[str]:
        """Get full upstream branch name (remote/branch)."""
        if self.upstream_remote and self.upstream_branch:
            return f"{self.upstream_remote}/{self.upstream_branch}"
        return None
    
    def is_ahead(self) -> bool:
        """Check if branch is ahead of upstream."""
        return self.ahead_count > 0
    
    def is_behind(self) -> bool:
        """Check if branch is behind upstream."""
        return self.behind_count > 0
    
    def needs_sync(self) -> bool:
        """Check if branch needs synchronization with upstream."""
        return self.is_ahead() or self.is_behind()


class GitCommit(BaseModel):
    """
    Git commit model.
    
    Represents a Git commit with metadata and changes.
    """
    
    hash: str = Field(..., description="Commit hash (SHA)")
    short_hash: str = Field(..., description="Short commit hash")
    message: str = Field(..., description="Commit message")
    author_name: str = Field(..., description="Commit author name")
    author_email: str = Field(..., description="Commit author email")
    committer_name: Optional[str] = Field(default=None, description="Committer name")
    committer_email: Optional[str] = Field(default=None, description="Committer email")
    
    # Timestamps
    author_date: datetime = Field(..., description="Author date")
    commit_date: datetime = Field(..., description="Commit date")
    
    # Commit details
    branch: Optional[str] = Field(default=None, description="Branch where commit was made")
    parent_hashes: List[str] = Field(default_factory=list, description="Parent commit hashes")
    is_merge: bool = Field(default=False, description="Whether this is a merge commit")
    
    # File changes
    files_changed: List[str] = Field(default_factory=list, description="List of changed files")
    insertions: int = Field(default=0, description="Number of lines inserted")
    deletions: int = Field(default=0, description="Number of lines deleted")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Associated tags")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator("hash")
    def validate_hash(cls, v):
        """Validate commit hash format."""
        if not v or len(v) < 7:
            raise ValueError("Commit hash must be at least 7 characters")
        
        # Check if it's a valid hex string
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Commit hash must be a valid hexadecimal string")
        
        return v.lower()
    
    @validator("short_hash")
    def validate_short_hash(cls, v):
        """Validate short commit hash."""
        if not v or len(v) < 7 or len(v) > 12:
            raise ValueError("Short hash must be 7-12 characters")
        
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Short hash must be a valid hexadecimal string")
        
        return v.lower()
    
    def get_author_info(self) -> str:
        """Get formatted author information."""
        return f"{self.author_name} <{self.author_email}>"
    
    def get_summary_line(self) -> str:
        """Get the first line of commit message."""
        return self.message.split('\n')[0] if self.message else ""
    
    def get_body(self) -> str:
        """Get commit message body (excluding first line)."""
        lines = self.message.split('\n')
        if len(lines) > 2:
            return '\n'.join(lines[2:]).strip()
        return ""


class GitStatus(BaseModel):
    """
    Git repository status model.
    
    Represents the current working directory status.
    """
    
    # Working directory status
    modified_files: List[str] = Field(default_factory=list, description="Modified files")
    added_files: List[str] = Field(default_factory=list, description="Added/new files")
    deleted_files: List[str] = Field(default_factory=list, description="Deleted files")
    renamed_files: List[str] = Field(default_factory=list, description="Renamed files")
    copied_files: List[str] = Field(default_factory=list, description="Copied files")
    untracked_files: List[str] = Field(default_factory=list, description="Untracked files")
    
    # Index status
    staged_files: List[str] = Field(default_factory=list, description="Files in staging area")
    unstaged_files: List[str] = Field(default_factory=list, description="Unstaged changes")
    
    # Repository state
    current_branch: Optional[str] = Field(default=None, description="Current branch name")
    is_clean: bool = Field(default=True, description="Whether working directory is clean")
    has_staged_changes: bool = Field(default=False, description="Whether there are staged changes")
    has_unstaged_changes: bool = Field(default=False, description="Whether there are unstaged changes")
    has_untracked_files: bool = Field(default=False, description="Whether there are untracked files")
    
    # Merge/conflict status
    is_merging: bool = Field(default=False, description="Whether repository is in merge state")
    is_rebasing: bool = Field(default=False, description="Whether repository is in rebase state")
    has_conflicts: bool = Field(default=False, description="Whether there are merge conflicts")
    conflicted_files: List[str] = Field(default_factory=list, description="Files with conflicts")
    
    # Tracking status
    ahead_count: int = Field(default=0, description="Commits ahead of upstream")
    behind_count: int = Field(default=0, description="Commits behind upstream")
    
    def get_total_changes(self) -> int:
        """Get total number of changes."""
        return len(self.modified_files) + len(self.added_files) + len(self.deleted_files)
    
    def needs_commit(self) -> bool:
        """Check if repository needs to be committed."""
        return self.has_staged_changes or self.has_unstaged_changes
    
    def can_commit(self) -> bool:
        """Check if repository can be committed (has staged changes)."""
        return self.has_staged_changes and not self.has_conflicts


class GitOperationResult(BaseModel):
    """
    Base class for Git operation results.
    
    Represents the result of a Git operation with status and metadata.
    """
    
    operation: str = Field(..., description="Operation name")
    status: GitOperationStatus = Field(..., description="Operation status")
    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(default="", description="Operation message")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Timing information
    started_at: datetime = Field(default_factory=datetime.now, description="Operation start time")
    completed_at: Optional[datetime] = Field(default=None, description="Operation completion time")
    duration_seconds: Optional[float] = Field(default=None, description="Operation duration")
    
    # Command information
    command: Optional[str] = Field(default=None, description="Git command executed")
    exit_code: Optional[int] = Field(default=None, description="Command exit code")
    stdout: Optional[str] = Field(default=None, description="Command standard output")
    stderr: Optional[str] = Field(default=None, description="Command standard error")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def mark_completed(self, success: bool = True, message: str = "") -> None:
        """Mark operation as completed."""
        self.completed_at = datetime.now()
        self.success = success
        self.status = GitOperationStatus.SUCCESS if success else GitOperationStatus.FAILED
        if message:
            self.message = message
        
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()


class CloneResult(GitOperationResult):
    """Result of a Git clone operation."""
    
    repository_path: Optional[Path] = Field(default=None, description="Path to cloned repository")
    remote_url: Optional[str] = Field(default=None, description="URL of cloned repository")
    default_branch: Optional[str] = Field(default=None, description="Default branch of repository")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Path: lambda v: str(v)
        }


class PullResult(GitOperationResult):
    """Result of a Git pull operation."""
    
    commits_pulled: int = Field(default=0, description="Number of commits pulled")
    files_changed: List[str] = Field(default_factory=list, description="Files changed in pull")
    had_conflicts: bool = Field(default=False, description="Whether pull had conflicts")
    conflict_files: List[str] = Field(default_factory=list, description="Files with conflicts")
    
    # Merge information
    merge_commit: Optional[str] = Field(default=None, description="Merge commit hash if created")
    fast_forward: bool = Field(default=False, description="Whether pull was fast-forward")


class PushResult(GitOperationResult):
    """Result of a Git push operation."""
    
    commits_pushed: int = Field(default=0, description="Number of commits pushed")
    bytes_pushed: Optional[int] = Field(default=None, description="Bytes pushed")
    remote_name: Optional[str] = Field(default=None, description="Remote name pushed to")
    branch_name: Optional[str] = Field(default=None, description="Branch pushed")
    
    # Push details
    rejected: bool = Field(default=False, description="Whether push was rejected")
    forced: bool = Field(default=False, description="Whether push was forced")
    created_remote_branch: bool = Field(default=False, description="Whether remote branch was created")


class CommitResult(GitOperationResult):
    """Result of a Git commit operation."""
    
    commit_hash: Optional[str] = Field(default=None, description="Hash of created commit")
    files_committed: List[str] = Field(default_factory=list, description="Files included in commit")
    commit_message: Optional[str] = Field(default=None, description="Commit message used")
    
    # Commit statistics
    insertions: int = Field(default=0, description="Lines inserted")
    deletions: int = Field(default=0, description="Lines deleted")
    files_changed: int = Field(default=0, description="Number of files changed")


class MergeResult(GitOperationResult):
    """Result of a Git merge operation."""
    
    merge_commit: Optional[str] = Field(default=None, description="Merge commit hash")
    merged_branch: Optional[str] = Field(default=None, description="Branch that was merged")
    fast_forward: bool = Field(default=False, description="Whether merge was fast-forward")
    
    # Conflict information
    had_conflicts: bool = Field(default=False, description="Whether merge had conflicts")
    conflict_files: List[str] = Field(default_factory=list, description="Files with conflicts")
    auto_resolved: int = Field(default=0, description="Number of auto-resolved conflicts")


class GitRepository(BaseModel):
    """
    Git repository model.
    
    Represents a complete Git repository with its configuration and state.
    """
    
    # Repository path and basic info
    path: Path = Field(..., description="Repository root path")
    name: str = Field(..., description="Repository name")
    
    # Repository state
    is_valid: bool = Field(default=True, description="Whether repository is valid")
    is_bare: bool = Field(default=False, description="Whether repository is bare")
    is_empty: bool = Field(default=False, description="Whether repository is empty")
    
    # Current state
    current_branch: Optional[GitBranch] = Field(default=None, description="Current active branch")
    status: Optional[GitStatus] = Field(default=None, description="Working directory status")
    
    # Repository components
    branches: List[GitBranch] = Field(default_factory=list, description="Repository branches")
    remotes: List[GitRemote] = Field(default_factory=list, description="Repository remotes")
    recent_commits: List[GitCommit] = Field(default_factory=list, description="Recent commits")
    
    # Configuration
    user_name: Optional[str] = Field(default=None, description="Git user.name config")
    user_email: Optional[str] = Field(default=None, description="Git user.email config")
    
    # Metadata
    created_at: Optional[datetime] = Field(default=None, description="Repository creation date")
    last_commit_date: Optional[datetime] = Field(default=None, description="Last commit date")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last status update")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Path: lambda v: str(v)
        }
    
    @validator("path", pre=True)
    def validate_path(cls, v):
        """Validate and convert repository path."""
        if isinstance(v, str):
            return Path(v).resolve()
        elif isinstance(v, Path):
            return v.resolve()
        else:
            raise ValueError("Repository path must be a string or Path object")
    
    def get_git_dir(self) -> Path:
        """Get path to .git directory."""
        if self.is_bare:
            return self.path
        return self.path / ".git"
    
    def get_remote(self, name: str) -> Optional[GitRemote]:
        """Get remote by name."""
        for remote in self.remotes:
            if remote.name == name:
                return remote
        return None
    
    def get_default_remote(self) -> Optional[GitRemote]:
        """Get the default remote (usually 'origin')."""
        for remote in self.remotes:
            if remote.is_default or remote.name == "origin":
                return remote
        
        # If no default found, return first remote
        return self.remotes[0] if self.remotes else None
    
    def get_branch(self, name: str) -> Optional[GitBranch]:
        """Get branch by name."""
        for branch in self.branches:
            if branch.name == name:
                return branch
        return None
    
    def get_local_branches(self) -> List[GitBranch]:
        """Get all local branches."""
        return [b for b in self.branches if b.branch_type == GitBranchType.LOCAL]
    
    def get_remote_branches(self) -> List[GitBranch]:
        """Get all remote branches."""
        return [b for b in self.branches if b.branch_type == GitBranchType.REMOTE]
    
    def needs_sync(self) -> bool:
        """Check if repository needs synchronization."""
        if not self.current_branch:
            return False
        return self.current_branch.needs_sync()
    
    def has_uncommitted_changes(self) -> bool:
        """Check if repository has uncommitted changes."""
        if not self.status:
            return False
        return not self.status.is_clean
    
    def get_summary(self) -> Dict[str, Any]:
        """Get repository summary information."""
        return {
            "name": self.name,
            "path": str(self.path),
            "is_valid": self.is_valid,
            "current_branch": self.current_branch.name if self.current_branch else None,
            "branch_count": len(self.branches),
            "remote_count": len(self.remotes),
            "has_changes": self.has_uncommitted_changes(),
            "needs_sync": self.needs_sync(),
            "last_updated": self.last_updated.isoformat()
        }