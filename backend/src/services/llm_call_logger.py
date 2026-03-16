"""LLM API call logger for MegaBook.

Logs every LLM API call to daily plain-text log files.
One file per day: YYYY-MM-DD.log inside the configured log directory.
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class LLMCallLogger:
    """Logs all LLM API calls to daily plain-text files.
    
    Each day gets its own file (YYYY-MM-DD.log). Entries are appended
    as human-readable plain text blocks separated by blank lines.
    """
    
    def __init__(self, log_dir: Path) -> None:
        """Initialize the logger.
        
        Args:
            log_dir: Directory to store daily log files.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_log_path(self) -> Path:
        """Get the log file path for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"{today}.log"
    
    def _write_entry(self, entry: str) -> None:
        """Append an entry to today's log file."""
        log_path = self._get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
            f.write("\n")
    
    def _format_messages(self, messages: List[Dict[str, str]], max_content_len: int = 300) -> str:
        """Format a messages array for logging."""
        lines = []
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if len(content) > max_content_len:
                content = content[:max_content_len] + f"... [{len(content)} chars total]"
            # Replace newlines in content for single-line display
            content = content.replace("\n", "\\n")
            lines.append(f"    [{i}] {role}: {content}")
        return "\n".join(lines)
    
    def log_call(
        self,
        method: str,
        model: str,
        messages: Optional[List[Dict[str, str]]] = None,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: Optional[float] = None,
        duration_ms: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None,
        response_preview: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a single LLM API call.
        
        Args:
            method: The method called (e.g. "generate_text", "generate_chat_response")
            model: Model name/deployment
            messages: Full messages array (for chat calls)
            prompt: User prompt (for text calls)
            system_prompt: System prompt (for text calls)
            temperature: Sampling temperature used
            max_tokens: Max tokens parameter
            prompt_tokens: Input tokens used
            completion_tokens: Output tokens used
            total_tokens: Total tokens used
            cost_usd: Estimated cost in USD
            duration_ms: Call duration in milliseconds
            success: Whether the call succeeded
            error: Error message if failed
            response_preview: First N chars of the response
            extra: Any additional metadata
        """
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        lines = [
            f"{'='*80}",
            f"[{timestamp}] {method}",
            f"  Model: {model}",
        ]
        
        if temperature is not None:
            lines.append(f"  Temperature: {temperature}")
        if max_tokens is not None:
            lines.append(f"  Max Tokens: {max_tokens}")
        
        # Log input
        if messages:
            lines.append(f"  Messages ({len(messages)}):")
            lines.append(self._format_messages(messages))
        elif prompt:
            prompt_preview = prompt[:300] + f"... [{len(prompt)} chars]" if len(prompt) > 300 else prompt
            prompt_preview = prompt_preview.replace("\n", "\\n")
            lines.append(f"  Prompt: {prompt_preview}")
            if system_prompt:
                sp_preview = system_prompt[:200] + f"... [{len(system_prompt)} chars]" if len(system_prompt) > 200 else system_prompt
                sp_preview = sp_preview.replace("\n", "\\n")
                lines.append(f"  System: {sp_preview}")
        
        # Log result
        status = "OK" if success else "ERROR"
        lines.append(f"  Status: {status}")
        
        if error:
            lines.append(f"  Error: {error}")
        
        if response_preview:
            preview = response_preview[:300] + f"... [{len(response_preview)} chars]" if len(response_preview) > 300 else response_preview
            preview = preview.replace("\n", "\\n")
            lines.append(f"  Response: {preview}")
        
        # Tokens and cost
        lines.append(f"  Tokens: {prompt_tokens} in / {completion_tokens} out / {total_tokens} total")
        
        if cost_usd is not None:
            lines.append(f"  Cost: ${cost_usd:.6f} USD")
        
        if duration_ms is not None:
            lines.append(f"  Duration: {duration_ms:.0f}ms")
        
        if extra:
            for k, v in extra.items():
                lines.append(f"  {k}: {v}")
        
        lines.append("")  # blank line separator
        
        self._write_entry("\n".join(lines))
    
    def log_embeddings_call(
        self,
        model: str,
        num_texts: int,
        total_chars: int,
        duration_ms: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log an embeddings API call.
        
        Args:
            model: Model name
            num_texts: Number of texts embedded
            total_chars: Total characters across all texts
            duration_ms: Call duration in milliseconds
            success: Whether the call succeeded
            error: Error message if failed
        """
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        status = "OK" if success else "ERROR"
        lines = [
            f"{'='*80}",
            f"[{timestamp}] generate_embeddings",
            f"  Model: {model}",
            f"  Texts: {num_texts} ({total_chars} chars total)",
            f"  Status: {status}",
        ]
        
        if error:
            lines.append(f"  Error: {error}")
        if duration_ms is not None:
            lines.append(f"  Duration: {duration_ms:.0f}ms")
        
        lines.append("")
        
        self._write_entry("\n".join(lines))
