"""Import Pipeline for MegaBook.

Handles manual import of markdown files from external sources (Milanote export,
file uploads, etc.) into the prompts/ directory.
"""
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.filesystem import FilesystemService
from src.pipelines.base import Pipeline, PipelineResult


@dataclass
class ImportItem:
    """Item to be imported."""
    source_path: Path
    target_path: str  # Relative path in prompts/
    content: str
    original_filename: str


@dataclass
class ImportResult:
    """Result of an import operation."""
    imported_files: List[str]
    skipped_files: List[str]
    errors: List[str]
    import_timestamp: str


class ImportPipeline(Pipeline[ImportResult]):
    """Pipeline for importing external markdown files.
    
    Takes files from a source directory and imports them into prompts/,
    preserving structure and handling naming conflicts.
    """
    
    def __init__(
        self,
        pipeline_id: str,
        storage_path: Path,
        filesystem: FilesystemService,
    ) -> None:
        """Initialize the import pipeline.
        
        Args:
            pipeline_id: Unique identifier
            storage_path: Path for state storage
            filesystem: Filesystem service instance
        """
        super().__init__(pipeline_id, storage_path)
        self.filesystem = filesystem
        self._import_items: List[ImportItem] = []
    
    async def prepare(
        self,
        source_path: Path,
        target_subdir: str = "",
        **kwargs: Any
    ) -> None:
        """Prepare import items from source directory.
        
        Args:
            source_path: Directory containing files to import
            target_subdir: Optional subdirectory under prompts/
        """
        source_path = Path(source_path)
        self._import_items = []
        
        if not source_path.exists():
            raise ValueError(f"Source path does not exist: {source_path}")
        
        # Find all markdown files
        md_files = list(source_path.rglob("*.md"))
        
        for md_file in md_files:
            # Calculate relative path from source
            rel_path = md_file.relative_to(source_path)
            
            # Build target path
            if target_subdir:
                target_rel = f"prompts/{target_subdir}/{rel_path}"
            else:
                target_rel = f"prompts/{rel_path}"
            
            # Read content
            content = md_file.read_text(encoding="utf-8")
            
            # Handle naming conflicts by adding timestamp
            target_path = Path(target_rel)
            counter = 1
            original_target = target_rel
            while self.filesystem.file_exists(target_rel):
                stem = target_path.stem
                suffix = target_path.suffix
                parent = str(target_path.parent).replace("\\", "/")
                target_rel = f"{parent}/{stem}_{counter}{suffix}"
                counter += 1
            
            self._import_items.append(ImportItem(
                source_path=md_file,
                target_path=target_rel,
                content=content,
                original_filename=str(rel_path),
            ))
        
        self._current_items = self._import_items
    
    async def process_item(self, item: ImportItem) -> Dict[str, Any]:
        """Import a single file.
        
        Args:
            item: Import item to process
            
        Returns:
            Result dictionary
        """
        try:
            # Write to filesystem
            self.filesystem.write_file(
                item.target_path,
                item.content,
            )
            
            return {
                "success": True,
                "source": str(item.source_path),
                "target": item.target_path,
                "original_name": item.original_filename,
            }
        except Exception as e:
            return {
                "success": False,
                "source": str(item.source_path),
                "error": str(e),
            }
    
    def _get_result_data(self) -> ImportResult:
        """Get import results."""
        imported = []
        errors = []
        
        for result in self._processed_items:
            if isinstance(result, dict):
                if result.get("success"):
                    imported.append(result["target"])
                else:
                    errors.append(f"{result.get('source')}: {result.get('error')}")
        
        # Determine skipped files
        skipped = [
            item.original_filename
            for item in self._import_items
            if item.original_filename not in [r.get("original_name") for r in self._processed_items if isinstance(r, dict)]
        ]
        
        return ImportResult(
            imported_files=imported,
            skipped_files=skipped,
            errors=errors,
            import_timestamp=datetime.now().isoformat(),
        )
    
    async def import_single_file(
        self,
        filename: str,
        content: str,
        target_subdir: str = "",
    ) -> PipelineResult[ImportResult]:
        """Import a single file directly (for UI uploads).
        
        Args:
            filename: Original filename
            content: File content
            target_subdir: Optional subdirectory under prompts/
            
        Returns:
            Pipeline result
        """
        # Create single item
        if target_subdir:
            target_path = f"prompts/{target_subdir}/{filename}"
        else:
            target_path = f"prompts/{filename}"
        
        # Handle conflicts
        counter = 1
        original_target = target_path
        while self.filesystem.file_exists(target_path):
            path_obj = Path(target_path)
            stem = path_obj.stem
            suffix = path_obj.suffix
            parent = str(path_obj.parent).replace("\\", "/")
            target_path = f"{parent}/{stem}_{counter}{suffix}"
            counter += 1
        
        self._import_items = [ImportItem(
            source_path=Path(filename),
            target_path=target_path,
            content=content,
            original_filename=filename,
        )]
        self._current_items = self._import_items
        self._progress.total_steps = 1
        
        # Process immediately
        result = await self.process_item(self._import_items[0])
        self._processed_items = [result]
        
        if result.get("success"):
            return PipelineResult(
                success=True,
                data=ImportResult(
                    imported_files=[result["target"]],
                    skipped_files=[],
                    errors=[],
                    import_timestamp=datetime.now().isoformat(),
                ),
            )
        else:
            return PipelineResult(
                success=False,
                error=result.get("error", "Unknown error"),
            )