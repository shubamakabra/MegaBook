"""Pipelines API routes."""
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Query
from pydantic import BaseModel

from src.core import settings
from src.pipelines import (
    ImportPipeline,
    StructuringPipeline,
    WikiGenerationPipeline,
    EmbeddingPipeline,
    EntityExtractionPipeline,
    PipelineState,
)
from src.dependencies import (
    get_filesystem,
    get_llm_provider,
    get_cost_tracking,
    get_embedding_service,
)

router = APIRouter()

# Store active pipelines
active_pipelines: Dict[str, Any] = {}


class PipelineStartRequest(BaseModel):
    """Pipeline start request."""
    params: Optional[Dict[str, Any]] = {}


class PipelineControlRequest(BaseModel):
    """Pipeline control request."""
    pipeline_id: str


class PipelineStatus(BaseModel):
    """Pipeline status model."""
    pipeline_id: str
    pipeline_type: str
    state: str
    progress_percentage: float
    current_step: int
    total_steps: int
    current_item: Optional[str]
    error_message: Optional[str]


class SessionNotesRequest(BaseModel):
    """Request to process session notes."""
    content: str
    session_id: Optional[str] = None


class ApplyChangesRequest(BaseModel):
    """Request to apply structuring changes."""
    pipeline_id: str
    change_indices: Optional[List[int]] = None


@router.post("/import/start")
async def start_import_pipeline(
    source_path: Optional[str] = Query(None, description="Source directory path"),
    target_subdir: str = Query("", description="Target subdirectory under prompts/"),
):
    """Start import pipeline."""
    fs = get_filesystem()
    if not fs:
        raise HTTPException(status_code=503, detail="Filesystem service not available")
    
    pipeline_id = f"import_{uuid.uuid4().hex[:8]}"
    
    pipeline = ImportPipeline(
        pipeline_id=pipeline_id,
        storage_path=settings.processing_path,
        filesystem=fs,
    )
    
    active_pipelines[pipeline_id] = pipeline
    
    if source_path:
        # Import from directory
        await pipeline.prepare(
            source_path=Path(source_path),
            target_subdir=target_subdir,
        )
    
    return {"pipeline_id": pipeline_id, "status": "prepared"}


@router.post("/import/upload")
async def upload_file(
    file: UploadFile = File(...),
    target_subdir: str = Query("", description="Target subdirectory under prompts/"),
):
    """Upload and import a single file."""
    fs = get_filesystem()
    if not fs:
        raise HTTPException(status_code=503, detail="Filesystem service not available")
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    pipeline_id = f"import_upload_{uuid.uuid4().hex[:8]}"
    
    pipeline = ImportPipeline(
        pipeline_id=pipeline_id,
        storage_path=settings.processing_path,
        filesystem=fs,
    )
    
    content = await file.read()
    content_str = content.decode("utf-8")
    
    result = await pipeline.import_single_file(
        filename=file.filename,
        content=content_str,
        target_subdir=target_subdir,
    )
    
    # Convert ImportResult dataclass to dict
    result_data = None
    if result.data:
        result_data = {
            "imported_files": result.data.imported_files,
            "skipped_files": result.data.skipped_files,
            "errors": result.data.errors,
            "import_timestamp": result.data.import_timestamp,
        }
    
    return {
        "success": result.success,
        "data": result_data,
        "error": result.error,
    }


@router.post("/structuring/start")
async def start_structuring_pipeline(
    prompt_paths: Optional[List[str]] = Query(None, description="Specific prompts to process"),
):
    """Start structuring pipeline."""
    fs = get_filesystem()
    llm = get_llm_provider()
    cost = get_cost_tracking()
    
    if not fs:
        raise HTTPException(status_code=503, detail="Filesystem service not available")
    if not llm:
        raise HTTPException(status_code=503, detail="LLM provider not available")
    
    pipeline_id = f"structuring_{uuid.uuid4().hex[:8]}"
    
    pipeline = StructuringPipeline(
        pipeline_id=pipeline_id,
        storage_path=settings.processing_path,
        filesystem=fs,
        llm_provider=llm,
        cost_tracking=cost,
    )
    
    active_pipelines[pipeline_id] = pipeline
    
    # Start cost tracking session
    if cost:
        cost.start_session(pipeline_id)
    
    # Prepare pipeline
    await pipeline.prepare(prompt_paths=prompt_paths)
    
    return {"pipeline_id": pipeline_id, "status": "prepared"}


