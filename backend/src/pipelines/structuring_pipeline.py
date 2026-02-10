"""Structuring Pipeline for MegaBook.

Transforms raw prompts (session notes, imports) into structured notes.
Uses LLM to analyze content and create/update canonical notes in notes/.
"""
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.filesystem import FilesystemService, KnowledgeLayer
from src.pipelines.base import Pipeline, PipelineResult
from src.services.llm_provider import LLMProvider
from src.services.cost_tracking import CostTrackingService


@dataclass
class ProcessingItem:
    """Item to be processed into structured notes."""
    prompt_path: str  # Relative path in prompts/
    content: str
    session_id: Optional[str] = None
    is_session_note: bool = False  # True if from session input


@dataclass
class ProposedChange:
    """A proposed change to the notes."""
    operation: str  # "create", "update", "merge"
    target_path: str  # Relative path in notes/
    current_content: Optional[str]  # None if new file
    proposed_content: str
    reason: str
    confidence: float


@dataclass
class StructuringResult:
    """Result of structuring operation."""
    processed_prompts: List[str]
    created_notes: List[str]
    updated_notes: List[str]
    merged_notes: List[str]
    changes: List[Dict]
    processing_timestamp: str


class StructuringPipeline(Pipeline[StructuringResult]):
    """Pipeline for transforming prompts into structured notes.
    
    Analyzes raw content (session notes, imported files) and:
    1. Identifies entities, topics, and relationships
    2. Proposes changes to notes/ structure
    3. Creates/updates canonical notes
    """
    
    def __init__(
        self,
        pipeline_id: str,
        storage_path: Path,
        filesystem: FilesystemService,
        llm_provider: LLMProvider,
        cost_tracking: Optional[CostTrackingService] = None,
    ) -> None:
        """Initialize the structuring pipeline.
        
        Args:
            pipeline_id: Unique identifier
            storage_path: Path for state storage
            filesystem: Filesystem service instance
            llm_provider: LLM provider for analysis
            cost_tracking: Optional cost tracking service
        """
        super().__init__(pipeline_id, storage_path, cost_tracking)
        self.filesystem = filesystem
        self.llm_provider = llm_provider
        self._processing_items: List[ProcessingItem] = []
        self._proposed_changes: List[ProposedChange] = []
    
    async def prepare(
        self,
        prompt_paths: Optional[List[str]] = None,
        session_content: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Prepare items for processing.
        
        Args:
            prompt_paths: Specific prompt files to process (or None for all unprocessed)
            session_content: Raw session notes content (alternative to prompt_paths)
            session_id: Identifier for this session
        """
        self._processing_items = []
        
        if session_content:
            # Process raw session notes
            self._processing_items.append(ProcessingItem(
                prompt_path=f"prompts/sessions/{session_id or datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                content=session_content,
                session_id=session_id,
                is_session_note=True,
            ))
        elif prompt_paths:
            # Process specific prompts
            for path in prompt_paths:
                content = self.filesystem.read_file(path)
                self._processing_items.append(ProcessingItem(
                    prompt_path=path,
                    content=content,
                ))
        else:
            # Process all prompts in prompts/
            files = self.filesystem.list_files(layer=KnowledgeLayer.PROMPTS)
            for file_info in files:
                content = self.filesystem.read_file(file_info.relative_path)
                self._processing_items.append(ProcessingItem(
                    prompt_path=file_info.relative_path,
                    content=content,
                ))
        
        self._current_items = self._processing_items
    
    async def process_item(self, item: ProcessingItem) -> Dict[str, Any]:
        """Process a single prompt into structured notes.
        
        Args:
            item: Processing item
            
        Returns:
            Processing result with proposed changes
        """
        # Step 1: Analyze content and extract entities/topics
        analysis = await self._analyze_content(item)
        
        # Step 2: Find related existing notes
        related_notes = await self._find_related_notes(analysis)
        
        # Step 3: Generate proposed changes
        changes = await self._generate_changes(item, analysis, related_notes)
        
        return {
            "prompt_path": item.prompt_path,
            "analysis": analysis,
            "related_notes": related_notes,
            "changes": [asdict(c) for c in changes],
        }
    
    async def _analyze_content(self, item: ProcessingItem) -> Dict[str, Any]:
        """Use LLM to analyze content structure."""
        system_prompt = """You are a knowledge extraction system. Analyze the provided content and extract:
1. Named entities (characters, locations, items, organizations)
2. Topics and themes
3. Relationships between entities
4. Key facts and events

Respond with a JSON object containing:
{
    "entities": [{"name": str, "type": str, "description": str}],
    "topics": [str],
    "relationships": [{"from": str, "to": str, "type": str}],
    "key_facts": [str],
    "suggested_note_files": [{"title": str, "category": str, "reason": str}]
}"""
        
        response = await self.llm_provider.generate_structured_output(
            prompt=item.content,
            output_schema={
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "description": {"type": "string"},
                            },
                        },
                    },
                    "topics": {"type": "array", "items": {"type": "string"}},
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "string"},
                                "to": {"type": "string"},
                                "type": {"type": "string"},
                            },
                        },
                    },
                    "key_facts": {"type": "array", "items": {"type": "string"}},
                    "suggested_note_files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "category": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                        },
                    },
                },
            },
            system_prompt=system_prompt,
        )
        
        # Record cost
        if self.cost_tracking:
            cost_per_1k = self.llm_provider.get_cost_per_1k_tokens()
            self.cost_tracking.record_usage(
                response.usage,
                self.llm_provider.model,
                cost_per_1k,
                operation="content_analysis",
            )
        
        return response.data
    
    async def _find_related_notes(
        self,
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find existing notes related to the analysis."""
        # Get all existing notes
        existing_notes = self.filesystem.list_files(layer=KnowledgeLayer.NOTES)
        
        if not existing_notes:
            return []
        
        # Build a simple lookup of note titles and paths
        note_lookup = {}
        for note in existing_notes:
            title = Path(note.relative_path).stem
            note_lookup[title.lower()] = {
                "path": note.relative_path,
                "title": title,
            }
        
        # Check for matches with extracted entities
        related = []
        for entity in analysis.get("entities", []):
            entity_name = entity["name"].lower()
            # Exact match
            if entity_name in note_lookup:
                related.append(note_lookup[entity_name])
            else:
                # Partial match
                for title, info in note_lookup.items():
                    if entity_name in title or title in entity_name:
                        related.append(info)
        
        # Remove duplicates
        seen = set()
        unique_related = []
        for r in related:
            if r["path"] not in seen:
                seen.add(r["path"])
                unique_related.append(r)
        
        return unique_related
    
    async def _generate_changes(
        self,
        item: ProcessingItem,
        analysis: Dict[str, Any],
        related_notes: List[Dict[str, Any]],
    ) -> List[ProposedChange]:
        """Generate proposed changes based on analysis."""
        changes = []
        
        # For each suggested note file
        for suggestion in analysis.get("suggested_note_files", []):
            title = suggestion["title"]
            category = suggestion["category"]
            
            # Determine target path
            safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
            target_path = f"notes/{category.lower()}/{safe_title}.md"
            
            # Check if note exists
            current_content = None
            if self.filesystem.file_exists(target_path):
                current_content = self.filesystem.read_file(target_path)
            
            # Generate content
            proposed_content = await self._generate_note_content(
                item.content,
                analysis,
                title,
                current_content,
            )
            
            # Determine operation
            if current_content:
                operation = "merge"
            else:
                operation = "create"
            
            changes.append(ProposedChange(
                operation=operation,
                target_path=target_path,
                current_content=current_content,
                proposed_content=proposed_content,
                reason=suggestion["reason"],
                confidence=0.8,  # Could be calculated from LLM response
            ))
        
        return changes
    
    async def _generate_note_content(
        self,
        source_content: str,
        analysis: Dict[str, Any],
        title: str,
        existing_content: Optional[str],
    ) -> str:
        """Generate note content using LLM."""
        if existing_content:
            system_prompt = f"""You are updating an existing knowledge base note.

EXISTING NOTE:
{existing_content}

NEW INFORMATION:
{source_content}

ANALYSIS:
{json.dumps(analysis, indent=2)}

Update the existing note by integrating the new information. Preserve the existing structure where appropriate, but add new sections for any new topics. Use proper Markdown formatting with headers, lists, and links."""
        else:
            system_prompt = f"""You are creating a new knowledge base note.

SOURCE CONTENT:
{source_content}

ANALYSIS:
{json.dumps(analysis, indent=2)}

Create a well-structured Markdown note for: {title}

Use proper Markdown with:
- Clear headers (# ## ###)
- Bullet points for lists
- Links to related topics in [[wiki-link]] format
- Frontmatter with metadata

Format:
```yaml
---
title: {title}
created: {datetime.now().strftime('%Y-%m-%d')}
source: session_notes
tags: []
---

# {title}

[content here]
```"""
        
        response = await self.llm_provider.generate_text(
            prompt=f"Generate or update the note for '{title}'",
            system_prompt=system_prompt,
            temperature=0.3,
        )
        
        # Record cost
        if self.cost_tracking:
            cost_per_1k = self.llm_provider.get_cost_per_1k_tokens()
            self.cost_tracking.record_usage(
                response.usage,
                self.llm_provider.model,
                cost_per_1k,
                operation="generate_note",
            )
        
        return response.content
    
    def get_proposed_changes(self) -> List[ProposedChange]:
        """Get all proposed changes from processed items."""
        changes = []
        for result in self._processed_items:
            if isinstance(result, dict) and "changes" in result:
                for change_dict in result["changes"]:
                    changes.append(ProposedChange(**change_dict))
        return changes
    
    async def apply_changes(self, change_indices: Optional[List[int]] = None) -> Dict[str, Any]:
        """Apply proposed changes to notes/.
        
        Args:
            change_indices: Optional list of indices to apply (None = all)
            
        Returns:
            Results of application
        """
        changes = self.get_proposed_changes()
        
        if change_indices:
            changes = [changes[i] for i in change_indices if i < len(changes)]
        
        applied = []
        failed = []
        
        for change in changes:
            try:
                self.filesystem.write_file(
                    change.target_path,
                    change.proposed_content,
                    layer=KnowledgeLayer.NOTES,
                )
                applied.append(change.target_path)
            except Exception as e:
                failed.append({"path": change.target_path, "error": str(e)})
        
        return {
            "applied": applied,
            "failed": failed,
            "total": len(changes),
        }
    
    def _get_result_data(self) -> StructuringResult:
        """Get structuring results."""
        changes = self.get_proposed_changes()
        
        created = []
        updated = []
        merged = []
        
        for change in changes:
            if change.operation == "create":
                created.append(change.target_path)
            elif change.operation == "update":
                updated.append(change.target_path)
            elif change.operation == "merge":
                merged.append(change.target_path)
        
        return StructuringResult(
            processed_prompts=[item.prompt_path for item in self._processing_items],
            created_notes=created,
            updated_notes=updated,
            merged_notes=merged,
            changes=[asdict(c) for c in changes],
            processing_timestamp=datetime.now().isoformat(),
        )