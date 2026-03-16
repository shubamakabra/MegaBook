"""Filesystem abstraction for MegaBook.

This module provides a clean abstraction over the filesystem operations
for an Obsidian-compatible vault. The vault is any folder of files —
MegaBook browses and edits it without imposing folder structure.

MegaBook stores its own metadata in a .megabook/ folder inside the vault.
"""
import os
from pathlib import Path
from typing import List, Optional, Set
from dataclasses import dataclass


# Folders that should be hidden from the file browser
HIDDEN_PREFIXES = frozenset((".megabook", ".obsidian", ".git", ".meta"))


@dataclass
class FileInfo:
    """Information about a file in the vault."""
    path: Path
    relative_path: str
    size: int
    modified: float


class RepositoryError(Exception):
    """Base exception for repository operations."""
    pass


class FilesystemService:
    """Service for filesystem operations on a vault."""

    def __init__(self, repo_path: Path) -> None:
        """Initialize the filesystem service.

        Args:
            repo_path: Root path of the vault (Obsidian vault or Git repo)
        """
        self.repo_path = Path(repo_path).resolve()
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create the .megabook metadata directory if it doesn't exist.

        We never create folders that belong to the user's vault structure.
        Only the hidden .megabook/ folder for MegaBook's own bookkeeping.
        """
        meta_dirs = [
            self.repo_path / ".megabook",
            self.repo_path / ".megabook" / "processing",
            self.repo_path / ".megabook" / "costs",
        ]
        for directory in meta_dirs:
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def meta_path(self) -> Path:
        """Path to the .megabook metadata directory."""
        return self.repo_path / ".megabook"

    def _is_hidden(self, relative_path: str) -> bool:
        """Check if a path is inside a hidden folder."""
        first_part = relative_path.split("/")[0] if "/" in relative_path else relative_path
        return first_part in HIDDEN_PREFIXES or first_part.startswith(".")

    def read_file(self, relative_path: str) -> str:
        """Read a file from the vault.

        Args:
            relative_path: Path relative to vault root

        Returns:
            File contents as string
        """
        full_path = self.repo_path / relative_path
        if not full_path.exists():
            raise RepositoryError(f"File not found: {relative_path}")

        return full_path.read_text(encoding="utf-8")

    def write_file(self, relative_path: str, content: str) -> None:
        """Write a file to the vault.

        Args:
            relative_path: Path relative to vault root
            content: Content to write
        """
        full_path = self.repo_path / relative_path

        # Safety: don't allow writing outside the vault
        try:
            full_path.resolve().relative_to(self.repo_path)
        except ValueError:
            raise RepositoryError(f"Path {relative_path} resolves outside the vault")

        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    def delete_file(self, relative_path: str) -> None:
        """Delete a file from the vault.

        Args:
            relative_path: Path relative to vault root
        """
        full_path = self.repo_path / relative_path
        if full_path.exists():
            full_path.unlink()

    def list_files(
        self,
        folder: Optional[str] = None,
        pattern: str = "**/*.md",
        include_hidden: bool = False,
    ) -> List[FileInfo]:
        """List files in the vault.

        Args:
            folder: Optional subfolder to search within (e.g. "notes")
            pattern: Glob pattern to match (default: all .md files recursively)
            include_hidden: If True, include files in hidden folders (.obsidian, .megabook, etc.)

        Returns:
            List of file information, sorted by relative path
        """
        files = []

        if folder:
            search_path = self.repo_path / folder
        else:
            search_path = self.repo_path

        if not search_path.exists():
            return files

        for file_path in search_path.glob(pattern):
            if not file_path.is_file():
                continue

            relative = str(file_path.relative_to(self.repo_path)).replace("\\", "/")

            # Skip hidden folders unless explicitly requested
            if not include_hidden and self._is_hidden(relative):
                continue

            stat = file_path.stat()
            files.append(FileInfo(
                path=file_path,
                relative_path=relative,
                size=stat.st_size,
                modified=stat.st_mtime,
            ))

        return sorted(files, key=lambda f: f.relative_path)

    def file_exists(self, relative_path: str) -> bool:
        """Check if a file exists."""
        return (self.repo_path / relative_path).exists()

    def get_file_stats(self, relative_path: str) -> Optional[FileInfo]:
        """Get information about a specific file."""
        full_path = self.repo_path / relative_path
        if not full_path.exists():
            return None

        stat = full_path.stat()
        return FileInfo(
            path=full_path,
            relative_path=relative_path,
            size=stat.st_size,
            modified=stat.st_mtime,
        )
