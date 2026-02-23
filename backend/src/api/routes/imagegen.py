"""Image Generation API routes."""
from typing import List, Optional
from pathlib import Path
import json
import uuid

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from src.core import settings
from src.core.filesystem import FilesystemService
from src.core.token_counter import format_token_count
from src.dependencies import get_filesystem
from src.services.image_generation_service import ImageGenerationService

router = APIRouter()

# Global service instance (initialized on first use)
_image_service: Optional[ImageGenerationService] = None


def get_image_service(fs: FilesystemService = Depends(get_filesystem)) -> ImageGenerationService:
    """Get image generation service instance."""
    global _image_service
    
    if _image_service is None:
        # Get Azure credentials from settings
        endpoint = getattr(settings, 'azure_image_endpoint', None)
        api_key = getattr(settings, 'azure_image_api_key', None)
        
        print(f"[IMAGE GEN ROUTE] Settings loaded:")
        print(f"  - azure_image_endpoint: {'SET' if endpoint else 'NOT SET'}")
        print(f"  - azure_image_api_key: {'SET' if api_key else 'NOT SET'}")
        
        if not endpoint or not api_key:
            # Use mock mode for testing
            print("[IMAGE GEN ROUTE] Warning: Azure image credentials not configured, using mock mode")
            endpoint = "https://mock.openai.azure.com"
            api_key = "mock-key"
        else:
            print(f"[IMAGE GEN ROUTE] Using Azure endpoint: {endpoint[:50]}...")
        
        storage_path = Path(settings.repo_path) / "generated-images"
        
        _image_service = ImageGenerationService(
            endpoint=endpoint,
            api_key=api_key,
            filesystem=fs,
            storage_path=storage_path,
        )
    
    return _image_service


# Request/Response Models

class GenerateImageRequest(BaseModel):
    """Request to generate an image."""
    prompt: str
    context_files: List[str] = []
    style_template_id: Optional[str] = None


class GenerateImageResponse(BaseModel):
    """Response from image generation."""
    success: bool
    image_data: Optional[str] = None  # base64 encoded
    image_path: Optional[str] = None
    revised_prompt: Optional[str] = None
    tokens_used: int
    formatted_tokens: str
    cost_usd: float
    error: Optional[str] = None


class TokenCountRequest(BaseModel):
    """Request to count tokens in files."""
    file_paths: List[str]


class TokenCountResponse(BaseModel):
    """Response with token counts."""
    total_tokens: int
    formatted_total: str
    max_tokens: int = 600000
    percentage: float
    breakdown: dict


class StyleTemplate(BaseModel):
    """Style template model with full prompt data."""
    id: str
    name: str
    category: str
    description: str
    base_prompt: str
    style_suffix: Optional[str] = None
    negative_prompt: Optional[str] = None


class StyleTemplatesResponse(BaseModel):
    """Response with style templates."""
    templates: List[StyleTemplate]


class CreatePromptRequest(BaseModel):
    """Request to create a new prompt."""
    name: str
    category: str
    description: str
    base_prompt: str
    style_suffix: Optional[str] = None
    negative_prompt: Optional[str] = None


# API Endpoints

