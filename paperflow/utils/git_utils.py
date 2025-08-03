"""
Git utilities for Paperflow.

This module provides utility functions for Git operations including
URL validation, credential management, command execution, and error handling.
"""

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import keyring

from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


@dataclass
class GitCredentials:
    """Git credentials for authentication."""

    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    ssh_key_path: Optional[str] = None


@dataclass
class GitUrl:
    """Parsed Git URL information."""

    original_url: str
    protocol: str  # https, ssh, git, file
    host: str
    owner: Optional[str] = None
    repository: str = ""
    is_valid: bool = True
    requires_auth: bool = False


class GitUrlParser:
    """Utility class for parsing and validating Git URLs."""

    # Common Git hosting services
    HOSTING_SERVICES = {
        "github.com": "GitHub",
        "gitlab.com": "GitLab",
        "bitbucket.org": "Bitbucket",
        "git.overleaf.com": "Overleaf",
        "overleaf.com": "Overleaf",
    }

    @staticmethod
    def parse_url(url: str) -> GitUrl:
        """
        Parse a Git URL and extract components.

        Args:
            url: Git URL to parse

        Returns:
            GitUrl object with parsed components
        """
        if not url or not isinstance(url, str):
            return GitUrl(original_url=url or "", protocol="", host="", is_valid=False)

        url = url.strip()

        try:
            # Handle different URL formats
            if url.startswith(("http://", "https://")):
                return GitUrlParser._parse_http_url(url)
            elif url.startswith("git@"):
                return GitUrlParser._parse_ssh_url(url)
            elif url.startswith("ssh://"):
                return GitUrlParser._parse_ssh_protocol_url(url)
            elif url.startswith("git://"):
                return GitUrlParser._parse_git_protocol_url(url)
            elif url.startswith("file://"):
                return GitUrlParser._parse_file_url(url)
            else:
                # Try to detect if it's a shorthand SSH URL
                if ":" in url and "/" in url:
                    return GitUrlParser._parse_ssh_url(f"git@{url}")

                return GitUrl(
                    original_url=url, protocol="unknown", host="", is_valid=False
                )

        except Exception as e:
            logger.warning(f"Failed to parse Git URL '{url}': {e}")
            return GitUrl(original_url=url, protocol="", host="", is_valid=False)

    @staticmethod
    def _parse_http_url(url: str) -> GitUrl:
        """Parse HTTP/HTTPS Git URL."""
        parsed = urlparse(url)

        if not parsed.hostname:
            return GitUrl(original_url=url, protocol="", host="", is_valid=False)

        # Extract owner and repository from path
        path_parts = parsed.path.strip("/").split("/")
        owner = path_parts[0] if len(path_parts) > 0 else None
        repo = path_parts[1] if len(path_parts) > 1 else ""

        # Remove .git suffix if present
        if repo.endswith(".git"):
            repo = repo[:-4]

        return GitUrl(
            original_url=url,
            protocol=parsed.scheme,
            host=parsed.hostname,
            owner=owner,
            repository=repo,
            requires_auth=GitUrlParser._requires_auth(parsed.hostname, owner),
        )

    @staticmethod
    def _parse_ssh_url(url: str) -> GitUrl:
        """Parse SSH Git URL (git@host:user/repo.git)."""
        # Remove git@ prefix
        if url.startswith("git@"):
            url = url[4:]

        if ":" not in url:
            return GitUrl(
                original_url=f"git@{url}", protocol="", host="", is_valid=False
            )

        host, path = url.split(":", 1)
        path_parts = path.strip("/").split("/")

        owner = path_parts[0] if len(path_parts) > 0 else None
        repo = path_parts[1] if len(path_parts) > 1 else ""

        # Remove .git suffix if present
        if repo.endswith(".git"):
            repo = repo[:-4]

        return GitUrl(
            original_url=f"git@{url}",
            protocol="ssh",
            host=host,
            owner=owner,
            repository=repo,
            requires_auth=True,  # SSH always requires authentication
        )

    @staticmethod
    def _parse_ssh_protocol_url(url: str) -> GitUrl:
        """Parse SSH protocol URL (ssh://git@host/user/repo.git)."""
        parsed = urlparse(url)

        if not parsed.hostname:
            return GitUrl(original_url=url, protocol="", host="", is_valid=False)

        path_parts = parsed.path.strip("/").split("/")
        owner = path_parts[0] if len(path_parts) > 0 else None
        repo = path_parts[1] if len(path_parts) > 1 else ""

        if repo.endswith(".git"):
            repo = repo[:-4]

        return GitUrl(
            original_url=url,
            protocol="ssh",
            host=parsed.hostname,
            owner=owner,
            repository=repo,
            requires_auth=True,
        )

    @staticmethod
    def _parse_git_protocol_url(url: str) -> GitUrl:
        """Parse Git protocol URL (git://host/user/repo.git)."""
        parsed = urlparse(url)

        if not parsed.hostname:
            return GitUrl(original_url=url, protocol="", host="", is_valid=False)

        path_parts = parsed.path.strip("/").split("/")
        owner = path_parts[0] if len(path_parts) > 0 else None
        repo = path_parts[1] if len(path_parts) > 1 else ""

        if repo.endswith(".git"):
            repo = repo[:-4]

        return GitUrl(
            original_url=url,
            protocol="git",
            host=parsed.hostname,
            owner=owner,
            repository=repo,
            requires_auth=False,  # Git protocol typically doesn't require auth
        )

    @staticmethod
    def _parse_file_url(url: str) -> GitUrl:
        """Parse file protocol URL (file:///path/to/repo)."""
        parsed = urlparse(url)
        repo_name = Path(parsed.path).name

        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        return GitUrl(
            original_url=url,
            protocol="file",
            host="localhost",
            repository=repo_name,
            requires_auth=False,
        )

    @staticmethod
    def _requires_auth(host: Optional[str], owner: Optional[str]) -> bool:
        """Determine if URL requires authentication."""
        if not host:
            return False

        # Public repositories on major hosting services may not require auth for read
        public_hosts = {"github.com", "gitlab.com"}

        # Overleaf always requires authentication
        if "overleaf.com" in host:
            return True

        # For known public hosts, assume auth is needed for private repos
        # This is a conservative approach
        if host in public_hosts:
            return True

        # Unknown hosts likely require authentication
        return True

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate if a string is a valid Git URL.

        Args:
            url: URL to validate

        Returns:
            True if valid Git URL
        """
        parsed = GitUrlParser.parse_url(url)
        return parsed.is_valid and bool(parsed.host)

    @staticmethod
    def get_service_name(url: str) -> Optional[str]:
        """
        Get the name of the Git hosting service.

        Args:
            url: Git URL

        Returns:
            Service name or None if unknown
        """
        parsed = GitUrlParser.parse_url(url)
        if not parsed.is_valid:
            return None

        return GitUrlParser.HOSTING_SERVICES.get(parsed.host)

    @staticmethod
    def convert_to_https(url: str) -> Optional[str]:
        """
        Convert SSH or other URL formats to HTTPS.

        Args:
            url: Original Git URL

        Returns:
            HTTPS URL or None if conversion not possible
        """
        parsed = GitUrlParser.parse_url(url)

        if not parsed.is_valid or not parsed.owner or not parsed.repository:
            return None

        # Already HTTPS
        if parsed.protocol == "https":
            return url

        # Convert to HTTPS format
        return f"https://{parsed.host}/{parsed.owner}/{parsed.repository}.git"

    @staticmethod
    def convert_to_ssh(url: str) -> Optional[str]:
        """
        Convert HTTPS or other URL formats to SSH.

        Args:
            url: Original Git URL

        Returns:
            SSH URL or None if conversion not possible
        """
        parsed = GitUrlParser.parse_url(url)

        if not parsed.is_valid or not parsed.owner or not parsed.repository:
            return None

        # Already SSH
        if parsed.protocol == "ssh" and url.startswith("git@"):
            return url

        # Convert to SSH format
        return f"git@{parsed.host}:{parsed.owner}/{parsed.repository}.git"


class GitCredentialManager:
    """Manages Git credentials using system keyring."""

    KEYRING_SERVICE = "paperflow-git"

    @staticmethod
    def store_credentials(
        host: str, username: str, credentials: GitCredentials
    ) -> bool:
        """
        Store credentials for a host.

        Args:
            host: Git host (e.g., github.com)
            username: Username or identifier
            credentials: Credentials to store

        Returns:
            True if successfully stored
        """
        try:
            # Store different types of credentials
            if credentials.password:
                keyring.set_password(
                    f"{GitCredentialManager.KEYRING_SERVICE}-password",
                    f"{host}:{username}",
                    credentials.password,
                )

            if credentials.token:
                keyring.set_password(
                    f"{GitCredentialManager.KEYRING_SERVICE}-token",
                    f"{host}:{username}",
                    credentials.token,
                )

            if credentials.ssh_key_path:
                keyring.set_password(
                    f"{GitCredentialManager.KEYRING_SERVICE}-ssh",
                    f"{host}:{username}",
                    credentials.ssh_key_path,
                )

            logger.info(f"Stored credentials for {username}@{host}")
            return True

        except Exception as e:
            logger.error(f"Failed to store credentials for {username}@{host}: {e}")
            return False

    @staticmethod
    def get_credentials(host: str, username: str) -> Optional[GitCredentials]:
        """
        Retrieve credentials for a host.

        Args:
            host: Git host
            username: Username or identifier

        Returns:
            GitCredentials object or None if not found
        """
        try:
            credentials = GitCredentials(username=username)

            # Try to get password
            try:
                password = keyring.get_password(
                    f"{GitCredentialManager.KEYRING_SERVICE}-password",
                    f"{host}:{username}",
                )
                if password:
                    credentials.password = password
            except Exception:
                pass

            # Try to get token
            try:
                token = keyring.get_password(
                    f"{GitCredentialManager.KEYRING_SERVICE}-token",
                    f"{host}:{username}",
                )
                if token:
                    credentials.token = token
            except Exception:
                pass

            # Try to get SSH key path
            try:
                ssh_key = keyring.get_password(
                    f"{GitCredentialManager.KEYRING_SERVICE}-ssh", f"{host}:{username}"
                )
                if ssh_key:
                    credentials.ssh_key_path = ssh_key
            except Exception:
                pass

            # Return credentials if we found anything
            if credentials.password or credentials.token or credentials.ssh_key_path:
                return credentials

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve credentials for {username}@{host}: {e}")
            return None

    @staticmethod
    def delete_credentials(host: str, username: str) -> bool:
        """
        Delete stored credentials.

        Args:
            host: Git host
            username: Username or identifier

        Returns:
            True if successfully deleted
        """
        try:
            key_types = ["password", "token", "ssh"]
            for key_type in key_types:
                try:
                    keyring.delete_password(
                        f"{GitCredentialManager.KEYRING_SERVICE}-{key_type}",
                        f"{host}:{username}",
                    )
                except keyring.errors.PasswordDeleteError:
                    pass  # Key didn't exist, that's fine

            logger.info(f"Deleted credentials for {username}@{host}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete credentials for {username}@{host}: {e}")
            return False


class GitCommandExecutor:
    """Executes Git commands asynchronously with proper error handling."""

    def __init__(self, repository_path: Optional[Path] = None):
        """
        Initialize Git command executor.

        Args:
            repository_path: Path to Git repository
        """
        self.repository_path = repository_path
        self.timeout = 300  # 5 minutes default timeout

    async def execute(
        self,
        command: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        input_data: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        """
        Execute a Git command asynchronously.

        Args:
            command: Git command as list of strings
            cwd: Working directory (defaults to repository_path)
            env: Environment variables
            timeout: Command timeout in seconds
            input_data: Data to send to stdin

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not command or command[0] != "git":
            command = ["git"] + command

        # Use provided cwd or default to repository path
        working_dir = cwd or self.repository_path
        if working_dir:
            working_dir = Path(working_dir).resolve()

        # Prepare environment
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        # Use provided timeout or default
        cmd_timeout = timeout or self.timeout

        logger.debug(f"Executing Git command: {' '.join(command)}")
        logger.debug(f"Working directory: {working_dir}")

        try:
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=working_dir,
                env=full_env,
                stdin=asyncio.subprocess.PIPE if input_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Execute with timeout
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(
                        input=input_data.encode() if input_data else None
                    ),
                    timeout=cmd_timeout,
                )

                exit_code = process.returncode
                stdout = stdout_data.decode("utf-8", errors="replace")
                stderr = stderr_data.decode("utf-8", errors="replace")

                if exit_code == 0:
                    logger.debug(
                        f"Git command succeeded: {command[1] if len(command) > 1 else 'git'}"
                    )
                else:
                    logger.warning(
                        f"Git command failed with exit code {exit_code}: {command}"
                    )
                    logger.warning(f"stderr: {stderr}")

                return exit_code, stdout, stderr

            except asyncio.TimeoutError:
                logger.error(
                    f"Git command timed out after {cmd_timeout} seconds: {command}"
                )
                process.kill()
                await process.wait()
                return -1, "", f"Command timed out after {cmd_timeout} seconds"

        except FileNotFoundError:
            error_msg = (
                "Git command not found. Please ensure Git is installed and in PATH."
            )
            logger.error(error_msg)
            return -1, "", error_msg

        except Exception as e:
            error_msg = f"Failed to execute Git command: {e}"
            logger.error(error_msg)
            return -1, "", error_msg

    async def execute_with_credentials(
        self, command: List[str], credentials: Optional[GitCredentials] = None, **kwargs
    ) -> Tuple[int, str, str]:
        """
        Execute Git command with authentication.

        Args:
            command: Git command
            credentials: Authentication credentials
            **kwargs: Additional arguments for execute()

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        env = kwargs.get("env", {}).copy()

        if credentials:
            # Set up authentication environment
            if credentials.token:
                # For token authentication, use as password with username 'token' or actual username
                env["GIT_ASKPASS"] = "echo"
                env["GIT_PASSWORD"] = credentials.token
                if credentials.username:
                    env["GIT_USERNAME"] = credentials.username
            elif credentials.password and credentials.username:
                # For password authentication
                env["GIT_ASKPASS"] = "echo"
                env["GIT_USERNAME"] = credentials.username
                env["GIT_PASSWORD"] = credentials.password

        kwargs["env"] = env
        return await self.execute(command, **kwargs)

    def set_repository_path(self, path: Path) -> None:
        """Set the repository path for commands."""
        self.repository_path = Path(path).resolve()

    def set_timeout(self, timeout: float) -> None:
        """Set the default timeout for commands."""
        self.timeout = timeout


class GitUtils:
    """General Git utility functions."""

    @staticmethod
    def is_git_repository(path: Path) -> bool:
        """
        Check if a directory is a Git repository.

        Args:
            path: Directory path to check

        Returns:
            True if directory contains a Git repository
        """
        if not path.exists() or not path.is_dir():
            return False

        git_dir = path / ".git"
        return git_dir.exists() and (git_dir.is_dir() or git_dir.is_file())

    @staticmethod
    def find_git_root(path: Path) -> Optional[Path]:
        """
        Find the root directory of a Git repository.

        Args:
            path: Starting path (can be subdirectory)

        Returns:
            Path to Git repository root or None if not found
        """
        current_path = Path(path).resolve()

        while current_path != current_path.parent:
            if GitUtils.is_git_repository(current_path):
                return current_path
            current_path = current_path.parent

        return None

    @staticmethod
    def get_repository_name(path: Path) -> str:
        """
        Get repository name from path.

        Args:
            path: Repository path

        Returns:
            Repository name
        """
        return path.name

    @staticmethod
    def parse_git_output(output: str, format_type: str = "lines") -> List[str]:
        """
        Parse Git command output.

        Args:
            output: Raw Git command output
            format_type: How to parse ('lines', 'null-separated')

        Returns:
            List of parsed items
        """
        if not output.strip():
            return []

        if format_type == "null-separated":
            return [item for item in output.split("\0") if item.strip()]
        else:
            return [line.strip() for line in output.splitlines() if line.strip()]

    @staticmethod
    def create_gitignore(path: Path, patterns: List[str]) -> bool:
        """
        Create or update .gitignore file.

        Args:
            path: Repository path
            patterns: List of patterns to ignore

        Returns:
            True if successful
        """
        try:
            gitignore_path = path / ".gitignore"

            # Read existing patterns if file exists
            existing_patterns = []
            if gitignore_path.exists():
                existing_patterns = gitignore_path.read_text().splitlines()

            # Add new patterns that don't already exist
            new_patterns = []
            for pattern in patterns:
                if pattern not in existing_patterns:
                    new_patterns.append(pattern)

            if new_patterns:
                # Append new patterns
                with gitignore_path.open("a", encoding="utf-8") as f:
                    if existing_patterns and not existing_patterns[-1].endswith("\n"):
                        f.write("\n")
                    f.write("\n".join(new_patterns) + "\n")

                logger.info(f"Added {len(new_patterns)} patterns to .gitignore")

            return True

        except Exception as e:
            logger.error(f"Failed to create/update .gitignore: {e}")
            return False

    @staticmethod
    def get_default_branch_name() -> str:
        """Get the default branch name (main or master)."""
        return "main"  # Modern default

    @staticmethod
    def escape_shell_arg(arg: str) -> str:
        """
        Escape shell argument for safe command execution.

        Args:
            arg: Argument to escape

        Returns:
            Escaped argument
        """
        # Basic escaping for shell safety
        if " " in arg or '"' in arg or "'" in arg:
            escaped_arg = arg.replace('"', '\\"')
            return f'"{escaped_arg}"'
        return arg

    @staticmethod
    async def check_git_version() -> Optional[str]:
        """
        Check Git version.

        Returns:
            Git version string or None if not available
        """
        try:
            executor = GitCommandExecutor()
            exit_code, stdout, stderr = await executor.execute(["--version"])

            if exit_code == 0 and stdout:
                # Parse version from output like "git version 2.34.1"
                version_match = re.search(r"git version (\S+)", stdout)
                return version_match.group(1) if version_match else None

            return None

        except Exception as e:
            logger.error(f"Failed to check Git version: {e}")
            return None

    @staticmethod
    def validate_branch_name(name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Git branch name.

        Args:
            name: Branch name to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, "Branch name cannot be empty"

        name = name.strip()

        # Git branch name restrictions
        invalid_patterns = [
            r"\s",  # No spaces
            r"\.\.",  # No double dots
            r"^-",  # Cannot start with dash
            r"[-.]$",  # Cannot end with dash or dot
            r"[~^:?*\[\]\\]",  # Invalid characters
            r"@{",  # No @{ sequence
            r"\.lock$",  # Cannot end with .lock
            r"/$",  # Cannot end with slash
        ]

        for pattern in invalid_patterns:
            if re.search(pattern, name):
                return False, f"Branch name contains invalid pattern: {pattern}"

        # Additional checks
        if len(name) > 255:
            return False, "Branch name too long (max 255 characters)"

        if name in ["HEAD", "ORIG_HEAD", "FETCH_HEAD", "MERGE_HEAD"]:
            return False, f"'{name}' is a reserved Git reference name"

        return True, None

    @staticmethod
    def format_commit_message(title: str, body: str = "", footer: str = "") -> str:
        """
        Format a proper Git commit message.

        Args:
            title: Commit title (first line)
            body: Commit body (optional)
            footer: Commit footer (optional)

        Returns:
            Formatted commit message
        """
        lines = [title.strip()]

        if body.strip():
            lines.append("")  # Blank line after title
            lines.extend(body.strip().splitlines())

        if footer.strip():
            if not body.strip():
                lines.append("")  # Blank line after title if no body
            lines.append("")  # Blank line before footer
            lines.extend(footer.strip().splitlines())

        return "\n".join(lines)
