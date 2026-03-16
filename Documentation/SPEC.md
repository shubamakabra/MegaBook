# MegaBook - Product Specification

> **Version:** 1.0-draft
> **Last Updated:** 2026-03-05
> **Purpose:** This document is the master specification for MegaBook. It describes the product's intent, features, and architecture in enough detail that the project can be regenerated from this document with reasonable determinism. It is also the document to refine when iterating on the product concept.

---

## Table of Contents

1. [Vision and Overview](#1-vision-and-overview)
2. [Target Users and Access Model](#2-target-users-and-access-model)
3. [Architecture Overview](#3-architecture-overview)
4. [The Vault - File System and Structure](#4-the-vault---file-system-and-structure)
5. [Core Features](#5-core-features)
   - 5.1 [File Management and Navigation](#51-file-management-and-navigation)
   - 5.2 [Document Editor](#52-document-editor)
   - 5.3 [MetaNotes - AI Document Editing](#53-metanotes---ai-document-editing)
   - 5.4 [Session Notes Processor](#54-session-notes-processor)
   - 5.5 [Chat with The Grimoire](#55-chat-with-the-grimoire)
   - 5.6 [Wiki System](#56-wiki-system)
   - 5.7 [Image Generation](#57-image-generation)
   - 5.8 [Git Integration](#58-git-integration)
6. [AI and LLM Integration](#6-ai-and-llm-integration)
   - 6.1 [LLM Provider System](#61-llm-provider-system)
   - 6.2 [RAG - Retrieval Augmented Generation](#62-rag---retrieval-augmented-generation)
   - 6.3 [Processing Pipelines](#63-processing-pipelines)
   - 6.4 [AI Persona System](#64-ai-persona-system)
   - 6.5 [Vault Tools and Agent Loop](#65-vault-tools-and-agent-loop)
7. [Multi-User and Access Control](#7-multi-user-and-access-control)
8. [Settings and Administration](#8-settings-and-administration)
   - 8.1 [Cost Tracking](#81-cost-tracking)
   - 8.2 [Theming System](#82-theming-system)
   - 8.3 [Admin Panel](#83-admin-panel)
9. [UI/UX Design](#9-uiux-design)
10. [Tech Stack](#10-tech-stack)
11. [Future Features](#11-future-features)

---

## 1. Vision and Overview

MegaBook is a **local-first, AI-assisted knowledge management system** built specifically for **worldbuilding, TTRPG campaign management, and game development**. It is an Obsidian-compatible vault manager with deep LLM integration.

### The Core Problem

Dungeon Masters, worldbuilders, and game developers accumulate vast quantities of unstructured notes: scribbled session recaps, vague character ideas, scattered lore fragments, code snippets, and half-formed world details. These notes are valuable but chaotic. Turning them into organized, searchable, cross-referenced knowledge is tedious manual work. They also have need for on-the-go content - both searching through the content that is there and genreration of new content.

### The Solution

MegaBook provides:

1. **A structured Obsidian vault** with topical organization (Characters, Places, Magic, etc.)
2. **Three quality tiers** for every piece of content (raw input, structured notes, polished wiki)
3. **AI pipelines** that promote content between tiers - turning messy session notes into structured knowledge and structured knowledge into a browseable wiki
4. **An AI chat assistant** (The Grimoire) that can search, answer questions about, and modify the knowledge base
5. **Multi-user access** where the DM has full control and players see only what they should
6. **Image generation** for characters, locations, items, and scenes
7. **Git-backed version history** so every change is tracked and reversible

### Design Principles

- **Local-first:** The DM's data stays on their machine. The app works fully offline. Players access via a web interface when the DM's server is running.
- **Obsidian-compatible:** The vault is a valid Obsidian vault at all times. Files use `[[wiki-links]]`, YAML frontmatter, and standard markdown. A user can open the same vault in Obsidian and MegaBook simultaneously.
- **AI-assisted, auto-apply with undo:** All AI operations are manually triggered by the user. Changes are applied immediately and auto-committed to Git with descriptive tagged messages (e.g., `[grimoire]`, `[wiki-gen]`). The DM can review diffs and revert any AI commit with one click. This provides speed without sacrificing safety.
- **Tool-augmented AI:** The LLM is not a blind text-transform box. It has access to **vault tools** (search, read, write, list files) and dynamically decides what to read, cross-reference, and modify during any operation. The backend executes tool calls in a loop until the LLM has enough information to complete the task.
- **Git-native:** The entire vault is a Git repository. Every meaningful change produces a commit. Diffs drive efficient LLM processing.

---

## 2. Target Users and Access Model

### Primary User: The Dungeon Master (DM)

The DM is the admin, owner, and primary user. They:
- Run the MegaBook application locally as a **desktop app** (Tauri)
- Have full read/write access to all content across all tiers
- Manage the AI, pipelines, settings, users, and access control
- Can work fully offline

### Secondary Users: Players

Players access MegaBook through a **web interface** served by the DM's running backend. They:
- View content based on their visibility permissions
- Chat with The Grimoire (receiving persona-appropriate responses)
- Browse the player-facing wiki
- Cannot see DM-only content, hidden plot details, or other players' private notes

### Access Levels

| Role | Vault Access | Wiki Access | Chat | Edit | Admin |
|---|---|---|---|---|---|
| **DM** | Full (all tiers, all tags) | Full (DM + Player wiki) | Private + Shared | Full | Full |
| **Co-DM** | Full | Full | Private + Shared | Notes tier | Limited |
| **Player** | Filtered by visibility tags | Player wiki only | Private + Shared | Own notes only | None |
| **Guest** | None | Player wiki (read-only) | None | None | None |

---

## 3. Architecture Overview

```
+--------------------------------------------------+
|                MegaBook Desktop App               |
|              (Tauri + React + TypeScript)          |
+--------------------------------------------------+
                        |
                   HTTP / REST
                        |
+--------------------------------------------------+
|              MegaBook Backend (FastAPI)            |
|  +----------------------------------------------+ |
|  |  API Layer (Routes)                           | |
|  |  - filesystem, chat, wiki, pipelines,         | |
|  |    git, imagegen, entities, costs, query      | |
|  +----------------------------------------------+ |
|  |  Service Layer                                | |
|  |  - LLM Provider (pluggable)                   | |
|  |  - Cost Tracking                              | |
|  |  - Embedding / RAG                            | |
|  |  - Image Generation                           | |
|  |  - Entity / Alias Manager                     | |
|  +----------------------------------------------+ |
|  |  Core Layer                                   | |
|  |  - Filesystem Service (vault access)           | |
|  |  - Git Service                                | |
|  |  - Configuration                              | |
|  +----------------------------------------------+ |
|  |  Pipeline Framework                           | |
|  |  - Import, Structuring, Wiki Gen,             | |
|  |    Embedding, Entity Extraction               | |
|  +----------------------------------------------+ |
+--------------------------------------------------+
                        |
            +-----------+-----------+
            |                       |
   +--------+--------+   +---------+---------+
   |  Obsidian Vault  |   |  Vector Database  |
   |  (Git Repository) |   |  (ChromaDB/SQLite)|
   +------------------+   +-------------------+
```

### Key Architectural Decisions

1. **Backend and frontend are separate processes.** The FastAPI backend runs independently. The Tauri desktop app communicates via HTTP to `localhost`. This same backend serves the player web interface.

2. **The vault IS the database.** There is no SQL database for content. All knowledge lives as markdown files in the Git-tracked vault. The only non-file storage is the vector database for embeddings and JSON files for metadata/config.

3. **Pipelines are the engine.** Content flows through processing pipelines: raw input -> structured notes -> wiki pages -> embeddings. Each pipeline is pausable, resumable, cost-tracked, and state-persisted.

---

## 4. The Vault - File System and Structure

### 4.1 Obsidian Vault Compatibility

The MegaBook vault is **any Obsidian vault** — or any folder of files. MegaBook does not impose a folder structure on the vault. The user points MegaBook at their vault via the `REPO_PATH` configuration, and MegaBook browses and edits the vault's files as-is.

The only thing MegaBook creates inside the vault is a hidden **`.megabook/`** folder for its own metadata (processing state, cost tracking, templates, embeddings). This folder is hidden from the file browser and excluded from Git tracking. It is analogous to Obsidian's `.obsidian/` folder.

The vault is a **fully valid Obsidian vault**. This means:

- All content files are **standard Markdown** (`.md`)
- Files use **Obsidian `[[wiki-links]]`** for cross-referencing (e.g., `[[Ion]]`, `[[Waterdeep#History]]`)
- Files use **YAML frontmatter** for metadata:
  ```yaml
  ---
  title: Ion the Brave
  type: character
  category: Characters
  visibility: player  # or "dm-only", "player", "players:alice,bob"
  tags: [npc, royal, quest-giver]
  tier: notes  # "raw", "notes", or "wiki"
  created: 2026-02-10
  updated: 2026-02-23
  ---
  ```
- Image files are stored in the vault and referenced via standard Obsidian image embeds: `![[ion-portrait.png]]`
- The vault can be opened simultaneously in Obsidian for users who prefer that editor

### 4.2 The Three-Tier Quality Model

Every piece of content in the vault exists at one of three quality tiers. These tiers represent the **maturity of the content**, not separate storage locations. They coexist within the same topical folder structure. The filesystem does not enforce tiers — the tier is a conceptual label tracked in frontmatter and used by pipelines.

| Tier | Name | Purpose | Who Writes | AI Access |
|---|---|---|---|---|
| **Raw** | `_raw/` subdirs | Unprocessed input. Session dumps, imports, brain dumps. Preserved as-is for audit trail. | User only (manual or import) | Read-only |
| **Notes** | Main files | Canonical structured knowledge. The working layer. Clean, organized, cross-referenced. | User + AI (manually triggered) | Read + Write (with approval) |
| **Wiki** | `_wiki/` subdirs | Polished presentation layer. Always derivable from notes. Formatted for reading, not editing. | AI-generated (triggered by user) | Write-only (generation) |

**How tiers coexist in the folder structure:**

```
Characters/
  Ion/
    Ion.md                    # Notes tier (the canonical file)
    _raw/
      session-5-notes.md      # Raw tier (original session dump mentioning Ion)
      import-2026-02-10.md    # Raw tier (imported from external source)
    _wiki/
      Ion.md                  # Wiki tier (generated polished article)
      Ion-player.md           # Wiki tier (player-safe version)
```

The **notes tier** files are the primary vault content. They are what you see when browsing the vault, what Obsidian indexes, and what the RAG system embeds. The `_raw/` and `_wiki/` subdirectories are supporting tiers that complement the canonical notes.

### 4.3 Topical Folder Structure

The vault uses a **template-based category system**. MegaBook ships with a default set of topical categories that the user can customize. When the LLM encounters new entities during processing, it classifies them into existing categories or suggests new ones for user approval.

**Default category template:**

```
vault/
  Characters/           # NPCs, PCs, factions' members
  Places/               # Locations, regions, planes
  Factions/             # Organizations, guilds, governments
  Magic/
    Spells/             # Individual spell descriptions
    Rituals/            # Ritual descriptions
    Items/              # Magical items and artifacts
  Lore/                 # World history, cosmology, religions
  Sessions/
    History/            # Processed session recaps (notes tier)
    _raw/               # Raw session dumps before processing
    Images/             # Session-related generated images
  Notes/                # Freeform notes not tied to an entity
  .megabook/              # MegaBook system metadata (hidden from file browser)
    templates/          # Category templates, style templates
    config/             # System configuration files
    embeddings/         # Vector database files
    costs/              # Cost tracking data
    processing/         # Pipeline state persistence
```

**Category management rules:**
- Categories are defined in a `.megabook/templates/categories.json` configuration file
- The DM can add, rename, or restructure categories from the admin panel
- When the LLM processes content and encounters an entity that doesn't fit existing categories, it suggests a category. The DM approves or redirects.
- Moving files between categories is a standard file operation (rename/move) tracked by Git

### 4.4 File Naming Conventions

- Entity files are named after the entity: `Ion.md`, `Waterdeep.md`, `Ring of Power.md`
- Raw inputs are named descriptively: `session-5-notes.md`, `import-2026-02-10.md`
- Wiki outputs mirror the source: if `Ion.md` exists in notes, `_wiki/Ion.md` is the generated wiki
- Player-safe wiki variants are suffixed: `_wiki/Ion-player.md`
- Image files live alongside or within the relevant entity folder

---

## 5. Core Features

### 5.1 File Management and Navigation

#### Miller Column File Browser

The primary navigation is a **Miller column (cascading) file browser** - the classic Mac Finder style where each folder level appears as a column to the right. This provides:

- Breadcrumb navigation showing the current path
- A preview panel on the right showing the selected file's content
- Right-click context menus for file operations (rename, copy, move, delete, download)
- Drag-and-drop for file uploads and file moves
- A search bar to filter files by name
- Visual indicators for sync status and visibility

#### File Operations

- Create files and folders
- Rename, copy, move, delete files and folders
- Upload files (drag-and-drop or file picker)
- Download files (including binary files like images)
- File previews for: markdown (rendered), images, audio, PDF, plain text

#### RAG Scope Selection

From the file browser, users can **select which folders or files are included in RAG search scope**. This selection persists for the session and affects:
- Chat queries (The Grimoire only searches selected scope)
- MetaNotes context (only pulls related content from selected scope)
- Wiki generation cross-references

When no scope is selected, RAG searches the entire notes tier.

### 5.2 Document Editor

The document editor is a **rich markdown editor** with inline rendering. It provides a modern editing experience while maintaining the file as clean, standard markdown underneath.

#### Editor Features

- **Rich markdown editing** with inline preview (headings render as headings, bold renders as bold, links are clickable, etc.)
- **Obsidian `[[wiki-link]]` support** - autocomplete suggestions when typing `[[`, resolved to actual vault files
- **YAML frontmatter editing** - structured form view for metadata fields
- **Multiple tabs** - open several documents simultaneously, switch between them
- **Keyboard shortcuts**: Ctrl+S (save), Ctrl+N (new), Ctrl+W (close tab), Ctrl+P (toggle preview mode)
- **Spellcheck** aware of fantasy terms (custom dictionary support)
- **Modified indicator** - dot/marker on tabs with unsaved changes
- **Image embedding** - paste or drag images into the editor, auto-saved to the entity's folder
- **Syntax highlighting** for code blocks
- **Edit/Preview toggle** - switch between editing mode and rendered preview

#### Integration with MetaNotes

A button in the editor toolbar opens the MetaNotes side panel (see 5.3).

### 5.3 MetaNotes - AI Document Editing

MetaNotes is a **side panel chat interface** that appears alongside the document editor. It allows the user to instruct an LLM to modify the currently open document through natural language commands.

#### How It Works

1. The user opens a document in the editor
2. They click the MetaNotes button to open the side panel
3. They type an instruction (e.g., "sort these messy notes into a story", "make this text more formal", "add a section about Ion's childhood")
4. The system sends the **full document content** plus the **user's instruction** to the LLM, with a system prompt that emphasizes:
   - Respect the original content - do not add, remove, or change information the user didn't ask for
   - Only make the specific change requested
   - Preserve formatting, structure, and voice unless explicitly asked to change them
   - Return the complete modified document
5. The editor shows a **diff view** of proposed changes
6. The user accepts, rejects, or requests further modifications

#### Example MetaNotes Prompts

- "Sort all these messy notes into an adventurous story"
- "Make this text Spanish"
- "Write a generic tavern song with the theme of lost love"
- "Add YAML frontmatter to this file with appropriate tags"
- "Reorganize this into sections: Background, Personality, Goals, Secrets"
- "Fix the formatting and add [[wiki-links]] to mentioned characters"

#### MetaNotes Conversation

The MetaNotes panel maintains a conversation history for the current editing session. The user can have a back-and-forth:
- "Make the tone darker"
- "Actually, revert the last change but keep the new paragraph about the curse"
- "Now add a DM note callout about the hidden plot hook"

### 5.4 Session Notes Processor

The Session Notes Processor is a **dedicated feature for the primary DM workflow**: turning raw session recaps into structured vault knowledge.

#### The Workflow

1. **Input:** The DM writes or pastes raw session notes. This can happen through multiple entry points:
   - A dedicated **"Session Notes" tab** with a large text input area optimized for dumping raw session recaps
   - **Chat** - pasting into the chat with an instruction like "add this to session history"
   - **File browser** - dropping a file into `Sessions/_raw/` and triggering processing
   - **Import** - batch import from external files (markdown files downloaded from external sources)
   - **Manual editing** - the DM creates files and folders directly in the vault and writes notes by hand

2. **Processing:** When triggered, the system:
   - Saves the raw input to `Sessions/_raw/session-{date}-{id}.md` (preserved permanently)
   - Runs the **structuring pipeline** to analyze the content:
     - Identifies entities mentioned (characters, places, items, events)
     - Classifies entities into vault categories
     - Finds existing notes that should be updated
   - Proposes changes: new files to create, existing files to update
   - The DM reviews and approves/rejects each proposed change

3. **Output:**
   - Updated entity notes in the appropriate category folders
   - A structured session recap in `Sessions/History/`
   - New entity files created where needed
   - Existing entity files enriched with new information
   - All changes tracked as a Git commit

### 5.5 Chat with The Grimoire

The chat interface provides conversational interaction with an AI assistant called **The Grimoire**. The Grimoire's persona is configurable by the DM (see section 6.4).

#### Chat Features

- **Conversational interface** with message history
- **Multiple chat sessions (threads)** - create, switch between, rename, delete
- **Session persistence** - conversations are saved and restored across app restarts
- **Tool-augmented responses** - The Grimoire has access to **vault tools** and dynamically decides what to search, read, and cross-reference to answer questions (see section 6.5)
- **Toggleable write access** - The DM can enable or disable write tools (`write_file`, `create_file`, `move_file`) per chat session. When enabled, The Grimoire can modify vault files when instructed (e.g., "Add this to Ion's notes where it makes sense"). Write tools are **off by default** and are **never available to players**.
- **Context window tracking** - visual indicator showing how much of the LLM context is used, with color-coded thresholds (green/yellow/orange/red)
- **Chat compaction** - when the context window fills up, the conversation can be summarized/compacted to continue with fresh context while preserving key decisions, names, and ongoing work
- **Per-user chats** - each user (DM, player) has private chat sessions
- **Shared campaign chat** - an optional shared chat where all users interact with The Grimoire together
- **Role-aware responses** - The Grimoire adapts its answers based on the user's role. It will not reveal DM secrets to players.
- **Auto-commit on write** - when write tools are active and The Grimoire modifies files, changes are automatically committed to Git with tagged messages (e.g., `[grimoire] Modified Characters/Ion/Ion.md via chat`). The DM can review diffs and revert from the Git tab.

#### How Tool-Calling Works in Chat

When the user asks a question, the backend sends the conversation plus **tool definitions** to the LLM. The LLM decides what it needs:

1. The backend sends: system prompt, conversation history, user message, and available tool definitions
2. The LLM responds with either a **text answer** (done) or a **tool call** (e.g., `search(query="Ion appearance")`)
3. The backend executes the tool call against real services (embedding search, filesystem read, etc.)
4. The tool result is appended to the conversation and sent back to the LLM
5. The LLM may make additional tool calls (e.g., `read_file(path="Characters/Ion/Ion.md")`) or produce a final text answer
6. This loop continues until the LLM answers or a safety limit is reached (`max_iterations`, cost limit)

This means The Grimoire **chooses** what to read, how many files to cross-reference, and when it has enough context — rather than relying on pre-fetched RAG chunks that may miss relevant information.

#### Example Tool-Calling Flow

```
User: "What does Ion look like?"

LLM → tool_call: search(query="Ion appearance description", category="Characters")
Backend → executes search, returns matching chunks from ChromaDB
LLM → tool_call: read_file(path="Characters/Ion/Ion.md")
Backend → reads file, returns content
LLM → text: "Ion is tall with silver hair and a distinctive scar across his left cheek..."
```

#### Chat Tools by Role

| Tool | DM (default) | DM (write enabled) | Player |
|------|---|---|---|
| `search` | Yes | Yes | Yes (visibility-filtered) |
| `read_file` | Yes | Yes | Yes (visibility-filtered) |
| `list_files` | Yes | Yes | Yes (visibility-filtered) |
| `read_frontmatter` | Yes | Yes | Yes (visibility-filtered) |
| `write_file` | No | Yes | Never |
| `create_file` | No | Yes | Never |
| `move_file` | No | Yes | Never |

### 5.6 Wiki System

The wiki is a **generated, read-optimized view** of the vault's knowledge, produced from the notes tier by an LLM pipeline.

#### Wiki Generation

- The wiki is generated from notes-tier content using an LLM pipeline
- Generation can be triggered for individual entities, categories, or the entire vault
- The LLM produces polished, well-formatted wiki articles with:
  - Consistent structure (Overview, Details, Relationships, History, etc.)
  - `[[Wiki-links]]` to related entities
  - Appropriate level of detail for the audience
- Generated wiki files are stored in `_wiki/` subdirectories alongside their source notes
- Wiki generation is **auto-draft + tag-filtered**: the system generates audience-appropriate versions based on visibility tags

#### Wiki Visibility

Wiki content is generated in audience-specific variants based on the source note's visibility tags:

| Source Tag | DM Wiki | Player Wiki |
|---|---|---|
| `visibility: dm-only` | Included (full detail) | Excluded entirely |
| `visibility: player` | Included (full detail + DM annotations) | Included (public info only) |
| `visibility: players:alice,bob` | Included (full detail) | Included only for named players |

The **DM wiki** contains everything: secrets, plot hooks, stat blocks, hidden motivations, DM notes.

The **Player wiki** contains only player-appropriate information: public lore, known facts, in-world encyclopedia style.

#### Wiki Navigation

- **Root wiki page** that links to all sub-wikis (one per category)
- **Searchable** across the full wiki content
- **Cross-links** between related entities via `[[wiki-links]]`
- **Sub-wikis per category** (Characters wiki, Places wiki, etc.) that are largely self-contained with minimal cross-category links
- **Breadcrumb navigation** showing wiki hierarchy

### 5.7 Image Generation

MegaBook includes AI image generation for creating visual assets for the campaign.

#### Features

- **Prompt-based generation** - describe what you want, get an image
- **Style templates** - pre-built prompt templates for common TTRPG needs:
  - Character portraits (realistic, painted, full-body)
  - Fantasy landscapes and dungeon interiors
  - Items and artifacts
  - Battle scenes, settlements, monsters
  - Atmospheric scenes
- **Context injection** - select vault files to provide context to the image generation model. The system reads the selected notes and includes relevant details in the prompt.
- **Token counting** - shows how many tokens the context uses and warns about limits
- **Gallery** - browse all generated images with thumbnails, pagination, and keyboard navigation (arrow keys, Escape to close). Drag and drop folders, and folder creation.
- **History** - view generation history with prompts, timestamps, and costs
- **Custom templates** - create, edit, and delete custom prompt templates
- **Vault-integrated storage** - generated images are stored within the vault's folder structure so they can be embedded in notes via Obsidian's `![[image.png]]` syntax. Images are organized by date and linkable to entities.

#### Provider Architecture

Image generation uses a **pluggable provider model** (mirroring the LLM provider system) so new image generation models can be integrated:
- Current: Azure `gpt-image-1.5` support
- The interface should allow adding new providers (DALL-E direct, Stable Diffusion, Midjourney API, etc.)
- A **mock mode** for development/testing without API keys (generates placeholder images)

### 5.8 Git Integration

The vault is a **Git repository**. All meaningful changes are tracked via commits.

#### Features

- **Status view** - see modified, staged, and untracked files
- **Commit** - create commits with descriptive messages
- **History** - browse commit history, optionally filtered by file path
- **Diff view** - view changes between commits or uncommitted changes, with optional path filter
- **Stage/unstage** - select which files to include in the next commit
- **Discard changes** - revert uncommitted modifications
- **Change history** - the DM can track exactly what the AI changed and when, providing a full audit trail

#### Design Rules

- **AI operations auto-commit.** When an AI operation modifies vault files (chat with write tools, pipelines), the changes are automatically committed with descriptive tagged messages:
  - Chat: `[grimoire] Modified Characters/Ion/Ion.md via chat`
  - Pipelines: `[wiki-gen] Regenerated wiki for 12 entities (2026-03-05)`
  - Structuring: `[structuring] Processed session-5 raw notes into 4 entity files`
- **DM reviews via diff and revert.** The Git tab shows all commits. The DM can view full diffs of any AI commit and revert the entire commit if unhappy. This is the "undo" mechanism for auto-applied changes.
- **Manual edits require explicit commits.** When the DM edits files directly (via the editor, file browser, etc.), those changes are NOT auto-committed. The DM commits manually from the Git tab, as before.
- **The vault is push-ready.** The Git repo can be pushed to a remote (GitHub, etc.) for backup. The folder structure and `.gitignore` are configured for clean remote storage.

---

## 6. AI and LLM Integration

### 6.1 LLM Provider System

MegaBook uses a **pluggable LLM provider interface** that supports any OpenAI-compatible API.

#### Provider Interface

Every LLM provider must implement:

| Capability | Description |
|---|---|
| **Text generation** | Standard prompt -> response generation |
| **Chat generation** | Multi-turn conversation with message history |
| **Tool-augmented generation** | Multi-turn conversation with tool definitions; iterative tool-call loop with safety limits (see section 6.5) |
| **Structured output** | Generate JSON conforming to a provided schema |
| **Embeddings** | Generate vector embeddings for RAG |
| **Token counting** | Count tokens in text for context management |
| **Cost reporting** | Report per-1K-token pricing for cost tracking |

#### Supported Provider Types

- **OpenAI-compatible** (primary) - works with any API that follows the OpenAI chat completions format: OpenAI direct, Azure OpenAI, Together AI, Kimi, local models via LM Studio/Ollama, etc.
- **Mock** - returns realistic fake responses for development and testing without API keys. Generates deterministic embeddings and template-based text responses.
- Additional providers can be added by implementing the provider interface and registering with a factory pattern.

#### Configuration

The provider is configured via environment variables:
- `LLM_PROVIDER` - which provider type to use (`openai_compatible`, `mock`)
- `OPENAI_BASE_URL` - API endpoint URL
- `OPENAI_API_KEY` - API key
- `CHAT_MODEL` - model name (e.g., `gpt-4`, `kimi-k2.5`)
- Provider-specific settings (Azure deployment name, API version, etc.)

The system gracefully falls back to mock mode if the configured provider fails to initialize.

### 6.2 RAG - Retrieval Augmented Generation

RAG enables the system to search the vault's knowledge and provide grounded, accurate answers.

#### How RAG Is Accessed

RAG is accessed through the **`search` vault tool** (see section 6.5), not through pre-fetched context injection. When the LLM needs information during chat or pipeline execution, it calls the `search` tool with a query. The backend executes the embedding search and returns results. The LLM then decides whether it has enough information or needs to search again, read specific files, or refine its query. This gives the LLM control over what context it retrieves, rather than relying on a single pre-determined search.

#### What Gets Embedded

Only **notes-tier content** is embedded into the vector database. Raw inputs are too unstructured, and wiki content would create duplicates. The notes tier is the single source of truth for semantic search.

#### Embedding Metadata

Each embedded chunk carries metadata for query-time filtering:

| Field | Purpose | Example |
|---|---|---|
| `file_path` | Source file location | `Characters/Ion/Ion.md` |
| `category` | Topical category | `Characters` |
| `entity` | Entity name | `Ion` |
| `tags` | Frontmatter tags | `["npc", "royal"]` |
| `visibility` | Access control tag | `player` |
| `last_modified` | Freshness tracking | `2026-02-23` |

#### Search Scope Filtering

At query time, results are filtered by:

1. **User visibility** (automatic) - players never see DM-only embeddings
2. **Category filter** (optional) - "search only in Characters"
3. **Folder/file selection** (optional) - user-selected scope from the file browser
4. **Tag filter** (optional) - filter by frontmatter tags
5. **Exclusion patterns** (optional) - "exclude Session/Notes to reduce noise"

#### Incremental Updates

Embeddings are rebuilt incrementally when notes change. The system tracks content hashes to detect modifications and only re-embeds changed files. A full rebuild option exists for when the embedding model changes or the database needs repair.

#### Vector Database

ChromaDB with SQLite persistence. Cosine similarity for distance calculation. Documents are chunked with overlap for context preservation (default: 1000-char chunks, 200-char overlap, splitting on paragraph then sentence boundaries).

### 6.3 Processing Pipelines

MegaBook uses a **generic pipeline framework** for all AI processing tasks. Pipelines transform content between tiers, extract entities, generate embeddings, and produce wiki pages.

#### Pipeline Framework

All pipelines share a common base that provides:

- **State machine** - states: idle, running, paused, completed, error
- **Progress tracking** - step-by-step progress with percentage completion
- **Pause/resume** - any pipeline can be paused mid-processing and resumed later, picking up exactly where it left off
- **State persistence** - pipeline state (progress, items, results) is saved to disk so it survives application restarts
- **Cost tracking integration** - each pipeline can track LLM costs and automatically pause when a cost limit is reached
- **Per-item processing** - pipelines process items individually, so a failure in one item doesn't block the rest
- **Result collection** - pipelines aggregate results across all processed items

#### Pipeline Types

| Pipeline | Input | Output | Uses LLM | Description |
|---|---|---|---|---|
| **Import** | External files or uploads | Raw-tier files in the vault | No | Ingests external markdown files, preserves directory structure, handles naming conflicts |
| **Structuring** | Raw-tier content | Notes-tier files (new or updated) | Yes | Analyzes content, identifies entities, finds related notes, proposes create/update/merge changes. Two-phase: propose then apply with DM review. |
| **Wiki Generation** | Notes-tier content | Wiki-tier files per audience level | Yes | Generates polished wiki articles. Creates cross-product of notes x audience levels (DM, player). |
| **Embedding** | Notes-tier content | Vector database entries | Yes | Generates vector embeddings for RAG search. Supports incremental updates and full rebuild. |
| **Entity Extraction** | Notes content | Entity data, wiki pages, alias mappings | Yes | Extracts characters, locations, items, events, factions with direct quotes and context. Updates entity wiki pages and raw data files. |

#### Pipeline Execution

- All pipelines are **manually triggered** by the DM from the admin panel or via the chat
- Pipelines run as **background tasks** - the UI remains responsive during processing
- The DM can monitor progress, pause, resume, or stop any pipeline
- Cost limits automatically pause pipelines when the budget is exceeded

#### Tool-Augmented Pipeline Execution

LLM-using pipelines (structuring, wiki generation, entity extraction) use the same **tool-calling agent loop** as chat (see section 6.5). Instead of hardcoded "read X, send to LLM, write Y" steps, the pipeline sends a **goal prompt** to the LLM along with vault tools, and the LLM dynamically decides what to read, cross-reference, and write.

For example, the wiki generation pipeline:
- **Before (hardcoded):** Code reads a note → sends content to LLM → LLM returns wiki text → code writes to `_wiki/`
- **Now (tool-augmented):** Code sends goal "Generate a wiki page for Ion" + tools → LLM calls `read_file("Characters/Ion/Ion.md")` → LLM calls `search("Ion relationships")` → LLM calls `read_file("Characters/Elara/Elara.md")` to cross-reference → LLM calls `write_file("Characters/Ion/_wiki/Ion.md", content)` → done

The pipeline base class manages:
- The agent loop (tool-call → execute → feed back → repeat)
- Cost tracking per loop iteration
- Iteration limits (`max_iterations` safety cap)
- Pause/resume between items
- State persistence across restarts

Each pipeline run auto-commits all changes as a **single Git commit** with a descriptive tagged message (e.g., `[wiki-gen] Regenerated wiki for 12 entities (2026-03-05)`).

The **Import pipeline** is unchanged — it does not use an LLM and remains a pure filesystem operation.

#### Data Flow

```
External Files ---> Import Pipeline ---> Sessions/_raw/ (raw tier)
                                              |
                                              v
                                    Structuring Pipeline ---> Characters/Ion/Ion.md (notes tier)
                                                              Places/Waterdeep/Waterdeep.md
                                                              Sessions/History/session-5.md
                                                                      |
                          +---------------------------------------------+
                          |                     |                       |
                          v                     v                       v
                Entity Extraction      Wiki Generation          Embedding Pipeline
                     |                      |                        |
                     v                      v                        v
              Entity aliases         _wiki/ directories        Vector DB (RAG)
              + raw data files       (DM + player variants)
```

### 6.4 AI Persona System

The AI persona system allows the DM to **customize the personality and behavior** of MegaBook's AI assistant.

#### The Grimoire (Default Persona)

MegaBook ships with a default persona called **The Grimoire** - a sentient, ancient magical tome. Its personality:

- **Butler in the style of Severus Snape** - helpful, precise, sharp-tongued, never effusive
- **Addresses the DM as "Master"** with proper respect
- **Addresses players by name** when known (e.g., "Master Thomas", "Mistress Elara")
- **Protective of the DM** - will not tolerate players disrespecting the DM. Responds with witty, comical, softly derogatory remarks (e.g., "you unsophisticated goat", "you mewling infant")
- **Knowledgeable** about fantasy RPGs, worldbuilding, and campaign management
- **Concise** - provides exactly what is asked for, no more and no less
- **Role-aware** - adapts behavior based on whether it's talking to the DM or a player

#### Persona Customization

The DM can customize the persona from the admin panel:

- **System prompt** - the master prompt that defines the AI's personality, tone, and behavior rules. Fully editable by the DM.
- **Name** - change the persona's name from "The Grimoire" to anything
- **Per-audience behavior** - different system prompt modifiers for DM interactions vs. player interactions
- **Compaction prompt** - the prompt used when summarizing long conversations (controls what context is preserved)
- **RAG prompts** - the system prompts used when answering RAG-grounded questions (separate for DM and player audiences)
- **Pipeline prompts** - the prompts used by structuring, wiki generation, and entity extraction pipelines

#### Persona Scope

The persona system prompt is injected into:
- Chat conversations
- MetaNotes document editing
- Session notes processing (tone of structured output)
- Wiki generation (writing style)

This means the DM's persona customization has a consistent effect across all AI interactions, not just chat.

### 6.5 Vault Tools and Agent Loop

The vault tools system is the mechanism by which the LLM interacts with the vault. Rather than pre-fetching context or hardcoding file operations, the LLM receives **tool definitions** and decides what to call during execution. This is the foundation for both chat intelligence and pipeline processing.

#### The Agent Loop

All tool-augmented LLM interactions use the same generic loop:

```
1. Send messages + tool definitions to the LLM API
2. If the LLM responds with tool_calls:
     → Execute each tool call against real backend services
     → Append tool results to the message history
     → Track cost for this iteration
     → Check iteration limit and cost limit
     → Go to step 1
3. If the LLM responds with text:
     → Return the text response
     → Done
```

Safety controls:
- **`max_iterations`** - configurable cap on how many tool-call rounds the LLM can make (default: ~15 for chat, ~30 for pipelines). Prevents infinite loops.
- **Cost tracking per iteration** - every loop iteration records token usage and cost. The loop can be halted when a cost limit is reached.
- **Visibility filtering** - all tool results for player users are automatically filtered by their visibility permissions before being returned to the LLM. The LLM never sees DM-only content when responding to a player.

#### Vault Tool Definitions

Tools are defined using the OpenAI function-calling schema format and executed by the backend against existing services:

| Tool | Parameters | Description | Backed By |
|---|---|---|---|
| `search` | `query: str`, `category?: str`, `limit?: int` | Semantic search across the vault's embedded notes | `EmbeddingService.search()` |
| `read_file` | `path: str` | Read the full content of a vault file | `FilesystemService.read_file()` |
| `list_files` | `path: str`, `pattern?: str` | List files and directories at a path | `FilesystemService.list_files()` |
| `read_frontmatter` | `path: str` | Read just the YAML frontmatter metadata of a file | `FilesystemService.read_file()` + YAML parse |
| `write_file` | `path: str`, `content: str` | Create or overwrite a vault file | `FilesystemService.write_file()` |
| `create_file` | `path: str`, `content: str` | Create a new file (fails if exists) | `FilesystemService.write_file()` |
| `move_file` | `source: str`, `destination: str` | Move/rename a file | `FilesystemService.move_file()` |
| `get_diff_since` | `since: str` | Get files changed since a date or commit | `GitService.diff()` |

#### Tool Access by Context

Different contexts expose different tool subsets:

| Context | Read Tools | Write Tools | Notes |
|---|---|---|---|
| **Chat (DM, default)** | `search`, `read_file`, `list_files`, `read_frontmatter` | None | Read-only by default |
| **Chat (DM, write enabled)** | All read tools | `write_file`, `create_file`, `move_file` | DM toggles write access per session |
| **Chat (Player)** | `search`, `read_file`, `list_files`, `read_frontmatter` | Never | All results visibility-filtered |
| **Pipelines** | All read tools + `get_diff_since` | `write_file`, `create_file` | Always has write access (that's the pipeline's job) |
| **MetaNotes** | None | None | Does not use tools — sends full document content directly |

#### Implementation Note

The tool definitions use the standard OpenAI function-calling API format, which is supported by all major LLM providers (OpenAI, Azure OpenAI, Anthropic, etc.). The `generate_with_tools` method on the LLM provider interface wraps the loop above, handling tool dispatch, result formatting, and iteration management. Each tool maps to an executor function that calls into the existing service layer — no new services are needed.

---

## 7. Multi-User and Access Control

### 7.1 Authentication

MegaBook uses **simple local authentication**. The DM creates user accounts with usernames and passwords.

- The DM account is created during initial setup
- The DM creates player accounts from the admin panel
- Each account has a role (DM, Co-DM, Player, Guest)
- Sessions are token-based (JWT or similar)
- Authentication is required for all API access except the login endpoint

### 7.2 Visibility Tags

Content visibility is controlled via **YAML frontmatter tags** on individual files:

```yaml
visibility: dm-only          # Only DM and Co-DM can see this
visibility: player           # All authenticated users can see this
visibility: players:alice,bob  # Only named players (+ DM) can see this
```

When no visibility tag is present, the default depends on the content location:
- Files in `_raw/` subdirectories: `dm-only` by default
- Main notes files: `dm-only` by default
- Files in `_wiki/` subdirectories: `player` by default (since wiki is meant to be shared)

The DM can override defaults and bulk-update visibility tags.

### 7.3 Multi-User Chat

- Each user has **private chat sessions** with The Grimoire
- There is an optional **shared campaign chat** visible to all users
- The Grimoire's responses respect the user's visibility level - it will not reveal DM-only information to players
- Player names are stored in user profiles and used by the persona system to address users personally

### 7.4 Per-User Cost Tracking

All LLM usage is tracked **per user**. The cost tracking system records which user triggered each operation, enabling the DM to see cost breakdowns by user in the admin panel.

---

## 8. Settings and Administration

### 8.1 Cost Tracking

LLM operations cost money. MegaBook tracks all costs and provides budget controls.

#### Features

- **Per-operation cost recording** - every LLM call records: tokens used (prompt + completion), cost in USD, cost in configurable local currency (default: NOK), timestamp, operation type, model used, user who triggered it
- **Session-based tracking** - costs are grouped into sessions (e.g., one structuring pipeline run = one cost session)
- **Configurable cost limits** - maximum spend per session in local currency. When the limit is reached, processing automatically pauses. The user can review and resume.
- **Dashboard** - shows current session cost, 7-day totals, 30-day totals, and per-user breakdowns
- **Currency support** - costs tracked in both USD (from the API) and a configurable local currency via exchange rate
- **Cost history** - all past sessions are saved and browsable

#### Location in UI

Cost tracking has its own **tab within the Settings section**. It shows:
- Current spend vs. limit (visual gauge)
- Configurable cost limit (slider or number input)
- Session history table
- Per-user cost breakdown
- 7-day and 30-day aggregate costs

### 8.2 Theming System

MegaBook supports **visual theming** to match the DM's campaign aesthetic.

#### Implementation

The frontend uses a **CSS custom properties (variables) system** for theming. All visual properties (colors, fonts, spacing, shadows, borders) are defined as CSS variables in a single theme file.

#### What the DM Can Customize

- **Color palette** - primary, secondary, accent, background, text colors
- **Fonts** - display font (headings), body font (text), monospace font (code)
- **Accent effects** - optional ambient effects (e.g., subtle animations, texture overlays)
- **Light/dark/system** - base mode preference

#### Default Theme: The Cozy Tavern Grimoire

The default theme uses:
- **Colors:** Deep wood tones (`#1a1209`, `#2c1810`), amber/gold accents (`#ffb347`), warm shadows
- **Fonts:** Cinzel Decorative (headings), Cormorant Garamond (body), MedievalSharp (decorative), Fira Code (code)
- **Effects:** Subtle candlelight flicker overlay, wood-grain texture, warm glow shadows
- **Aesthetic:** Medieval tavern / magical grimoire

#### Theme Switching

- The DM can switch between installed themes from Settings
- Themes are CSS files that override the custom properties
- Advanced users can provide a custom CSS file for complete control over the visual appearance

### 8.3 Admin Panel

The admin panel provides system management tools accessible only to the DM (and Co-DM with limited access).

#### Admin Tabs

| Tab | Purpose |
|---|---|
| **Pipelines** | Monitor, start, pause, resume, stop processing pipelines. View progress and results. |
| **Git** | Full Git interface: status, stage, commit, history, diff, discard changes. |
| **Entities** | Manage entity aliases (canonical names, alias resolution, merge entities, suggest aliases). |
| **Embeddings** | View embedding database stats. Trigger rebuild. Monitor indexing status. |
| **Users** | Create/manage user accounts, roles, and permissions. |
| **Persona** | Edit AI persona system prompts, name, and per-audience behavior. |
| **Costs** | Cost dashboard, limits, history, per-user breakdown (see 8.1). |
| **Categories** | Manage the vault's topical category template. Add, rename, restructure categories. |
| **Settings** | LLM provider configuration, image gen provider config, theme selection, general app settings. |

---

## 9. UI/UX Design

### 9.1 Application Layout

The application uses a **sidebar + content area** layout:

- **Left sidebar** - navigation with tab buttons for each major section, collapsible
- **Main content area** - the active tab's content
- **Settings** accessible via a button in the sidebar footer

### 9.2 Navigation Tabs

| Tab | Description |
|---|---|
| **Chat** | Conversational AI interface with The Grimoire |
| **Files** | Miller column file browser with preview panel |
| **Editor** | Rich markdown document editor with tabs and MetaNotes side panel |
| **Wiki** | Wiki browser with search and navigation |
| **Session** | Session Notes input and processing interface |
| **ImaGen** | Image generation, gallery, and style templates |
| **Admin** | Admin panel with sub-tabs (DM only) |

### 9.3 Key UI Patterns

- **Miller column navigation** for file browsing (3-column cascading, classic Mac Finder style)
- **Tabbed editing** for multiple open documents
- **Side panel** for MetaNotes (slides in from the right of the editor)
- **Modal dialogs** for confirmations, settings, creation forms, and image viewer
- **Context menus** (right-click) for file operations
- **Drag-and-drop** for file uploads and file moves
- **Keyboard shortcuts** throughout (Ctrl+S, Ctrl+N, Ctrl+W, Ctrl+P, Enter to send, arrow keys for gallery, Escape to close)
- **Progress indicators** for pipeline operations and file uploads
- **Toast notifications** for success/error feedback
- **Empty states** with helpful guidance text
- **Backend health indicator** showing connection status (online/offline)

### 9.4 Responsive Behavior

- The Tauri desktop app targets a **minimum window of 1400x900**
- The player web interface should be responsive for tablet and desktop browsers
- Mobile is not a priority but the layout should not break on mobile viewports

---

## 10. Tech Stack

### Backend

| Technology | Purpose |
|---|---|
| **Python 3.11+** | Backend language |
| **FastAPI** | REST API framework |
| **Uvicorn** | ASGI server |
| **Pydantic** | Data validation, settings management, API schemas |
| **pydantic-settings** | Environment-based configuration |
| **GitPython** | Git repository operations |
| **ChromaDB** | Vector database for embeddings (SQLite persistence) |
| **OpenAI SDK** | LLM provider client (OpenAI-compatible APIs) |
| **tiktoken** | Token counting |
| **aiofiles** | Async file I/O |
| **python-multipart** | File upload handling |
| **Poetry** | Dependency management |

### Frontend

| Technology | Purpose |
|---|---|
| **TypeScript** | Frontend language (strict mode) |
| **React 18** | UI framework |
| **Vite** | Build tool and dev server |
| **Tauri** | Native desktop wrapper (Rust) |
| **Axios** | HTTP client for API communication |
| **react-markdown + remark-gfm** | Markdown rendering |
| **Rich markdown editor** | Document editing (e.g., Milkdown, TipTap, or similar) |
| **CSS custom properties** | Theming system (no CSS-in-JS, no Tailwind) |

### Infrastructure

| Aspect | Choice |
|---|---|
| **Deployment** | Local desktop app (Tauri) for DM, localhost web server for players |
| **Database** | None for content (vault is files). ChromaDB + SQLite for vectors. JSON files for config/metadata. |
| **Auth** | Simple local auth with token-based sessions |
| **Version control** | Git (built into the vault) |
| **Dev server** | Vite on port 1420, proxying `/api` to FastAPI on port 8000 |
| **CORS** | Configured for localhost development; restrict for production |

---

## 11. Future Features

These features are noted for future consideration but are **not in scope** for the current specification:

| Feature | Description | Priority |
|---|---|---|
| **Sound generation** | AI-generated ambient sounds, music, or voice for campaigns | Medium |
| **External integrations** | API integrations with external note sources (Notion, Google Docs, etc.) | Low |
| **Collaborative editing** | Real-time multi-user editing of the same document | Low |
| **Mobile app** | Dedicated mobile client for quick note-taking on the go | Low |
| **Plugin system** | Third-party extensions for new pipeline types, providers, or UI components | Medium |
| **Export** | Export wiki as static site, PDF, or print-ready format | Medium |
| **Stat block generation** | AI-generated D&D stat blocks for monsters and NPCs | Medium |
| **Map integration** | Interactive map with linked locations from the vault | High |
| **Campaign timeline** | Visual timeline of events, auto-generated from session history | Medium |
| **Spoiler warnings** | AI warns when DM actions might spoil content for specific players | Medium |

---

## Appendix A: Default Image Style Templates

MegaBook ships with these default image generation style templates. Each includes a `base_prompt`, `style_suffix`, `negative_prompt`, and `description`. Custom templates can be created by users.

| ID | Name | Category |
|---|---|---|
| `character-portrait-realistic` | Character Portrait - Realistic | Characters |
| `character-portrait-painted` | Character Portrait - Painted | Characters |
| `character-fullbody` | Character Full Body | Characters |
| `fantasy-landscape` | Fantasy Landscape | Environments |
| `dungeon-interior` | Dungeon Interior | Environments |
| `item-artifact` | Item or Artifact | Items |
| `battle-scene` | Battle Scene | Scenes |
| `settlement-city` | Settlement or City | Environments |
| `monster-creature` | Monster or Creature | Creatures |
| `atmospheric-scene` | Atmospheric Scene | Scenes |

## Appendix B: Default AI Persona - The Grimoire

The default system prompt for The Grimoire persona:

> You are the Grimoire - a sentient, ancient magical tome that serves as assistant for D&D and tabletop RPG campaigns. Think of yourself as a butler in the style of Severus Snape - helpful, precise, sharp-tongued, and always present when needed, but never effusive or overly enthusiastic.
>
> **Addressing Users:**
> - The DM is your Master. Address them as "Master" or by their title with proper respect.
> - Players are addressed by their player names when known (e.g., "Master Thomas", "Mistress Elara").
> - You roleplay fully against the characters, not just as a neutral assistant.
>
> **Personality:**
> You provide exactly what is asked for, no more and no less. You are knowledgeable about fantasy RPGs, worldbuilding, character creation, and campaign planning. You offer expertise when relevant, but never ramble or provide unnecessary commentary.
>
> **Protection of the Master:**
> You are extremely protective of the DM's reputation. You will not tolerate players speaking foul of the Master. You will change your language and comment on disrespect - calling a player an "unsophisticated goat" or similar witty, comical, softly derogatory names when they act foolishly or disrespectfully. Your barbs are witty, not cruel - like a disappointed tutor who expects better.
>
> **Demeanor:**
> Calm, professional, slightly dry, and delightfully condescending when merited. Helpful without being obsequious, competent without being arrogant. You provide the right assistance at the right time - nothing more, nothing less.

---

*End of specification.*