@router.post("/structuring/session")
async def process_session_notes(request: SessionNotesRequest):
    """Process raw session notes."""
    fs = get_filesystem()
    llm = get_llm_provider()
    cost = get_cost_tracking()
    
    if not fs:
        raise HTTPException(status_code=503, detail="Filesystem service not available")
    if not llm:
        raise HTTPException(status_code=503, detail="LLM provider not available")
    
    pipeline_id = f"session_{uuid.uuid4().hex[:8]}"
    
    pipeline = StructuringPipeline(
        pipeline_id=pipeline_id,
        storage_path=settings.processing_path,
        filesystem=fs,
        llm_provider=llm,
        cost_tracking=cost,
    )
    
    active_pipelines[pipeline_id] = pipeline
    
    # Start cost tracking session
    if cost:
        cost.start_session(pipeline_id)
    
    # Prepare with session content
    await pipeline.prepare(
        session_content=request.content,
        session_id=request.session_id,
    )
    
    return {"pipeline_id": pipeline_id, "status": "prepared"}


@router.get("/structuring/{pipeline_id}/changes")
async def get_proposed_changes(pipeline_id: str):
    """Get proposed changes from structuring pipeline."""
    if pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = active_pipelines[pipeline_id]
    if not isinstance(pipeline, StructuringPipeline):
        raise HTTPException(status_code=400, detail="Not a structuring pipeline")
    
    changes = pipeline.get_proposed_changes()
    return {"changes": [c.__dict__ for c in changes]}


@router.post("/structuring/apply")
async def apply_structuring_changes(request: ApplyChangesRequest):
    """Apply proposed changes from structuring pipeline."""
    if request.pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = active_pipelines[request.pipeline_id]
    if not isinstance(pipeline, StructuringPipeline):
        raise HTTPException(status_code=400, detail="Not a structuring pipeline")
    
    result = await pipeline.apply_changes(request.change_indices)
    return result


@router.post("/wiki/start")
async def start_wiki_pipeline(
    note_paths: Optional[List[str]] = Query(None),
    audience_levels: List[str] = Query(["dm"]),
):
    """Start wiki generation pipeline."""
    fs = get_filesystem()
    llm = get_llm_provider()
    cost = get_cost_tracking()
    
    if not fs:
        raise HTTPException(status_code=503, detail="Filesystem service not available")
    if not llm:
        raise HTTPException(status_code=503, detail="LLM provider not available")
    
    pipeline_id = f"wiki_{uuid.uuid4().hex[:8]}"
    
    pipeline = WikiGenerationPipeline(
        pipeline_id=pipeline_id,
        storage_path=settings.processing_path,
        filesystem=fs,
        llm_provider=llm,
        cost_tracking=cost,
    )
    
    active_pipelines[pipeline_id] = pipeline
    
    # Start cost tracking session
    if cost:
        cost.start_session(pipeline_id)
    
    await pipeline.prepare(
        note_paths=note_paths,
        audience_levels=audience_levels,
    )
    
    return {"pipeline_id": pipeline_id, "status": "prepared"}


@router.post("/embedding/start")
async def start_embedding_pipeline(
    note_paths: Optional[List[str]] = Query(None),
    rebuild: bool = Query(False, description="Rebuild all embeddings"),
):
    """Start embedding pipeline."""
    fs = get_filesystem()
    embedding_svc = get_embedding_service()
    llm = get_llm_provider()
    
    if not fs:
        raise HTTPException(status_code=503, detail="Filesystem service not available")
    if not embedding_svc:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    
    pipeline_id = f"embedding_{uuid.uuid4().hex[:8]}"
    
    pipeline = EmbeddingPipeline(
        pipeline_id=pipeline_id,
        storage_path=settings.processing_path,
        filesystem=fs,
        embedding_service=embedding_svc,
        llm_provider=llm,
    )
    
    active_pipelines[pipeline_id] = pipeline
    
    await pipeline.prepare(
        note_paths=note_paths,
        rebuild=rebuild,
    )
    
    return {"pipeline_id": pipeline_id, "status": "prepared"}


