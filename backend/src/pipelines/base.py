"""Processing pipeline system for MegaBook.

Provides the base infrastructure for all processing pipelines with:
- Pause/resume functionality
- Progress persistence
- Cost tracking integration
- Atomic operations
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, TypeVar, Callable

from src.services.cost_tracking import CostTrackingService


class PipelineState(Enum):
    """Pipeline execution states."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    ERROR = auto()


class PipelineError(Exception):
    """Base exception for pipeline errors."""
    pass


class CostLimitExceededError(PipelineError):
    """Raised when cost limit is exceeded."""
    pass


@dataclass
class PipelineProgress:
    """Progress information for a pipeline."""
    pipeline_id: str
    pipeline_type: str
    current_step: int
    total_steps: int
    current_item: Optional[str] = None
    state: str = "idle"
    started_at: Optional[str] = None
    last_updated: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pipeline_id": self.pipeline_id,
            "pipeline_type": self.pipeline_type,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "current_item": self.current_item,
            "state": self.state,
            "started_at": self.started_at,
            "last_updated": self.last_updated,
            "error_message": self.error_message,
            "percentage": self.percentage,
            "metadata": self.metadata,
        }


T = TypeVar("T")


@dataclass
class PipelineResult(Generic[T]):
    """Result from a pipeline execution."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    stats: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = {}


class Pipeline(ABC, Generic[T]):
    """Base class for all processing pipelines.
    
    Provides:
    - Progress tracking
    - State persistence
    - Cost monitoring
    - Pause/resume functionality
    """
    
    def __init__(
        self,
        pipeline_id: str,
        storage_path: Path,
        cost_tracking: Optional[CostTrackingService] = None,
    ) -> None:
        """Initialize the pipeline.
        
        Args:
            pipeline_id: Unique identifier for this pipeline instance
            storage_path: Directory to store progress state
            cost_tracking: Optional cost tracking service
        """
        self.pipeline_id = pipeline_id
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.cost_tracking = cost_tracking
        
        self._state = PipelineState.IDLE
        self._progress = PipelineProgress(
            pipeline_id=pipeline_id,
            pipeline_type=self.__class__.__name__,
            current_step=0,
            total_steps=0,
        )
        self._current_items: List[Any] = []
        self._processed_items: List[Any] = []
        self._on_pause_callback: Optional[Callable] = None
        self._on_resume_callback: Optional[Callable] = None
        
        # Try to load existing state
        self._load_state()
    
    @property
    def state(self) -> PipelineState:
        """Get current pipeline state."""
        return self._state
    
    @property
    def progress(self) -> PipelineProgress:
        """Get current progress."""
        return self._progress
    
    @abstractmethod
    async def prepare(self, **kwargs: Any) -> None:
        """Prepare the pipeline for execution.
        
        Override this to set up items to process.
        """
        pass
    
    @abstractmethod
    async def process_item(self, item: Any) -> Any:
        """Process a single item.
        
        This is the atomic unit of work. Override this method
        to implement the actual processing logic.
        
        Args:
            item: Item to process
            
        Returns:
            Result of processing
        """
        pass
    
    async def run(
        self,
        resume: bool = False,
        **kwargs: Any
    ) -> PipelineResult[T]:
        """Run the pipeline.
        
        Args:
            resume: Whether to resume from saved state
            **kwargs: Additional arguments for prepare()
            
        Returns:
            PipelineResult with execution results
        """
        try:
            if resume:
                if self._state != PipelineState.PAUSED:
                    return PipelineResult(
                        success=False,
                        error="Cannot resume: pipeline not in PAUSED state",
                    )
                self._state = PipelineState.RUNNING
                self._progress.state = "running"
            else:
                # Fresh start
                self._state = PipelineState.RUNNING
                self._progress.state = "running"
                self._progress.started_at = datetime.now().isoformat()
                self._progress.current_step = 0
                self._processed_items = []
                await self.prepare(**kwargs)
                self._progress.total_steps = len(self._current_items)
            
            self._save_state()
            
            # Process items
            start_idx = len(self._processed_items)
            for i in range(start_idx, len(self._current_items)):
                # Check if paused
                if self._state == PipelineState.PAUSED:
                    self._save_state()
                    if self._on_pause_callback:
                        self._on_pause_callback()
                    return PipelineResult(
                        success=False,
                        error="Pipeline paused by user",
                    )
                
                # Check cost limit
                if self.cost_tracking:
                    should_stop, reason = self.cost_tracking.check_limit()
                    if should_stop:
                        self._state = PipelineState.PAUSED
                        self.cost_tracking.stop_session(reason)
                        self._progress.state = "paused"
                        self._progress.error_message = reason
                        self._save_state()
                        raise CostLimitExceededError(reason)
                
                item = self._current_items[i]
                self._progress.current_item = str(item)
                self._progress.current_step = i + 1
                self._progress.last_updated = datetime.now().isoformat()
                
                try:
                    result = await self.process_item(item)
                    self._processed_items.append(result)
                    self._save_state()
                except Exception as e:
                    self._state = PipelineState.ERROR
                    self._progress.state = "error"
                    self._progress.error_message = str(e)
                    self._save_state()
                    return PipelineResult(
                        success=False,
                        error=f"Error processing item {item}: {str(e)}",
                    )
            
            # Completed successfully
            self._state = PipelineState.COMPLETED
            self._progress.state = "completed"
            self._progress.current_item = None
            self._progress.last_updated = datetime.now().isoformat()
            self._save_state()
            
            return PipelineResult(
                success=True,
                data=self._get_result_data(),
                stats={
                    "total_items": len(self._current_items),
                    "processed_items": len(self._processed_items),
                    "duration": self._calculate_duration(),
                },
            )
            
        except CostLimitExceededError:
            raise
        except Exception as e:
            self._state = PipelineState.ERROR
            self._progress.state = "error"
            self._progress.error_message = str(e)
            self._save_state()
            return PipelineResult(success=False, error=str(e))
    
    def pause(self) -> None:
        """Pause the pipeline.
        
        The pipeline will pause after completing the current item.
        """
        if self._state == PipelineState.RUNNING:
            self._state = PipelineState.PAUSED
            self._progress.state = "paused"
            self._progress.last_updated = datetime.now().isoformat()
            self._save_state()
    
    def resume(self) -> None:
        """Resume a paused pipeline.
        
        This just sets the state; actual resumption happens in run().
        """
        if self._state == PipelineState.PAUSED:
            self._state = PipelineState.IDLE  # Will be set to RUNNING in run()
            self.cost_tracking.resume_session() if self.cost_tracking else None
            if self._on_resume_callback:
                self._on_resume_callback()
    
    def stop(self) -> None:
        """Stop the pipeline completely."""
        self._state = PipelineState.IDLE
        self._progress.state = "idle"
        self._progress.last_updated = datetime.now().isoformat()
        self._save_state()
    
    def set_pause_callback(self, callback: Callable) -> None:
        """Set callback for when pipeline pauses."""
        self._on_pause_callback = callback
    
    def set_resume_callback(self, callback: Callable) -> None:
        """Set callback for when pipeline resumes."""
        self._on_resume_callback = callback
    
    def _get_result_data(self) -> T:
        """Get the final result data.
        
        Override this to customize what data is returned.
        """
        return self._processed_items  # type: ignore
    
    def _save_state(self) -> None:
        """Save current state to disk."""
        state_file = self.storage_path / f"{self.pipeline_id}_state.json"
        
        state_data = {
            "pipeline_id": self.pipeline_id,
            "state": self._state.name,
            "progress": self._progress.to_dict(),
            "current_items": self._serialize_items(self._current_items),
            "processed_items": self._serialize_items(self._processed_items),
        }
        
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)
    
    def _load_state(self) -> bool:
        """Load state from disk if it exists.
        
        Returns:
            True if state was loaded, False otherwise
        """
        state_file = self.storage_path / f"{self.pipeline_id}_state.json"
        
        if not state_file.exists():
            return False
        
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            
            self._state = PipelineState[state_data.get("state", "IDLE")]
            
            progress_data = state_data.get("progress", {})
            self._progress = PipelineProgress(
                pipeline_id=progress_data.get("pipeline_id", self.pipeline_id),
                pipeline_type=progress_data.get("pipeline_type", self.__class__.__name__),
                current_step=progress_data.get("current_step", 0),
                total_steps=progress_data.get("total_steps", 0),
                current_item=progress_data.get("current_item"),
                state=progress_data.get("state", "idle"),
                started_at=progress_data.get("started_at"),
                last_updated=progress_data.get("last_updated"),
                error_message=progress_data.get("error_message"),
                metadata=progress_data.get("metadata", {}),
            )
            
            self._current_items = self._deserialize_items(state_data.get("current_items", []))
            self._processed_items = self._deserialize_items(state_data.get("processed_items", []))
            
            return True
        except Exception:
            return False
    
    def _serialize_items(self, items: List[Any]) -> List[Any]:
        """Serialize items for storage. Override if items need custom serialization."""
        return items
    
    def _deserialize_items(self, items: List[Any]) -> List[Any]:
        """Deserialize items from storage. Override if items need custom deserialization."""
        return items
    
    def _calculate_duration(self) -> Optional[float]:
        """Calculate pipeline duration in seconds."""
        if not self._progress.started_at or not self._progress.last_updated:
            return None
        
        start = datetime.fromisoformat(self._progress.started_at)
        end = datetime.fromisoformat(self._progress.last_updated)
        return (end - start).total_seconds()
    
    def cleanup(self) -> None:
        """Clean up saved state files."""
        state_file = self.storage_path / f"{self.pipeline_id}_state.json"
        if state_file.exists():
            state_file.unlink()