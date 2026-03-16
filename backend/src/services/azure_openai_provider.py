"""Azure OpenAI Provider using the openai package (more reliable)."""
import json
import time
from typing import Any, Dict, List, Optional
from openai import AzureOpenAI

from src.services.llm_provider import (
    LLMProvider,
    LLMResponse,
    StructuredLLMResponse,
    UsageInfo,
)


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider using the openai package."""
    
    def __init__(
        self,
        model: str,
        endpoint: str,
        api_key: str,
        api_version: str = "2024-02-01",
        **kwargs: Any
    ) -> None:
        """Initialize Azure OpenAI provider.
        
        Args:
            model: Deployment name (e.g., "gpt-4")
            endpoint: Azure endpoint URL (e.g., "https://your-resource.openai.azure.com/")
            api_key: Azure API key
            api_version: API version
        """
        super().__init__(model, **kwargs)
        
        try:
            # Validate endpoint format
            if not endpoint.startswith('https://'):
                endpoint = f"https://{endpoint}"
            
            # Ensure endpoint ends with /
            if not endpoint.endswith('/'):
                endpoint = f"{endpoint}/"
            
            print(f"   [CONN] Connecting to: {endpoint}")
            
            # Create client - let it use default http client
            self.client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
            )
            
            # Test the connection with a simple request
            print(f"   [TEST] Testing connection...")
            try:
                # Try to list models or make a simple request
                self.client.models.list()
                print(f"[OK] Azure OpenAI client initialized and tested: {endpoint}")
            except Exception as test_e:
                print(f"   [WARN] Connection test failed: {test_e}")
                print(f"   [OK] Client initialized but endpoint may not be reachable")
                
        except Exception as e:
            print(f"[ERROR] Failed to initialize Azure OpenAI: {e}")
            print(f"   [TIP] Check your .env file:")
            print(f"      AZURE_ENDPOINT=https://your-resource.openai.azure.com/")
            print(f"      AZURE_API_KEY=your-key")
            raise
    
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
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        start_time = time.time()
        try:
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
            
            usage = UsageInfo(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            
            content = response.choices[0].message.content
            duration_ms = (time.time() - start_time) * 1000
            
            # Log the call
            if self._logger:
                cost_per_1k = self.get_cost_per_1k_tokens()
                cost_usd = (cost_per_1k["input"] * usage.prompt_tokens / 1000) + (cost_per_1k["output"] * usage.completion_tokens / 1000)
                self._logger.log_call(
                    method="generate_text",
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    cost_usd=cost_usd,
                    duration_ms=duration_ms,
                    success=True,
                    response_preview=content,
                )
            
            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            print(f"Azure OpenAI API error: {e}")
            
            if self._logger:
                self._logger.log_call(
                    method="generate_text",
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    duration_ms=duration_ms,
                    success=False,
                    error=str(e),
                )
            raise
    
    async def generate_structured_output(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> StructuredLLMResponse[Dict[str, Any]]:
        """Generate structured output using Azure OpenAI."""
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
        
        start_time = time.time()
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
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            usage = UsageInfo(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Log the call
            if self._logger:
                cost_per_1k = self.get_cost_per_1k_tokens()
                cost_usd = (cost_per_1k["input"] * usage.prompt_tokens / 1000) + (cost_per_1k["output"] * usage.completion_tokens / 1000)
                self._logger.log_call(
                    method="generate_structured_output",
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    cost_usd=cost_usd,
                    duration_ms=duration_ms,
                    success=True,
                    response_preview=content,
                )
            
            return StructuredLLMResponse(
                data=data,
                usage=usage,
                model=self.model,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            print(f"Azure OpenAI structured output error: {e}")
            
            if self._logger:
                self._logger.log_call(
                    method="generate_structured_output",
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    duration_ms=duration_ms,
                    success=False,
                    error=str(e),
                )
            raise
    
    async def generate_embeddings(
        self,
        texts: List[str],
        **kwargs: Any
    ) -> List[List[float]]:
        """Generate embeddings using Azure OpenAI."""
        import asyncio
        
        start_time = time.time()
        total_chars = sum(len(t) for t in texts)
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                )
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            if self._logger:
                self._logger.log_embeddings_call(
                    model=self.model,
                    num_texts=len(texts),
                    total_chars=total_chars,
                    duration_ms=duration_ms,
                    success=True,
                )
            
            return [item.embedding for item in response.data]
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            print(f"Azure OpenAI embeddings error: {e}")
            
            if self._logger:
                self._logger.log_embeddings_call(
                    model=self.model,
                    num_texts=len(texts),
                    total_chars=total_chars,
                    duration_ms=duration_ms,
                    success=False,
                    error=str(e),
                )
            raise
    
    def get_token_count(self, text: str) -> int:
        """Get the token count for a text."""
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    
    def get_cost_per_1k_tokens(self) -> Dict[str, float]:
        """Get the cost per 1000 tokens."""
        # Azure OpenAI pricing (approximate)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-35-turbo": {"input": 0.0015, "output": 0.002},
        }
        return pricing.get(self.model, {"input": 0.01, "output": 0.03})
