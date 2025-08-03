"""
Git service for Paperflow.

This service provides comprehensive Git operations for managing repositories,
including cloning, pulling, pushing, branching, and commit operations with
proper error handling and async support.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from paperflow.config.settings import Settings
from paperflow.models.git import (
    CloneResult,
    CommitResult,
    GitBranch,
    GitBranchType,
    GitCommit,
    GitOperationResult,
    GitOperationStatus,
    GitRemote,
    GitRemoteType,
    GitRepository,
    GitStatus,
    MergeResult,
    PullResult,
    PushResult,
)
from paperflow.services.base import BaseService
from paperflow.utils.git_utils import (
    GitCommandExecutor,
    GitCredentialManager,
    GitCredentials,
    GitUrlParser,
    GitUtils,
)
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class GitService(BaseService):
    """
    Comprehensive Git service for repository management.

    Provides async Git operations with proper error handling, credential
    management, and integration with the Paperflow ecosystem.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize Git service.

        Args:
            settings: Service configuration settings
        """
        super().__init__(settings)
        self.executor: Optional[GitCommandExecutor] = None
        self.credential_manager = GitCredentialManager()

    def _perform_initialization(self) -> None:
        """Perform Git service initialization."""
        self.executor = GitCommandExecutor()
        logger.info("Git service initialized")

    def _perform_cleanup(self) -> None:
        """Perform Git service cleanup."""
        self.executor = None
        logger.info("Git service cleaned up")

    # Repository Management

    async def clone_repository(
        self,
        url: str,
        destination: Path,
        branch: Optional[str] = None,
        credentials: Optional[GitCredentials] = None,
        depth: Optional[int] = None,
        recursive: bool = False,
    ) -> CloneResult:
        """
        Clone a Git repository.

        Args:
            url: Repository URL to clone
            destination: Local path for cloned repository
            branch: Specific branch to clone
            credentials: Authentication credentials
            depth: Clone depth (for shallow clones)
            recursive: Whether to clone submodules recursively

        Returns:
            CloneResult with operation details
        """
        result = CloneResult(
            operation="clone",
            status=GitOperationStatus.PENDING,
            success=False,
            remote_url=url,
            repository_path=destination,
        )

        try:
            # Validate URL
            parsed_url = GitUrlParser.parse_url(url)
            if not parsed_url.is_valid:
                result.error = f"Invalid Git URL: {url}"
                result.status = GitOperationStatus.FAILED
                return result

            # Prepare clone command
            command = ["clone"]

            if branch:
                command.extend(["--branch", branch])

            if depth:
                command.extend(["--depth", str(depth)])

            if recursive:
                command.append("--recursive")

            command.extend([url, str(destination)])

            # Execute clone
            if credentials and parsed_url.requires_auth:
                (
                    exit_code,
                    stdout,
                    stderr,
                ) = await self.executor.execute_with_credentials(command, credentials)
            else:
                exit_code, stdout, stderr = await self.executor.execute(command)

            result.command = f"git {' '.join(command)}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                # Get cloned repository information
                repo_executor = GitCommandExecutor(destination)

                # Get default branch
                exit_code, branch_output, _ = await repo_executor.execute(
                    ["symbolic-ref", "refs/remotes/origin/HEAD"]
                )
                if exit_code == 0 and branch_output:
                    default_branch = branch_output.strip().split("/")[-1]
                    result.default_branch = default_branch

                result.mark_completed(
                    True, f"Successfully cloned repository to {destination}"
                )
                logger.info(f"Cloned repository {url} to {destination}")
            else:
                result.error = f"Clone failed: {stderr}"
                result.mark_completed(False, f"Failed to clone repository: {stderr}")
                logger.error(f"Failed to clone {url}: {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Clone operation failed: {e}")
            logger.error(f"Error during clone operation: {e}")

        return result

    async def load_repository(self, path: Path) -> Optional[GitRepository]:
        """
        Load an existing Git repository.

        Args:
            path: Path to repository directory

        Returns:
            GitRepository object or None if not a valid repository
        """
        try:
            # Check if it's a valid Git repository
            if not GitUtils.is_git_repository(path):
                logger.warning(f"Directory {path} is not a Git repository")
                return None

            # Initialize executor for this repository
            repo_executor = GitCommandExecutor(path)

            # Create repository object
            repository = GitRepository(
                path=path, name=GitUtils.get_repository_name(path)
            )

            # Load repository information
            await self._load_repository_status(repository, repo_executor)
            await self._load_repository_branches(repository, repo_executor)
            await self._load_repository_remotes(repository, repo_executor)
            await self._load_repository_config(repository, repo_executor)
            await self._load_recent_commits(repository, repo_executor)

            repository.last_updated = datetime.now()
            logger.info(f"Loaded repository: {repository.name}")

            return repository

        except Exception as e:
            logger.error(f"Failed to load repository from {path}: {e}")
            return None

    async def _load_repository_status(
        self, repository: GitRepository, executor: GitCommandExecutor
    ) -> None:
        """Load repository working directory status."""
        try:
            # Get status
            exit_code, stdout, stderr = await executor.execute(
                ["status", "--porcelain=v1", "-z"]
            )

            if exit_code != 0:
                logger.warning(f"Failed to get repository status: {stderr}")
                return

            status = GitStatus()

            # Parse porcelain output
            if stdout:
                files = GitUtils.parse_git_output(stdout, "null-separated")
                for file_line in files:
                    if len(file_line) < 3:
                        continue

                    index_status = file_line[0]
                    worktree_status = file_line[1]
                    filename = file_line[3:]  # Skip "XY "

                    # Parse status codes
                    if index_status != " ":
                        status.staged_files.append(filename)
                        status.has_staged_changes = True

                    if worktree_status != " ":
                        status.unstaged_files.append(filename)
                        status.has_unstaged_changes = True

                    # Categorize by type
                    if worktree_status == "M" or index_status == "M":
                        status.modified_files.append(filename)
                    elif worktree_status == "A" or index_status == "A":
                        status.added_files.append(filename)
                    elif worktree_status == "D" or index_status == "D":
                        status.deleted_files.append(filename)
                    elif worktree_status == "R" or index_status == "R":
                        status.renamed_files.append(filename)
                    elif worktree_status == "C" or index_status == "C":
                        status.copied_files.append(filename)
                    elif worktree_status == "?":
                        status.untracked_files.append(filename)
                        status.has_untracked_files = True

            # Check if repository is clean
            status.is_clean = not (
                status.has_staged_changes
                or status.has_unstaged_changes
                or status.has_untracked_files
            )

            # Get current branch
            exit_code, branch_output, _ = await executor.execute(
                ["branch", "--show-current"]
            )
            if exit_code == 0 and branch_output.strip():
                status.current_branch = branch_output.strip()

            # Check for merge/rebase state
            git_dir = repository.get_git_dir()
            status.is_merging = (git_dir / "MERGE_HEAD").exists()
            status.is_rebasing = (git_dir / "rebase-merge").exists() or (
                git_dir / "rebase-apply"
            ).exists()

            # Check for conflicts
            if status.is_merging or status.is_rebasing:
                exit_code, conflict_output, _ = await executor.execute(
                    ["diff", "--name-only", "--diff-filter=U"]
                )
                if exit_code == 0 and conflict_output:
                    status.conflicted_files = GitUtils.parse_git_output(conflict_output)
                    status.has_conflicts = len(status.conflicted_files) > 0

            repository.status = status

        except Exception as e:
            logger.error(f"Failed to load repository status: {e}")

    async def _load_repository_branches(
        self, repository: GitRepository, executor: GitCommandExecutor
    ) -> None:
        """Load repository branches."""
        try:
            # Get local branches
            exit_code, stdout, stderr = await executor.execute(
                ["branch", "-v", "--no-abbrev"]
            )

            if exit_code == 0 and stdout:
                for line in stdout.splitlines():
                    if not line.strip():
                        continue

                    is_current = line.startswith("*")
                    line = line[2:] if is_current else line[2:]  # Remove "* " or "  "

                    parts = line.split()
                    if len(parts) >= 2:
                        branch_name = parts[0]
                        commit_hash = parts[1]
                        commit_message = " ".join(parts[2:]) if len(parts) > 2 else ""

                        branch = GitBranch(
                            name=branch_name,
                            branch_type=GitBranchType.LOCAL,
                            is_current=is_current,
                            last_commit_hash=commit_hash,
                            last_commit_message=commit_message,
                        )

                        # Get upstream information
                        exit_code, upstream_output, _ = await executor.execute(
                            ["rev-parse", "--abbrev-ref", f"{branch_name}@{{upstream}}"]
                        )
                        if exit_code == 0 and upstream_output.strip():
                            upstream_parts = upstream_output.strip().split("/")
                            if len(upstream_parts) >= 2:
                                branch.upstream_remote = upstream_parts[0]
                                branch.upstream_branch = "/".join(upstream_parts[1:])

                        # Get ahead/behind counts
                        if branch.upstream_remote and branch.upstream_branch:
                            upstream_ref = (
                                f"{branch.upstream_remote}/{branch.upstream_branch}"
                            )
                            exit_code, count_output, _ = await executor.execute(
                                [
                                    "rev-list",
                                    "--count",
                                    "--left-right",
                                    f"{upstream_ref}...{branch_name}",
                                ]
                            )
                            if exit_code == 0 and count_output.strip():
                                counts = count_output.strip().split("\t")
                                if len(counts) == 2:
                                    branch.behind_count = int(counts[0])
                                    branch.ahead_count = int(counts[1])

                        repository.branches.append(branch)

                        if is_current:
                            repository.current_branch = branch

            # Get remote branches
            exit_code, stdout, stderr = await executor.execute(
                ["branch", "-r", "-v", "--no-abbrev"]
            )

            if exit_code == 0 and stdout:
                for line in stdout.splitlines():
                    if not line.strip() or "->" in line:  # Skip symbolic refs
                        continue

                    line = line.strip()
                    parts = line.split()
                    if len(parts) >= 2:
                        branch_name = parts[0]
                        commit_hash = parts[1]
                        commit_message = " ".join(parts[2:]) if len(parts) > 2 else ""

                        branch = GitBranch(
                            name=branch_name,
                            branch_type=GitBranchType.REMOTE,
                            last_commit_hash=commit_hash,
                            last_commit_message=commit_message,
                        )

                        repository.branches.append(branch)

        except Exception as e:
            logger.error(f"Failed to load repository branches: {e}")

    async def _load_repository_remotes(
        self, repository: GitRepository, executor: GitCommandExecutor
    ) -> None:
        """Load repository remotes."""
        try:
            # Get remote names
            exit_code, stdout, stderr = await executor.execute(["remote"])

            if exit_code == 0 and stdout:
                remote_names = GitUtils.parse_git_output(stdout)

                for remote_name in remote_names:
                    # Get remote URL
                    exit_code, url_output, _ = await executor.execute(
                        ["remote", "get-url", remote_name]
                    )
                    if exit_code != 0 or not url_output.strip():
                        continue

                    url = url_output.strip()
                    parsed_url = GitUrlParser.parse_url(url)

                    # Determine remote type
                    remote_type = GitRemoteType.ORIGIN
                    if remote_name == "upstream":
                        remote_type = GitRemoteType.UPSTREAM
                    elif parsed_url.is_github():
                        remote_type = GitRemoteType.GITHUB
                    elif parsed_url.is_gitlab():
                        remote_type = GitRemoteType.GITLAB
                    elif parsed_url.is_overleaf():
                        remote_type = GitRemoteType.OVERLEAF

                    remote = GitRemote(
                        name=remote_name,
                        url=url,
                        remote_type=remote_type,
                        is_default=(remote_name == "origin"),
                        requires_auth=parsed_url.requires_auth,
                    )

                    # Check if there's a different fetch URL
                    exit_code, fetch_url_output, _ = await executor.execute(
                        ["remote", "get-url", "--push", remote_name]
                    )
                    if (
                        exit_code == 0
                        and fetch_url_output.strip()
                        and fetch_url_output.strip() != url
                    ):
                        remote.fetch_url = url
                        remote.url = fetch_url_output.strip()

                    repository.remotes.append(remote)

        except Exception as e:
            logger.error(f"Failed to load repository remotes: {e}")

    async def _load_repository_config(
        self, repository: GitRepository, executor: GitCommandExecutor
    ) -> None:
        """Load repository configuration."""
        try:
            # Get user name
            exit_code, name_output, _ = await executor.execute(
                ["config", "--get", "user.name"]
            )
            if exit_code == 0 and name_output.strip():
                repository.user_name = name_output.strip()

            # Get user email
            exit_code, email_output, _ = await executor.execute(
                ["config", "--get", "user.email"]
            )
            if exit_code == 0 and email_output.strip():
                repository.user_email = email_output.strip()

        except Exception as e:
            logger.error(f"Failed to load repository config: {e}")

    async def _load_recent_commits(
        self, repository: GitRepository, executor: GitCommandExecutor, limit: int = 10
    ) -> None:
        """Load recent commits."""
        try:
            # Get recent commits
            format_str = (
                "%H%x00%h%x00%s%x00%an%x00%ae%x00%cn%x00%ce%x00%at%x00%ct%x00%P"
            )
            exit_code, stdout, stderr = await executor.execute(
                ["log", f"--max-count={limit}", f"--pretty=format:{format_str}"]
            )

            if exit_code == 0 and stdout:
                for line in stdout.splitlines():
                    if not line.strip():
                        continue

                    parts = line.split("\x00")
                    if len(parts) >= 9:
                        try:
                            commit = GitCommit(
                                hash=parts[0],
                                short_hash=parts[1],
                                message=parts[2],
                                author_name=parts[3],
                                author_email=parts[4],
                                committer_name=parts[5] if parts[5] else parts[3],
                                committer_email=parts[6] if parts[6] else parts[4],
                                author_date=datetime.fromtimestamp(int(parts[7])),
                                commit_date=datetime.fromtimestamp(int(parts[8])),
                                parent_hashes=parts[9].split()
                                if len(parts) > 9 and parts[9]
                                else [],
                                is_merge=len(parts[9].split()) > 1
                                if len(parts) > 9
                                else False,
                            )

                            repository.recent_commits.append(commit)

                            # Update repository last commit date
                            if (
                                not repository.last_commit_date
                                or commit.commit_date > repository.last_commit_date
                            ):
                                repository.last_commit_date = commit.commit_date

                        except (ValueError, IndexError) as e:
                            logger.warning(f"Failed to parse commit: {e}")
                            continue

        except Exception as e:
            logger.error(f"Failed to load recent commits: {e}")

    # Branch Operations

    async def create_branch(
        self,
        repository: GitRepository,
        branch_name: str,
        start_point: Optional[str] = None,
        checkout: bool = True,
    ) -> GitOperationResult:
        """
        Create a new branch.

        Args:
            repository: Repository to create branch in
            branch_name: Name of new branch
            start_point: Commit/branch to start from
            checkout: Whether to checkout the new branch

        Returns:
            GitOperationResult with operation details
        """
        result = GitOperationResult(
            operation="create_branch", status=GitOperationStatus.PENDING, success=False
        )

        try:
            # Validate branch name
            is_valid, error_msg = GitUtils.validate_branch_name(branch_name)
            if not is_valid:
                result.error = error_msg
                result.mark_completed(False, f"Invalid branch name: {error_msg}")
                return result

            executor = GitCommandExecutor(repository.path)

            # Check if branch already exists
            exit_code, stdout, _ = await executor.execute(
                ["branch", "--list", branch_name]
            )
            if exit_code == 0 and stdout.strip():
                result.error = f"Branch '{branch_name}' already exists"
                result.mark_completed(False, result.error)
                return result

            # Create branch
            command = ["branch", branch_name]
            if start_point:
                command.append(start_point)

            exit_code, stdout, stderr = await executor.execute(command)
            result.command = f"git {' '.join(command)}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                # Checkout if requested
                if checkout:
                    checkout_result = await self.checkout_branch(
                        repository, branch_name
                    )
                    if not checkout_result.success:
                        result.error = f"Branch created but checkout failed: {checkout_result.error}"
                        result.mark_completed(False, result.error)
                        return result

                result.mark_completed(True, f"Created branch '{branch_name}'")
                logger.info(f"Created branch '{branch_name}' in {repository.name}")
            else:
                result.error = f"Failed to create branch: {stderr}"
                result.mark_completed(False, result.error)
                logger.error(f"Failed to create branch '{branch_name}': {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Branch creation failed: {e}")
            logger.error(f"Error creating branch: {e}")

        return result

    async def checkout_branch(
        self, repository: GitRepository, branch_name: str
    ) -> GitOperationResult:
        """
        Checkout a branch.

        Args:
            repository: Repository to checkout branch in
            branch_name: Name of branch to checkout

        Returns:
            GitOperationResult with operation details
        """
        result = GitOperationResult(
            operation="checkout", status=GitOperationStatus.PENDING, success=False
        )

        try:
            executor = GitCommandExecutor(repository.path)

            # Execute checkout
            exit_code, stdout, stderr = await executor.execute(
                ["checkout", branch_name]
            )
            result.command = f"git checkout {branch_name}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                result.mark_completed(True, f"Checked out branch '{branch_name}'")
                logger.info(f"Checked out branch '{branch_name}' in {repository.name}")
            else:
                result.error = f"Checkout failed: {stderr}"
                result.mark_completed(False, result.error)
                logger.error(f"Failed to checkout branch '{branch_name}': {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Checkout failed: {e}")
            logger.error(f"Error during checkout: {e}")

        return result

    async def delete_branch(
        self, repository: GitRepository, branch_name: str, force: bool = False
    ) -> GitOperationResult:
        """
        Delete a branch.

        Args:
            repository: Repository to delete branch from
            branch_name: Name of branch to delete
            force: Whether to force delete (even if not merged)

        Returns:
            GitOperationResult with operation details
        """
        result = GitOperationResult(
            operation="delete_branch", status=GitOperationStatus.PENDING, success=False
        )

        try:
            executor = GitCommandExecutor(repository.path)

            # Check if trying to delete current branch
            if (
                repository.current_branch
                and repository.current_branch.name == branch_name
            ):
                result.error = "Cannot delete currently checked out branch"
                result.mark_completed(False, result.error)
                return result

            # Delete branch
            flag = "-D" if force else "-d"
            exit_code, stdout, stderr = await executor.execute(
                ["branch", flag, branch_name]
            )
            result.command = f"git branch {flag} {branch_name}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                result.mark_completed(True, f"Deleted branch '{branch_name}'")
                logger.info(f"Deleted branch '{branch_name}' from {repository.name}")
            else:
                result.error = f"Failed to delete branch: {stderr}"
                result.mark_completed(False, result.error)
                logger.error(f"Failed to delete branch '{branch_name}': {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Branch deletion failed: {e}")
            logger.error(f"Error deleting branch: {e}")

        return result

    # Commit Operations

    async def add_files(
        self,
        repository: GitRepository,
        files: Union[List[str], str] = ".",
        force: bool = False,
    ) -> GitOperationResult:
        """
        Add files to staging area.

        Args:
            repository: Repository to add files in
            files: Files to add (list of paths or "." for all)
            force: Whether to force add ignored files

        Returns:
            GitOperationResult with operation details
        """
        result = GitOperationResult(
            operation="add", status=GitOperationStatus.PENDING, success=False
        )

        try:
            executor = GitCommandExecutor(repository.path)

            # Prepare command
            command = ["add"]
            if force:
                command.append("--force")

            if isinstance(files, str):
                command.append(files)
            else:
                command.extend(files)

            # Execute add
            exit_code, stdout, stderr = await executor.execute(command)
            result.command = f"git {' '.join(command)}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                file_desc = (
                    "all files"
                    if files == "."
                    else f"{len(files) if isinstance(files, list) else 1} file(s)"
                )
                result.mark_completed(True, f"Added {file_desc} to staging area")
                logger.info(f"Added files to staging area in {repository.name}")
            else:
                result.error = f"Failed to add files: {stderr}"
                result.mark_completed(False, result.error)
                logger.error(f"Failed to add files: {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Add operation failed: {e}")
            logger.error(f"Error adding files: {e}")

        return result

    async def commit_changes(
        self,
        repository: GitRepository,
        message: str,
        author: Optional[str] = None,
        email: Optional[str] = None,
        amend: bool = False,
    ) -> CommitResult:
        """
        Commit staged changes.

        Args:
            repository: Repository to commit in
            message: Commit message
            author: Author name (optional)
            email: Author email (optional)
            amend: Whether to amend the last commit

        Returns:
            CommitResult with operation details
        """
        result = CommitResult(
            operation="commit",
            status=GitOperationStatus.PENDING,
            success=False,
            commit_message=message,
        )

        try:
            executor = GitCommandExecutor(repository.path)

            # Prepare environment
            env = {}
            if author:
                env["GIT_AUTHOR_NAME"] = author
            if email:
                env["GIT_AUTHOR_EMAIL"] = email

            # Prepare command
            command = ["commit", "-m", message]
            if amend:
                command.append("--amend")

            # Execute commit
            exit_code, stdout, stderr = await executor.execute(command, env=env)
            result.command = f"git {' '.join(command)}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                # Parse commit hash from output
                commit_hash_match = re.search(r"\[([a-f0-9]+)\]", stdout)
                if commit_hash_match:
                    result.commit_hash = commit_hash_match.group(1)

                # Parse statistics
                stats_match = re.search(
                    r"(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?",
                    stdout,
                )
                if stats_match:
                    result.files_changed = int(stats_match.group(1))
                    result.insertions = int(stats_match.group(2) or 0)
                    result.deletions = int(stats_match.group(3) or 0)

                action = "Amended commit" if amend else "Created commit"
                result.mark_completed(
                    True, f"{action}: {result.commit_hash or 'unknown'}"
                )
                logger.info(
                    f"Committed changes in {repository.name}: {message[:50]}..."
                )
            else:
                result.error = f"Commit failed: {stderr}"
                result.mark_completed(False, result.error)
                logger.error(f"Failed to commit changes: {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Commit operation failed: {e}")
            logger.error(f"Error during commit: {e}")

        return result

    # Remote Operations

    async def add_remote(
        self, repository: GitRepository, name: str, url: str
    ) -> GitOperationResult:
        """
        Add a remote repository.

        Args:
            repository: Repository to add remote to
            name: Remote name
            url: Remote URL

        Returns:
            GitOperationResult with operation details
        """
        result = GitOperationResult(
            operation="add_remote", status=GitOperationStatus.PENDING, success=False
        )

        try:
            # Validate URL
            parsed_url = GitUrlParser.parse_url(url)
            if not parsed_url.is_valid:
                result.error = f"Invalid Git URL: {url}"
                result.mark_completed(False, result.error)
                return result

            executor = GitCommandExecutor(repository.path)

            # Add remote
            exit_code, stdout, stderr = await executor.execute(
                ["remote", "add", name, url]
            )
            result.command = f"git remote add {name} {url}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                result.mark_completed(True, f"Added remote '{name}': {url}")
                logger.info(f"Added remote '{name}' to {repository.name}")
            else:
                result.error = f"Failed to add remote: {stderr}"
                result.mark_completed(False, result.error)
                logger.error(f"Failed to add remote '{name}': {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Add remote operation failed: {e}")
            logger.error(f"Error adding remote: {e}")

        return result

    async def remove_remote(
        self, repository: GitRepository, name: str
    ) -> GitOperationResult:
        """
        Remove a remote repository.

        Args:
            repository: Repository to remove remote from
            name: Remote name to remove

        Returns:
            GitOperationResult with operation details
        """
        result = GitOperationResult(
            operation="remove_remote", status=GitOperationStatus.PENDING, success=False
        )

        try:
            executor = GitCommandExecutor(repository.path)

            # Remove remote
            exit_code, stdout, stderr = await executor.execute(
                ["remote", "remove", name]
            )
            result.command = f"git remote remove {name}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                result.mark_completed(True, f"Removed remote '{name}'")
                logger.info(f"Removed remote '{name}' from {repository.name}")
            else:
                result.error = f"Failed to remove remote: {stderr}"
                result.mark_completed(False, result.error)
                logger.error(f"Failed to remove remote '{name}': {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Remove remote operation failed: {e}")
            logger.error(f"Error removing remote: {e}")

        return result

    async def pull_changes(
        self,
        repository: GitRepository,
        remote: str = "origin",
        branch: Optional[str] = None,
        credentials: Optional[GitCredentials] = None,
        rebase: bool = False,
    ) -> PullResult:
        """
        Pull changes from remote repository.

        Args:
            repository: Repository to pull changes into
            remote: Remote name to pull from
            branch: Branch to pull (defaults to current)
            credentials: Authentication credentials
            rebase: Whether to rebase instead of merge

        Returns:
            PullResult with operation details
        """
        result = PullResult(
            operation="pull", status=GitOperationStatus.PENDING, success=False
        )

        try:
            executor = GitCommandExecutor(repository.path)

            # Prepare command
            command = ["pull"]
            if rebase:
                command.append("--rebase")

            command.append(remote)
            if branch:
                command.append(branch)

            # Execute pull
            if credentials:
                exit_code, stdout, stderr = await executor.execute_with_credentials(
                    command, credentials
                )
            else:
                exit_code, stdout, stderr = await executor.execute(command)

            result.command = f"git {' '.join(command)}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                # Parse pull result
                if "Fast-forward" in stdout:
                    result.fast_forward = True

                # Extract files changed
                files_match = re.findall(r"^\s+(\S+)\s+\|", stdout, re.MULTILINE)
                result.files_changed = files_match

                # Extract commit count
                commits_match = re.search(r"(\d+) files? changed", stdout)
                if commits_match:
                    result.commits_pulled = int(commits_match.group(1))

                result.mark_completed(
                    True, f"Successfully pulled changes from {remote}"
                )
                logger.info(f"Pulled changes from {remote} to {repository.name}")
            else:
                # Check for conflicts
                if "CONFLICT" in stderr or "fix conflicts" in stderr.lower():
                    result.had_conflicts = True
                    result.status = GitOperationStatus.CONFLICT

                    # Get conflicted files
                    conflict_exit_code, conflict_output, _ = await executor.execute(
                        ["diff", "--name-only", "--diff-filter=U"]
                    )
                    if conflict_exit_code == 0 and conflict_output:
                        result.conflict_files = GitUtils.parse_git_output(
                            conflict_output
                        )

                    result.error = f"Pull completed with conflicts: {len(result.conflict_files)} files"
                    result.mark_completed(False, result.error)
                else:
                    result.error = f"Pull failed: {stderr}"
                    result.mark_completed(False, result.error)

                logger.warning(f"Pull from {remote} had issues: {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Pull operation failed: {e}")
            logger.error(f"Error during pull: {e}")

        return result

    async def push_changes(
        self,
        repository: GitRepository,
        remote: str = "origin",
        branch: Optional[str] = None,
        credentials: Optional[GitCredentials] = None,
        force: bool = False,
        set_upstream: bool = False,
    ) -> PushResult:
        """
        Push changes to remote repository.

        Args:
            repository: Repository to push changes from
            remote: Remote name to push to
            branch: Branch to push (defaults to current)
            credentials: Authentication credentials
            force: Whether to force push
            set_upstream: Whether to set upstream tracking

        Returns:
            PushResult with operation details
        """
        result = PushResult(
            operation="push",
            status=GitOperationStatus.PENDING,
            success=False,
            remote_name=remote,
            branch_name=branch,
        )

        try:
            executor = GitCommandExecutor(repository.path)

            # Get current branch if not specified
            if not branch and repository.current_branch:
                branch = repository.current_branch.name
                result.branch_name = branch

            # Prepare command
            command = ["push"]
            if force:
                command.append("--force")
            if set_upstream:
                command.extend(["--set-upstream"])

            command.append(remote)
            if branch:
                command.append(branch)

            # Execute push
            if credentials:
                exit_code, stdout, stderr = await executor.execute_with_credentials(
                    command, credentials
                )
            else:
                exit_code, stdout, stderr = await executor.execute(command)

            result.command = f"git {' '.join(command)}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr
            result.forced = force

            if exit_code == 0:
                # Parse push result
                if "new branch" in stderr:
                    result.created_remote_branch = True

                # Extract commit count and bytes
                commits_match = re.search(r"(\d+) objects", stderr)
                if commits_match:
                    result.commits_pushed = int(commits_match.group(1))

                bytes_match = re.search(r"(\d+) bytes", stderr)
                if bytes_match:
                    result.bytes_pushed = int(bytes_match.group(1))

                result.mark_completed(True, f"Successfully pushed to {remote}/{branch}")
                logger.info(
                    f"Pushed changes from {repository.name} to {remote}/{branch}"
                )
            else:
                # Check if push was rejected
                if "rejected" in stderr or "non-fast-forward" in stderr:
                    result.rejected = True
                    result.error = "Push rejected - remote has newer commits"
                else:
                    result.error = f"Push failed: {stderr}"

                result.mark_completed(False, result.error)
                logger.error(f"Failed to push to {remote}: {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Push operation failed: {e}")
            logger.error(f"Error during push: {e}")

        return result

    # Merge Operations

    async def merge_branch(
        self,
        repository: GitRepository,
        branch_name: str,
        strategy: Optional[str] = None,
        no_ff: bool = False,
    ) -> MergeResult:
        """
        Merge a branch into current branch.

        Args:
            repository: Repository to perform merge in
            branch_name: Branch to merge
            strategy: Merge strategy (e.g., 'ours', 'theirs')
            no_ff: Whether to create merge commit even for fast-forward

        Returns:
            MergeResult with operation details
        """
        result = MergeResult(
            operation="merge",
            status=GitOperationStatus.PENDING,
            success=False,
            merged_branch=branch_name,
        )

        try:
            executor = GitCommandExecutor(repository.path)

            # Prepare command
            command = ["merge"]
            if strategy:
                command.extend(["-X", strategy])
            if no_ff:
                command.append("--no-ff")

            command.append(branch_name)

            # Execute merge
            exit_code, stdout, stderr = await executor.execute(command)
            result.command = f"git {' '.join(command)}"
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            if exit_code == 0:
                # Parse merge result
                if "Fast-forward" in stdout:
                    result.fast_forward = True
                else:
                    # Extract merge commit hash
                    merge_match = re.search(
                        r"Merge made by.*commit ([a-f0-9]+)", stdout
                    )
                    if merge_match:
                        result.merge_commit = merge_match.group(1)

                result.mark_completed(True, f"Successfully merged '{branch_name}'")
                logger.info(f"Merged branch '{branch_name}' in {repository.name}")
            else:
                # Check for conflicts
                if "CONFLICT" in stdout or "Automatic merge failed" in stdout:
                    result.had_conflicts = True
                    result.status = GitOperationStatus.CONFLICT

                    # Get conflicted files
                    conflict_exit_code, conflict_output, _ = await executor.execute(
                        ["diff", "--name-only", "--diff-filter=U"]
                    )
                    if conflict_exit_code == 0 and conflict_output:
                        result.conflict_files = GitUtils.parse_git_output(
                            conflict_output
                        )

                    result.error = (
                        f"Merge has conflicts in {len(result.conflict_files)} files"
                    )
                    result.mark_completed(False, result.error)
                else:
                    result.error = f"Merge failed: {stderr}"
                    result.mark_completed(False, result.error)

                logger.warning(f"Merge of '{branch_name}' had issues: {stderr}")

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Merge operation failed: {e}")
            logger.error(f"Error during merge: {e}")

        return result

    # Conflict Resolution

    async def resolve_conflicts(
        self, repository: GitRepository, resolution_strategy: str = "manual"
    ) -> GitOperationResult:
        """
        Resolve merge conflicts.

        Args:
            repository: Repository with conflicts
            resolution_strategy: Strategy for resolution ('ours', 'theirs', 'manual')

        Returns:
            GitOperationResult with operation details
        """
        result = GitOperationResult(
            operation="resolve_conflicts",
            status=GitOperationStatus.PENDING,
            success=False,
        )

        try:
            executor = GitCommandExecutor(repository.path)

            # Get conflicted files
            exit_code, conflict_output, _ = await executor.execute(
                ["diff", "--name-only", "--diff-filter=U"]
            )
            if exit_code != 0 or not conflict_output:
                result.error = "No conflicts found"
                result.mark_completed(False, result.error)
                return result

            conflicted_files = GitUtils.parse_git_output(conflict_output)

            if resolution_strategy in ["ours", "theirs"]:
                # Automatic resolution
                for file_path in conflicted_files:
                    if resolution_strategy == "ours":
                        exit_code, _, stderr = await executor.execute(
                            ["checkout", "--ours", file_path]
                        )
                    else:  # theirs
                        exit_code, _, stderr = await executor.execute(
                            ["checkout", "--theirs", file_path]
                        )

                    if exit_code != 0:
                        result.error = f"Failed to resolve {file_path}: {stderr}"
                        result.mark_completed(False, result.error)
                        return result

                    # Add resolved file
                    await executor.execute(["add", file_path])

                result.mark_completed(
                    True,
                    f"Resolved {len(conflicted_files)} conflicts using '{resolution_strategy}' strategy",
                )
                logger.info(
                    f"Resolved conflicts in {repository.name} using '{resolution_strategy}' strategy"
                )
            else:
                # Manual resolution - just report the files that need attention
                result.error = f"Manual resolution required for {len(conflicted_files)} files: {', '.join(conflicted_files)}"
                result.mark_completed(False, result.error)

        except Exception as e:
            result.error = str(e)
            result.mark_completed(False, f"Conflict resolution failed: {e}")
            logger.error(f"Error resolving conflicts: {e}")

        return result

    # Utility Methods

    async def get_repository_status(self, repository: GitRepository) -> GitStatus:
        """
        Get current repository status.

        Args:
            repository: Repository to check status for

        Returns:
            GitStatus object with current status
        """
        try:
            executor = GitCommandExecutor(repository.path)
            await self._load_repository_status(repository, executor)
            return repository.status or GitStatus()
        except Exception as e:
            logger.error(f"Failed to get repository status: {e}")
            return GitStatus()

    async def validate_repository(self, path: Path) -> Dict[str, Any]:
        """
        Validate repository health and structure.

        Args:
            path: Repository path to validate

        Returns:
            Dictionary with validation results
        """
        validation_result = {"valid": False, "errors": [], "warnings": [], "info": {}}

        try:
            # Check if directory exists
            if not path.exists():
                validation_result["errors"].append(f"Directory does not exist: {path}")
                return validation_result

            if not path.is_dir():
                validation_result["errors"].append(f"Path is not a directory: {path}")
                return validation_result

            # Check if it's a Git repository
            if not GitUtils.is_git_repository(path):
                validation_result["errors"].append("Directory is not a Git repository")
                return validation_result

            # Load repository
            repository = await self.load_repository(path)
            if not repository:
                validation_result["errors"].append("Failed to load repository")
                return validation_result

            # Basic validation checks
            validation_result["valid"] = True
            validation_result["info"] = {
                "name": repository.name,
                "current_branch": repository.current_branch.name
                if repository.current_branch
                else None,
                "branch_count": len(repository.branches),
                "remote_count": len(repository.remotes),
                "has_changes": repository.has_uncommitted_changes(),
                "needs_sync": repository.needs_sync(),
            }

            # Check for common issues
            if not repository.remotes:
                validation_result["warnings"].append("No remotes configured")

            if repository.has_uncommitted_changes():
                validation_result["warnings"].append(
                    "Repository has uncommitted changes"
                )

            if repository.status and repository.status.has_conflicts:
                validation_result["errors"].append(
                    "Repository has unresolved conflicts"
                )
                validation_result["valid"] = False

            logger.info(f"Validated repository: {repository.name}")

        except Exception as e:
            validation_result["errors"].append(f"Validation failed: {e}")
            logger.error(f"Repository validation error: {e}")

        return validation_result

    async def get_commit_history(
        self,
        repository: GitRepository,
        branch: Optional[str] = None,
        limit: int = 50,
        since: Optional[str] = None,
    ) -> List[GitCommit]:
        """
        Get commit history for a repository.

        Args:
            repository: Repository to get history for
            branch: Branch to get history from (defaults to current)
            limit: Maximum number of commits to return
            since: Date/time to get commits since

        Returns:
            List of GitCommit objects
        """
        try:
            executor = GitCommandExecutor(repository.path)

            # Prepare command
            command = ["log", f"--max-count={limit}"]

            if since:
                command.extend(["--since", since])

            if branch:
                command.append(branch)

            # Use detailed format
            format_str = (
                "%H%x00%h%x00%s%x00%an%x00%ae%x00%cn%x00%ce%x00%at%x00%ct%x00%P"
            )
            command.extend([f"--pretty=format:{format_str}"])

            exit_code, stdout, stderr = await executor.execute(command)

            if exit_code != 0:
                logger.error(f"Failed to get commit history: {stderr}")
                return []

            commits = []
            for line in stdout.splitlines():
                if not line.strip():
                    continue

                parts = line.split("\x00")
                if len(parts) >= 9:
                    try:
                        commit = GitCommit(
                            hash=parts[0],
                            short_hash=parts[1],
                            message=parts[2],
                            author_name=parts[3],
                            author_email=parts[4],
                            committer_name=parts[5] if parts[5] else parts[3],
                            committer_email=parts[6] if parts[6] else parts[4],
                            author_date=datetime.fromtimestamp(int(parts[7])),
                            commit_date=datetime.fromtimestamp(int(parts[8])),
                            parent_hashes=parts[9].split()
                            if len(parts) > 9 and parts[9]
                            else [],
                            is_merge=len(parts[9].split()) > 1
                            if len(parts) > 9
                            else False,
                        )
                        commits.append(commit)
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse commit: {e}")
                        continue

            logger.info(f"Retrieved {len(commits)} commits from {repository.name}")
            return commits

        except Exception as e:
            logger.error(f"Error getting commit history: {e}")
            return []
