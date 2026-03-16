"""Chat API routes with conversation history support."""
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.dependencies import get_llm_provider, get_filesystem
from src.core import settings
from src.utils import CHAT_SYSTEM_PROMPT, CHAT_COMPACTION_PROMPT
from src.services.vault_tools import VAULT_TOOLS, VaultToolExecutor, AccessContext
from src.services.llm_provider import UsageInfo

router = APIRouter()

# Context window sizes for known models (in tokens)
MODEL_CONTEXT_WINDOWS = {
    "kimi-k2.5": 131072,       # Kimi K2.5: 128K context
    "kimi-k2": 131072,
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4.1": 1047576,        # GPT-4.1: ~1M context
    "gpt-4.1-mini": 1047576,
    "gpt-3.5-turbo": 16385,
    "o1": 200000,
    "o1-mini": 128000,
    "o3": 200000,
    "o3-mini": 200000,
    "o4-mini": 200000,
}

DEFAULT_CONTEXT_WINDOW = 128000  # Safe default for unknown models


def get_context_window(model: str) -> int:
    """Get the context window size for a model."""
    model_lower = model.lower()
    for key, window in MODEL_CONTEXT_WINDOWS.items():
        if key in model_lower:
            return window
    return DEFAULT_CONTEXT_WINDOW


# Simple file-based chat history storage
CHAT_HISTORY_DIR = settings.meta_path / "chat_history"
CHAT_META_DIR = settings.meta_path / "chat_meta"


def get_chat_file(chat_id: str) -> Path:
    """Get the file path for a chat session."""
    CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_HISTORY_DIR / f"{chat_id}.json"


def get_meta_file(chat_id: str) -> Path:
    """Get the metadata file path for a chat session."""
    CHAT_META_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_META_DIR / f"{chat_id}.json"


