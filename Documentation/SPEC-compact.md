# MegaBook - Compact Specification

> Local-first, AI-assisted knowledge management for TTRPG worldbuilding and campaign management. Obsidian-compatible vault with deep LLM integration.

---

## Architecture

**Desktop app** (Tauri + React + TypeScript) → HTTP → **Backend** (FastAPI/Python) → **Obsidian Vault** (Git repo) + **ChromaDB** (vectors)

- Backend and frontend are separate processes; backend serves both desktop app and player web interface
- The vault IS the database — all content is markdown files in a Git repo
- No SQL database; only ChromaDB/SQLite for embeddings and JSON for config/metadata

## Users & Access

| Role | Vault | Wiki | Chat | Edit | Admin |
|------|-------|------|------|------|-------|
| **DM** | Full | Full | Private + Shared | Full | Full |
| **Co-DM** | Full | Full | Private + Shared | Notes tier | Limited |
| **Player** | Filtered by visibility | Player wiki | Private + Shared | Own notes | None |
| **Guest** | None | Player wiki (read-only) | None | None | None |

- DM uses Tauri desktop app (works offline); players access via web when DM's server is running
- Simple local auth with token-based sessions
- Visibility via YAML frontmatter: `dm-only`, `player`, `players:alice,bob`

## Vault Structure

MegaBook points at any Obsidian vault (or any folder) via `REPO_PATH`. It does not impose folder structure. The only thing MegaBook creates is a hidden `.megabook/` metadata folder (analogous to `.obsidian/`).

### Three-Tier Quality Model

| Tier | Location | Purpose |
|------|----------|---------|
| **Raw** | `_raw/` subdirs | Unprocessed input, preserved as-is |
| **Notes** | Main files | Canonical structured knowledge (what RAG embeds) |
| **Wiki** | `_wiki/` subdirs | AI-generated polished articles per audience |

Tiers are a conceptual label (tracked in frontmatter), not a filesystem enforcement rule. They coexist within topical entity folders:
```
Characters/Ion/Ion.md          <- notes (canonical)
Characters/Ion/_raw/           <- raw inputs
Characters/Ion/_wiki/          <- generated wiki (DM + player variants)
```

### Topical Categories

Template-based, customizable: `Characters/`, `Places/`, `Factions/`, `Magic/{Spells,Rituals,Items}/`, `Lore/`, `Sessions/{History,_raw,Images}/`, `Notes/`, `.megabook/`

LLM classifies new entities into categories; suggests new categories for DM approval.

### Obsidian Compatibility

All files are standard markdown with `[[wiki-links]]`, YAML frontmatter, and `![[image.png]]` embeds. Vault opens simultaneously in Obsidian.

## Core Features

### File Browser
Miller column (cascading, Mac Finder style). Breadcrumbs, preview panel, right-click context menus, drag-and-drop, search filter. RAG scope selection from file browser.

### Document Editor
Rich markdown editor with inline rendering. `[[wiki-link]]` autocomplete, YAML frontmatter form, multiple tabs, keyboard shortcuts (Ctrl+S/N/W/P), image embedding, edit/preview toggle.

### MetaNotes
Side-panel chat alongside editor. User instructs LLM to modify the open document via natural language. Shows diff of proposed changes. Maintains conversation history per editing session. System prompt emphasizes minimal, careful changes.

### Session Notes Processor
Multiple entry points: dedicated tab, chat command, file browser import, manual editing. Processing flow:
1. Raw input saved to `Sessions/_raw/`
2. Structuring pipeline identifies entities, classifies, finds related notes
3. DM reviews proposed changes (create/update/merge)
4. Approved changes committed via Git

