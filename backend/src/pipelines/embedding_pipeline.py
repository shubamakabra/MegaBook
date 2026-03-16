"""Embedding Pipeline for MegaBook.

Generates and manages vector embeddings for notes to enable RAG queries.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.filesystem import FilesystemService
from src.pipelines.base import Pipeline, PipelineResult
from src.services.embedding_service import EmbeddingService
from src.services.llm_provider import LLMProvider


@dataclass
class EmbeddingItem:
    """Item to generate embeddings for."""
    note_path: str
    content: str


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    processed_notes: int
    total_chunks: int
    failed_notes: List[str]
    generation_timestamp: str
    db_stats: Dict[str, Any]


class EmbeddingPipeline(Pipeline[EmbeddingResult]):
    """Pipeline for generating embeddings from notes.
    
    Processes notes/ and generates vector embeddings for RAG queries.
    """
    
    def __init__(
        self,
        pipeline_id: str,
        storage_path: Path,
        filesystem: FilesystemService,
        embedding_service: EmbeddingService,
        llm_provider: Optional[LLMProvider] = None,
    ) -> None:
        """Initialize the embedding pipeline.
        
        Args:
            pipeline_id: Unique identifier
            storage_path: Path for state storage
            filesystem: Filesystem service instance
            embedding_service: Embedding service instance
            llm_provider: Optional LLM provider for embeddings
        """
        super().__init__(pipeline_id, storage_path)
        self.filesystem = filesystem
        self.embedding_service = embedding_service
        self.llm_provider = llm_provider
    
    async def prepare(
        self,
        note_paths: Optional[List[str]] = None,
        rebuild: bool = False,
        **kwargs: Any
    ) -> None:
        """Prepare notes for embedding generation.
        
        Args:
            note_paths: Specific notes to process (None = all notes)
            rebuild: If True, clear existing embeddings first
        """
        if rebuild:
            self.embedding_service.clear_all()
        
        self._current_items = []
        
        if note_paths:
            for path in note_paths:
                content = self.filesystem.read_file(path)
                self._current_items.append(EmbeddingItem(
                    note_path=path,
                    content=content,
                ))
        else:
            # Get all notes
            all_notes = self.filesystem.list_files(folder="notes")
            for note_info in all_notes:
                content = self.filesystem.read_file(note_info.relative_path)
                self._current_items.append(EmbeddingItem(
                    note_path=note_info.relative_path,
                    content=content,
                ))
    
    async def process_item(self, item: EmbeddingItem) -> Dict[str, Any]:
        """Process a single note into embeddings.
        
        Args:
            item: Embedding item
            
        Returns:
            Processing result
        """
        try:
            # Delete existing embeddings for this note
            import hashlib
            note_id = hashlib.md5(item.note_path.encode()).hexdigest()
            self.embedding_service.delete_notes([note_id])
            
            # Add new embeddings
            notes_data = [{
                "id": note_id,
                "content": item.content,
                "metadata": {
                    "file_path": item.note_path,
                    "title": Path(item.note_path).stem,
                },
            }]
            
            ids = await self.embedding_service.add_notes(notes_data)
            
            return {
                "success": True,
                "note_path": item.note_path,
                "chunks_created": len(ids),
            }
        except Exception as e:
            return {
                "success": False,
                "note_path": item.note_path,
                "error": str(e),
            }
    
    def _get_result_data(self) -> EmbeddingResult:
        """Get embedding results."""
        processed = 0
        failed = []
        total_chunks = 0
        
        for result in self._processed_items:
            if isinstance(result, dict):
                if result.get("success"):
                    processed += 1
                    total_chunks += result.get("chunks_created", 0)
                else:
                    failed.append(result["note_path"])
        
        return EmbeddingResult(
            processed_notes=processed,
            total_chunks=total_chunks,
            failed_notes=failed,
            generation_timestamp=datetime.now().isoformat(),
            db_stats=self.embedding_service.get_stats(),
        )