"""Image Generation Service for MegaBook.

Integrates with Azure gpt-image-1.5 for AI image generation using REST API.
"""
import json
import base64
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.filesystem import FilesystemService
from src.core.token_counter import count_tokens, format_token_count


@dataclass
class ImageGenerationResult:
    """Result of image generation."""
    success: bool
    image_data: Optional[str]  # base64 encoded
    image_path: Optional[str]  # local file path
    revised_prompt: Optional[str]
    tokens_used: int
    cost_usd: float
    error: Optional[str] = None


class ImageGenerationService:
    """Service for generating images using Azure gpt-image-1.5."""
    
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        filesystem: FilesystemService,
        storage_path: Path,
    ):
        """Initialize the image generation service.
        
        Args:
            endpoint: Azure OpenAI endpoint URL (full URL with path)
            api_key: Azure OpenAI API key
            filesystem: Filesystem service instance
            storage_path: Path to store generated images
        """
        print(f"[IMAGE GEN SERVICE] Initializing...")
        print(f"[IMAGE GEN SERVICE] Endpoint: {endpoint[:60] if endpoint else 'None'}...")
        print(f"[IMAGE GEN SERVICE] API key present: {bool(api_key)}")
        print(f"[IMAGE GEN SERVICE] Is mock: {'mock' in endpoint.lower()}")
        
        self.endpoint = endpoint
        self.api_key = api_key
        self.filesystem = filesystem
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Check if we should use mock mode
        self._use_mock = not api_key or 'mock' in endpoint.lower() or not endpoint
        
        if self._use_mock:
            print("[IMAGE GEN SERVICE] Using MOCK mode")
        else:
            print("[IMAGE GEN SERVICE] Using REAL Azure API mode")
        
        # Load style templates
        self._style_templates = self._load_style_templates()
        print(f"[IMAGE GEN SERVICE] Loaded {len(self._style_templates)} style templates")
    
    def _load_style_templates(self) -> Dict[str, Dict]:
        """Load style templates from JSON."""
        template_path = Path(__file__).parent.parent / "templates" / "image-styles" / "templates.json"
        
        if not template_path.exists():
            return {}
        
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Create lookup by ID
                return {t["id"]: t for t in data.get("templates", [])}
        except Exception:
            return {}
    
    def reload_templates(self) -> None:
        """Reload style templates from disk (call after modifications)."""
        self._style_templates = self._load_style_templates()
    
    def get_style_templates(self) -> List[Dict]:
        """Get all available style templates."""
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "category": t["category"],
                "description": t["description"],
                "base_prompt": t.get("base_prompt", ""),
                "style_suffix": t.get("style_suffix"),
                "negative_prompt": t.get("negative_prompt"),
            }
            for t in self._style_templates.values()
        ]
    
    def get_style_template(self, template_id: str) -> Optional[Dict]:
        """Get a specific style template by ID."""
        return self._style_templates.get(template_id)
    
    def build_prompt(
        self,
        user_prompt: str,
        context: str = "",
        style_template_id: Optional[str] = None,
    ) -> str:
        """Build the final prompt from components.
        
        Args:
            user_prompt: User's description
            context: Context from notes (optional)
            style_template_id: Style template ID (optional)
            
        Returns:
            Final prompt string
        """
        parts = []
        
        # Add style base prompt
        if style_template_id and style_template_id in self._style_templates:
            template = self._style_templates[style_template_id]
            parts.append(template["base_prompt"])
        
        # Add context if provided
        if context:
            parts.append(f"Context: {context}")
        
        # Add user prompt
        parts.append(user_prompt)
        
        # Add style suffix if available
        if style_template_id and style_template_id in self._style_templates:
            template = self._style_templates[style_template_id]
            if template.get("style_suffix"):
                parts.append(template["style_suffix"])
        
        return " ".join(parts)
    
    def count_context_tokens(self, context_files: List[str]) -> Dict[str, Any]:
        """Count tokens in context files.
        
        Args:
            context_files: List of file paths
            
        Returns:
            Dictionary with token counts and breakdown
        """
        total_tokens = 0
        breakdown = {}
        
        for path in context_files:
            try:
                content = self.filesystem.read_file(path)
                tokens = count_tokens(content)
                breakdown[path] = tokens
                total_tokens += tokens
            except Exception:
                breakdown[path] = 0
        
        return {
            "total_tokens": total_tokens,
            "breakdown": breakdown,
            "formatted": format_token_count(total_tokens),
        }
    
    async def generate_image(
        self,
        prompt: str,
        context_files: Optional[List[str]] = None,
        style_template_id: Optional[str] = None,
    ) -> ImageGenerationResult:
        """Generate an image.
        
        Args:
            prompt: User's image description
            context_files: List of note file paths for context
            style_template_id: Style template to use
            
        Returns:
            ImageGenerationResult with image data or error
        """
        try:
            # Gather context from files
            context_parts = []
            if context_files:
                for path in context_files:
                    try:
                        content = self.filesystem.read_file(path)
                        # Truncate very long files to avoid token limits
                        if len(content) > 10000:
                            content = content[:10000] + "... [truncated]"
                        context_parts.append(f"From {path}:\n{content}")
                    except Exception as e:
                        print(f"Warning: Could not read context file {path}: {e}")
            
            context = "\n\n".join(context_parts)
            
            # Build final prompt
            final_prompt = self.build_prompt(prompt, context, style_template_id)
            
            # Count tokens
            tokens_used = count_tokens(final_prompt)
            
            # Check token limit (600k for gpt-image-1.5)
            if tokens_used > 600000:
                return ImageGenerationResult(
                    success=False,
                    image_data=None,
                    image_path=None,
                    revised_prompt=None,
                    tokens_used=tokens_used,
                    cost_usd=0.0,
                    error=f"Token limit exceeded: {format_token_count(tokens_used)}/600k",
                )
            
            # Call Azure API (or mock if not available)
            if self._use_mock:
                return await self._mock_generate(final_prompt, tokens_used)
            else:
                return await self._azure_generate(final_prompt, tokens_used)
            
        except Exception as e:
            return ImageGenerationResult(
                success=False,
                image_data=None,
                image_path=None,
                revised_prompt=None,
                tokens_used=0,
                cost_usd=0.0,
                error=str(e),
            )
    
    async def _azure_generate(
        self,
        prompt: str,
        tokens_used: int,
    ) -> ImageGenerationResult:
        """Generate image using Azure OpenAI REST API."""
        import httpx
        import asyncio
        
        try:
            print(f"[IMAGE GEN] Calling Azure API with prompt length: {len(prompt)} chars")
            
            # Prepare the request
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            }
            
            payload = {
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "medium"
            }
            
            # Make the API call
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    json=payload
                )
                
                print(f"[IMAGE GEN] Response status: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = response.text
                    print(f"[IMAGE GEN] API Error: {error_text}")
                    return await self._mock_generate(
                        prompt, tokens_used, 
                        error=f"Azure API error: {response.status_code} - {error_text}"
                    )
                
                data = response.json()
                
                # Extract image data
                if "data" in data and len(data["data"]) > 0:
                    image_data = data["data"][0].get("b64_json")
                    revised_prompt = data["data"][0].get("revised_prompt", prompt)
                else:
                    return await self._mock_generate(
                        prompt, tokens_used,
                        error="No image data in response"
                    )
                
                # Save to file
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
                filename = f"{timestamp}_{prompt_hash}"
                
                # Create date-based subdirectory
                date_dir = datetime.now().strftime("%Y-%m-%d")
                save_dir = self.storage_path / date_dir
                save_dir.mkdir(parents=True, exist_ok=True)
                
                image_path = save_dir / f"{filename}.png"
                
                # Decode and save image
                image_bytes = base64.b64decode(image_data)
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                
                print(f"[IMAGE GEN] Image saved to: {image_path}")
                
                # Save metadata
                metadata = {
                    "prompt": prompt,
                    "revised_prompt": revised_prompt,
                    "tokens_used": tokens_used,
                    "timestamp": datetime.now().isoformat(),
                    "image_path": str(image_path),
                }
                
                metadata_path = save_dir / f"{filename}.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)
                
                # Estimate cost (approximate for gpt-image-1.5)
                # Standard quality 1024x1024: ~$0.04 per image
                cost_usd = 0.04
                
                return ImageGenerationResult(
                    success=True,
                    image_data=image_data,
                    image_path=str(image_path),
                    revised_prompt=revised_prompt,
                    tokens_used=tokens_used,
                    cost_usd=cost_usd,
                )
            
        except Exception as e:
            print(f"[IMAGE GEN] Azure API error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to mock on API error
            return await self._mock_generate(prompt, tokens_used, error=str(e))
    
    async def _mock_generate(
        self,
        prompt: str,
        tokens_used: int,
        error: Optional[str] = None,
    ) -> ImageGenerationResult:
        """Mock image generation for testing without Azure credentials."""
        print(f"[MOCK MODE] Generating image for prompt: {prompt[:50]}...")
        
        # Create a simple placeholder image (1x1 pixel transparent PNG)
        placeholder_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        # Save to file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        filename = f"{timestamp}_{prompt_hash}"
        
        # Create date-based subdirectory
        date_dir = datetime.now().strftime("%Y-%m-%d")
        save_dir = self.storage_path / date_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        
        image_path = save_dir / f"{filename}.png"
        
        with open(image_path, "wb") as f:
            f.write(placeholder_png)
        
        # Save metadata
        metadata = {
            "prompt": prompt,
            "revised_prompt": f"[MOCK] {prompt}",
            "tokens_used": tokens_used,
            "timestamp": datetime.now().isoformat(),
            "image_path": str(image_path),
        }
        
        metadata_path = save_dir / f"{filename}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        return ImageGenerationResult(
            success=True,
            image_data=base64.b64encode(placeholder_png).decode(),
            image_path=str(image_path),
            revised_prompt=f"[MOCK] {prompt}",
            tokens_used=tokens_used,
            cost_usd=0.0,
            error=error,
        )
    
    def get_generation_history(self, limit: int = 20) -> List[Dict]:
        """Get recent generation history.
        
        Args:
            limit: Maximum number of items to return
            
        Returns:
            List of generation metadata
        """
        history = []
        
        # Walk through storage directory
        for date_dir in sorted(self.storage_path.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            
            for metadata_file in sorted(date_dir.glob("*.json"), reverse=True):
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                        history.append(metadata)
                        
                        if len(history) >= limit:
                            break
                except Exception:
                    continue
            
            if len(history) >= limit:
                break
        
        return history[:limit]