### Chat (The Grimoire)
Conversational AI with **tool-calling** — The Grimoire receives vault tools (`search`, `read_file`, `list_files`, `read_frontmatter`) and dynamically decides what to read/search to answer questions. No pre-fetched RAG; the LLM controls context retrieval. **Toggleable write access**: DM can enable `write_file`/`create_file`/`move_file` per session (off by default, never for players). Write operations auto-commit to Git. Multiple threads, persistence, context window tracking, chat compaction. Per-user private sessions + shared campaign chat. Role-aware responses (won't reveal DM secrets to players).

### Wiki System
LLM-generated from notes tier. Audience-specific variants (DM wiki = everything; player wiki = public info only). Cross-linked via `[[wiki-links]]`. Sub-wikis per category. Root wiki page as index.

### Image Generation
Prompt-based with style templates (10 defaults: portraits, landscapes, dungeons, items, battles, etc.). Context injection from vault files. Gallery with thumbnails/pagination/keyboard nav. Pluggable provider (currently Azure gpt-image-1.5). Images stored in vault for Obsidian embedding. Mock mode for dev.

### Git Integration
Status, stage/unstage, commit, history, diff, discard. **AI operations auto-commit** with tagged messages (`[grimoire]`, `[wiki-gen]`, `[structuring]`). DM reviews diffs and reverts AI commits with one click. Manual user edits still require explicit commits. Push-ready for remote backup.

## AI & LLM

### Provider System
Pluggable, OpenAI-compatible interface. Capabilities: text gen, chat, **tool-augmented generation** (agent loop with vault tools), structured output (JSON schema), embeddings, token counting, cost reporting. Mock provider for dev. Configured via env vars (`LLM_PROVIDER`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `CHAT_MODEL`).

### RAG
Embeds notes-tier only. Metadata per chunk: `file_path`, `category`, `entity`, `tags`, `visibility`, `last_modified`. Filtered at query time by user role, category, folder, tags, exclusions. ChromaDB with cosine similarity, 1000-char chunks / 200-char overlap. Incremental updates via content hashing. **RAG is accessed via the `search` vault tool** — the LLM decides when and what to search, rather than context being pre-fetched.

### Pipelines

Generic framework: state machine (idle/running/paused/completed/error), progress tracking, pause/resume, state persistence, cost limits, per-item processing. All manually triggered. **LLM-using pipelines are tool-augmented** — the LLM receives a goal prompt + vault tools and dynamically reads, cross-references, and writes files via the agent loop. Each pipeline run auto-commits changes as a single tagged Git commit. Import pipeline remains pure filesystem (no LLM).

| Pipeline | Input → Output | LLM |
|----------|---------------|-----|
| **Import** | External files → raw tier | No |
| **Structuring** | Raw → notes (tool-augmented) | Yes |
| **Wiki Generation** | Notes → wiki per audience (tool-augmented) | Yes |
| **Embedding** | Notes → vector DB | Yes |
| **Entity Extraction** | Notes → entity data, aliases, wiki pages (tool-augmented) | Yes |

### Vault Tools & Agent Loop
Generic tool-calling loop used by chat and pipelines. LLM receives tool definitions, decides what to call, backend executes and feeds results back, loop repeats until text response or limit hit. Safety: `max_iterations`, cost-per-iteration tracking, visibility filtering for players.

**Tools:** `search` (semantic), `read_file`, `list_files`, `read_frontmatter`, `write_file`, `create_file`, `move_file`, `get_diff_since`. Each wraps an existing backend service.

**Access:** Chat DM = read-only default (write toggleable per session). Chat Player = read-only always (visibility-filtered). Pipelines = read + write always. MetaNotes = no tools (sends full document directly).

### AI Persona
Default: **The Grimoire** — sentient ancient tome, Snape-like butler. Addresses DM as "Master", players by name. Protective, sharp-tongued, concise. Fully customizable: system prompt, name, per-audience behavior, compaction prompt, RAG prompts, pipeline prompts. Persona affects chat, MetaNotes, session processing, and wiki generation.

## Settings & Admin

### Cost Tracking
Own tab in Settings. Per-operation recording (tokens, USD, local currency). Session-based grouping. Configurable cost limits (auto-pause). Dashboard: current session, 7/30-day totals, per-user breakdown. Default local currency: NOK.

### Theming
CSS custom properties. Default: **The Cozy Tavern Grimoire** (deep wood tones, amber/gold accents, Cinzel Decorative + Cormorant Garamond fonts, candlelight flicker). DM can swap themes or provide custom CSS.

### Admin Panel Tabs
Pipelines, Git, Entities, Embeddings, Users, Persona, Costs, Categories, Settings.

## UI Layout

Sidebar (collapsible) + main content area. Tabs: **Chat**, **Files**, **Editor**, **Wiki**, **Session**, **ImaGen**, **Admin**. Min window: 1400x900. Player web interface responsive for tablet/desktop.

## Tech Stack

**Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic, GitPython, ChromaDB, OpenAI SDK, tiktoken, aiofiles, Poetry
**Frontend:** TypeScript (strict), React 18, Vite, Tauri, Axios, react-markdown, rich markdown editor (Milkdown/TipTap), CSS custom properties (no Tailwind)
**Dev:** Vite on :1420 proxying `/api` to FastAPI on :8000

## Future Features (Not in Scope)

Sound generation, external integrations, collaborative editing, mobile app, plugin system, static site export, stat block generation, interactive maps, campaign timeline, spoiler warnings.

---

*Compact version of SPEC.md — see full spec for detailed descriptions, examples, and appendices.*
