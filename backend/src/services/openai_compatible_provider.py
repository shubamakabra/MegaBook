"""Modular OpenAI-compatible LLM Provider.

Works with any OpenAI-compatible API including:
- Azure OpenAI
- Kimi K2.5 (Moonshot AI)
- Together AI
- Local models (LM Studio, etc.)
- Any other OpenAI-compatible endpoint
"""
import json
from typing import Any, Dict, List, Optional
from openai import OpenAI

from src.services.llm_provider import (
    LLMProvider,
    LLMResponse,
    StructuredLLMResponse,
    UsageInfo,
)


class OpenAICompatibleProvider(LLMProvider):
    """Generic OpenAI-compatible provider for any OpenAI API.
    
    Works with Kimi K2.5, Azure, Together AI, local models, etc.
    """
    
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        **kwargs: Any
    ) -> None:
        """Initialize OpenAI-compatible provider.
        
        Args:
            model: Model name/deployment (e.g., "Kimi-K2.5", "gpt-4")
            base_url: API endpoint URL (e.g., "https://agent-garage.services.ai.azure.com/openai/v1/")
            api_key: API key
        """
        super().__init__(model, **kwargs)
        
        try:
            print(f"   [CONN] Connecting to: {base_url}")
            print(f"   [MODEL] Model: {model}")
            
            # Parse URL
            from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode
            parsed = urlsplit(base_url)
            
            # Check if it's an Azure OpenAI endpoint
            is_azure = 'azure.com' in parsed.netloc or 'azure' in parsed.netloc
            
            if is_azure:
                # For Azure OpenAI, keep query parameters (api-version is required)
                clean_url = base_url
                print(f"   [AZURE] Detected Azure endpoint - preserving query params")
            else:
                # For other providers, remove query parameters
                clean_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
                if clean_url != base_url:
                    print(f"   [CLEAN] Cleaned URL: {clean_url}")
            
            # Create standard OpenAI client with custom base_url
            # This works with Kimi, Azure, Together AI, etc.
            import httpx
            http_client = httpx.Client()
            
            self.client = OpenAI(
                base_url=clean_url,
                api_key=api_key,
                http_client=http_client,
            )
            
            print(f"[OK] OpenAI-compatible client initialized")
            
        except Exception as e:
            print(f"[ERROR] Failed to initialize OpenAI client: {e}")
            raise
    
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate text using OpenAI-compatible API."""
        import asyncio
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            # Debug: Log the exact request being made
            import json
            print(f"   [API CALL] Model: {self.model}")
            print(f"   [API CALL] Messages count: {len(messages)}")
            print(f"   [API CALL] Full messages array:")
            for i, msg in enumerate(messages):
                print(f"      [{i}] role={msg['role']}: {msg['content'][:200]}{'...' if len(msg['content']) > 200 else ''}")
            print(f"   [API CALL] Temperature: {temperature}, Max tokens: {max_tokens}")
            
            # Run synchronous OpenAI call in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )
            
            # Handle missing usage info gracefully
            usage = UsageInfo(
                prompt_tokens=getattr(response.usage, 'prompt_tokens', 0) if response.usage else 0,
                completion_tokens=getattr(response.usage, 'completion_tokens', 0) if response.usage else 0,
                total_tokens=getattr(response.usage, 'total_tokens', 0) if response.usage else 0,
            )
            
            content = response.choices[0].message.content or ""
            
            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model,
            )
        except Exception as e:
            print(f"   [API ERROR] OpenAI API error: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate chat response with full conversation history.
        
        Args:
            messages: Full array of messages including system, user, and assistant
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            LLMResponse with the assistant's response
        """
        import asyncio
        
        try:
            # Debug: Log the request
            print(f"   [CHAT CALL] Model: {self.model}")
            print(f"   [CHAT CALL] Messages count: {len(messages)}")
            print(f"   [CHAT CALL] Full conversation:")
            for i, msg in enumerate(messages):
                preview = msg['content'][:150] + '...' if len(msg['content']) > 150 else msg['content']
                print(f"      [{i}] {msg['role']}: {preview}")
            print(f"   [CHAT CALL] Temperature: {temperature}, Max tokens: {max_tokens}")
            
            # Run synchronous OpenAI call in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )
            
            # Handle missing usage info gracefully
            usage = UsageInfo(
                prompt_tokens=getattr(response.usage, 'prompt_tokens', 0) if response.usage else 0,
                completion_tokens=getattr(response.usage, 'completion_tokens', 0) if response.usage else 0,
                total_tokens=getattr(response.usage, 'total_tokens', 0) if response.usage else 0,
            )
            
            content = response.choices[0].message.content or ""
            
            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model,
            )
        except Exception as e:
            print(f"   [CHAT ERROR] OpenAI API error: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def generate_structured_output(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> StructuredLLMResponse[Dict[str, Any]]:
        """Generate structured output using OpenAI-compatible API."""
        import asyncio
        
        schema_prompt = f"""
You must respond with valid JSON that matches this schema:
{json.dumps(output_schema, indent=2)}

Respond ONLY with the JSON, no other text."""
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt + schema_prompt})
        else:
            messages.append({"role": "system", "content": schema_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
            )
            
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            
            usage = UsageInfo(
                prompt_tokens=getattr(response.usage, 'prompt_tokens', 0) if response.usage else 0,
                completion_tokens=getattr(response.usage, 'completion_tokens', 0) if response.usage else 0,
                total_tokens=getattr(response.usage, 'total_tokens', 0) if response.usage else 0,
            )
            
            return StructuredLLMResponse(
                data=data,
                usage=usage,
                model=self.model,
            )
        except Exception as e:
            print(f"OpenAI structured output error: {e}")
            raise
    
    async def generate_embeddings(
        self,
        texts: List[str],
        **kwargs: Any
    ) -> List[List[float]]:
        """Generate embeddings using OpenAI-compatible API."""
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                )
            )
            
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"OpenAI embeddings error: {e}")
            raise
    
    def get_token_count(self, text: str) -> int:
        """Get the token count for a text."""
        import tiktoken
        try:
            # Try to get encoding for the model
            encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback to cl100k_base for unknown models
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    
    def get_cost_per_1k_tokens(self) -> Dict[str, float]:
        """Get the cost per 1000 tokens."""
        # Generic pricing - override based on actual model if needed
        # Kimi K2.5 pricing (approximate):
        if "kimi" in self.model.lower():
            return {"input": 0.001, "output": 0.003}
        
        # OpenAI pricing
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        }
        
        # Check if model name contains any of the keys
        for model_key, costs in pricing.items():
            if model_key in self.model.lower():
                return costs
        
        # Default fallback
        return {"input": 0.01, "output": 0.03}


# Register the provider
from src.services.llm_provider import LLMProviderFactory, ProviderType
LLMProviderFactory.register(ProviderType.OPENAI_COMPATIBLE, OpenAICompatibleProvider)