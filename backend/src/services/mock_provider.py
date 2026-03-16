"""Mock LLM Provider for testing without Azure/OpenAI.

This provider simulates LLM responses for development and testing.
It returns realistic-looking but fake data with zero cost.
"""
import json
import random
import hashlib
import time
from typing import Any, Dict, List, Optional

from src.services.llm_provider import (
    LLMProvider,
    LLMResponse,
    StructuredLLMResponse,
    UsageInfo,
    ProviderType,
    LLMProviderFactory,
)


class MockProvider(LLMProvider):
    """Mock LLM provider for testing.
    
    Returns realistic-looking fake responses with zero cost.
    Useful for development and testing without API keys.
    """
    
    def __init__(self, model: str = "mock-gpt-4", **kwargs: Any) -> None:
        """Initialize mock provider."""
        super().__init__(model, **kwargs)
        self.response_count = 0
    
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate fake text response."""
        self.response_count += 1
        start_time = time.time()
        
        # Generate a mock response based on the prompt
        content = self._generate_mock_text(prompt)
        
        # Calculate fake usage
        prompt_tokens = len(prompt.split())
        completion_tokens = len(content.split())
        usage = UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Log the call
        if self._logger:
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
                cost_usd=0.0,
                duration_ms=duration_ms,
                success=True,
                response_preview=content,
                extra={"provider": "mock"},
            )
        
        return LLMResponse(
            content=content,
            usage=usage,
            model=self.model,
        )
    
    async def generate_structured_output(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> StructuredLLMResponse[Dict[str, Any]]:
        """Generate fake structured output."""
        self.response_count += 1
        start_time = time.time()
        
        # Generate mock structured data
        data = self._generate_mock_structured(prompt, output_schema)
        
        prompt_tokens = len(prompt.split())
        completion_tokens = len(json.dumps(data).split())
        usage = UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Log the call
        if self._logger:
            self._logger.log_call(
                method="generate_structured_output",
                model=self.model,
                prompt=prompt,
                system_prompt=system_prompt,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cost_usd=0.0,
                duration_ms=duration_ms,
                success=True,
                response_preview=json.dumps(data)[:300],
                extra={"provider": "mock"},
            )
        
        return StructuredLLMResponse(
            data=data,
            usage=usage,
            model=self.model,
        )
    
    async def generate_embeddings(
        self,
        texts: List[str],
        **kwargs: Any
    ) -> List[List[float]]:
        """Generate fake embeddings (deterministic based on text)."""
        start_time = time.time()
        total_chars = sum(len(t) for t in texts)
        
        embeddings = []
        for text in texts:
            # Create deterministic embedding from text hash
            embedding = self._generate_mock_embedding(text)
            embeddings.append(embedding)
        
        duration_ms = (time.time() - start_time) * 1000
        
        if self._logger:
            self._logger.log_embeddings_call(
                model=self.model,
                num_texts=len(texts),
                total_chars=total_chars,
                duration_ms=duration_ms,
                success=True,
            )
        
        return embeddings
    
    def get_token_count(self, text: str) -> int:
        """Estimate token count."""
        return len(text.split())
    
    def get_cost_per_1k_tokens(self) -> Dict[str, float]:
        """Mock provider has zero cost."""
        return {"input": 0.0, "output": 0.0}
    
    def _generate_mock_text(self, prompt: str) -> str:
        """Generate a mock text response."""
        # Simple template responses based on prompt content
        if "entity" in prompt.lower() or "analyze" in prompt.lower():
            return """I've analyzed the content and identified the following key elements:

**Entities:**
- Hero Character (protagonist)
- Dark Forest (location)
- Ancient Artifact (item)
- Mysterious NPC (character)

**Key Facts:**
- The party discovered a hidden entrance
- There was combat with shadow creatures
- A clue was found about the main quest

**Themes:** Adventure, Mystery, Combat"""
        
        elif "wiki" in prompt.lower() or "article" in prompt.lower():
            return """# Sample Wiki Article

## Overview
This is a mock wiki article generated for testing purposes.

## Details
Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

## Connections
- [[Related Topic 1]]
- [[Related Topic 2]]
- [[Main Quest]]

> **Note:** This is mock content for testing the MegaBook system."""
        
        elif "note" in prompt.lower() or "markdown" in prompt.lower():
            return """---
title: Mock Generated Note
created: 2024-01-15
source: session_notes
tags: [mock, test]
---

# Generated Note

This note was automatically generated from session notes.

## Summary
- Point 1 from the session
- Point 2 from the session
- Key discovery made

## Details
Additional context and details would go here...

## Related
- [[Character Name]]
- [[Location Name]]"""
        
        else:
            return f"""This is a mock response to your prompt.

**Prompt received:** {prompt[:100]}...

**Mock Analysis:**
The system is working correctly with the mock provider. No actual LLM calls are being made.

**Next Steps:**
1. Configure real Azure/OpenAI credentials in .env
2. Change LLM_PROVIDER to 'azure' or 'openai'
3. Restart the backend

*This is response #{self.response_count} from the mock provider.*"""
    
    def _generate_mock_structured(
        self, 
        prompt: str, 
        output_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate mock structured data matching the schema."""
        result = {}
        
        # Simple schema-based generation
        if "properties" in output_schema:
            for key, prop in output_schema["properties"].items():
                prop_type = prop.get("type", "string")
                
                if prop_type == "array":
                    # Generate array of items
                    items = prop.get("items", {})
                    if items.get("type") == "object":
                        result[key] = [
                            {
                                "name": f"Entity {i}",
                                "type": "character",
                                "description": f"Description for entity {i}"
                            }
                            for i in range(1, 4)
                        ]
                    else:
                        result[key] = [f"Item {i}" for i in range(1, 4)]
                
                elif prop_type == "object":
                    result[key] = {"key": "value"}
                
                elif prop_type == "string":
                    result[key] = f"Mock {key} value"
                
                elif prop_type == "number":
                    result[key] = random.randint(1, 100)
                
                elif prop_type == "boolean":
                    result[key] = True
        
        # Add specific mock data for common fields
        if "entities" in result:
            result["entities"] = [
                {"name": "Gandalf", "type": "NPC", "description": "A wise wizard"},
                {"name": "Rivendell", "type": "Location", "description": "Elven city"},
                {"name": "The Ring", "type": "Item", "description": "Powerful artifact"},
            ]
        
        if "topics" in result:
            result["topics"] = ["Adventure", "Magic", "Combat", "Exploration"]
        
        if "suggested_note_files" in result:
            result["suggested_note_files"] = [
                {"title": "Main Character", "category": "characters", "reason": "Important NPC"},
                {"title": "Dark Cave", "category": "locations", "reason": "Key location"},
            ]
        
        return result
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Generate deterministic mock embedding."""
        # Use hash to create deterministic but varied embedding
        hash_obj = hashlib.md5(text.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        # Generate 1536-dimensional vector (standard for text-embedding-ada-002)
        random.seed(hash_int)
        embedding = [random.gauss(0, 1) for _ in range(1536)]
        
        # Normalize to unit length
        magnitude = sum(x**2 for x in embedding) ** 0.5
        embedding = [x / magnitude for x in embedding]
        
        return embedding


# Register the mock provider
LLMProviderFactory.register(ProviderType.MOCK, MockProvider)