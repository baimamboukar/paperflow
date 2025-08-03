"""
File utilities for Paperflow.

This module provides common file operations and utilities used
throughout the application.
"""

import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Generator
import hashlib

from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class FileUtils:
    """Utility class for file operations."""
    
    @staticmethod
    def ensure_directory(path: Path) -> None:
        """
        Ensure directory exists, creating it if necessary.
        
        Args:
            path: Directory path to ensure.
        """
        path.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def remove_directory(path: Path) -> None:
        """
        Remove directory and all its contents.
        
        Args:
            path: Directory path to remove.
        """
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
    
    @staticmethod
    def copy_file(src: Path, dst: Path) -> None:
        """
        Copy file from source to destination.
        
        Args:
            src: Source file path.
            dst: Destination file path.
        """
        FileUtils.ensure_directory(dst.parent)
        shutil.copy2(src, dst)
    
    @staticmethod
    def copy_directory(src: Path, dst: Path) -> None:
        """
        Copy directory and all its contents.
        
        Args:
            src: Source directory path.
            dst: Destination directory path.
        """
        if dst.exists():
            FileUtils.remove_directory(dst)
        shutil.copytree(src, dst)
    
    @staticmethod
    def find_files(
        directory: Path,
        pattern: str = "*",
        recursive: bool = True
    ) -> List[Path]:
        """
        Find files matching pattern in directory.
        
        Args:
            directory: Directory to search in.
            pattern: Glob pattern to match.
            recursive: Whether to search recursively.
            
        Returns:
            List of matching file paths.
        """
        if recursive:
            return list(directory.rglob(pattern))
        else:
            return list(directory.glob(pattern))
    
    @staticmethod
    def get_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
        """
        Get hash of file contents.
        
        Args:
            file_path: Path to file.
            algorithm: Hash algorithm to use.
            
        Returns:
            Hexadecimal hash string.
        """
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    @staticmethod
    def create_temp_directory(prefix: str = "paperflow_") -> Path:
        """
        Create temporary directory.
        
        Args:
            prefix: Prefix for temporary directory name.
            
        Returns:
            Path to created temporary directory.
        """
        return Path(tempfile.mkdtemp(prefix=prefix))
    
    @staticmethod
    def read_text_file(file_path: Path, encoding: str = "utf-8") -> str:
        """
        Read text file contents.
        
        Args:
            file_path: Path to text file.
            encoding: File encoding.
            
        Returns:
            File contents as string.
        """
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read()
    
    @staticmethod
    def write_text_file(
        file_path: Path,
        content: str,
        encoding: str = "utf-8"
    ) -> None:
        """
        Write text to file.
        
        Args:
            file_path: Path to output file.
            content: Text content to write.
            encoding: File encoding.
        """
        FileUtils.ensure_directory(file_path.parent)
        
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
    
    @staticmethod
    def get_file_size(file_path: Path) -> int:
        """
        Get file size in bytes.
        
        Args:
            file_path: Path to file.
            
        Returns:
            File size in bytes.
        """
        return file_path.stat().st_size
    
    @staticmethod
    def is_text_file(file_path: Path) -> bool:
        """
        Check if file is a text file.
        
        Args:
            file_path: Path to file.
            
        Returns:
            True if file appears to be text.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1024)
            return True
        except (UnicodeDecodeError, PermissionError):
            return False
    
    @staticmethod
    def backup_file(file_path: Path, backup_suffix: str = ".backup") -> Path:
        """
        Create backup copy of file.
        
        Args:
            file_path: Path to file to backup.
            backup_suffix: Suffix for backup file.
            
        Returns:
            Path to backup file.
        """
        backup_path = file_path.with_suffix(file_path.suffix + backup_suffix)
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """
        Clean filename by removing/replacing invalid characters.
        
        Args:
            filename: Original filename.
            
        Returns:
            Cleaned filename safe for filesystem.
        """
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        cleaned = filename
        
        for char in invalid_chars:
            cleaned = cleaned.replace(char, '_')
        
        # Remove leading/trailing whitespace and dots
        cleaned = cleaned.strip('. ')
        
        # Ensure filename is not empty
        if not cleaned:
            cleaned = "unnamed"
        
        return cleaned