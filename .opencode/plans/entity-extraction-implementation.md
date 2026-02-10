# Smart Note Processing - Implementation Plan

## Overview
This implementation plan details the architecture, components, and phased approach for building the Smart Note Processing & Entity Extraction system. The system automatically processes session notes, extracts named entities (characters, locations, items, organizations), and maintains synchronized wiki pages with bidirectional linking.

---

## Architecture Overview

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                             │
├─────────────────────────────────────────────────────────────────┤
│ Notes Tab │ Wiki Tab │ Process Modal │ Sync Status             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ API Calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                            │
├─────────────────────────────────────────────────────────────────┤
│  FileSystem Routes │ Pipeline Routes │ Entity Routes             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│   Pipeline System        │    │   Entity Resolution System   │
│                          │    │                              │
│ • EntityExtractionPipeline│    │ • AliasManager               │
│ • QuoteExtractor         │    │ • DisambiguationEngine       │
│ • WikiSyncEngine         │    │ • RelationshipTracker        │
└──────────────────────────┘    └──────────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│ Session Notes (.md) │ Wiki Pages (.md) │ Metadata (.json)      │
└─────────────────────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Non-destructive Processing**: Manual edits to wiki pages are preserved within designated sections
2. **Idempotent Operations**: Re-processing the same note produces the same results (deterministic)
3. **Eventual Consistency**: Async processing with clear status tracking
4. **Extensible Entity Types**: Easy to add new entity categories beyond the initial set

---

## Backend Components

### 1. EntityExtractionPipeline

**Location**: `backend/pipelines/entity_extraction.py`

#### Class Structure

```python
class EntityExtractionPipeline(BasePipeline):
    """
    Pipeline for extracting entities from session notes and 
    synchronizing them with wiki pages.
    """
    
    def __init__(self, config: PipelineConfig):
        super().__init__(config)
        self.alias_manager = AliasManager()
        self.quote_extractor = QuoteExtractor()
        self.wiki_sync = WikiSyncEngine()
        self.deduplicator = QuoteDeduplicator()
    
    async def prepare(self, session_note_path: str) -> PreparationResult:
        """
        Validate input and load necessary resources.
        
        Returns:
            PreparationResult with:
            - validation_status: bool
            - estimated_entities: int
            - estimated_cost: float
            - existing_entities: List[str]  # Already in wiki
            - new_entities: List[str]       # Not yet in wiki
        """
        pass
    
    async def process(self, session_note_path: str) -> ProcessingResult:
        """
        Main processing method - orchestrates the entire pipeline.
        
        Steps:
        1. Load and parse session note
        2. Extract entities using LLM
        3. Resolve aliases and disambiguate
        4. Extract quotes with attribution
        5. Deduplicate quotes against existing wiki
        6. Update/create wiki pages
        7. Update sync index
        
        Returns:
            ProcessingResult with:
            - success: bool
            - entities_processed: int
            - wiki_pages_created: int
            - wiki_pages_updated: int
            - quotes_added: int
            - quotes_deprecated: int
            - errors: List[str]
        """
        pass
    
    async def _extract_entities(self, content: str) -> List[Entity]:
        """
        Use LLM to identify entities in note content.
        
        Returns list of Entity objects with:
        - name: str (canonical name)
        - type: EntityType (CHARACTER, LOCATION, ITEM, ORGANIZATION)
        - mentions: List[Mention]  # All occurrences with context
        - confidence: float
        """
        pass
    
    async def _update_wiki_pages(self, entities: List[Entity], 
                                  source_note: str) -> WikiUpdateResult:
        """
        Create new wiki pages or update existing ones.
        
        Handles:
        - Auto-generated section markers
        - Preserving manual content
        - Merging new quotes
        - Deprecating removed content
        """
        pass
    
    async def _resolve_aliases(self, entities: List[Entity]) -> List[Entity]:
        """
        Normalize entity names using alias system.
        
        Example:
        "Ion" → "Ion the Brave"
        "Prince Ion" → "Ion the Brave"
        """
        pass
```

#### Integration with Pipeline Base Class

The `EntityExtractionPipeline` extends the existing `BasePipeline` class:

```python
# backend/pipelines/base.py
class BasePipeline(ABC):
    @abstractmethod
    async def prepare(self, *args, **kwargs) -> PreparationResult:
        pass
    
    @abstractmethod
    async def process(self, *args, **kwargs) -> ProcessingResult:
        pass
```

**Key Integration Points**:
- Uses existing `PipelineConfig` for LLM settings
- Leverages `ProgressTracker` for long-running operations
- Integrates with existing error handling middleware

---

### 2. Entity Alias System

**Location**: `backend/entities/alias_manager.py`

#### Problem Statement
Characters may be referred to by multiple names:
- Full name: "Ion the Brave"
- Short name: "Ion"
- Title: "Prince Ion"
- Nickname: "The Prince"

