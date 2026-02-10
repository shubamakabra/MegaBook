"""Entity Extraction Pipeline for MegaBook.

Analyzes session notes and extracts entities (characters, locations, items)
with their associated quotes and context. Creates wiki pages with
bidirectional links between notes and wiki.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import json
import re
import hashlib

from src.core.filesystem import FilesystemService
from src.core.alias_manager import AliasManager
from src.pipelines.base import Pipeline, PipelineResult
from src.services.llm_provider import LLMProvider
from src.services.cost_tracking import CostTrackingService


@dataclass
class ExtractedEntity:
    """An entity extracted from notes."""
    name: str
    type: str  # "character", "location", "item", "event", "faction"
    quotes: List[str]  # Direct quotes from the source
    context: str  # LLM-generated summary/context
    confidence: float  # 0-1 confidence score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "quotes": self.quotes,
            "context": self.context,
            "confidence": self.confidence,
        }


@dataclass
class EntityExtractionResult:
    """Result of entity extraction."""
    source_note: str
    extracted_entities: List[ExtractedEntity]
    processing_timestamp: str
    processing_id: str
    content_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_note": self.source_note,
            "extracted_entities": [e.to_dict() for e in self.extracted_entities],
            "processing_timestamp": self.processing_timestamp,
            "processing_id": self.processing_id,
            "content_hash": self.content_hash,
        }


class EntityExtractionPipeline(Pipeline[EntityExtractionResult]):
    """Pipeline for extracting entities from session notes.
    
    Workflow:
    1. Read session note
    2. Use LLM to identify and extract entities with quotes
    3. Update or create wiki pages for each entity
    4. Create/update .raw.md files with all quotes
    5. Update metadata tracking
    """
    
    def __init__(
        self,
        pipeline_id: str,
        storage_path: Path,
        filesystem: FilesystemService,
        llm_provider: LLMProvider,
        cost_tracking: Optional[CostTrackingService] = None,
    ) -> None:
        super().__init__(pipeline_id, storage_path, cost_tracking)
        self.filesystem = filesystem
        self.llm_provider = llm_provider
        self._source_note: Optional[str] = None
        self._note_content: Optional[str] = None
        self._content_hash: Optional[str] = None
        self._extracted_entities: List[ExtractedEntity] = []
    
    async def prepare(self, **kwargs: Any) -> None:
        """Prepare the note for processing.
        
        Args:
            note_path: Path to the note file (relative to notes/)
        """
        note_path = kwargs.get('note_path')
        if not note_path:
            raise ValueError("note_path is required")
        self._source_note = note_path
        self._note_content = self.filesystem.read_file(note_path)
        # Calculate content hash for sync tracking
        if self._note_content:
            self._content_hash = hashlib.sha256(
                self._note_content.encode('utf-8')
            ).hexdigest()
        else:
            self._content_hash = ""
        self._extracted_entities = []
    
    async def process_item(self, item: Any) -> Any:
        """Process a single item (not used - we process the whole note at once)."""
        pass
    
    async def process(self) -> PipelineResult[EntityExtractionResult]:
        """Process the note and extract entities."""
        try:
            # Step 1: Extract entities using LLM
            self._extracted_entities = await self._extract_entities()
            
            # Step 2: Update wiki pages
            await self._update_wiki_pages()
            
            # Step 3: Update raw files
            await self._update_raw_files()
            
            # Step 4: Update metadata
            await self._update_metadata()
            
            if self._source_note is None or self._content_hash is None:
                return PipelineResult(success=False, error="Source note not prepared")
            
            result = EntityExtractionResult(
                source_note=self._source_note,
                extracted_entities=self._extracted_entities,
                processing_timestamp=datetime.now().isoformat(),
                processing_id=self.pipeline_id,
                content_hash=self._content_hash,
            )
            
            return PipelineResult(success=True, data=result)
            
        except Exception as e:
            return PipelineResult(success=False, error=str(e))
    
    async def _extract_entities(self) -> List[ExtractedEntity]:
        """Use LLM to extract entities from the note."""
        
        system_prompt = """You are an expert Dungeon Master assistant specializing in analyzing campaign notes.

Your task is to analyze session notes and extract all entities mentioned (characters, locations, items, events, factions).