@router.post("/generate", response_model=GenerateImageResponse)
async def generate_image(
    request: GenerateImageRequest,
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Generate an image from prompt and context."""
    try:
        result = await image_service.generate_image(
            prompt=request.prompt,
            context_files=request.context_files,
            style_template_id=request.style_template_id,
        )
        
        return GenerateImageResponse(
            success=result.success,
            image_data=result.image_data,
            image_path=result.image_path,
            revised_prompt=result.revised_prompt,
            tokens_used=result.tokens_used,
            formatted_tokens=format_token_count(result.tokens_used),
            cost_usd=result.cost_usd,
            error=result.error,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/count-tokens", response_model=TokenCountResponse)
async def count_tokens(
    request: TokenCountRequest,
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Count tokens in selected context files."""
    try:
        result = image_service.count_context_tokens(request.file_paths)
        
        percentage = (result["total_tokens"] / 600000) * 100
        
        return TokenCountResponse(
            total_tokens=result["total_tokens"],
            formatted_total=result["formatted"],
            max_tokens=600000,
            percentage=round(percentage, 1),
            breakdown=result["breakdown"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/styles", response_model=StyleTemplatesResponse)
async def list_style_templates(
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """List available style templates with full prompt data."""
    try:
        templates = image_service.get_style_templates()
        return StyleTemplatesResponse(
            templates=[
                StyleTemplate(
                    id=t["id"],
                    name=t["name"],
                    category=t["category"],
                    description=t["description"],
                    base_prompt=t.get("base_prompt", ""),
                    style_suffix=t.get("style_suffix"),
                    negative_prompt=t.get("negative_prompt"),
                )
                for t in templates
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/styles/{template_id}")
async def get_style_template(
    template_id: str,
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Get a specific style template."""
    try:
        template = image_service.get_style_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompts")
async def create_prompt(
    request: CreatePromptRequest,
    fs: FilesystemService = Depends(get_filesystem),
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Create a new custom prompt template."""
    try:
        # Generate unique ID
        prompt_id = f"custom_{uuid.uuid4().hex[:8]}"
        
        # Load existing templates
        template_path = Path(__file__).parent.parent / "templates" / "image-styles" / "templates.json"
        
        templates_data = {"templates": []}
        if template_path.exists():
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    templates_data = json.load(f)
            except:
                pass
        
        # Create new template
        new_template = {
            "id": prompt_id,
            "name": request.name,
            "category": request.category,
            "description": request.description,
            "base_prompt": request.base_prompt,
            "style_suffix": request.style_suffix or "",
            "negative_prompt": request.negative_prompt or "",
        }
        
        # Add to templates
        templates_data["templates"].append(new_template)
        
        # Save back to file
        template_path.parent.mkdir(parents=True, exist_ok=True)
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(templates_data, f, indent=2)
        
        # Reload templates after creating
        image_service.reload_templates()
        
        return {
            "success": True,
            "template_id": prompt_id,
            "message": "Prompt created successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: str,
    request: CreatePromptRequest,
    fs: FilesystemService = Depends(get_filesystem),
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Update an existing prompt template."""
    try:
        # Load existing templates
        template_path = Path(__file__).parent.parent / "templates" / "image-styles" / "templates.json"
        
        if not template_path.exists():
            raise HTTPException(status_code=404, detail="Template not found")
        
        with open(template_path, "r", encoding="utf-8") as f:
            templates_data = json.load(f)
        
        # Find and update template
        templates = templates_data.get("templates", [])
        template_found = False
        
        for i, template in enumerate(templates):
            if template["id"] == prompt_id:
                templates[i] = {
                    "id": prompt_id,
                    "name": request.name,
                    "category": request.category,
                    "description": request.description,
                    "base_prompt": request.base_prompt,
                    "style_suffix": request.style_suffix or "",
                    "negative_prompt": request.negative_prompt or "",
                }
                template_found = True
                break
        
        if not template_found:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Save back to file
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(templates_data, f, indent=2)
        
        # Reload templates after updating
        image_service.reload_templates()
        
        return {
            "success": True,
            "message": "Prompt updated successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    fs: FilesystemService = Depends(get_filesystem),
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Delete a custom prompt template."""
    try:
        # Load existing templates
        template_path = Path(__file__).parent.parent / "templates" / "image-styles" / "templates.json"
        
        if not template_path.exists():
            raise HTTPException(status_code=404, detail="Template not found")
        
        with open(template_path, "r", encoding="utf-8") as f:
            templates_data = json.load(f)
        
        # Find and remove template
        templates = templates_data.get("templates", [])
        original_count = len(templates)
        templates_data["templates"] = [t for t in templates if t["id"] != prompt_id]
        
        if len(templates_data["templates"]) == original_count:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Save back to file
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(templates_data, f, indent=2)
        
        # Reload templates after deleting
        image_service.reload_templates()
        
        return {
            "success": True,
            "message": "Prompt deleted successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_generation_history(
    limit: int = Query(20, ge=1, le=100),
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Get recent generation history."""
    try:
        history = image_service.get_generation_history(limit=limit)
        return {"history": history, "count": len(history)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_image_service_status(
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Get image generation service status."""
    return {
        "mock_mode": image_service._use_mock,
        "endpoint": image_service.endpoint[:50] + "..." if len(image_service.endpoint) > 50 else image_service.endpoint,
        "api_key_configured": bool(image_service.api_key) and 'mock' not in image_service.api_key.lower(),
        "storage_path": str(image_service.storage_path),
    }


@router.get("/image/{date}/{filename}")
async def serve_image(
    date: str,
    filename: str,
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Serve a generated image file."""
    from fastapi.responses import FileResponse
    
    # Security: validate date and filename to prevent directory traversal
    if '..' in date or '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    image_path = image_service.storage_path / date / filename
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(
        image_path,
        media_type="image/png",
        filename=filename
    )


@router.get("/gallery")
async def get_gallery(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    image_service: ImageGenerationService = Depends(get_image_service),
):
    """Get gallery of all generated images with thumbnails."""
    try:
        history = image_service.get_generation_history(limit=limit + offset)
        
        # Apply offset
        history = history[offset:offset + limit]
        
        # Add thumbnail URLs
        for item in history:
            if 'image_path' in item:
                path_parts = Path(item['image_path']).parts
                if len(path_parts) >= 2:
                    # Extract date and filename from path
                    date = path_parts[-2]
                    filename = path_parts[-1]
                    item['thumbnail_url'] = f"/api/imagegen/image/{date}/{filename}"
        
        return {
            "images": history,
            "count": len(history),
            "offset": offset,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
