from __future__ import annotations

import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Defaults kept here so tests can import functions from main that delegate
DEFAULT_MAX_CONTEXT_TOKENS = int(
    __import__("os").getenv("OLLAMA_MAX_CONTEXT_TOKENS", "16384")
)
DEFAULT_MAX_OUTPUT_CHARS = int(
    __import__("os").getenv("OLLAMA_MAX_OUTPUT_CHARS", "4000")
)

logger = logging.getLogger(__name__)

# =============================================================================
# Token Management (Core Responsibility)
# =============================================================================

def estimate_tokens(text: str) -> int:
    """Estimate token count for text using tiktoken or heuristic fallback.
    
    Args:
        text: Text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    try:
        import tiktoken  # type: ignore

        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            try:
                enc = tiktoken.encoding_for_model("gpt-4")
                return len(enc.encode(text))
            except Exception:
                pass
    except Exception:
        pass
    return max(1, len(text) // 4)


def trim_history_for_tokens(
    history: List[Dict[str, Any]],
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    reserve_for_response: int = 512,
) -> List[Dict[str, Any]]:
    """Trim history to fit within token budget.
    
    Keeps most recent messages that fit within the token budget.
    
    Args:
        history: Full conversation history
        max_tokens: Maximum tokens for context
        reserve_for_response: Tokens to reserve for model response
        
    Returns:
        Trimmed history list
    """
    if not history:
        return []
    budget = max(0, max_tokens - reserve_for_response)
    kept: List[Dict[str, Any]] = []
    acc = 0
    for item in reversed(history):
        role = item.get("role")
        if role == "user" or role == "assistant":
            text = item.get("text", "")
        elif role == "shell":
            text = (
                (item.get("command", "") or "") + "\n" + (item.get("output", "") or "")
            )
        else:
            text = item.get("text") or item.get("output") or ""
        tokens = estimate_tokens(str(text))
        if acc + tokens > budget and kept:
            break
        acc += tokens
        kept.append(item)
    return list(reversed(kept))


def optimize_history_item_for_model(
    item: Dict[str, Any], model_name: str | None = None
) -> Dict[str, Any]:
    """Optimize a single history item for model context.
    
    This creates an optimized version of the history item suitable for sending to the model,
    while keeping the original intact for archiving.
    
    Args:
        item: Original history item
        model_name: Model name for profile-based optimization
        
    Returns:
        Optimized copy of the item
    """
    from lib.config import get_model_profile
    from lib.shell_output import summarize_smart
    
    optimized = item.copy()

    if item.get("role") == "shell":
        # Get profile for smart shell output sizing
        profile = get_model_profile(model_name)
        max_chars = profile.get("shell_output_max", 500) if profile else 500

        # Apply smart summarization for model context
        cmd = item.get("command", "")
        output = item.get("output", "")

        optimized["output"] = summarize_smart(
            command=cmd,
            output=output,
            context_role="model",
            max_chars=max_chars
        )

    return optimized


def build_model_history_from_full(
    full_history: List[Dict[str, Any]],
    model_name: str | None = None
) -> List[Dict[str, Any]]:
    """Build optimized model history from full history.
    
    This is useful when loading an archived session and need to create
    the optimized version for model context.
    
    Args:
        full_history: Complete history with full shell outputs
        model_name: Model name for profile-based optimization
        
    Returns:
        Optimized history suitable for model context
    """
    return [optimize_history_item_for_model(item, model_name) for item in full_history]


# =============================================================================
# Re-exports from new modules (Backward Compatibility)
# =============================================================================

# Config module
from lib.config import get_model_profile, load_config as _load_config

# Shell output module
from lib.shell_output import (
    is_traceback as _is_traceback,
    is_safe_to_drop as _is_safe_to_drop,
    has_errors as _has_errors,
    extract_error_summary as _extract_error_summary,
    summarize_output as summarize_shell_output,
    summarize_smart as summarize_shell_output_smart,
)

# Message builder module
from lib.message_builder import (
    build_prompt_from_history as build_model_prompt_from_history_full,
    build_messages_from_history as build_model_messages_from_history,
    compress_system_message,
)

# Session manager module
from lib.session_manager import (
    SESSIONS_DIR,
    ensure_sessions_dir as _ensure_sessions_dir,
    create_session as create_new_session,
    list_sessions,
    load_session,
    delete_session,
    save_history,
    load_history,
)

# Backward compatibility aliases for old underscore names
_estimate_tokens = estimate_tokens
_trim_history_for_tokens = trim_history_for_tokens


# Expose config cache access for tests (backward compatibility)
def _get_config_cache():
    """Get config cache reference."""
    import config as cfg
    return cfg._config_cache


def _set_config_cache(value):
    """Set config cache value."""
    import config as cfg
    cfg._config_cache = value


# For backward compatibility, allow tests to access _config_cache directly
# This uses module __getattr__ and __setattr__ magic


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Constants
    "DEFAULT_MAX_CONTEXT_TOKENS",
    "DEFAULT_MAX_OUTPUT_CHARS",
    "SESSIONS_DIR",
    # Token management
    "estimate_tokens",
    "trim_history_for_tokens",
    "_estimate_tokens",  # Backward compat
    "_trim_history_for_tokens",  # Backward compat
    # Config
    "get_model_profile",
    "_load_config",
    # Shell output
    "_is_traceback",
    "_is_safe_to_drop",
    "_has_errors",
    "_extract_error_summary",
    "summarize_shell_output",
    "summarize_shell_output_smart",
    # Message building
    "build_model_prompt_from_history_full",
    "build_model_messages_from_history",
    "compress_system_message",
    # Session management
    "_ensure_sessions_dir",
    "create_new_session",
    "list_sessions",
    "load_session",
    "delete_session",
    "save_history",
    "load_history",
    # Optimization
    "optimize_history_item_for_model",
    "build_model_history_from_full",
]


# Module-level __getattr__ and __setattr__ for backward compatibility
def __getattr__(name):
    """Allow access to _config_cache from config module."""
    if name == "_config_cache":
        import config as cfg
        return cfg._config_cache
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __setattr__(name, value):
    """Allow setting _config_cache in config module."""
    if name == "_config_cache":
        import config as cfg
        cfg._config_cache = value
    else:
        globals()[name] = value
