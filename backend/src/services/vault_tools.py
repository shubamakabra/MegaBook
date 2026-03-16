"""Vault tools for the chat agent loop.

Defines OpenAI function-calling tool schemas and an executor that runs
them against the FilesystemService. The agent loop sends these tool
definitions alongside messages so the LLM can decide to read vault files,
search for content, list directory trees, or inspect frontmatter.

**Access Control**

Every tool respects the caller's ``AccessContext``. Files declare access
via YAML frontmatter::

    ---
    access: all            # everyone
    access: dm             # DM only (same as default for untagged files)
    access: players        # all player characters
    access:                # specific characters:
      - Gandalf
      - Aragorn
    ---

Folders can set defaults with a ``.access.yaml`` file::

    # .access.yaml
    default: players       # everything in this folder defaults to player-visible
    # override per-file with frontmatter

Inline DM-only sections are stripped for non-DM users::

    %%DM-ONLY%%
    Secret plot twist here
    %%END%%

Untagged files with no folder default are **DM-only** by default.
"""
import json
import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

from src.core.filesystem import FilesystemService


# =============================================================================
# Access Control
# =============================================================================

@dataclass
class AccessContext:
    """Describes who is making the request.

    Attributes:
        is_dm: True if the user is the Dungeon Master (sees everything).
        character_name: The player's character name (e.g. "Gandalf").
                        None for DM users. Case-insensitive matching.
    """
    is_dm: bool = True
    character_name: Optional[str] = None

    @property
    def is_player(self) -> bool:
        return not self.is_dm


# Sentinel for "no access field found"
_NO_ACCESS = object()

# Regex for %%DM-ONLY%% ... %%END%% blocks (dotall, case-insensitive)
_DM_ONLY_PATTERN = re.compile(
    r"%%\s*DM[_-]?ONLY\s*%%.*?%%\s*END\s*%%",
    re.DOTALL | re.IGNORECASE,
)


def _parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
    """Parse YAML frontmatter from markdown content. Returns None if absent."""
    if not content.startswith("---"):
        return None
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return None
    yaml_text = content[3:end_idx].strip()
    try:
        return yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return None


def _get_access_field(frontmatter: Optional[Dict[str, Any]]) -> Any:
    """Extract the 'access' field from parsed frontmatter.

    Returns _NO_ACCESS sentinel if no access field is present.
    """
    if frontmatter is None:
        return _NO_ACCESS
    return frontmatter.get("access", _NO_ACCESS)


class AccessChecker:
    """Resolves whether an AccessContext may view a given file.

    Resolution order (first match wins):
      1. File-level frontmatter ``access`` field
      2. Nearest ancestor folder's ``.access.yaml`` ``default`` field
      3. Global default: DM-only
    """

    def __init__(self, filesystem: FilesystemService) -> None:
        self.fs = filesystem
        # Cache folder-level defaults: folder_relative_path -> access value
        self._folder_cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def can_access_file(self, relative_path: str, ctx: AccessContext) -> bool:
        """Check whether *ctx* is allowed to see the file at *relative_path*."""
        if ctx.is_dm:
            return True  # DM sees everything

        # Try file-level frontmatter
        access = _NO_ACCESS
        if relative_path.endswith(".md"):
            try:
                content = self.fs.read_file(relative_path)
                fm = _parse_frontmatter(content)
                access = _get_access_field(fm)
            except Exception:
                pass

        # Fall back to folder default
        if access is _NO_ACCESS:
            access = self._resolve_folder_access(relative_path)

        # Fall back to global default (DM-only)
        if access is _NO_ACCESS:
            return False  # DM-only by default

        return self._access_allows(access, ctx)

    def filter_content(self, content: str, ctx: AccessContext) -> str:
        """Strip DM-only inline sections from *content* for non-DM users."""
        if ctx.is_dm:
            return content
        return _DM_ONLY_PATTERN.sub("", content).strip()

    def filter_frontmatter(
        self, frontmatter: Dict[str, Any], ctx: AccessContext
    ) -> Dict[str, Any]:
        """Optionally strip sensitive frontmatter keys for non-DM users."""
        if ctx.is_dm:
            return frontmatter
        # Remove the access field itself (no need to expose the ACL)
        filtered = {k: v for k, v in frontmatter.items() if k != "access"}
        return filtered

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _access_allows(self, access: Any, ctx: AccessContext) -> bool:
        """Check whether an access value permits *ctx*."""
        if isinstance(access, str):
            lower = access.lower().strip()
            if lower == "all":
                return True
            if lower == "dm":
                return ctx.is_dm
            if lower == "players":
                return True  # any player character
            # Treat a single string as a character name
            if ctx.character_name and lower == ctx.character_name.lower():
                return True
            return False

        if isinstance(access, list):
            # List of character names
            if not ctx.character_name:
                return False
            char_lower = ctx.character_name.lower()
            return any(
                (isinstance(name, str) and name.lower().strip() == char_lower)
                or (isinstance(name, str) and name.lower().strip() in ("all", "players"))
                for name in access
            )

        # Unknown format — deny
        return False

    def _resolve_folder_access(self, relative_path: str) -> Any:
        """Walk up parent folders looking for .access.yaml with a ``default``."""
        parts = Path(relative_path).parts
        # Walk from innermost folder to root
        for i in range(len(parts) - 1, 0, -1):
            folder_rel = "/".join(parts[:i])
            if folder_rel in self._folder_cache:
                val = self._folder_cache[folder_rel]
                if val is not _NO_ACCESS:
                    return val
                continue

            access_file = self.fs.repo_path / folder_rel / ".access.yaml"
            if access_file.exists():
                try:
                    data = yaml.safe_load(access_file.read_text(encoding="utf-8"))
                    default = data.get("default", _NO_ACCESS) if isinstance(data, dict) else _NO_ACCESS
                    self._folder_cache[folder_rel] = default
                    if default is not _NO_ACCESS:
                        return default
                except Exception:
                    self._folder_cache[folder_rel] = _NO_ACCESS
            else:
                self._folder_cache[folder_rel] = _NO_ACCESS

        return _NO_ACCESS


