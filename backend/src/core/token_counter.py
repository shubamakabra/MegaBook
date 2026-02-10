"""Token counter utility for MegaBook."""
import tiktoken
from typing import List, Dict
from src.core.filesystem import FilesystemService


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken.
    
    Args:
        text: The text to count tokens for
        model: The model encoding to use (default: gpt-4)
        
    Returns:
        Number of tokens
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base (used by GPT-4, GPT-3.5, etc.)
        encoding = tiktoken.get_encoding("cl100k_base")
    
    return len(encoding.encode(text))


def count_tokens_in_files(file_paths: List[str], fs: FilesystemService) -> Dict[str, int]:
    """Count tokens in multiple files.
    
    Args:
        file_paths: List of file paths to count
        fs: Filesystem service instance
        
    Returns:
        Dictionary mapping file_path -> token_count
    """
    result = {}
    
    for path in file_paths:
        try:
            content = fs.read_file(path)
            result[path] = count_tokens(content)
        except Exception:
            result[path] = 0
    
    return result


def format_token_count(count: int) -> str:
    """Format token count for display (e.g., 125000 -> "125k").
    
    Args:
        count: Token count
        
    Returns:
        Formatted string
    """
    if count >= 1000000:
        return f"{count / 1000000:.1f}M"
    elif count >= 1000:
        return f"{count / 1000:.0f}k"
    else:
        return str(count)
