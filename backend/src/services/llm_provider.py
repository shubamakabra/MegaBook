"""LLM Provider abstraction layer for MegaBook.

This module defines the interface for LLM providers and implements
the Azure AI Foundry provider as the initial implementation.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypeVar, Generic
from enum import Enum


class ProviderType(Enum):
    """Supported LLM provider types."""
    AZURE = "azure"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"  # Generic OpenAI-compatible (Kimi, Together AI, etc.)
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    MOCK = "mock"


@dataclass
class UsageInfo:
    """Token usage information from an LLM call."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
    def __add__(self, other: "UsageInfo") -> "UsageInfo":
        """Combine two usage info objects."""
        return UsageInfo(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    usage: UsageInfo
    model: str
    raw_response: Optional[Dict[str, Any]] = None


T = TypeVar("T")


@dataclass
class StructuredLLMResponse(Generic[T]):
    """Structured response from an LLM provider."""
    data: T
    usage: UsageInfo
    model: str
    raw_response: Optional[Dict[str, Any]] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model: str, **kwargs: Any) -> None:
        """Initialize the provider.
        
        Args:
            model: Model name/identifier
            **kwargs: Provider-specific configuration
        """
        self.model = model
        self.config = kwargs
    
    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate text from a prompt.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with generated text and usage info
        """
        pass
    
    @abstractmethod
    async def generate_structured_output(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> StructuredLLMResponse[Dict[str, Any]]:
        """Generate structured output from a prompt.
        
        Args:
            prompt: The user prompt
            output_schema: JSON schema for the output
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific parameters
            
        Returns:
            StructuredLLMResponse with parsed data and usage info
        """
        pass
    
    @abstractmethod
    async def generate_embeddings(
        self,
        texts: List[str],
        **kwargs: Any
    ) -> List[List[float]]:
        """Generate embeddings for texts.
        
        Args:
            texts: List of texts to embed
            **kwargs: Additional provider-specific parameters
            
        Returns:
            List of embedding vectors
        """
        pass
    
    @abstractmethod
    def get_token_count(self, text: str) -> int:
        """Get the token count for a text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        pass
    
    @abstractmethod
    def get_cost_per_1k_tokens(self) -> Dict[str, float]:
        """Get the cost per 1000 tokens.
        
        Returns:
            Dictionary with 'input' and 'output' costs in USD
        """
        pass


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""
    
    _providers: Dict[ProviderType, type] = {}
    
    @classmethod
    def register(cls, provider_type: ProviderType, provider_class: type) -> None:
        """Register a provider class.
        
        Args:
            provider_type: Provider type enum
            provider_class: Provider class (must inherit from LLMProvider)
        """
        cls._providers[provider_type] = provider_class
    
    @classmethod
    def create(
        cls,
        provider_type: ProviderType,
        model: str,
        **config: Any
    ) -> LLMProvider:
        """Create a provider instance.
        
        Args:
            provider_type: Type of provider to create
            model: Model name
            **config: Provider configuration
            
        Returns:
            Configured provider instance
            
        Raises:
            ValueError: If provider type is not registered
        """
        if provider_type not in cls._providers:
            raise ValueError(f"Provider {provider_type} not registered")
        
        provider_class = cls._providers[provider_type]
        return provider_class(model=model, **config)
    
    @classmethod
    def list_providers(cls) -> List[ProviderType]:
        """List available provider types."""
        return list(cls._providers.keys())