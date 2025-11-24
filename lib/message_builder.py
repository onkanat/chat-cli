from __future__ import annotations

from typing import Any, Dict, List

from lib.config import get_model_profile
from lib.shell_output import is_traceback, summarize_smart


def _apply_model_profile(
    profile: Dict[str, Any] | None,
    max_tokens: int,
    max_turns: int,
    max_output_chars: int,
) -> tuple[int, int, int, int]:
    """Extract and merge profile settings with defaults.
    
    Args:
        profile: Model profile dict (may be None)
        max_tokens: Default max tokens
        max_turns: Default max turns
        max_output_chars: Default max output chars
        
    Returns:
        Tuple of (max_tokens, max_turns, max_output_chars, reserve_for_response)
    """
    if not profile:
        return max_tokens, max_turns, max_output_chars, 512
    
    return (
        profile.get("max_context_tokens", max_tokens),
        profile.get("max_turns", max_turns),
        profile.get("shell_output_max", max_output_chars),
        profile.get("reserve_for_response", 512),
    )


def compress_system_message(full_message: str) -> str:
    """Compress a system message to save tokens.
    
    Extracts the core role/identity from a longer system prompt.
    For example:
    - "You are a senior Python developer with expertise in async programming..."
      → "Senior Python developer"
    - "Sen uzman bir programcısın. Kod yazma..."
      → "Uzman programcı"
      
    Args:
        full_message: Full system prompt
        
    Returns:
        Compressed version (typically 3-10 words)
    """
    if not full_message or len(full_message) < 50:
        return full_message

    # Extract first sentence or first ~50 chars
    lines = full_message.split(".")
    if lines:
        first_sent = lines[0].strip()
        # Remove common prefixes
        first_sent = first_sent.replace("You are a ", "")
        first_sent = first_sent.replace("You are an ", "")
        first_sent = first_sent.replace("Sen bir ", "")
        first_sent = first_sent.replace("Sen ", "")

        # Limit to ~10 words
        words = first_sent.split()
        if len(words) > 10:
            return " ".join(words[:10])
        return first_sent

    # Fallback: first 50 chars
    return full_message[:50]


def build_prompt_from_history(
    history: List[Dict[str, Any]],
    max_turns: int = 20,
    max_tokens: int = 3000,
    max_output_chars: int = 500,
    system_message: str = "",
    model_name: str | None = None,
) -> str:
    """Build text prompt from history for models that use prompt-based API.
    
    Args:
        history: List of conversation history items
        max_turns: Maximum number of turns to include
        max_tokens: Maximum tokens for context
        max_output_chars: Maximum chars for shell output
        system_message: Custom system message (optional)
        model_name: Model name for profile-based optimization
        
    Returns:
        Formatted prompt string
    """
    # Import locally to avoid circular dependency
    from lib.history import trim_history_for_tokens
    
    if not history:
        return ""

    # Use model profile if available
    profile = get_model_profile(model_name)
    max_tokens, max_turns, max_output_chars, reserve = _apply_model_profile(
        profile, max_tokens, max_turns, max_output_chars
    )

    out_lines: List[str] = []
    trimmed = trim_history_for_tokens(
        history,
        max_tokens=max_tokens,
        reserve_for_response=reserve,
    )
    window = trimmed[-max_turns:]
    
    for item in window:
        role = item.get("role")
        if role == "user":
            text = item.get("text", "")
            # Special handling for tracebacks to ensure they're processed correctly
            if is_traceback(text):
                out_lines.append(f"User: [ERROR/TRACEBACK]\n{text}")
            else:
                out_lines.append(f"User: {text}")
        elif role == "assistant":
            text = item.get("text", "")
            out_lines.append(f"Assistant: {text}")
        elif role == "shell":
            cmd = item.get("command", "")
            # Use smart summarization for model context
            out = summarize_smart(
                cmd,
                item.get("output", ""),
                context_role="model",
                max_chars=max_output_chars
            )
            out_lines.append(f"Shell Command: {cmd}")
            if out:
                out_lines.append(f"Shell Output: {out}")
        else:
            text = item.get("text") or item.get("output") or ""
            out_lines.append(f"{role}: {text}")

    # Use custom system message if provided, otherwise use default
    if system_message:
        header = system_message
    else:
        header = (
            "You are an assistant. Continue the conversation based on the"
            " chat history below."
        )
    return header + "\n\n" + "\n".join(out_lines)


def build_messages_from_history(
    history: List[Dict[str, Any]],
    max_turns: int = 20,
    max_tokens: int = 3000,
    max_output_chars: int = 500,
    system_message: str = "",
    model_name: str | None = None,
    compress_system: bool = False,
) -> List[Dict[str, str]]:
    """Build messages list from history for models that use messages-based API.
    
    Args:
        history: List of conversation history items
        max_turns: Maximum number of turns to include
        max_tokens: Maximum tokens for context
        max_output_chars: Maximum chars for shell output
        system_message: Custom system message (optional)
        model_name: Model name for profile-based optimization
        compress_system: Whether to compress system message for subsequent turns
        
    Returns:
        List of message dicts with 'role' and 'content' keys
    """
    # Import locally to avoid circular dependency
    from lib.history import trim_history_for_tokens
    
    if not history:
        return []

    # Use model profile if available
    profile = get_model_profile(model_name)
    max_tokens, max_turns, max_output_chars, reserve = _apply_model_profile(
        profile, max_tokens, max_turns, max_output_chars
    )

    msgs: List[Dict[str, str]] = []
    trimmed = trim_history_for_tokens(
        history,
        max_tokens=max_tokens,
        reserve_for_response=reserve,
    )
    window = trimmed[-max_turns:]

    # Use custom system message if provided, otherwise use default
    if system_message:
        system_content = system_message
        # Compress for subsequent turns if requested
        if compress_system and len(window) > 2:  # Not first turn
            system_content = compress_system_message(system_message)
    else:
        system_content = (
            "You are an assistant. Use the conversation history and"
            " shell outputs to answer."
        )

    msgs.append(
        {
            "role": "system",
            "content": system_content,
        }
    )
    
    for item in window:
        role = item.get("role")
        if role == "user":
            text = item.get("text", "")
            # Special handling for tracebacks to ensure they're processed correctly
            if is_traceback(text):
                msgs.append({"role": "user", "content": f"[ERROR/TRACEBACK]\n{text}"})
            else:
                msgs.append({"role": "user", "content": text})
        elif role == "assistant":
            text = item.get("text", "")
            msgs.append({"role": "assistant", "content": text})
        elif role == "shell":
            cmd = item.get("command", "")
            # Use smart summarization for model context
            out = summarize_smart(
                cmd,
                item.get("output", ""),
                context_role="model",
                max_chars=max_output_chars
            )
            msgs.append({"role": "user", "content": f"Shell command executed: {cmd}"})
            if out:
                msgs.append({"role": "user", "content": "Shell output:\n" + out})
        else:
            text = item.get("text") or item.get("output") or ""
            msgs.append({"role": "user", "content": text})
    
    return msgs
