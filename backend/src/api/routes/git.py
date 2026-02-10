"""Git API routes."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from src.dependencies import get_git_service

router = APIRouter()


class GitStatus(BaseModel):
    """Git status model."""
    is_dirty: bool
    untracked_files: List[str]
    modified_files: List[str]
    staged_files: List[str]
    active_branch: str
    commit_count: int


class CommitInfo(BaseModel):
    """Commit information model."""
    hash: str
    short_hash: str
    message: str
    author: str
    date: str


class CommitRequest(BaseModel):
    """Commit request model."""
    message: str
    author_name: Optional[str] = None


class DiffResponse(BaseModel):
    """Diff response model."""
    diff: str
    path: Optional[str] = None


@router.get("/status", response_model=GitStatus)
async def get_status(git_service = Depends(get_git_service)):
    """Get Git repository status."""
    if git_service is None:
        raise HTTPException(status_code=503, detail="Git service not available")
    
    try:
        status = git_service.get_status()
        return GitStatus(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/commit")
async def create_commit(request: CommitRequest, git_service = Depends(get_git_service)):
    """Create a Git commit."""
    if git_service is None:
        raise HTTPException(status_code=503, detail="Git service not available")
    
    try:
        commit_hash = git_service.commit(
            message=request.message,
            author_name=request.author_name,
        )
        return {"success": True, "commit_hash": commit_hash}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history", response_model=List[CommitInfo])
async def get_history(
    path: Optional[str] = Query(None, description="Filter by file path"),
    max_count: int = Query(50, description="Maximum number of commits"),
    git_service = Depends(get_git_service),
):
    """Get commit history."""
    if git_service is None:
        raise HTTPException(status_code=503, detail="Git service not available")
    
    try:
        history = git_service.get_history(path=path, max_count=max_count)
        return [CommitInfo(**commit) for commit in history]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diff", response_model=DiffResponse)
async def get_diff(
    path: Optional[str] = Query(None, description="Specific file path"),
    git_service = Depends(get_git_service),
):
    """Get diff of uncommitted changes."""
    if git_service is None:
        raise HTTPException(status_code=503, detail="Git service not available")
    
    try:
        diff = git_service.get_diff(path=path)
        return DiffResponse(diff=diff, path=path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diff/{path:path}", response_model=DiffResponse)
async def get_file_diff(path: str, git_service = Depends(get_git_service)):
    """Get diff for a specific file."""
    if git_service is None:
        raise HTTPException(status_code=503, detail="Git service not available")
    
    try:
        diff = git_service.get_file_diff(path)
        return DiffResponse(diff=diff, path=path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stage")
async def stage_files(paths: List[str], git_service = Depends(get_git_service)):
    """Stage files for commit."""
    if git_service is None:
        raise HTTPException(status_code=503, detail="Git service not available")
    
    try:
        git_service.stage_files(paths)
        return {"success": True, "staged_count": len(paths)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stage-all")
async def stage_all(git_service = Depends(get_git_service)):
    """Stage all changes."""
    if git_service is None:
        raise HTTPException(status_code=503, detail="Git service not available")
    
    try:
        git_service.stage_all()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/discard")
async def discard_changes(
    paths: Optional[List[str]] = None,
    git_service = Depends(get_git_service),
):
    """Discard uncommitted changes."""
    if git_service is None:
        raise HTTPException(status_code=503, detail="Git service not available")
    
    try:
        git_service.discard_changes(paths)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))