"""Azure AI Foundry LLM Provider implementation."""
import json
from typing import Any, Dict, List, Optional

from azure.ai.inference import ChatCompletionsClient, EmbeddingsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

from src.services.llm_provider import (
    LLMProvider,
    LLMResponse,
    StructuredLLMResponse,
    UsageInfo,
    ProviderType,
    LLMProviderFactory,
)


# Azure OpenAI pricing (as of early 2024) - update as needed
AZURE_PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-35-turbo": {"input": 0.0005, "output": 0.0015},
    "text-embedding-ada-002": {"input": 0.0001, "output": 0.0},
    "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
}

DEFAULT_FALLBACK_PRICING = {"input": 0.01, "output": 0.03}


class AzureProvider(LLMProvider):
    """Azure AI Foundry LLM provider."""
    
    def __init__(
        self,
        model: str,
        endpoint: str,
        api_key: str,
        api_version: str = "2024-02-01",
        **kwargs: Any
    ) -> None:
        """Initialize Azure provider.
        
        Args:
            model: Deployment name
            endpoint: Azure endpoint URL
            api_key: Azure API key
            api_version: API version
            **kwargs: Additional configuration
        """
        super().__init__(model, **kwargs)
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_version = api_version
        
        credential = AzureKeyCredential(api_key)
        
        self.chat_client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=credential,
            api_version=api_version,
        )
        
        self.embeddings_client = EmbeddingsClient(
            endpoint=endpoint,
            credential=credential,
            api_version=api_version,
        )
    
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate text using Azure OpenAI."""
        import asyncio
        
        messages = []
        
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        
        messages.append(UserMessage(content=prompt))
        
        try:
            # Run the synchronous Azure call in a thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.chat_client.complete(
                    messages=messages,
                    model=self.model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            )
            
            usage = UsageInfo(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                usage=usage,
                model=self.model,
                raw_response=response.as_dict() if hasattr(response, 'as_dict') else None,
            )
        except Exception as e:
            print(f"Azure API error in generate_text: {e}")
            raise
    
    async def generate_structured_output(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> StructuredLLMResponse[Dict[str, Any]]:
        """Generate structured output using Azure OpenAI."""
        # Add schema to system prompt
        schema_prompt = f"""
You must respond with valid JSON that matches this schema:
{json.dumps(output_schema, indent=2)}

Respond ONLY with the JSON, no other text."""
        
        full_system = f"{system_prompt or ''}\n\n{schema_prompt}".strip()
        
        messages = [SystemMessage(content=full_system)]
        messages.append(UserMessage(content=prompt))
        
        response = self.chat_client.complete(
            messages=messages,
            model=self.model,
            response_format={"type": "json_object"},
            **kwargs
        )
        
        content = response.choices[0].message.content
        
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse structured output: {e}")
        
        usage = UsageInfo(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        )
        
        return StructuredLLMResponse(
            data=data,
            usage=usage,
            model=self.model,
            raw_response=response.as_dict() if hasattr(response, 'as_dict') else None,
        )
    
    async def generate_embeddings(
        self,
        texts: List[str],
        **kwargs: Any
    ) -> List[List[float]]:
        """Generate embeddings using Azure OpenAI."""
        response = self.embeddings_client.embed(
            input=texts,
            model=self.model,
            **kwargs
        )
        
        return [item.embedding for item in response.data]
    
    def get_token_count(self, text: str) -> int:
        """Estimate token count using rough approximation.
        
        For accurate counts, use tiktoken (added as dependency).
        """
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except:
            # Fallback: rough estimate (4 chars per token)
            return len(text) // 4
    
    def get_cost_per_1k_tokens(self) -> Dict[str, float]:
        """Get Azure pricing for the model."""
        # Try to match model name
        for model_key, pricing in AZURE_PRICING.items():
            if model_key in self.model.lower():
                return pricing
        
        # Default fallback
        return DEFAULT_FALLBACK_PRICING


# Import and use the new Azure OpenAI provider instead
from src.services.azure_openai_provider import AzureOpenAIProvider

# Register the provider
LLMProviderFactory.register(ProviderType.AZURE, AzureOpenAIProvider)