# =============================================================================
# Tool Schemas (OpenAI function-calling format)
# =============================================================================

VAULT_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files and folders in the vault. Returns a directory listing. "
                "Use this to explore the vault structure and discover what content exists. "
                "Call with no arguments to see top-level contents, or provide a folder path "
                "to list its children. Only files the current user has access to are shown."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": (
                            "Folder path relative to vault root to list contents of. "
                            "Omit or use empty string for the vault root."
                        ),
                    },
                    "pattern": {
                        "type": "string",
                        "description": (
                            "Glob pattern to filter results. Default is '*' (immediate children). "
                            "Use '**/*.md' to recursively find all markdown files."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the full contents of a file from the vault. "
                "Use this to examine notes, lore entries, character sheets, session logs, etc. "
                "The path should be relative to the vault root (e.g. 'Characters/Gandalf.md'). "
                "Returns only content the current user is allowed to see."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to vault root.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_vault",
            "description": (
                "Search for files in the vault whose filename or content matches a query string. "
                "Returns a list of matching file paths with a preview snippet of matching content. "
                "Use this when looking for specific topics, characters, locations, etc. "
                "Only files the current user has access to are searched."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query — matched case-insensitively against file names and contents.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Default 10.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_frontmatter",
            "description": (
                "Read only the YAML frontmatter of a markdown file, without the body content. "
                "Useful for quickly inspecting metadata (tags, aliases, type, status, etc.) "
                "without reading the entire file. Returns parsed YAML as JSON. "
                "Only accessible if the current user has access to the file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to vault root (must be a .md file).",
                    },
                },
                "required": ["path"],
            },
        },
    },
]


# =============================================================================
# Tool Executor
# =============================================================================

# Maximum content size returned from a single tool call (characters)
MAX_FILE_CONTENT = 12000
MAX_SEARCH_SNIPPET = 200
MAX_SEARCH_RESULTS = 20


