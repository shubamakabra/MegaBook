"""Core module initialization."""
from src.core.config import Settings, settings
from src.core.filesystem import FilesystemService, KnowledgeLayer, FileInfo
from src.core.git_service import GitService

__all__ = [
    "Settings",
    "settings",
    "FilesystemService",
    "KnowledgeLayer",
    "FileInfo",
    "GitService",
]