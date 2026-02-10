"""Chat API routes with conversation history support."""
from typing import List, Optional, Dict
from datetime import datetime
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.dependencies import get_llm_provider
from src.core import settings

router = APIRouter()

# Simple file-based chat history storage
CHAT_HISTORY_DIR = settings.meta_path / "chat_history"


def get_chat_file(chat_id: str) -> Path:
    """Get the file path for a chat session."""
    CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_HISTORY_DIR / f"{chat_id}.json"


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


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp")


class ConversationChatRequest(BaseModel):
    """Chat request with conversation history."""
    message: str = Field(..., description="New message from user")
    chat_id: Optional[str] = Field(default=None, description="Chat session ID (omit for new chat)")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Previous messages (alternative to chat_id)")


class ConversationChatResponse(BaseModel):
    """Chat response with conversation history."""
    content: str = Field(..., description="AI response content")
    model: str = Field(..., description="Model used")
    tokens_used: int = Field(..., description="Total tokens used")
    chat_id: str = Field(..., description="Chat session ID")
    history: List[ChatMessage] = Field(..., description="Full conversation history")


# System prompt for the AI assistant
SYSTEM_PROMPT = """You are a helpful AI assistant for D&D and tabletop RPG campaigns. 
You maintain conversation context and remember what has been discussed.
Help the user with worldbuilding, character creation, plot ideas, and campaign planning.
Be creative, supportive, and knowledgeable about fantasy RPGs.
When appropriate, reference previous parts of the conversation to provide continuity."""


@router.post("/conversation", response_model=ConversationChatResponse)
async def conversation_chat(request: ConversationChatRequest):
    """Chat endpoint with full conversation history support.
    
    Either provide chat_id to continue an existing conversation,
    or provide history array to send specific context.
    If neither is provided, a new chat session is created.
    """
    import time
    
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"[CHAT] [Conversation] New message received")
    print(f"   Message: {request.message[:100]}{'...' if len(request.message) > 100 else ''}")
    
    llm_provider = get_llm_provider()
    
    if not llm_provider:
        print(f"   [ERROR] LLM provider is None!")
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=503, 
            detail="LLM provider not available. Check backend logs for initialization errors."
        )
    
    print(f"   [OK] LLM provider: {llm_provider.model}")
    
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
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": request.message})
    
    print(f"   [CONTEXT] Total messages to send: {len(messages)}")
    
    try:
        print(f"   [CALL] Calling LLM with conversation context...")
        
        # Call LLM with full conversation history
        response = await llm_provider.generate_chat_response(
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        )
        
        duration = time.time() - start_time
        
        # Update history with new exchange
        history.append({"role": "user", "content": request.message})
        history.append({"role": "assistant", "content": response.content})
        
        # Save updated history
        save_chat_history(chat_id, history)
        
        # Convert history to ChatMessage objects for response
        response_history = [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in history
        ]
        
        print(f"   [OK] Response generated in {duration:.2f}s")
        print(f"   [TOKENS] Tokens: {response.usage.total_tokens}")
        print(f"   [HISTORY] Saved {len(history)} messages to chat {chat_id[:8]}...")
        print(f"{'='*60}\n")
        
        return ConversationChatResponse(
            content=response.content,
            model=response.model,
            tokens_used=response.usage.total_tokens,
            chat_id=chat_id,
            history=response_history,
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
    """Delete a chat session's history."""
    chat_file = get_chat_file(chat_id)
    if chat_file.exists():
        chat_file.unlink()
        return {"message": f"Chat history {chat_id} deleted"}
    raise HTTPException(status_code=404, detail="Chat history not found")
