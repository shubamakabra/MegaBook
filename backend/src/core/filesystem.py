"""Filesystem abstraction layer for MegaBook.

This module provides a clean abstraction over the filesystem operations,
enforcing the knowledge layer hierarchy rules.
"""
import os
from pathlib import Path
from typing import List, Optional, Set
from dataclasses import dataclass
from enum import Enum, auto


class KnowledgeLayer(Enum):
    """The three knowledge layers in MegaBook."""
    PROMPTS = auto()  # Immutable source of truth
    NOTES = auto()    # Canonical structured knowledge
    WIKI = auto()     # Derived presentation layer


@dataclass
class FileInfo:
    """Information about a file in the repository."""
    path: Path
    layer: KnowledgeLayer
    relative_path: str
    size: int
    modified: float


class RepositoryError(Exception):
    """Base exception for repository operations."""
    pass


class LayerViolationError(RepositoryError):
    """Raised when attempting to violate layer rules."""
    pass


class FilesystemService:
    """Service for filesystem operations with layer enforcement."""
    
    def __init__(self, repo_path: Path) -> None:
        """Initialize the filesystem service.
        
        Args:
            repo_path: Root path of the Git repository
        """
        self.repo_path = Path(repo_path).resolve()
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [
            self.repo_path / "prompts",
            self.repo_path / "notes",
            self.repo_path / "wiki",
            self.repo_path / ".meta" / "processing",
            self.repo_path / ".meta" / "costs",
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _get_layer_for_path(self, path: Path) -> KnowledgeLayer:
        """Determine which knowledge layer a path belongs to."""
        try:
            rel_path = path.relative_to(self.repo_path)
        except ValueError:
            raise RepositoryError(f"Path {path} is outside repository")
        
        first_part = rel_path.parts[0] if rel_path.parts else ""
        
        if first_part == "prompts":
            return KnowledgeLayer.PROMPTS
        elif first_part == "notes":
            return KnowledgeLayer.NOTES
        elif first_part == "wiki":
            return KnowledgeLayer.WIKI
        else:
            raise RepositoryError(f"Path {path} is not in a knowledge layer")
    
    def read_file(self, relative_path: str) -> str:
        """Read a file from the repository.
        
        Args:
            relative_path: Path relative to repo root
            
        Returns:
            File contents as string
        """
        full_path = self.repo_path / relative_path
        if not full_path.exists():
            raise RepositoryError(f"File not found: {relative_path}")
        
        return full_path.read_text(encoding="utf-8")
    
    def write_file(
        self, 
        relative_path: str, 
        content: str, 
        layer: Optional[KnowledgeLayer] = None
    ) -> None:
        """Write a file to the repository.
        
        Args:
            relative_path: Path relative to repo root
            content: Content to write
            layer: Expected layer (for validation)
        """
        full_path = self.repo_path / relative_path
        actual_layer = self._get_layer_for_path(full_path)
        
        if layer and actual_layer != layer:
            raise LayerViolationError(
                f"Path {relative_path} is in layer {actual_layer.name}, "
                f"expected {layer.name}"
            )
        
        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
    
    def delete_file(self, relative_path: str) -> None:
        """Delete a file from the repository.
        
        Args:
            relative_path: Path relative to repo root
        """
        full_path = self.repo_path / relative_path
        if full_path.exists():
            full_path.unlink()
    
    def list_files(
        self, 
        layer: Optional[KnowledgeLayer] = None,
        pattern: str = "**/*.md"
    ) -> List[FileInfo]:
        """List files in the repository.
        
        Args:
            layer: Filter by knowledge layer
            pattern: Glob pattern to match
            
        Returns:
            List of file information
        """
        files = []
        
        if layer:
            search_paths = [self._get_layer_path(layer)]
        else:
            search_paths = [
                self._get_layer_path(KnowledgeLayer.PROMPTS),
                self._get_layer_path(KnowledgeLayer.NOTES),
                self._get_layer_path(KnowledgeLayer.WIKI),
            ]
        
        for base_path in search_paths:
            if not base_path.exists():
                continue
                
            for file_path in base_path.glob(pattern):
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append(FileInfo(
                        path=file_path,
                        layer=self._get_layer_for_path(file_path),
                        relative_path=str(file_path.relative_to(self.repo_path)),
                        size=stat.st_size,
                        modified=stat.st_mtime
                    ))
        
        return sorted(files, key=lambda f: f.relative_path)
    
    def _get_layer_path(self, layer: KnowledgeLayer) -> Path:
        """Get the base path for a knowledge layer."""
        layer_dirs = {
            KnowledgeLayer.PROMPTS: self.repo_path / "prompts",
            KnowledgeLayer.NOTES: self.repo_path / "notes",
            KnowledgeLayer.WIKI: self.repo_path / "wiki",
        }
        return layer_dirs[layer]
    
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
            layer=self._get_layer_for_path(full_path),
            relative_path=relative_path,
            size=stat.st_size,
            modified=stat.st_mtime
        )