For each entity found, provide:
1. Name (as mentioned in the text)
2. Type: character, location, item, event, or faction
3. Direct quotes from the text that mention this entity (preserve exact wording)
4. Brief context/summary about what was revealed

Return ONLY a JSON object in this exact format:
{
  "entities": [
    {
      "name": "Character Name",
      "type": "character",
      "quotes": ["Exact quote 1 from text", "Exact quote 2 from text"],
      "context": "Brief summary of what was revealed about this character",
      "confidence": 0.95
    }
  ]
}

Guidelines:
- Extract ALL mentions, even brief ones
- Preserve exact quotes with proper punctuation
- Include page numbers or timestamps if present in source
- Multiple quotes per entity are encouraged
- Confidence should reflect how certain you are (0.0 to 1.0)
- Be thorough - don't miss any entity mentioned"""

        user_prompt = f"""Analyze these session notes and extract all entities:

--- NOTES BEGIN ---
{self._note_content}
--- NOTES END ---

Extract all entities with their direct quotes from the text."""

        response = await self.llm_provider.generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )
        response_text = response.content
        
        # Parse JSON response
        try:
            data = json.loads(response_text)
            entities = []
            for entity_data in data.get("entities", []):
                entities.append(ExtractedEntity(
                    name=entity_data["name"],
                    type=entity_data["type"],
                    quotes=entity_data.get("quotes", []),
                    context=entity_data.get("context", ""),
                    confidence=entity_data.get("confidence", 0.8),
                ))
            return entities
        except json.JSONDecodeError:
            # Fallback: try to extract from markdown code block
            match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                entities = []
                for entity_data in data.get("entities", []):
                    entities.append(ExtractedEntity(
                        name=entity_data["name"],
                        type=entity_data["type"],
                        quotes=entity_data.get("quotes", []),
                        context=entity_data.get("context", ""),
                        confidence=entity_data.get("confidence", 0.8),
                    ))
                return entities
            raise ValueError(f"Failed to parse LLM response as JSON: {response_text[:200]}")
    
    async def _update_wiki_pages(self) -> None:
        """Update wiki pages for extracted entities."""
        for entity in self._extracted_entities:
            await self._update_wiki_page(entity)
    
    async def _update_wiki_page(self, entity: ExtractedEntity) -> None:
        """Update or create a wiki page for an entity."""
        if self._source_note is None:
            raise ValueError("Source note not prepared")
        
        # Determine wiki path based on entity type
        type_folder = {
            "character": "NPCs",
            "location": "Locations",
            "item": "Items",
            "event": "Events",
            "faction": "Factions",
        }.get(entity.type, "Misc")
        
        # Sanitize name for filename
        safe_name = self._sanitize_filename(entity.name)
        wiki_path = f"wiki/dm/{type_folder}/{safe_name}.md"
        raw_path = f"wiki/dm/{type_folder}/{safe_name}.raw.md"
        
        # Read existing wiki or create new
        try:
            existing_content = self.filesystem.read_file(wiki_path)
        except FileNotFoundError:
            existing_content = None
        
        # Format new auto-generated section
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        source_link = f"[[{self._source_note}]]"
        
        auto_section = f"""<!-- AUTO-GENERATED-START: source={self._source_note} timestamp={timestamp} -->
## Update: {timestamp}
**Source:** {source_link}

{entity.context}

### Direct Quotes:
"""
        for quote in entity.quotes:
            auto_section += f"> {quote}\n>\n"
        
        auto_section += f"""<!-- AUTO-GENERATED-END -->

---

"""
        
        # Combine with existing or create new
        if self._source_note is None:
            raise ValueError("Source note not prepared")
        
        if existing_content:
            # Check if there's already an auto-section from this source
            # If so, replace it; otherwise append
            new_content = self._merge_wiki_content(existing_content, auto_section, self._source_note)
        else:
            # Create new wiki page
            new_content = f"""# {entity.name}

**Type:** {entity.type.capitalize()}  
**Last Updated:** {timestamp}  
**Raw Data:** [[{raw_path}]]

<!-- DM-MANUAL-CONTENT -->

<!-- DM-MANUAL-CONTENT-END -->

{auto_section}
"""
        
        # Write wiki page
        self.filesystem.write_file(wiki_path, new_content)
    
    async def _update_raw_files(self) -> None:
        """Update the .raw.md files with all quotes."""
        for entity in self._extracted_entities:
            await self._update_raw_file(entity)
    
    async def _update_raw_file(self, entity: ExtractedEntity) -> None:
        """Update the .raw.md file with all quotes."""
        if self._source_note is None:
            raise ValueError("Source note not prepared")
        
        type_folder = {
            "character": "NPCs",
            "location": "Locations",
            "item": "Items",
            "event": "Events",
            "faction": "Factions",
        }.get(entity.type, "Misc")
        
        safe_name = self._sanitize_filename(entity.name)
        raw_path = f"wiki/dm/{type_folder}/{safe_name}.raw.md"
        
        # Read existing raw file or create new
        try:
            existing_content = self.filesystem.read_file(raw_path)
        except FileNotFoundError:
            existing_content = None
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        source_link = f"[[{self._source_note}]]"
        
        # Format new raw quotes section
        raw_section = f"""## {timestamp} - {source_link}

"""
        for i, quote in enumerate(entity.quotes, 1):
            raw_section += f"{i}. {quote}\n\n"
        
        raw_section += "---\n\n"
        
        if existing_content:
            new_content = existing_content + "\n" + raw_section
        else:
            new_content = f"""# {entity.name} - Raw Data

**Type:** {entity.type.capitalize()}  
**Wiki Page:** [[wiki/dm/{type_folder}/{safe_name}.md]]

This file contains all raw quotes and mentions from session notes.

{raw_section}
"""
        
        self.filesystem.write_file(raw_path, new_content)
    
    async def _update_metadata(self) -> None:
        """Update metadata tracking for the processed file."""
        if self._source_note is None or self._content_hash is None:
            raise ValueError("Source note not prepared")
        
        metadata_path = "metadata/sync_index.json"
        
        # Read existing metadata
        try:
            metadata_content = self.filesystem.read_file(metadata_path)
            metadata = json.loads(metadata_content)
        except (FileNotFoundError, json.JSONDecodeError):
            metadata = {"files": {}}
        
        # Update metadata for this file
        metadata["files"][self._source_note] = {
            "last_processed": datetime.now().isoformat(),
            "processing_id": self.pipeline_id,
            "content_hash": self._content_hash,
            "entities_extracted": [e.name for e in self._extracted_entities],
            "is_synced": True,
            "entity_count": len(self._extracted_entities),
        }
        
        # Write updated metadata
        self.filesystem.write_file(metadata_path, json.dumps(metadata, indent=2))
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize entity name for use as filename."""
        # Remove or replace characters that are invalid in filenames
        safe = re.sub(r'[\\/*?:"<>|]', '', name)
        # Replace spaces with underscores
        safe = safe.replace(' ', '_')
        # Limit length
        return safe[:50]
    
    def _merge_wiki_content(self, existing: str, new_section: str, source_note: str) -> str:
        """Merge new auto-section with existing wiki content.
        
        If there's already an auto-section from this source, replace it.
        Otherwise, append after the last auto-section or at the end.
        """
        # Check if there's already an auto-section from this source
        source_pattern = f'<!-- AUTO-GENERATED-START: source={source_note}'
        
        if source_pattern in existing:
            # Replace existing section from this source
            pattern = f'<!-- AUTO-GENERATED-START: source={re.escape(source_note)}.*?<!-- AUTO-GENERATED-END -->\s*\n*---\s*\n*'
            return re.sub(pattern, new_section, existing, flags=re.DOTALL)
        else:
            # Find the last AUTO-GENERATED-END and insert after it
            # Or insert after DM-MANUAL-CONTENT-END if no auto sections
            
            if '<!-- AUTO-GENERATED-END -->' in existing:
                # Insert after the last auto-section
                parts = existing.rsplit('<!-- AUTO-GENERATED-END -->', 1)
                if len(parts) == 2:
                    return parts[0] + '<!-- AUTO-GENERATED-END -->\n\n' + new_section + parts[1]
            elif '<!-- DM-MANUAL-CONTENT-END -->' in existing:
                # Insert after manual content
                parts = existing.split('<!-- DM-MANUAL-CONTENT-END -->', 1)
                if len(parts) == 2:
                    return parts[0] + '<!-- DM-MANUAL-CONTENT-END -->\n\n' + new_section + parts[1]
            
            # Default: append to end
            return existing + '\n\n' + new_section