All should resolve to the same canonical entity.

#### Implementation

```python
class AliasManager:
    """
    Manages entity aliases and canonical names.
    """
    
    ALIASES_FILE = "metadata/aliases.json"
    
    def __init__(self):
        self._aliases: Dict[str, str] = {}  # alias -> canonical
        self._canonical_entities: Dict[str, EntityAliases] = {}
        self._load_aliases()
    
    def resolve(self, name: str) -> Optional[str]:
        """
        Resolve an alias to canonical name.
        Returns None if not found.
        """
        name_normalized = self._normalize(name)
        return self._aliases.get(name_normalized)
    
    def add_alias(self, canonical: str, alias: str, 
                  confidence: float = 1.0) -> bool:
        """
        Add a new alias for an entity.
        Returns False if conflict detected.
        """
        pass
    
    def suggest_aliases(self, entity_name: str, 
                        context: str) -> List[str]:
        """
        Use LLM to suggest potential aliases from context.
        """
        pass
    
    def _normalize(self, name: str) -> str:
        """Normalize for comparison (lowercase, remove articles)."""
        return name.lower().strip().replace("the ", "")
```

#### Alias Storage Schema

**File**: `metadata/aliases.json`

```json
{
  "version": "1.0",
  "last_updated": "2026-02-09T14:32:00Z",
  "entities": {
    "ion-the-brave": {
      "canonical": "Ion the Brave",
      "aliases": [
        {"alias": "Ion", "type": "short", "confidence": 1.0},
        {"alias": "Prince Ion", "type": "title", "confidence": 0.95},
        {"alias": "The Prince", "type": "nickname", "confidence": 0.8}
      ],
      "disambiguation": {
        "type": "character",
        "context_hints": ["royalty", "half-elf", "sorcerer"]
      }
    }
  },
  "conflicts": [
    {
      "alias": "The Prince",
      "entities": ["ion-the-brave", "victor-montague"],
      "resolution_strategy": "context_based"
    }
  ]
}
```

#### Disambiguation Logic

```python
class DisambiguationEngine:
    """
    Resolves ambiguous aliases using context.
    """
    
    def disambiguate(self, alias: str, context: str, 
                     candidates: List[str]) -> str:
        """
        Determine which entity an ambiguous alias refers to.
        
        Strategies:
        1. Context keyword matching (titles, descriptions)
        2. Co-occurrence with other known entities
        3. recency (most recently mentioned)
        4. Confidence scores from alias system
        """
        pass
```

---

### 3. Quote Deduplication Strategy

#### The Problem

