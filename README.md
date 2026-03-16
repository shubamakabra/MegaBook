# MegaBook

Local-first, Git-backed, AI-assisted knowledge management system for TTRPG worldbuilding.

## Overview

MegaBook transforms raw session notes and imported content into structured knowledge using LLM services. It maintains three strictly separated layers:

- **prompts/** - Immutable source of truth (raw notes, imports)
- **notes/** - Canonical structured knowledge (organized by you and LLM)
- **wiki/** - Derived presentation layer (player-safe or DM-full)

## Architecture

```
├── backend/           # Python FastAPI backend
│   ├── src/
│   │   ├── core/      # Filesystem, Git, Config
│   │   ├── services/  # LLM, Embeddings, Cost Tracking
│   │   ├── pipelines/ # Import, Structuring, Wiki, Embedding
│   │   └── api/       # FastAPI routes
│   └── tests/
├── frontend/          # Tauri + React frontend
│   ├── src/
│   └── src-tauri/    # Tauri configuration
├── prompts/          # Knowledge layer: raw content
├── notes/            # Knowledge layer: structured notes
├── wiki/             # Knowledge layer: derived wiki
└── .meta/            # Processing state, embeddings, costs
```

## Backend Features

### Core Services
- **Filesystem Abstraction** - Layer-enforced file operations
- **Git Integration** - Manual commits only (no automatic commits)
- **LLM Provider Interface** - Azure AI Foundry (swappable)
- **Cost Tracking** - NOK and USD tracking with configurable limits
- **Embedding Service** - ChromaDB with SQLite backend

### Processing Pipelines (Manual Trigger Only)
1. **Import Pipeline** - Ingest markdown files from Milanote exports
2. **Structuring Pipeline** - Transform prompts → structured notes
3. **Wiki Generation Pipeline** - Generate player/DM wiki pages
4. **Embedding Pipeline** - Generate vector embeddings for RAG
5. **RAG Query Pipeline** - Query knowledge with vector search

### Key Features
- Pause/resume processing with state persistence
- Cost-based automatic stops (configurable limit in NOK)
- Atomic operations with resume capability
- Progress tracking in `.meta/processing/`

## API Endpoints

### Filesystem
- `GET /api/filesystem/files` - List files
- `GET /api/filesystem/files/{path}` - Read file
- `POST /api/filesystem/files` - Write file
- `GET /api/filesystem/tree` - Get file tree

### Git
- `GET /api/git/status` - Repository status
- `POST /api/git/commit` - Create commit
- `GET /api/git/history` - Commit history
- `GET /api/git/diff` - Get diff

### Pipelines
- `POST /api/pipelines/import/start` - Start import
- `POST /api/pipelines/import/upload` - Upload file
- `POST /api/pipelines/structuring/start` - Start structuring
- `POST /api/pipelines/structuring/session` - Process session notes
- `GET /api/pipelines/structuring/{id}/changes` - Get proposed changes
- `POST /api/pipelines/structuring/apply` - Apply changes
- `POST /api/pipelines/wiki/start` - Start wiki generation
- `POST /api/pipelines/embedding/start` - Start embedding
- `POST /api/pipelines/run/{id}` - Run pipeline
- `POST /api/pipelines/pause/{id}` - Pause pipeline
- `POST /api/pipelines/resume/{id}` - Resume pipeline
- `GET /api/pipelines/status/{id}` - Get status

### Query (RAG)
- `POST /api/query/search` - Vector search
- `POST /api/query/rag` - RAG query with LLM

### Costs
- `GET /api/costs/stats` - Cost statistics
- `GET /api/costs/current-session` - Current session costs
- `POST /api/costs/limit` - Update cost limit

## Setup

### Run frontend and backend together

From the repository root:

```bash
make run
```

This starts:
- Backend: `poetry run uvicorn src.main:app --reload`
- Frontend: `npm run dev`

Backend startup resolution order:
- `poetry run uvicorn ...` (if Poetry is available)
- `backend/venv` Python
- Root `.venv` Python

Use `Ctrl+C` to stop both processes.

If port `1420` is already in use, frontend will automatically pick the next available port.

### Backend

**Option 1: Using pip (standard)**
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Run development server (uses mock LLM by default)
uvicorn src.main:app --reload
```

**To use Azure OpenAI instead of mock:**
Edit `.env` and set:
```
LLM_PROVIDER=azure
AZURE_ENDPOINT=your-endpoint
AZURE_API_KEY=your-key
AZURE_DEPLOYMENT=gpt-4
```

**Option 2: Using Poetry (alternative)**
```bash
cd backend

# Install Poetry if not already installed
pip install poetry

# Install dependencies
poetry install

# Create .env file (same as above)

# Run development server
poetry run uvicorn src.main:app --reload
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Or run with Tauri
npm run tauri dev
```

## Development

### Backend Development

```bash
# Run tests
poetry run pytest

# Lint
poetry run black src/
poetry run ruff check src/
poetry run mypy src/
```

### Frontend Development

```bash
# Type check
npm run typecheck

# Lint
npm run lint
```

## Knowledge Layer Rules

### prompts/ (IMMUTABLE)
- **Never** modified by LLM
- **Never** modified automatically
- Write-only via user actions or imports
- LLM has read-only access
- Permanent audit log

### notes/ (CANONICAL)
- Structured, organized knowledge
- Editable by user and LLM (when triggered)
- Primary source for wiki and RAG
- Git versioned

### wiki/ (DERIVED)
- **Never** source of truth
- Always rebuildable from notes/
- LLM writable only via manual trigger
- Player-safe and DM-full versions

## Cost Tracking

Costs are tracked in both NOK and USD. The system will:
- Pause processing when cost limit is reached (default: 10 NOK)
- Complete current atomic operation before stopping
- Show current costs in admin panel
- Save cost history to `.meta/costs/`

## License

MIT