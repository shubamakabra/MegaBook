"""Filesystem API routes."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, File, UploadFile
from pydantic import BaseModel

from src.core import FilesystemService
from src.dependencies import get_filesystem
import json
import hashlib
from pathlib import Path

router = APIRouter()


class FileInfo(BaseModel):
    """File information model."""
    path: str
    relative_path: str
    size: int
    modified: float


class FileContent(BaseModel):
    """File content model."""
    path: str
    content: str


class WriteFileRequest(BaseModel):
    """Write file request model."""
    path: str
    content: str


@router.get("/files", response_model=List[FileInfo])
async def list_files(
    folder: Optional[str] = Query(None, description="Filter by subfolder (e.g. 'notes')"),
    pattern: Optional[str] = Query(None, description="Glob pattern (default: **/*.md)"),
    fs: FilesystemService = Depends(get_filesystem),
):
    """List files in the vault."""
    kwargs = {}
    if folder:
        kwargs["folder"] = folder
    if pattern:
        kwargs["pattern"] = pattern

    files = fs.list_files(**kwargs)
    return [
        FileInfo(
            path=str(f.path),
            relative_path=f.relative_path,
            size=f.size,
            modified=f.modified,
        )
        for f in files
    ]


@router.get("/files/{path:path}", response_model=FileContent)
async def read_file(path: str, fs: FilesystemService = Depends(get_filesystem)):
    """Read a file from the vault."""
    try:
        content = fs.read_file(path)

        return FileContent(
            path=path,
            content=content,
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
    """Write a file to the vault."""
    try:
        fs.write_file(request.path, request.content)
        return {"success": True, "path": request.path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    path: str = Query(..., description="Target path for the file"),
    fs: FilesystemService = Depends(get_filesystem)
):
    """Upload a binary file to the vault."""
    try:
        content = await file.read()
        full_path = fs.repo_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return {"success": True, "path": path, "size": len(content)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/files/{path:path}")
async def delete_file(path: str, fs: FilesystemService = Depends(get_filesystem)):
    """Delete a file from the vault."""
    try:
        fs.delete_file(path)
        return {"success": True, "path": path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class RenameRequest(BaseModel):
    """Rename request model."""
    old_path: str
    new_path: str


@router.post("/rename")
async def rename_file(request: RenameRequest, fs: FilesystemService = Depends(get_filesystem)):
    """Rename or move a file/folder."""
    try:
        import shutil
        old_full_path = fs.repo_path / request.old_path
        new_full_path = fs.repo_path / request.new_path

        if not old_full_path.exists():
            raise HTTPException(status_code=404, detail=f"Source not found: {request.old_path}")

        if new_full_path.exists():
            raise HTTPException(status_code=400, detail=f"Destination already exists: {request.new_path}")

        # Ensure parent directory exists
        new_full_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(old_full_path), str(new_full_path))
        return {"success": True, "old_path": request.old_path, "new_path": request.new_path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class CopyRequest(BaseModel):
    """Copy request model."""
    source_path: str
    target_path: str


@router.post("/copy")
async def copy_file(request: CopyRequest, fs: FilesystemService = Depends(get_filesystem)):
    """Copy a file or folder."""
    try:
        import shutil
        source_full_path = fs.repo_path / request.source_path
        target_full_path = fs.repo_path / request.target_path

        if not source_full_path.exists():
            raise HTTPException(status_code=404, detail=f"Source not found: {request.source_path}")

        if target_full_path.exists():
            raise HTTPException(status_code=400, detail=f"Destination already exists: {request.target_path}")

        # Ensure parent directory exists
        target_full_path.parent.mkdir(parents=True, exist_ok=True)

        if source_full_path.is_dir():
            shutil.copytree(str(source_full_path), str(target_full_path))
        else:
            shutil.copy2(str(source_full_path), str(target_full_path))

        return {"success": True, "source_path": request.source_path, "target_path": request.target_path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class CreateFolderRequest(BaseModel):
    """Create folder request model."""
    path: str


@router.post("/mkdir")
async def create_folder(request: CreateFolderRequest, fs: FilesystemService = Depends(get_filesystem)):
    """Create a new folder."""
    try:
        full_path = fs.repo_path / request.path
        full_path.mkdir(parents=True, exist_ok=True)
        return {"success": True, "path": request.path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tree")
async def get_file_tree(
    folder: Optional[str] = Query(None, description="Filter by subfolder"),
    fs: FilesystemService = Depends(get_filesystem),
):
    """Get vault file tree structure."""
    files = fs.list_files(folder=folder)

    # Build tree structure as array (for frontend compatibility)
    def build_tree(path: str = "") -> list:
        """Recursively build tree array structure."""
        items = []

        # Get items at current path
        if path:
            current_files = [f for f in files if f.relative_path.startswith(path + "/")]
        else:
            current_files = files

        # Get immediate children
        seen = set()
        for f in current_files:
            rel_path = f.relative_path[len(path):] if path else f.relative_path
            if rel_path.startswith("/"):
                rel_path = rel_path[1:]

            parts = rel_path.split("/")
            name = parts[0]

            if name in seen:
                continue
            seen.add(name)

            if len(parts) == 1:
                # File
                items.append({
                    "name": name,
                    "type": "file",
                    "path": f.relative_path,
                    "size": f.size,
                    "modified": f.modified,
                })
            else:
                # Directory
                child_path = path + "/" + name if path else name
                children = build_tree(child_path)
                items.append({
                    "name": name,
                    "type": "directory",
                    "path": child_path,
                    "children": children,
                })

        return items

    tree = build_tree()
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
