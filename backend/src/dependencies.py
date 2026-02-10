"""Dependency injection functions for FastAPI."""
from typing import Optional

from src.core import FilesystemService, GitService
from src.services.cost_tracking import CostTrackingService
from src.services.embedding_service import EmbeddingService

# Global services container (will be set during app initialization)
_services: dict = {}


def set_services(services: dict) -> None:
    """Set the global services dictionary."""
    global _services
    _services = services


def get_filesystem() -> Optional[FilesystemService]:
    """Get filesystem service instance."""
    return _services.get("filesystem")


def get_git_service() -> Optional[GitService]:
    """Get Git service instance."""
    return _services.get("git")


def get_llm_provider():
    """Get LLM provider instance."""
    return _services.get("llm_provider")


def get_cost_tracking() -> Optional[CostTrackingService]:
    """Get cost tracking service instance."""
    return _services.get("cost_tracking")


def get_embedding_service() -> Optional[EmbeddingService]:
    """Get embedding service instance."""
    return _services.get("embedding")