def load_chat_history(chat_id: str) -> List[Dict]:
    """Load chat history from file."""
    chat_file = get_chat_file(chat_id)
    if chat_file.exists():
        with open(chat_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_chat_history(chat_id: str, messages: List[Dict]):
    """Save chat history to file."""
    chat_file = get_chat_file(chat_id)
    with open(chat_file, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)


def load_chat_meta(chat_id: str) -> Optional[Dict]:
    """Load metadata for a chat session."""
    meta_file = get_meta_file(chat_id)
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_chat_meta(chat_id: str, meta: Dict):
    """Save metadata for a chat session."""
    meta_file = get_meta_file(chat_id)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def delete_chat_meta(chat_id: str):
    """Delete metadata file for a chat session."""
    meta_file = get_meta_file(chat_id)
    if meta_file.exists():
        meta_file.unlink()


def generate_chat_title(first_message: str) -> str:
    """Generate a short title from the first user message."""
    # Take first 60 chars, cut at last word boundary
    title = first_message.strip().replace("\n", " ")
    if len(title) > 60:
        title = title[:60].rsplit(" ", 1)[0] + "..."
    return title


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp")


class ChatSessionInfo(BaseModel):
    """Summary info for a chat session (used in session list)."""
    id: str = Field(..., description="Chat session UUID")
    title: str = Field(..., description="Short title derived from first message")
    created_at: str = Field(..., description="ISO timestamp when chat was created")
    updated_at: str = Field(..., description="ISO timestamp of last activity")
    message_count: int = Field(default=0, description="Number of messages in the conversation")
    preview: str = Field(default="", description="Preview of the first user message")


class ChatSessionListResponse(BaseModel):
    """Response for listing chat sessions."""
    sessions: List[ChatSessionInfo] = Field(..., description="List of chat sessions, sorted newest first")


class ConversationChatRequest(BaseModel):
    """Chat request with conversation history."""
    message: str = Field(..., description="New message from user")
    chat_id: Optional[str] = Field(default=None, description="Chat session ID (omit for new chat)")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Previous messages (alternative to chat_id)")
    access_mode: str = Field(default="dm", description="Access mode: 'dm' or 'player'")
    character_name: Optional[str] = Field(default=None, description="Player's character name (required when access_mode='player')")


class RenameSessionRequest(BaseModel):
    """Request to rename a chat session."""
    title: str = Field(..., description="New title for the chat session")


class CompactRequest(BaseModel):
    """Request to compact/summarize a chat session."""
    chat_id: str = Field(..., description="Chat session ID to compact")


class CompactResponse(BaseModel):
    """Response from a chat compaction."""
    new_chat_id: str = Field(..., description="New chat session ID with compacted history")
    old_chat_id: str = Field(..., description="Original chat session ID (preserved)")
    summary: str = Field(..., description="The compacted summary content")
    history: List[ChatMessage] = Field(..., description="New chat history (just the summary message)")
    prompt_tokens: int = Field(..., description="Tokens used in the compaction request")
    context_window: int = Field(..., description="Context window size for the model")


class ToolUsageInfo(BaseModel):
    """Information about a single tool invocation during the agent loop."""
    tool_name: str = Field(..., description="Name of the tool that was called")
    arguments: Dict[str, Any] = Field(..., description="Arguments passed to the tool")
    result_preview: str = Field("", description="First ~200 chars of the tool result")


class ConversationChatResponse(BaseModel):
    """Chat response with conversation history."""
    content: str = Field(..., description="AI response content")
    model: str = Field(..., description="Model used")
    tokens_used: int = Field(..., description="Total tokens used across all iterations")
    prompt_tokens: int = Field(..., description="Tokens used by the prompt/context sent to the model")
    completion_tokens: int = Field(..., description="Tokens used by the model's response")
    context_window: int = Field(..., description="Maximum context window size for the model")
    chat_id: str = Field(..., description="Chat session ID")
    history: List[ChatMessage] = Field(..., description="Full conversation history")
    tool_usage: List[ToolUsageInfo] = Field(default_factory=list, description="Tools invoked during this response")
    agent_iterations: int = Field(default=1, description="Number of LLM calls made (1 = no tools used)")





@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_chat_sessions():
    """List all chat sessions with metadata, sorted by most recent first.
    
    Scans both the chat_meta directory and chat_history directory.
    Sessions with metadata are returned directly.
    Orphan history files (no metadata) get backfilled metadata automatically.
    """
    sessions: List[ChatSessionInfo] = []
    
    # Collect all known chat IDs from both directories
    meta_ids = set()
    CHAT_META_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load sessions that have metadata
    for meta_file in CHAT_META_DIR.glob("*.json"):
        chat_id = meta_file.stem
        meta_ids.add(chat_id)
        try:
            meta = load_chat_meta(chat_id)
            if meta:
                sessions.append(ChatSessionInfo(
                    id=chat_id,
                    title=meta.get("title", "Untitled Chat"),
                    created_at=meta.get("created_at", ""),
                    updated_at=meta.get("updated_at", ""),
                    message_count=meta.get("message_count", 0),
                    preview=meta.get("preview", ""),
                ))
        except Exception as e:
            print(f"[SESSIONS] Error loading meta for {chat_id}: {e}")
    
    # Backfill orphan history files that have no metadata
    for history_file in CHAT_HISTORY_DIR.glob("*.json"):
        chat_id = history_file.stem
        if chat_id in meta_ids:
            continue  # Already have metadata
        
        try:
            history = load_chat_history(chat_id)
            if not history:
                continue
            
            # Find first user message for title/preview
            first_user_msg = next((m["content"] for m in history if m.get("role") == "user"), "")
            title = generate_chat_title(first_user_msg) if first_user_msg else "Untitled Chat"
            preview = first_user_msg[:120] + ("..." if len(first_user_msg) > 120 else "") if first_user_msg else ""
            
            # Use file modification time as a fallback
            file_stat = history_file.stat()
            created_at = datetime.fromtimestamp(file_stat.st_ctime).isoformat()
            updated_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            # Save backfilled metadata
            meta = {
                "title": title,
                "created_at": created_at,
                "updated_at": updated_at,
                "message_count": len(history),
                "preview": preview,
            }
            save_chat_meta(chat_id, meta)
            
            sessions.append(ChatSessionInfo(
                id=chat_id,
                title=title,
                created_at=created_at,
                updated_at=updated_at,
                message_count=len(history),
                preview=preview,
            ))
            print(f"[SESSIONS] Backfilled metadata for orphan chat {chat_id[:8]}...")
        except Exception as e:
            print(f"[SESSIONS] Error backfilling {chat_id}: {e}")
    
    # Sort by updated_at descending (newest first)
    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    
    return ChatSessionListResponse(sessions=sessions)


@router.patch("/sessions/{chat_id}", response_model=ChatSessionInfo)
async def rename_chat_session(chat_id: str, request: RenameSessionRequest):
    """Rename a chat session."""
    meta = load_chat_meta(chat_id)
    if not meta:
        # Check if history exists at least
        history = load_chat_history(chat_id)
        if not history:
            raise HTTPException(status_code=404, detail="Chat session not found")
        # Create minimal metadata
        now = datetime.now().isoformat()
        meta = {
            "title": request.title,
            "created_at": now,
            "updated_at": now,
            "message_count": len(history),
            "preview": "",
        }
    
    meta["title"] = request.title
    meta["updated_at"] = datetime.now().isoformat()
    save_chat_meta(chat_id, meta)
    
    return ChatSessionInfo(
        id=chat_id,
        title=meta["title"],
        created_at=meta["created_at"],
        updated_at=meta["updated_at"],
        message_count=meta.get("message_count", 0),
        preview=meta.get("preview", ""),
    )


@router.post("/conversation", response_model=ConversationChatResponse)
async def conversation_chat(request: ConversationChatRequest):
    """Chat endpoint with full conversation history and vault tool-calling.
    
    Implements an agent loop: sends messages + vault tool definitions to the
    LLM. If the LLM returns tool_calls, executes them and loops. When the
    LLM returns text content, the loop ends and the response is returned.
    
    Either provide chat_id to continue an existing conversation,
    or provide history array to send specific context.
    If neither is provided, a new chat session is created.
    """
    import time
    
    MAX_AGENT_ITERATIONS = 8  # Safety cap on tool-calling loops
    
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"[CHAT] [Conversation] New message received")
    print(f"   Message: {request.message[:100]}{'...' if len(request.message) > 100 else ''}")
    
    llm_provider = get_llm_provider()
    filesystem = get_filesystem()
    
    if not llm_provider:
        print(f"   [ERROR] LLM provider is None!")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=503, 
            detail="LLM provider not available. Check backend logs for initialization errors."
        )
    
    print(f"   [OK] LLM provider: {llm_provider.model}")
    
    # Build access context from request
    is_dm = request.access_mode.lower() != "player"
    access_ctx = AccessContext(
        is_dm=is_dm,
        character_name=request.character_name if not is_dm else None,
    )
    char_display = request.character_name or "unnamed"
    print(f"   [ACCESS] Mode: {'DM' if is_dm else f'Player ({char_display})'}")
    
    # Only enable tools if filesystem is available and provider supports them
    has_tools = filesystem is not None and hasattr(llm_provider, "generate_chat_with_tools")
    tool_executor = VaultToolExecutor(filesystem, access=access_ctx) if filesystem else None
    tools = VAULT_TOOLS if has_tools else None
    
    if has_tools:
        print(f"   [TOOLS] Vault tools enabled ({len(VAULT_TOOLS)} tools)")
    else:
        reason = "no filesystem" if not filesystem else "provider lacks generate_chat_with_tools"
        print(f"   [TOOLS] Vault tools disabled ({reason})")
    
    # Get or create chat session
    chat_id = request.chat_id or str(uuid.uuid4())
    
    # Load existing history or use provided history
    if request.history:
        # Use provided history
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
        print(f"   [HISTORY] Using provided history: {len(history)} messages")
    else:
        # Load from file or start fresh
        history = load_chat_history(chat_id)
        print(f"   [HISTORY] Loaded from file: {len(history)} messages")
    
    # Build messages array with system prompt + history + new message
    user_type = "DM" if is_dm else "PLAYER"
    player_name = request.character_name or "N/A"
    system_prompt = CHAT_SYSTEM_PROMPT.format(user_type=user_type, player_name=player_name)
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": request.message})
    
    print(f"   [CONTEXT] Total messages to send: {len(messages)}")
    
    try:
        # === Agent Loop ===
        total_usage = UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        tool_usage_log: List[ToolUsageInfo] = []
        iteration = 0
        final_content = ""
        response_model = llm_provider.model
        
        while iteration < MAX_AGENT_ITERATIONS:
            iteration += 1
            print(f"   [AGENT] Iteration {iteration}/{MAX_AGENT_ITERATIONS}")
            
            if has_tools:
                # Use the tool-calling variant
                result = await llm_provider.generate_chat_with_tools(
                    messages=messages,
                    tools=tools,
                    temperature=0.7,
                    max_tokens=2000,
                )
                total_usage = total_usage + result.usage
                response_model = result.model
                
                if result.tool_calls:
                    # LLM wants to use tools — execute them and loop
                    print(f"   [AGENT] LLM requested {len(result.tool_calls)} tool call(s)")
                    
                    # Append the assistant message with tool_calls to the conversation
                    assistant_msg: Dict[str, Any] = {
                        "role": "assistant",
                        "content": result.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function_name,
                                    "arguments": tc.arguments,
                                },
                            }
                            for tc in result.tool_calls
                        ],
                    }
                    messages.append(assistant_msg)
                    
                    # Execute each tool call and append results
                    for tc in result.tool_calls:
                        try:
                            args = json.loads(tc.arguments)
                        except json.JSONDecodeError:
                            args = {}
                        
                        print(f"   [TOOL] Executing {tc.function_name}({json.dumps(args)[:100]})")
                        assert tool_executor is not None  # guaranteed by has_tools check
                        tool_result = tool_executor.execute(tc.function_name, args)
                        print(f"   [TOOL] Result: {tool_result[:150]}...")
                        
                        # Log tool usage for the response
                        tool_usage_log.append(ToolUsageInfo(
                            tool_name=tc.function_name,
                            arguments=args,
                            result_preview=tool_result[:200],
                        ))
                        
                        # Append tool result message
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_result,
                        })
                    
                    # Continue the loop — LLM will see tool results next iteration
                    continue
                else:
                    # No tool calls — LLM returned final text
                    final_content = result.content or ""
                    break
            else:
                # Fallback: no tools, use the simple chat response method
                response = await llm_provider.generate_chat_response(
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000,
                )
                total_usage = total_usage + response.usage
                response_model = response.model
                final_content = response.content
                break
        else:
            # Hit max iterations — use whatever content we have, or explain
            print(f"   [AGENT] Hit max iterations ({MAX_AGENT_ITERATIONS})")
            if not final_content:
                final_content = (
                    "I apologize — I was exploring your vault files but ran out of "
                    "processing steps. Here is what I found so far based on the tools "
                    "I used. Please ask again if you need more detail."
                )
        
        duration = time.time() - start_time
        
        # Update history with new exchange (only user message + final assistant text)
        history.append({"role": "user", "content": request.message})
        history.append({"role": "assistant", "content": final_content})
        
        # Save updated history
        save_chat_history(chat_id, history)
        
        # Update session metadata
        now = datetime.now().isoformat()
        existing_meta = load_chat_meta(chat_id)
        if existing_meta:
            existing_meta["updated_at"] = now
            existing_meta["message_count"] = len(history)
            save_chat_meta(chat_id, existing_meta)
        else:
            first_user_msg = request.message
            meta = {
                "title": generate_chat_title(first_user_msg),
                "created_at": now,
                "updated_at": now,
                "message_count": len(history),
                "preview": first_user_msg[:120] + ("..." if len(first_user_msg) > 120 else ""),
            }
            save_chat_meta(chat_id, meta)
        
        # Convert history to ChatMessage objects for response
        response_history = [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in history
        ]
        
        print(f"   [OK] Response generated in {duration:.2f}s ({iteration} iteration(s), {len(tool_usage_log)} tool calls)")
        print(f"   [TOKENS] Total tokens: {total_usage.total_tokens}")
        print(f"   [HISTORY] Saved {len(history)} messages to chat {chat_id[:8]}...")
        print(f"{'='*60}\n")
        
        context_window = get_context_window(response_model)
        
        return ConversationChatResponse(
            content=final_content,
            model=response_model,
            tokens_used=total_usage.total_tokens,
            prompt_tokens=total_usage.prompt_tokens,
            completion_tokens=total_usage.completion_tokens,
            context_window=context_window,
            chat_id=chat_id,
            history=response_history,
            tool_usage=tool_usage_log,
            agent_iterations=iteration,
        )
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        print(f"   [ERROR] Error after {duration:.2f}s: {error_msg}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        # Provide helpful error message based on error type
        if "404" in error_msg:
            detail = f"Azure endpoint not found (404). Error: {error_msg}"
        elif "401" in error_msg or "403" in error_msg:
            detail = f"Authentication failed. Check your AZURE_API_KEY. Error: {error_msg}"
        elif "429" in error_msg:
            detail = f"Rate limit exceeded. Please wait and try again. Error: {error_msg}"
        else:
            detail = f"LLM error: {error_msg}"
        
        raise HTTPException(status_code=500, detail=detail)


@router.get("/history/{chat_id}", response_model=List[ChatMessage])
async def get_chat_history(chat_id: str):
    """Get the conversation history for a specific chat session."""
    history = load_chat_history(chat_id)
    return [ChatMessage(role=msg["role"], content=msg["content"]) for msg in history]


@router.delete("/history/{chat_id}")
async def delete_chat_history(chat_id: str):
    """Delete a chat session's history and metadata."""
    chat_file = get_chat_file(chat_id)
    if chat_file.exists():
        chat_file.unlink()
        delete_chat_meta(chat_id)
        return {"message": f"Chat history {chat_id} deleted"}
    raise HTTPException(status_code=404, detail="Chat history not found")


@router.post("/compact", response_model=CompactResponse)
async def compact_chat(request: CompactRequest):
    """Compact a chat session by summarizing the full conversation into a new thread.

    Loads the full history for chat_id, sends it to the LLM with a compaction
    prompt, then creates a new chat session containing just the summary as the
    first assistant message. The old chat is left untouched.
    """
    import time

    start_time = time.time()
    chat_id = request.chat_id
    print(f"\n{'='*60}")
    print(f"[COMPACT] Starting compaction for chat {chat_id[:8]}...")

    # Load existing history
    history = load_chat_history(chat_id)
    if not history:
        raise HTTPException(status_code=404, detail="Chat session not found or has no history")

    # Load existing metadata for title
    old_meta = load_chat_meta(chat_id)
    old_title = old_meta.get("title", "Untitled Chat") if old_meta else "Untitled Chat"

    # Get LLM provider
    llm_provider = get_llm_provider()
    if not llm_provider:
        raise HTTPException(
            status_code=503,
            detail="LLM provider not available. Check backend logs for initialization errors."
        )

    # Build the compaction messages:
    # 1. System = compaction instructions
    # 2. All user/assistant messages as context
    # 3. Final user message requesting the compaction
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": CHAT_COMPACTION_PROMPT}
    ]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": "Compact this conversation now. Produce the structured summary."
    })

    print(f"   [CONTEXT] Sending {len(history)} messages for compaction")

    try:
        response = await llm_provider.generate_chat_response(
            messages=messages,
            temperature=0.3,  # Lower temperature for factual summary
            max_tokens=4000,
        )

        summary = response.content
        duration = time.time() - start_time

        # Create new chat session
        new_chat_id = str(uuid.uuid4())

        # The new history contains a single assistant message with the [COMPACTED] marker
        compacted_marker = f"[COMPACTED] Summary of conversation from thread {chat_id[:8]}...\n\n"
        new_history = [
            {"role": "assistant", "content": compacted_marker + summary}
        ]

        # Save new chat history
        save_chat_history(new_chat_id, new_history)

        # Save new metadata
        now = datetime.now().isoformat()
        new_meta = {
            "title": f"Compacted: {old_title}",
            "created_at": now,
            "updated_at": now,
            "message_count": 1,
            "preview": f"Compacted from {len(history)} messages",
        }
        save_chat_meta(new_chat_id, new_meta)

        context_window = get_context_window(response.model)

        print(f"   [OK] Compaction done in {duration:.2f}s")
        print(f"   [TOKENS] Compaction used {response.usage.total_tokens} tokens")
        print(f"   [NEW] New thread {new_chat_id[:8]}... created")
        print(f"{'='*60}\n")

        response_history = [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in new_history
        ]

        return CompactResponse(
            new_chat_id=new_chat_id,
            old_chat_id=chat_id,
            summary=summary,
            history=response_history,
            prompt_tokens=response.usage.prompt_tokens,
            context_window=context_window,
        )

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        print(f"   [ERROR] Compaction failed after {duration:.2f}s: {error_msg}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        raise HTTPException(status_code=500, detail=f"Compaction failed: {error_msg}")