class VaultToolExecutor:
    """Executes vault tool calls against a FilesystemService instance.

    Every tool call is filtered through an ``AccessChecker`` so that
    non-DM users only see content they are allowed to access.
    """

    def __init__(
        self,
        filesystem: FilesystemService,
        access: Optional[AccessContext] = None,
    ) -> None:
        self.fs = filesystem
        self.access = access or AccessContext(is_dm=True)
        self.checker = AccessChecker(filesystem)

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool call and return the result as a string.

        Args:
            tool_name: One of the defined tool names.
            arguments: Parsed JSON arguments from the LLM.

        Returns:
            A string result to be sent back to the LLM as tool output.
        """
        try:
            if tool_name == "list_files":
                return self._list_files(
                    folder=arguments.get("folder", ""),
                    pattern=arguments.get("pattern", "*"),
                )
            elif tool_name == "read_file":
                return self._read_file(path=arguments["path"])
            elif tool_name == "search_vault":
                return self._search_vault(
                    query=arguments["query"],
                    max_results=arguments.get("max_results", 10),
                )
            elif tool_name == "read_frontmatter":
                return self._read_frontmatter(path=arguments["path"])
            else:
                return f"Error: Unknown tool '{tool_name}'"
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _list_files(self, folder: str = "", pattern: str = "*") -> str:
        """List files and directories in a vault folder."""
        search_root = self.fs.repo_path
        if folder:
            search_root = self.fs.repo_path / folder

        if not search_root.exists():
            return f"Error: Folder '{folder}' does not exist in the vault."

        if not search_root.is_dir():
            return f"Error: '{folder}' is not a directory."

        entries: List[str] = []
        try:
            for item in sorted(search_root.glob(pattern)):
                relative = str(item.relative_to(self.fs.repo_path)).replace("\\", "/")

                # Skip hidden folders
                first_part = relative.split("/")[0]
                if first_part.startswith("."):
                    continue

                if item.is_dir():
                    # Directories are always shown (access is per-file)
                    entries.append(f"  [dir]  {relative}/")
                else:
                    # Check file access
                    if not self.checker.can_access_file(relative, self.access):
                        continue
                    size_kb = item.stat().st_size / 1024
                    entries.append(f"  [file] {relative}  ({size_kb:.1f} KB)")

                if len(entries) >= 100:
                    entries.append(f"  ... (truncated, more than 100 entries)")
                    break
        except Exception as e:
            return f"Error listing '{folder}': {str(e)}"

        if not entries:
            return f"Folder '{folder or '/'}' is empty or contains no files you have access to."

        header = f"Contents of '{folder or '/'}' (pattern: {pattern}):\n"
        return header + "\n".join(entries)

    def _read_file(self, path: str) -> str:
        """Read a file's contents, with access check and DM-section stripping."""
        # Access check
        if not self.checker.can_access_file(path, self.access):
            return f"Access denied: you do not have permission to read '{path}'."

        try:
            content = self.fs.read_file(path)
        except Exception as e:
            return f"Error reading '{path}': {str(e)}"

        # Strip DM-only inline sections for non-DM users
        content = self.checker.filter_content(content, self.access)

        if len(content) > MAX_FILE_CONTENT:
            truncated = content[:MAX_FILE_CONTENT]
            return (
                f"File: {path}\n"
                f"(Truncated to first {MAX_FILE_CONTENT} characters — "
                f"full file is {len(content)} characters)\n\n"
                f"{truncated}\n\n[... truncated ...]"
            )

        return f"File: {path}\n\n{content}"

    def _search_vault(self, query: str, max_results: int = 10) -> str:
        """Search the vault for files matching a query string."""
        max_results = min(max_results, MAX_SEARCH_RESULTS)
        query_lower = query.lower()

        all_files = self.fs.list_files(pattern="**/*")
        results: List[Dict[str, str]] = []

        for file_info in all_files:
            if len(results) >= max_results:
                break

            rel_path = file_info.relative_path

            # Access check
            if not self.checker.can_access_file(rel_path, self.access):
                continue

            # Check filename match
            name_match = query_lower in rel_path.lower()

            # Check content match for text files
            content_snippet = ""
            if rel_path.endswith((".md", ".txt", ".yaml", ".yml", ".json")):
                try:
                    content = self.fs.read_file(rel_path)
                    # Strip DM sections before searching for non-DM users
                    content = self.checker.filter_content(content, self.access)
                    content_lower = content.lower()
                    idx = content_lower.find(query_lower)
                    if idx >= 0:
                        start = max(0, idx - 80)
                        end = min(len(content), idx + len(query) + 80)
                        snippet = content[start:end].replace("\n", " ").strip()
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(content):
                            snippet = snippet + "..."
                        content_snippet = snippet
                    elif not name_match:
                        continue
                except Exception:
                    if not name_match:
                        continue
            elif not name_match:
                continue

            results.append({
                "path": rel_path,
                "match_type": "name+content" if name_match and content_snippet else ("name" if name_match else "content"),
                "snippet": content_snippet,
            })

        if not results:
            return f"No accessible files found matching '{query}'."

        lines = [f"Search results for '{query}' ({len(results)} matches):"]
        for r in results:
            line = f"  - {r['path']} [{r['match_type']}]"
            if r["snippet"]:
                line += f"\n    Preview: {r['snippet'][:MAX_SEARCH_SNIPPET]}"
            lines.append(line)

        return "\n".join(lines)

    def _read_frontmatter(self, path: str) -> str:
        """Extract and return YAML frontmatter from a markdown file."""
        if not path.endswith(".md"):
            return f"Error: '{path}' is not a markdown file."

        # Access check
        if not self.checker.can_access_file(path, self.access):
            return f"Access denied: you do not have permission to read '{path}'."

        try:
            content = self.fs.read_file(path)
        except Exception as e:
            return f"Error reading '{path}': {str(e)}"

        if not content.startswith("---"):
            return f"File '{path}' has no YAML frontmatter."

        end_idx = content.find("---", 3)
        if end_idx == -1:
            return f"File '{path}' has malformed frontmatter (no closing ---)."

        yaml_text = content[3:end_idx].strip()
        try:
            parsed = yaml.safe_load(yaml_text) or {}
            # Filter frontmatter for non-DM users
            parsed = self.checker.filter_frontmatter(parsed, self.access)
            return f"Frontmatter for '{path}':\n{json.dumps(parsed, indent=2, default=str)}"
        except yaml.YAMLError as e:
            return f"Error parsing YAML frontmatter in '{path}': {str(e)}"
