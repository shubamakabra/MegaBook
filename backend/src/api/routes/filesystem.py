"""Filesystem API routes."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from src.core import FilesystemService, KnowledgeLayer
from src.dependencies import get_filesystem
import json
import hashlib
from pathlib import Path

router = APIRouter()


class FileInfo(BaseModel):
    """File information model."""
    path: str
    layer: str
    relative_path: str
    size: int
    modified: float


class FileContent(BaseModel):
    """File content model."""
    path: str
    content: str
    layer: str


class WriteFileRequest(BaseModel):
    """Write file request model."""
    path: str
    content: str


@router.get("/files", response_model=List[FileInfo])
async def list_files(
    layer: Optional[str] = Query(None, description="Filter by layer (prompts, notes, wiki)"),
    fs: FilesystemService = Depends(get_filesystem),
):
    """List files in the repository."""
    knowledge_layer = None
    if layer:
        try:
            knowledge_layer = KnowledgeLayer[layer.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid layer: {layer}")
    
    files = fs.list_files(layer=knowledge_layer)
    return [
        FileInfo(
            path=str(f.path),
            layer=f.layer.name.lower(),
            relative_path=f.relative_path,
            size=f.size,
            modified=f.modified,
        )
        for f in files
    ]


@router.get("/files/{path:path}", response_model=FileContent)
async def read_file(path: str, fs: FilesystemService = Depends(get_filesystem)):
    """Read a file from the repository."""
    try:
        content = fs.read_file(path)
        file_info = fs.get_file_stats(path)
        
        return FileContent(
            path=path,
            content=content,
            layer=file_info.layer.name.lower() if file_info else "unknown",
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/download/{path:path}")
async def download_file(path: str, fs: FilesystemService = Depends(get_filesystem)):
    """Download a file (for binary files like images)."""
    from fastapi.responses import FileResponse
    from pathlib import Path
    import mimetypes
    
    try:
        # Construct full path using repo_path
        full_path = fs.repo_path / path
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Guess content type
        content_type, _ = mimetypes.guess_type(str(full_path))
        if not content_type:
            content_type = "application/octet-stream"
        
        return FileResponse(
            path=str(full_path),
            media_type=content_type,
            filename=full_path.name,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/files")
async def write_file(request: WriteFileRequest, fs: FilesystemService = Depends(get_filesystem)):
    """Write a file to the repository."""
    try:
        fs.write_file(request.path, request.content)
        return {"success": True, "path": request.path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/files/{path:path}")
async def delete_file(path: str, fs: FilesystemService = Depends(get_filesystem)):
    """Delete a file from the repository."""
    try:
        fs.delete_file(path)
        return {"success": True, "path": path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tree")
async def get_file_tree(
    layer: Optional[str] = Query(None, description="Filter by layer"),
    fs: FilesystemService = Depends(get_filesystem),
):
    """Get repository file tree structure."""
    knowledge_layer = None
    if layer:
        try:
            knowledge_layer = KnowledgeLayer[layer.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid layer: {layer}")
    
    files = fs.list_files(layer=knowledge_layer)
    
    # Build tree structure
    tree = {}
    for f in files:
        parts = f.relative_path.split("/")
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # File
                current[part] = {
                    "type": "file",
                    "path": f.relative_path,
                    "size": f.size,
                    "modified": f.modified,
                }
            else:
                # Directory
                if part not in current:
                    current[part] = {"type": "directory", "children": {}}
                current = current[part]["children"]
    
    return tree


class SyncStatusResponse(BaseModel):
    """Sync status response model."""
    file_path: str
    is_synced: bool
    last_processed: Optional[str] = None
    content_hash: Optional[str] = None
    current_hash: str
    content_changed: bool
    entities_count: int = 0


@router.get("/sync-status", response_model=SyncStatusResponse)
async def get_sync_status(
    path: str = Query(..., description="File path to check"),
    fs: FilesystemService = Depends(get_filesystem),
):
    """Get sync status for a file."""
    try:
        # Read current file content and calculate hash
        content = fs.read_file(path)
        current_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        # Read metadata
        metadata_path = "metadata/sync_index.json"
        try:
            metadata_content = fs.read_file(metadata_path)
            metadata = json.loads(metadata_content)
        except (FileNotFoundError, json.JSONDecodeError):
            metadata = {"files": {}}
        
        # Get file metadata
        file_meta = metadata.get("files", {}).get(path, {})
        stored_hash = file_meta.get("content_hash")
        last_processed = file_meta.get("last_processed")
        entities_count = file_meta.get("entity_count", 0)
        
        # Check if synced
        is_synced = stored_hash == current_hash and last_processed is not None
        content_changed = stored_hash != current_hash
        
        return SyncStatusResponse(
            file_path=path,
            is_synced=is_synced,
            last_processed=last_processed,
            content_hash=stored_hash,
            current_hash=current_hash,
            content_changed=content_changed,
            entities_count=entities_count,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


class SyncStatusBatchResponse(BaseModel):
    """Batch sync status response."""
    files: List[SyncStatusResponse]


@router.post("/sync-status/batch", response_model=SyncStatusBatchResponse)
async def get_sync_status_batch(
    paths: List[str],
    fs: FilesystemService = Depends(get_filesystem),
):
    """Get sync status for multiple files."""
    results = []
    
    # Read metadata once
    metadata_path = "metadata/sync_index.json"
    try:
        metadata_content = fs.read_file(metadata_path)
        metadata = json.loads(metadata_content)
    except (FileNotFoundError, json.JSONDecodeError):
        metadata = {"files": {}}
    
    for path in paths:
        try:
            content = fs.read_file(path)
            current_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            file_meta = metadata.get("files", {}).get(path, {})
            stored_hash = file_meta.get("content_hash")
            last_processed = file_meta.get("last_processed")
            entities_count = file_meta.get("entity_count", 0)
            
            is_synced = stored_hash == current_hash and last_processed is not None
            content_changed = stored_hash != current_hash
            
            results.append(SyncStatusResponse(
                file_path=path,
                is_synced=is_synced,
                last_processed=last_processed,
                content_hash=stored_hash,
                current_hash=current_hash,
                content_changed=content_changed,
                entities_count=entities_count,
            ))
        except Exception:
            # Skip files that can't be read
            pass
    
    return SyncStatusBatchResponse(files=results)