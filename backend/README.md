# MegaBook Backend

Local-first, Git-backed, AI-assisted knowledge management system backend.

## Development Setup

```bash
# Install dependencies
poetry install

# Run development server
poetry run uvicorn src.main:app --reload

# Run tests
poetry run pytest
```

## Architecture

- **Core**: Filesystem abstraction, Git service, configuration
- **Services**: LLM providers, embeddings, cost tracking
- **Pipelines**: Import, Structuring, Wiki Generation, Embedding, Query
- **API**: FastAPI endpoints

## Knowledge Layers

- `prompts/` - Immutable source of truth
- `notes/` - Canonical structured knowledge
- `wiki/` - Derived presentation layer