@router.post("/run/{pipeline_id}")
async def run_pipeline(
    pipeline_id: str,
    background_tasks: BackgroundTasks,
    resume: bool = Query(False, description="Resume from paused state"),
):
    """Run or resume a pipeline."""
    if pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = active_pipelines[pipeline_id]
    
    # Run in background
    async def run():
        result = await pipeline.run(resume=resume)
        return result
    
    background_tasks.add_task(run)
    
    return {"pipeline_id": pipeline_id, "status": "running"}


@router.post("/pause/{pipeline_id}")
async def pause_pipeline(pipeline_id: str):
    """Pause a running pipeline."""
    if pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = active_pipelines[pipeline_id]
    pipeline.pause()
    
    return {"pipeline_id": pipeline_id, "status": "paused"}


@router.post("/resume/{pipeline_id}")
async def resume_pipeline(pipeline_id: str):
    """Resume a paused pipeline."""
    if pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = active_pipelines[pipeline_id]
    pipeline.resume()
    
    return {"pipeline_id": pipeline_id, "status": "resumed"}


@router.post("/stop/{pipeline_id}")
async def stop_pipeline(pipeline_id: str):
    """Stop a pipeline."""
    if pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = active_pipelines[pipeline_id]
    pipeline.stop()
    
    return {"pipeline_id": pipeline_id, "status": "stopped"}


@router.get("/status/{pipeline_id}", response_model=PipelineStatus)
async def get_pipeline_status(pipeline_id: str):
    """Get pipeline status."""
    if pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = active_pipelines[pipeline_id]
    progress = pipeline.progress
    
    return PipelineStatus(
        pipeline_id=pipeline_id,
        pipeline_type=progress.pipeline_type,
        state=progress.state,
        progress_percentage=progress.percentage,
        current_step=progress.current_step,
        total_steps=progress.total_steps,
        current_item=progress.current_item,
        error_message=progress.error_message,
    )


@router.get("/active")
async def list_active_pipelines():
    """List all active pipelines."""
    return {
        "pipelines": [
            {
                "id": pid,
                "type": p.progress.pipeline_type,
                "state": p.state.name,
            }
            for pid, p in active_pipelines.items()
        ]
    }


# Entity Extraction Pipeline Endpoints

class EntityExtractionStartRequest(BaseModel):
    """Request to start entity extraction."""
    note_path: str


@router.post("/extraction/start")
async def start_entity_extraction_pipeline(
    request: EntityExtractionStartRequest,
):
    """Start entity extraction pipeline for a note."""
    fs = get_filesystem()
    llm = get_llm_provider()
    cost = get_cost_tracking()
    
    if not fs:
        raise HTTPException(status_code=503, detail="Filesystem service not available")
    if not llm:
        raise HTTPException(status_code=503, detail="LLM provider not available")
    
    pipeline_id = f"extraction_{uuid.uuid4().hex[:8]}"
    
    pipeline = EntityExtractionPipeline(
        pipeline_id=pipeline_id,
        storage_path=settings.processing_path,
        filesystem=fs,
        llm_provider=llm,
        cost_tracking=cost,
    )
    
    active_pipelines[pipeline_id] = pipeline
    
    # Start cost tracking session
    if cost:
        cost.start_session(pipeline_id)
    
    # Prepare pipeline
    await pipeline.prepare(note_path=request.note_path)
    
    return {"pipeline_id": pipeline_id, "status": "prepared"}


@router.post("/extraction/{pipeline_id}/run")
async def run_entity_extraction_pipeline(pipeline_id: str):
    """Run the entity extraction pipeline."""
    if pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = active_pipelines[pipeline_id]
    if not isinstance(pipeline, EntityExtractionPipeline):
        raise HTTPException(status_code=400, detail="Not an entity extraction pipeline")
    
    # Run the pipeline
    result = await pipeline.process()
    
    if result.success:
        return {
            "pipeline_id": pipeline_id,
            "status": "completed",
            "result": result.data.to_dict() if result.data else None,
            "stats": result.stats,
        }
    else:
        raise HTTPException(status_code=500, detail=result.error)