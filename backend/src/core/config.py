"""MegaBook configuration management."""
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Repository paths
    repo_path: Path = Field(default=Path("."), description="Path to the vault (Obsidian vault or any folder)")
    meta_dir: str = Field(default=".megabook", description="MegaBook metadata directory name")
    
    # LLM Configuration
    llm_provider: str = Field(default="openai_compatible", description="LLM provider (openai_compatible, azure, mock)")
    
    # Generic OpenAI-compatible (works with Kimi, Together AI, local models, etc.)
    openai_base_url: Optional[str] = Field(default=None, description="OpenAI-compatible API base URL")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI-compatible API key")
    chat_model: str = Field(default="gpt-4", description="Chat model name (e.g., 'Kimi-K2.5', 'gpt-4')")
    
    # Azure OpenAI (legacy support)
    azure_endpoint: Optional[str] = Field(default=None, description="Azure AI endpoint")
    azure_api_key: Optional[str] = Field(default=None, description="Azure AI API key")
    azure_deployment: Optional[str] = Field(default=None, description="Azure deployment name")
    
    # Image Generation Configuration
    azure_image_endpoint: Optional[str] = Field(default=None, description="Azure Image Gen endpoint")
    azure_image_api_key: Optional[str] = Field(default=None, description="Azure Image Gen API key")
    
    # Cost tracking
    cost_limit_nok: float = Field(default=10.0, description="Cost limit in Norwegian Kroner")
    cost_limit_usd: Optional[float] = Field(default=None, description="Cost limit in USD")
    enable_cost_stops: bool = Field(default=True, description="Enable cost-based processing stops")
    
    # Embeddings
    embedding_model: str = Field(default="text-embedding-ada-002", description="Embedding model name")
    vector_db_path: Path = Field(default=Path(".megabook/embeddings.sqlite"), description="Vector database path")
    
    # Processing
    atomic_batch_size: int = Field(default=10, description="Number of items to process atomically")
    
    @property
    def meta_path(self) -> Path:
        """Get absolute path to .megabook metadata directory."""
        return self.repo_path / self.meta_dir

    @property
    def processing_path(self) -> Path:
        """Get absolute path to processing state directory."""
        return self.meta_path / "processing"

    @property
    def costs_path(self) -> Path:
        """Get absolute path to costs tracking directory."""
        return self.meta_path / "costs"

    @property
    def logs_path(self) -> Path:
        """Get absolute path to LLM call logs directory."""
        return self.meta_path / "logs"


# Global settings instance
settings = Settings()