When re-processing notes, we need to identify:
- New quotes (add to wiki)
- Existing quotes (preserve)
- Removed quotes (deprecate, don't delete)
- Modified quotes (treat as new, deprecate old)

#### Challenge: Similar but Not Identical Quotes

Same quote may appear slightly differently:
- "I'll protect you" vs "I will protect you"
- "He said, 'Run!'" vs "Run!" (attribution difference)
- Typos or transcription variations

#### Proposed Solutions

**Option A: Exact Match Only**
- Store hash of exact text
- Pros: Simple, fast, no false positives
- Cons: Misses near-duplicates, creates duplicates in wiki

**Option B: Normalized Match**
- Normalize: lowercase, remove punctuation, expand contractions
- Hash normalized version
- Pros: Catches simple variations
- Cons: May miss context differences, false positives possible

**Option C: Semantic Similarity (Recommended)**
- Use embeddings to compare quote similarity
- Threshold: >0.85 cosine similarity = same quote
- Store quote_id with embedding vector
- Pros: Handles paraphrasing, robust to variations
- Cons: Requires vector DB or embedding calls, more complex

#### Recommended Implementation

```python
class QuoteDeduplicator:
    """
    Multi-tier deduplication strategy.
    """
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.similarity_threshold = 0.85
    
    async def find_duplicate(self, new_quote: Quote, 
                             existing_quotes: List[Quote]) -> Optional[Quote]:
        """
        Three-tier matching:
        1. Exact text match (fast path)
        2. Normalized text match
        3. Semantic similarity (expensive, only if needed)
        """
        # Tier 1: Exact match
        for existing in existing_quotes:
            if existing.text == new_quote.text:
                return existing
        
        # Tier 2: Normalized match
        new_normalized = self._normalize(new_quote.text)
        for existing in existing_quotes:
            if self._normalize(existing.text) == new_normalized:
                return existing
        
        # Tier 3: Semantic similarity (batch for efficiency)
        candidates = self._filter_candidates_by_length(
            existing_quotes, new_quote.text
        )
        
        if candidates:
            new_embedding = await self.embedding_service.embed(new_quote.text)
            for existing in candidates:
                similarity = cosine_similarity(new_embedding, existing.embedding)
                if similarity > self.similarity_threshold:
                    return existing
        
        return None
```

---

### 4. Wiki Page Format with Auto-Generated Markers

#### Page Structure

Each wiki page maintains a strict separation between auto-generated and manual content:

```markdown
# Ion the Brave

<!-- AUTO-GENERATED-START: source=notes/session-5.md timestamp=2026-02-09T14:32:00 hash=abc123 -->
## Basic Information

**Type:** Character
**Race:** Half-Elf
**Class:** Sorcerer

## Quotes

> "I'll protect you, no matter the cost."
> — Session 5
> *Source: [Session 5 Notes](../session-notes/session-5.md)*

> "Magic flows through all living things."
> — Session 5
> *Source: [Session 5 Notes](../session-notes/session-5.md)*

## Relationships

- [[Elara Moonwhisper]] - Mentor
- [[King Aldric]] - Father

## First Appearance

- [Session 5: The Crown of Dawn](../session-notes/session-5.md)

## Auto-Generated Statistics

- **Mentions:** 12 times across 3 sessions
- **Last Updated:** 2026-02-09 14:32 UTC
<!-- AUTO-GENERATED-END -->

---

## Manual Content

### Background

[Ion was born in the year 1247...]

### DM Notes

- Keep Ion mysterious in early sessions
- His true heritage should be a reveal in Session 10

### Custom Sections

[Any content added manually by the DM stays here]
```

#### Marker Specification

```python
class AutoGeneratedSection:
    """
    Handles parsing and updating auto-generated sections.
    """
    
    START_MARKER_PATTERN = r'<!-- AUTO-GENERATED-START: (.*?) -->'
    END_MARKER = '<!-- AUTO-GENERATED-END -->'
    
    @dataclass
    class MarkerAttributes:
        source: str           # Source file path
        timestamp: datetime   # ISO format
        hash: str            # Content hash for change detection
    
    def parse_section(self, content: str) -> Tuple[str, str, str]:
        """
        Split content into: (auto_generated, manual)
        Returns (auto_section, manual_section) or ("", content) if no markers
        """
        pass
    
    def create_section(self, content: str, source: str) -> str:
        """
        Wrap content with auto-generated markers.
        """
        timestamp = datetime.utcnow().isoformat()
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        
        return f'''<!-- AUTO-GENERATED-START: source={source} timestamp={timestamp} hash={content_hash} -->
{content}
<!-- AUTO-GENERATED-END -->'''
```

---

### 5. Deprecation System

#### Purpose
Instead of deleting removed quotes, mark them as deprecated to preserve history.

#### Implementation

```python
class DeprecationManager:
    """
    Handles deprecation of wiki content.
    """
    
    def deprecate_quote(self, wiki_path: str, quote: Quote, 
                        reason: str = "removed_from_source"):
        """
        Move quote to deprecated section with metadata.
        """
        pass
```

#### Deprecated Content Format

```markdown
<!-- AUTO-GENERATED-START: source=notes/session-5.md timestamp=2026-02-09T14:32:00 -->

## Deprecated Content

The following content was previously auto-generated but has been removed from source:

### Deprecated Quotes

> ~~"This quote was removed from Session 5"~~
> — Session 5 (DEPRECATED 2026-02-10: No longer in source notes)

### Deprecation Log

| Date | Source | Reason | Content Preview |
|------|--------|--------|-----------------|
| 2026-02-10 | session-5.md | removed_from_source | "This quote was..." |

<!-- AUTO-GENERATED-END -->
```

#### Visual Indicators

In the frontend wiki view:
- Deprecated quotes shown with strikethrough
- Collapsible "Show Deprecated" section
- Hover tooltip showing deprecation reason and date

---

### 6. Sync Status Tracking

#### Purpose
Track synchronization state between session notes and wiki pages for:
- Determining if re-processing is needed
- Showing sync status in UI
- Incremental updates (future optimization)

#### File Structure

**File**: `metadata/sync_index.json`

```json
{
  "version": "1.0",
  "last_full_sync": "2026-02-09T14:32:00Z",
  "files": {
    "session-notes/session-5.md": {
      "last_processed": "2026-02-09T14:32:00Z",
      "content_hash": "sha256:abc123...",
      "status": "synced",
      "entities_extracted": 5,
      "wiki_pages_affected": [
        "wiki/ion-the-brave.md",
        "wiki/elara-moonwhisper.md"
      ],
      "processing_metadata": {
        "pipeline_version": "1.2.0",
        "llm_model": "gpt-4",
        "processing_time_ms": 4500
      }
    },
    "session-notes/session-6.md": {
      "last_processed": null,
      "content_hash": "sha256:xyz789...",
      "status": "pending",
      "entities_extracted": 0,
      "wiki_pages_affected": []
    }
  },
  "entities": {
    "ion-the-brave": {
      "last_updated": "2026-02-09T14:32:00Z",
      "source_files": ["session-notes/session-5.md"],
      "quote_count": 3,
      "hash": "sha256:def456..."
    }
  }
}
```

#### Hash-Based Change Detection

```python
class SyncIndex:
    """
    Manages sync state and change detection.
    """
    
    def __init__(self, index_path: str = "metadata/sync_index.json"):
        self.index_path = index_path
        self._index = self._load_index()
    
    def compute_hash(self, file_path: str) -> str:
        """
        Compute SHA-256 hash of file content.
        """
        with open(file_path, 'rb') as f:
            return f"sha256:{hashlib.sha256(f.read()).hexdigest()}"
    
    def check_status(self, file_path: str) -> SyncStatus:
        """
        Determine if file needs re-processing.
        
        Returns:
            SyncStatus.SYNCED - File unchanged since last process
            SyncStatus.PENDING - File changed or never processed
            SyncStatus.ERROR - Last processing failed
        """
        current_hash = self.compute_hash(file_path)
        entry = self._index.get("files", {}).get(file_path)
        
        if not entry:
            return SyncStatus.PENDING
        
        if entry.get("status") == "error":
            return SyncStatus.ERROR
        
        if entry.get("content_hash") != current_hash:
            return SyncStatus.PENDING
        
        return SyncStatus.SYNCED
    
    def update_entry(self, file_path: str, result: ProcessingResult):
        """
        Update sync index after successful processing.
        """
        pass
```

#### API Endpoints for Sync Status

```python
# routes/filesystem.py

@router.get("/sync-status")
async def get_sync_status(
    path: Optional[str] = None,
    index: SyncIndex = Depends(get_sync_index)
):
    """
    Get sync status for files.
    
    Query params:
    - path: Specific file or directory (default: all session notes)
    
    Returns:
    {
      "files": [
        {
          "path": "session-notes/session-5.md",
          "status": "synced|pending|error",
          "last_processed": "2026-02-09T14:32:00Z",
          "entity_count": 5
        }
      ],
      "summary": {
        "total": 10,
        "synced": 7,
        "pending": 2,
        "error": 1
      }
    }
    """
    pass

@router.get("/files/{path:path}/sync-status")
async def get_file_sync_status(
    path: str,
    index: SyncIndex = Depends(get_sync_index)
):
    """
    Get detailed sync status for a specific file.
    """
    pass
```

---

## Frontend Components

### 1. Notes Tab Updates

#### Process Button Placement

```typescript
// components/notes/NotesToolbar.tsx

interface NotesToolbarProps {
  currentFile: FileNode;
  syncStatus: SyncStatus;
  onProcess: () => void;
}

export const NotesToolbar: React.FC<NotesToolbarProps> = ({
  currentFile,
  syncStatus,
  onProcess
}) => {
  return (
    <div className="notes-toolbar">
      {/* Existing buttons */}
      <Button variant="secondary">Edit</Button>
      <Button variant="secondary">Preview</Button>
      
      {/* New Process Button */}
      <ProcessButton 
        status={syncStatus}
        onClick={onProcess}
        entityCount={syncStatus.entityCount}
      />
      
      {/* Sync Status Indicator */}
      <SyncStatusIndicator status={syncStatus} />
    </div>
  );
};
```

#### Sync Status Indicator Component

```typescript
// components/notes/SyncStatusIndicator.tsx

export enum SyncStatusColor {
  GREEN = 'green',   // Synced
  YELLOW = 'yellow', // Pending/Unprocessed
  RED = 'red'        // Error
}

export const SyncStatusIndicator: React.FC<{
  status: SyncStatus;
}> = ({ status }) => {
  const config = {
    synced: { color: 'green', icon: CheckCircle, text: 'Synced' },
    pending: { color: 'yellow', icon: Clock, text: 'Pending' },
    error: { color: 'red', icon: AlertCircle, text: 'Error' }
  };
  
  const { color, icon: Icon, text } = config[status.status];
  
  return (
    <Tooltip content={`Last sync: ${status.lastProcessed || 'Never'}`}>
      <Badge color={color}>
        <Icon size={14} />
        {text}
        {status.entityCount > 0 && ` (${status.entityCount} entities)`}
      </Badge>
    </Tooltip>
  );
};
```

---

### 2. Process Confirmation Modal

```typescript
// components/modals/ProcessConfirmationModal.tsx

interface ProcessConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (options: ProcessOptions) => void;
  file: FileNode;
  preparationResult: PreparationResult;
}

export const ProcessConfirmationModal: React.FC<ProcessConfirmationModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  file,
  preparationResult
}) => {
  const [options, setOptions] = useState<ProcessOptions>({
    mode: 'single',  // 'single' or 'batch'
    extractQuotes: true,
    resolveAliases: true,
    dryRun: false
  });
  
  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg">
      <ModalHeader>
        Process Session Note
        <Subtitle>{file.name}</Subtitle>
      </ModalHeader>
      
      <ModalBody>
        {/* Cost Estimation */}
        <Section title="Cost Estimation">
          <CostBreakdown
            estimatedTokens={preparationResult.estimatedTokens}
            estimatedCost={preparationResult.estimatedCost}
            model={preparationResult.model}
          />
        </Section>
        
        {/* Entity Preview */}
        <Section title="Entities to Extract">
          <EntityPreview
            existingEntities={preparationResult.existingEntities}
            newEntities={preparationResult.newEntities}
          />
        </Section>
        
        {/* Processing Options */}
        <Section title="Options">
          <Checkbox
            checked={options.extractQuotes}
            onChange={(v) => setOptions({...options, extractQuotes: v})}
          >
            Extract quotes with attribution
          </Checkbox>
          
          <Checkbox
            checked={options.resolveAliases}
            onChange={(v) => setOptions({...options, resolveAliases: v})}
          >
            Resolve entity aliases
          </Checkbox>
          
          <RadioGroup
            value={options.mode}
            onChange={(v) => setOptions({...options, mode: v})}
          >
            <Radio value="single">Process this file only</Radio>
            <Radio value="batch">Process all pending files ({preparationResult.pendingCount})</Radio>
          </RadioGroup>
        </Section>
      </ModalBody>
      
      <ModalFooter>
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button 
          variant="primary" 
          onClick={() => onConfirm(options)}
          loading={isProcessing}
        >
          Start Processing
        </Button>
      </ModalFooter>
    </Modal>
  );
};
```

---

### 3. Wiki Tab

#### Link Rendering [[Wiki Links]]

```typescript
// components/wiki/WikiLink.tsx

interface WikiLinkProps {
  entityName: string;
  displayText?: string;
}

export const WikiLink: React.FC<WikiLinkProps> = ({ 
  entityName, 
  displayText 
}) => {
  const { exists, path } = useWikiPage(entityName);
  
  return (
    <Link 
      to={`/wiki/${path}`}
      className={cn(
        'wiki-link',
        !exists && 'wiki-link-missing'  // Red link if page doesn't exist
      )}
    >
      {displayText || entityName}
      {!exists && <Tooltip>Page not yet created</Tooltip>}
    </Link>
  );
};

// Markdown renderer integration
const wikiLinkPlugin = () => {
  return (tree: Node) => {
    visit(tree, 'text', (node: TextNode) => {
      const regex = /\[\[([^\]]+)\]\]/g;
      const matches = [...node.value.matchAll(regex)];
      
      if (matches.length > 0) {
        // Replace with WikiLink components
        // Implementation details...
      }
    });
  };
};
```

#### Bidirectional Navigation

```typescript
// components/wiki/BacklinksSection.tsx

export const BacklinksSection: React.FC<{
  entityName: string;
}> = ({ entityName }) => {
  const { backlinks } = useBacklinks(entityName);
  
  if (backlinks.length === 0) return null;
  
  return (
    <div className="backlinks-section">
      <h3>Linked From</h3>
      <ul>
        {backlinks.map(link => (
          <li key={link.source}>
            <WikiLink entityName={link.source} />
            <span className="context">{link.context}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};
```

#### Source Attribution Display

```typescript
// components/wiki/SourceAttribution.tsx

export const SourceAttribution: React.FC<{
  sources: Source[];
}> = ({ sources }) => {
  return (
    <div className="source-attribution">
      <h4>Sources</h4>
      {sources.map(source => (
        <div key={source.path} className="source-item">
          <Icon name="file-text" size={14} />
          <Link to={`/notes/${source.path}`}>
            {source.displayName}
          </Link>
          <Timestamp value={source.timestamp} />
          <Badge variant="secondary">{source.quoteCount} quotes</Badge>
        </div>
      ))}
    </div>
  );
};
```

---

## API Endpoints

### Pipeline Endpoints

```python
# routes/pipelines.py

@router.post("/extraction/start")
async def start_extraction(
    request: ExtractionRequest,
    background_tasks: BackgroundTasks,
    pipeline: EntityExtractionPipeline = Depends(get_extraction_pipeline)
) -> ExtractionResponse:
    """
    Start entity extraction pipeline.
    
    Request:
    {
      "files": ["session-notes/session-5.md"],
      "options": {
        "extractQuotes": true,
        "resolveAliases": true,
        "dryRun": false
      }
    }
    
    Response:
    {
      "jobId": "uuid",
      "status": "queued|processing|completed|failed",
      "estimatedCompletion": "2026-02-09T14:35:00Z",
      "files": [...]
    }
    """
    pass

@router.get("/extraction/{job_id}/status")
async def get_extraction_status(
    job_id: str,
    pipeline: EntityExtractionPipeline = Depends(get_extraction_pipeline)
) -> JobStatus:
    """
    Get status of extraction job.
    
    Response:
    {
      "jobId": "uuid",
      "status": "processing",
      "progress": {
        "total": 10,
        "completed": 5,
        "currentFile": "session-notes/session-5.md"
      },
      "results": [...],  # Partial results if available
      "errors": []
    }
    """
    pass

@router.get("/extraction/{job_id}/result")
async def get_extraction_result(
    job_id: str
) -> ExtractionResult:
    """
    Get final result of completed extraction job.
    """
    pass

@router.post("/extraction/prepare")
async def prepare_extraction(
    request: PreparationRequest
) -> PreparationResult:
    """
    Preview what would be extracted without running full pipeline.
    Used for cost estimation and entity preview.
    """
    pass
```

### Entity Endpoints

```python
# routes/entities.py

@router.get("/entities")
async def list_entities(
    type: Optional[EntityType] = None,
    search: Optional[str] = None,
    alias_manager: AliasManager = Depends(get_alias_manager)
) -> List[EntitySummary]:
    """
    List all entities with optional filtering.
    """
    pass

@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str
) -> EntityDetail:
    """
    Get detailed information about an entity including:
    - All mentions across files
    - Quotes
    - Relationships
    - Backlinks
    """
    pass

@router.post("/entities/{entity_id}/aliases")
async def add_entity_alias(
    entity_id: str,
    alias: str,
    alias_type: AliasType = AliasType.ALTERNATIVE
) -> AliasResponse:
    """
    Add a new alias for an entity.
    """
    pass

@router.get("/entities/{entity_id}/aliases")
async def get_entity_aliases(
    entity_id: str
) -> List[Alias]:
    """
    Get all aliases for an entity.
    """
    pass

@router.post("/entities/resolve")
async def resolve_entity_name(
    request: ResolutionRequest
) -> ResolutionResponse:
    """
    Resolve a name to its canonical entity.
    
    Request:
    {
      "name": "Ion",
      "context": "Ion cast a fireball..."
    }
    
    Response:
    {
      "canonical": "Ion the Brave",
      "confidence": 0.95,
      "alternatives": [...]
    }
    """
    pass
```

### Filesystem Endpoints

```python
# routes/filesystem.py (additions)

@router.get("/sync-status")
async def get_files_sync_status(
    path: Optional[str] = None
) -> SyncStatusResponse:
    """
    Get sync status for files.
    """
    pass

@router.post("/sync")
async def trigger_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks
) -> SyncResponse:
    """
    Manually trigger sync for specific files or all pending.
    """
    pass

@router.get("/files/{path:path}/entities")
async def get_file_entities(
    path: str
) -> List[EntityMention]:
    """
    Get all entities mentioned in a specific file.
    """
    pass
```

### Wiki Endpoints

```python
# routes/wiki.py (additions)

@router.get("/wiki/{entity_id}/backlinks")
async def get_wiki_backlinks(
    entity_id: str
) -> List[Backlink]:
    """
    Get all pages that link to this entity.
    """
    pass

@router.post("/wiki/regenerate")
async def regenerate_wiki_pages(
    request: RegenerationRequest,
    background_tasks: BackgroundTasks
) -> RegenerationResponse:
    """
    Regenerate auto-generated sections for specified wiki pages.
    """
    pass
```

---

## Implementation Phases

### Phase 1: Core Pipeline (Days 1-2)

**Goal**: Basic entity extraction and wiki page creation

**Day 1 Tasks**:
- [ ] Create `EntityExtractionPipeline` class structure
- [ ] Implement `prepare()` method with validation
- [ ] Implement basic `process()` orchestration
- [ ] Create entity extraction prompt for LLM
- [ ] Build entity parsing from LLM response
- [ ] Add `metadata/sync_index.json` schema and basic SyncIndex class

**Day 2 Tasks**:
- [ ] Implement `_update_wiki_pages()` method
- [ ] Create wiki page template system
- [ ] Implement auto-generated section markers
- [ ] Add basic quote extraction
- [ ] Build initial API endpoints:
  - POST /api/pipelines/extraction/start
  - GET /api/pipelines/extraction/{id}/status
- [ ] Write unit tests for pipeline components

**Deliverables**:
- Working pipeline that creates/updates wiki pages
- Basic API endpoints
- Unit tests

---

### Phase 2: Entity Resolution (Days 3)

**Goal**: Robust alias handling and disambiguation

**Day 3 Tasks**:
- [ ] Create `AliasManager` class
- [ ] Implement alias storage in `metadata/aliases.json`
- [ ] Build `_resolve_aliases()` pipeline method
- [ ] Create `DisambiguationEngine` with context-based resolution
- [ ] Add alias suggestion using LLM
- [ ] Implement entity endpoints:
  - GET /api/entities
  - POST /api/entities/{id}/aliases
  - POST /api/entities/resolve
- [ ] Add alias management UI (basic)

**Deliverables**:
- Working alias resolution
- Disambiguation for ambiguous names
- Entity management API

---

### Phase 3: Frontend Integration (Days 4)

**Goal**: UI for processing and sync status

**Day 4 Tasks**:
- [ ] Create `SyncStatusIndicator` component
- [ ] Add process button to Notes toolbar
- [ ] Build `ProcessConfirmationModal` with cost estimation
- [ ] Implement sync status API integration
- [ ] Create processing progress display
- [ ] Add error handling and retry UI
- [ ] Build entity preview in modal
- [ ] Add notification system for completion/failure

**Deliverables**:
- Process button with status indicator
- Confirmation modal
- Progress tracking UI

---

### Phase 4: Wiki Rendering (Days 5)

**Goal**: Rich wiki display with links and navigation

**Day 5 Tasks**:
- [ ] Implement `[[Wiki Link]]` markdown parser
- [ ] Create `WikiLink` React component
- [ ] Build backlinks display component
- [ ] Add source attribution section to wiki pages
- [ ] Implement bidirectional navigation
- [ ] Style wiki pages with auto/manual section distinction
- [ ] Add "Edit" protection for auto-generated sections
- [ ] Create backlinks API endpoint

**Deliverables**:
- Working wiki links
- Backlinks navigation
- Source attribution display

---

### Phase 5: Polish & Edge Cases (Days 6-7)

**Goal**: Production-ready system

**Day 6 Tasks**:
- [ ] Implement quote deduplication (semantic similarity)
- [ ] Build deprecation system for removed quotes
- [ ] Add hash-based change detection
- [ ] Create batch processing for multiple files
- [ ] Implement incremental updates (only changed entities)
- [ ] Add comprehensive error handling
- [ ] Build retry logic for failed operations

**Day 7 Tasks**:
- [ ] Write integration tests
- [ ] Add frontend component tests
- [ ] Performance optimization:
  - Cache entity embeddings
  - Batch LLM calls
  - Optimize file I/O
- [ ] Create documentation
- [ ] Add logging and monitoring
- [ ] Final bug fixes

**Deliverables**:
- Deduplication working
- Deprecation system
- Full test coverage
- Performance optimized

---

## Database/Storage Schema

### Directory Structure

```
campaign/
├── session-notes/
│   ├── session-1.md
│   ├── session-2.md
│   └── ...
├── wiki/
│   ├── ion-the-brave.md
│   ├── elara-moonwhisper.md
│   ├── locations/
│   │   ├── waterdeep.md
│   │   └── ...
│   ├── items/
│   │   └── ...
│   └── organizations/
│       └── ...
└── metadata/
    ├── aliases.json
    ├── sync_index.json
    ├── entity_cache.json
    └── embeddings/
        └── quote_embeddings.index
```

### File Formats

#### Session Notes
Standard Markdown with YAML frontmatter:

```markdown
---
session_number: 5
date: 2026-02-09
title: The Crown of Dawn
---

# Session 5: The Crown of Dawn

The party gathered at the tavern...
```

#### Wiki Pages
See "Wiki Page Format" section above for full specification.

#### Metadata Files

**aliases.json**:
```json
{
  "version": "1.0",
  "last_updated": "2026-02-09T14:32:00Z",
  "entities": { ... }
}
```

**sync_index.json**:
```json
{
  "version": "1.0",
  "last_full_sync": "2026-02-09T14:32:00Z",
  "files": { ... },
  "entities": { ... }
}
```

**entity_cache.json** (for quick lookups):
```json
{
  "entities": {
    "ion-the-brave": {
      "name": "Ion the Brave",
      "type": "character",
      "wiki_path": "wiki/ion-the-brave.md",
      "aliases": ["Ion", "Prince Ion"],
      "first_seen": "session-5.md",
      "mention_count": 12
    }
  }
}
```

---

## Testing Strategy

### Unit Tests

**Pipeline Tests**:
```python
# tests/pipelines/test_entity_extraction.py

class TestEntityExtractionPipeline:
    async def test_extract_entities_basic(self):
        """Test basic entity extraction from text."""
        pass
    
    async def test_resolve_aliases(self):
        """Test alias resolution."""
        pass
    
    async def test_wiki_page_update(self):
        """Test wiki page creation and update."""
        pass
```

**Alias Manager Tests**:
```python
# tests/entities/test_alias_manager.py

class TestAliasManager:
    def test_resolve_exact_match(self):
        """Test resolving exact alias match."""
        pass
    
    def test_resolve_normalized(self):
        """Test case-insensitive resolution."""
        pass
    
    def test_disambiguation(self):
        """Test context-based disambiguation."""
        pass
```

### Integration Tests

```python
# tests/integration/test_full_pipeline.py

class TestFullPipeline:
    async def test_end_to_end_processing(self, tmp_campaign):
        """Test complete processing flow."""
        # Create test session note
        # Run pipeline
        # Verify wiki pages created
        # Verify sync index updated
        pass
    
    async def test_reprocessing_idempotent(self, tmp_campaign):
        """Test that re-processing produces same results."""
        pass
    
    async def test_incremental_update(self, tmp_campaign):
        """Test updating existing wiki with new notes."""
        pass
```

### Frontend Tests

```typescript
// components/__tests__/SyncStatusIndicator.test.tsx

describe('SyncStatusIndicator', () => {
  it('shows green badge for synced status', () => {
    render(<SyncStatusIndicator status={{ status: 'synced' }} />);
    expect(screen.getByText('Synced')).toHaveClass('badge-green');
  });
  
  it('shows yellow badge for pending status', () => {
    render(<SyncStatusIndicator status={{ status: 'pending' }} />);
    expect(screen.getByText('Pending')).toHaveClass('badge-yellow');
  });
});

// components/__tests__/ProcessConfirmationModal.test.tsx

describe('ProcessConfirmationModal', () => {
  it('displays cost estimation correctly', () => {
    const result = {
      estimatedTokens: 1500,
      estimatedCost: 0.045,
      model: 'gpt-4'
    };
    
    render(<ProcessConfirmationModal preparationResult={result} ... />);
    expect(screen.getByText('$0.05')).toBeInTheDocument();
  });
});
```

### Test Data

Create sample campaign for testing:

```
tests/fixtures/
└── test-campaign/
    ├── session-notes/
    │   ├── session-1.md
    │   └── session-2.md
    ├── wiki/
    │   └── ion-the-brave.md
    └── metadata/
        └── aliases.json
```

---

## Open Questions & Decisions

### Q1: Vector Database for Embeddings?
**Options**:
- ChromaDB (lightweight, local)
- SQLite with sqlite-vss (no extra dependencies)
- Skip vector DB, compute on-demand (simpler, slower)

**Recommendation**: Start with on-demand computation, add ChromaDB if performance becomes an issue.

### Q2: Real-time vs Batch Processing?
**Options**:
- Real-time: Process on every save
- On-demand: Process when user clicks button
- Hybrid: Auto-process small changes, manual for large

**Recommendation**: Start with on-demand to give users control. Add auto-processing option later.

### Q3: LLM Provider?
**Options**:
- OpenAI (best quality, cost)
- Local models (privacy, no cost, slower)
- Hybrid: Use local for simple tasks, OpenAI for complex

**Recommendation**: Support pluggable providers, default to OpenAI for extraction quality.

---

## Success Metrics

1. **Accuracy**: >90% correct entity extraction (measured by manual review)
2. **Performance**: Process 10-page session note in <30 seconds
3. **Cost**: < $0.10 per session note on average
4. **Coverage**: 100% of named entities captured
5. **User Experience**: < 3 clicks to process a note

---

## Appendix: Prompt Templates

### Entity Extraction Prompt

```
You are an expert at extracting named entities from D&D session notes.

Extract all named entities from the following text and categorize them:

Categories:
- CHARACTER: Named people, NPCs, player characters
- LOCATION: Places, buildings, cities, regions
- ITEM: Named objects, artifacts, weapons
- ORGANIZATION: Groups, factions, guilds, families

For each entity, provide:
1. Name (as mentioned in text)
2. Category
3. All quotes attributed to this entity (if CHARACTER)
4. Context clues for disambiguation
5. Relationships to other entities

Text:
{session_note_content}

Output in JSON format:
{
  "entities": [
    {
      "name": "string",
      "category": "CHARACTER|LOCATION|ITEM|ORGANIZATION",
      "mentions": [{"text": "...", "position": 123}],
      "quotes": [{"text": "...", "speaker": "...", "context": "..."}],
      "relationships": [{"type": "...", "target": "..."}],
      "disambiguation_hints": ["..."]
    }
  ]
}
```

### Alias Suggestion Prompt

```
Given the entity "{entity_name}" and the following context:

{context}

What are other names, titles, or aliases by which this entity might be referred?
Consider:
- Shortened names (e.g., "Alexander" → "Alex")
- Titles (e.g., "King Arthur" → "The King")
- Nicknames
- Alternative spellings

Output as JSON array: ["alias1", "alias2", ...]
```

---

*Document Version: 1.0*
*Last Updated: 2026-02-09*
*Author: Development Team*
