"""Data models for Paperflow."""

from paperflow.models.project import Project
from paperflow.models.author import Author
from paperflow.models.config import SyncConfig, BuildConfig, WebConfig
from paperflow.models.git import (
    GitRepository, GitRemote, GitBranch, GitCommit, GitStatus,
    GitOperationResult, CloneResult, PullResult, PushResult, 
    CommitResult, MergeResult
)
from paperflow.models.github import (
    GitHubRepository, GitHubPages, GitHubWebhook, GitHubRelease,
    GitHubDeployKey, GitHubUser, GitHubAPICredentials,
    GitHubOperationResult, RepositoryCreateResult, PagesConfigResult,
    WebhookCreateResult, ReleaseCreateResult, DeployKeyCreateResult
)
from paperflow.models.processor import (
    LaTeXDocument, HTMLDocument, Citation, Bibliography, Figure, Equation,
    ProcessingResult, ProcessingError, ProcessingWarning, DocumentSection,
    CrossReference, ProcessorConfig, ProcessingStatus, CitationStyle, MathRenderer
)

__all__ = [
    "Project",
    "Author", 
    "SyncConfig",
    "BuildConfig",
    "WebConfig",
    "GitRepository",
    "GitRemote", 
    "GitBranch",
    "GitCommit",
    "GitStatus",
    "GitOperationResult",
    "CloneResult",
    "PullResult",
    "PushResult",
    "CommitResult",
    "MergeResult",
    "GitHubRepository",
    "GitHubPages",
    "GitHubWebhook",
    "GitHubRelease",
    "GitHubDeployKey",
    "GitHubUser",
    "GitHubAPICredentials",
    "GitHubOperationResult",
    "RepositoryCreateResult",
    "PagesConfigResult",
    "WebhookCreateResult",
    "ReleaseCreateResult",
    "DeployKeyCreateResult",
    # Processor models
    "LaTeXDocument",
    "HTMLDocument",
    "Citation",
    "Bibliography",
    "Figure",
    "Equation",
    "ProcessingResult",
    "ProcessingError",
    "ProcessingWarning",
    "DocumentSection",
    "CrossReference",
    "ProcessorConfig",
    "ProcessingStatus",
    "CitationStyle",
    "MathRenderer",
]