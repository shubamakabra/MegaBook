"""API routes initialization."""
from src.api.routes import filesystem, git, pipelines, query, costs

__all__ = ["filesystem", "git", "pipelines", "query", "costs"]