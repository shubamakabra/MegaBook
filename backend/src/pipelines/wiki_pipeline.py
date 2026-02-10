"""Wiki Generation Pipeline for MegaBook.

Generates wiki pages from structured notes for different audience levels.
Supports creating spoiler-free (player) and full-detail (DM) versions.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.filesystem import FilesystemService, KnowledgeLayer
from src.pipelines.base import Pipeline, PipelineResult
from src.services.llm_provider import LLMProvider
from src.services.cost_tracking import CostTrackingService


@dataclass
class WikiGenerationItem:
    """Item to generate wiki page for."""
    note_path: str
    content: str
    audience_level: str  # "dm" or "player"


@dataclass
class WikiPage:
    """Generated wiki page."""
    source_note: str
    wiki_path: str
    content: str
    audience_level: str
    generated_at: str


@dataclass
class WikiGenerationResult:
    """Result of wiki generation."""
    generated_pages: List[str]
    audience_levels: List[str]
    generation_timestamp: str


class WikiGenerationPipeline(Pipeline[WikiGenerationResult]):
    """Pipeline for generating wiki pages from notes.
    
    Creates derived wiki pages suitable for different audiences:
    - DM level: Full detail, all spoilers
    - Player level: Spoiler-free, public knowledge only
    """
    
    def __init__(
        self,
        pipeline_id: str,
        storage_path: Path,
        filesystem: FilesystemService,
        llm_provider: LLMProvider,
        cost_tracking: Optional[CostTrackingService] = None,
    ) -> None:
        """Initialize the wiki generation pipeline.
        
        Args:
            pipeline_id: Unique identifier
            storage_path: Path for state storage
            filesystem: Filesystem service instance
            llm_provider: LLM provider for generation
            cost_tracking: Optional cost tracking service
        """
        super().__init__(pipeline_id, storage_path, cost_tracking)
        self.filesystem = filesystem
        self.llm_provider = llm_provider
    
    async def prepare(
        self,
        note_paths: Optional[List[str]] = None,
        audience_levels: List[str] = ["dm"],
        **kwargs: Any
    ) -> None:
        """Prepare items for wiki generation.
        
        Args:
            note_paths: Specific notes to process (None = all notes)
            audience_levels: List of audience levels to generate for ("dm", "player")
        """
        self._current_items = []
        
        if note_paths:
            notes_to_process = []
            for path in note_paths:
                content = self.filesystem.read_file(path)
                notes_to_process.append({"path": path, "content": content})
        else:
            # Get all notes
            all_notes = self.filesystem.list_files(layer=KnowledgeLayer.NOTES)
            notes_to_process = []
            for note_info in all_notes:
                content = self.filesystem.read_file(note_info.relative_path)
                notes_to_process.append({
                    "path": note_info.relative_path,
                    "content": content,
                })
        
        # Create items for each note and audience level
        for note in notes_to_process:
            for level in audience_levels:
                self._current_items.append(WikiGenerationItem(
                    note_path=note["path"],
                    content=note["content"],
                    audience_level=level,
                ))
    
    async def process_item(self, item: WikiGenerationItem) -> Dict[str, Any]:
        """Generate wiki page for a note.
        
        Args:
            item: Wiki generation item
            
        Returns:
            Generation result
        """
        # Generate wiki content
        wiki_content = await self._generate_wiki_content(item)
        
        # Determine output path
        note_relative = item.note_path.replace("notes/", "")
        wiki_path = f"wiki/{item.audience_level}/{note_relative}"
        
        # Create wiki page
        wiki_page = WikiPage(
            source_note=item.note_path,
            wiki_path=wiki_path,
            content=wiki_content,
            audience_level=item.audience_level,
            generated_at=datetime.now().isoformat(),
        )
        
        # Write to filesystem
        self.filesystem.write_file(
            wiki_page.wiki_path,
            wiki_page.content,
            layer=KnowledgeLayer.WIKI,
        )
        
        return {
            "success": True,
            "source": item.note_path,
            "wiki_path": wiki_page.wiki_path,
            "audience_level": item.audience_level,
        }
    
    async def _generate_wiki_content(self, item: WikiGenerationItem) -> str:
        """Generate wiki page content using LLM.
        
        Args:
            item: Wiki generation item
            
        Returns:
            Generated wiki content
        """
        if item.audience_level == "player":
            system_prompt = """You are generating a player-facing wiki page.

Transform the source note into a spoiler-free version suitable for players.

Rules:
- Remove all DM-only information (secrets, hidden motives, future plans)
- Keep only what players would reasonably know
- Write in an in-world encyclopedia style
- Include public history, known facts, and visible characteristics
- Use "[[Wiki Links]]" for cross-references
- Format as clean Markdown

Output should be a well-structured wiki article."""
        else:  # dm level
            system_prompt = """You are generating a DM-facing wiki page.

Transform the source note into a comprehensive reference page.

Rules:
- Preserve all information from the source
- Organize with clear sections (Overview, Details, Secrets, Plot Hooks)
- Add cross-references using "[[Wiki Links]]" format
- Include DM notes in callout blocks (> **DM Note:** ...)
- Format as clean Markdown with proper headers

Output should be a comprehensive reference for DM use."""
        
        prompt = f"Source note:\n\n{item.content}\n\nGenerate the {item.audience_level}-level wiki page."
        
        response = await self.llm_provider.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.4,
        )
        
        # Record cost
        if self.cost_tracking:
            cost_per_1k = self.llm_provider.get_cost_per_1k_tokens()
            self.cost_tracking.record_usage(
                response.usage,
                self.llm_provider.model,
                cost_per_1k,
                operation=f"generate_wiki_{item.audience_level}",
            )
        
        return response.content
    
    def _get_result_data(self) -> WikiGenerationResult:
        """Get wiki generation results."""
        generated = []
        audience_levels = set()
        
        for result in self._processed_items:
            if isinstance(result, dict) and result.get("success"):
                generated.append(result["wiki_path"])
                audience_levels.add(result["audience_level"])
        
        return WikiGenerationResult(
            generated_pages=generated,
            audience_levels=list(audience_levels),
            generation_timestamp=datetime.now().isoformat(),
        )