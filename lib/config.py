from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

# Config cache for model profiles
_config_cache: Dict[str, Any] | None = None
# Track last read mtime to auto-reload when config changes or CWD switches
_config_mtime: float | None = None


def load_config() -> Dict[str, Any]:
    """Load config.json with smart caching and auto-reload.

    Behavior:
    - If config.json exists and its mtime changed, re-read the file.
    - If working directory changes (common in tests), mtime mismatch triggers reload.
    - If file does not exist, cache and return an empty dict.

    Returns:
        Dict containing configuration settings. Empty dict if file doesn't exist.
    """
    global _config_cache, _config_mtime

    config_path = Path("config.json")

    # Determine current mtime (None if file missing)
    current_mtime: float | None = None
    try:
        if config_path.exists():
            current_mtime = config_path.stat().st_mtime
    except Exception:
        # On any filesystem error, fall back to re-read logic below
        current_mtime = None

    # If we have a cache and mtime hasn't changed, return cached
    if _config_cache is not None and _config_mtime == current_mtime:
        return _config_cache

    # Read or initialize config
    if current_mtime is None:
        _config_cache = {}
        _config_mtime = None
        return _config_cache

    # Load from file when available
    try:
        content = config_path.read_text(encoding="utf-8")
        _config_cache = json.loads(content)
        _config_mtime = current_mtime
        return _config_cache
    except Exception:
        _config_cache = {}
        _config_mtime = current_mtime
        return _config_cache


def save_config(cfg: Dict[str, Any]) -> None:
    """Persist configuration to config.json and update cache.

    Writes the provided dictionary to config.json with pretty formatting,
    and refreshes the in-memory cache and mtime tracker to keep subsequent
    reads consistent.
    """
    global _config_cache, _config_mtime

    config_path = Path("config.json")
    try:
        config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        _config_cache = cfg
        try:
            _config_mtime = config_path.stat().st_mtime
        except Exception:
            # If we cannot stat, leave mtime as None to force reload later
            _config_mtime = None
    except Exception:
        # Silently ignore write errors to avoid crashing the CLI
        pass


def detect_model_size(model_name: str) -> str:
    """Detect model size category from model name.
    
    Args:
        model_name: Model name string (e.g., "gemma:2b", "llama3:8b")
        
    Returns:
        Size category: "small" (<3B), "medium" (3-8B), or "large" (>8B)
    """
    if not model_name:
        return "medium"
    
    model_lower = model_name.lower()
    
    # Detect small models (1b, 2b, 3b, including decimal variants like 2.7b)
    # Match patterns like: 0.5b, 1b, 1.5b, 2b, 2.7b, 3b
    small_pattern = r'\b([0-2]\.\d+b|[0-3]b)\b'
    if re.search(small_pattern, model_lower):
        return "small"
    
    # Detect medium models (4b, 5b, 6b, 7b, 8b including decimals)
    medium_pattern = r'\b([4-8]b|[4-8]\.\d+b)\b'
    if re.search(medium_pattern, model_lower):
        return "medium"
    
    # Large models (>8B or unknown)
    return "large"


def get_profile_by_size(size: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Get profile configuration for given size category.
    
    Args:
        size: Size category ("small", "medium", or "large")
        config: Configuration dict containing model_profiles
        
    Returns:
        Profile dict with settings for the size category
    """
    profiles = config.get("model_profiles", {})
    
    default_profiles = {
        "small": {
            "max_context_tokens": 2000,
            "max_turns": 8,
            "shell_output_max": 150,
            "reserve_for_response": 300,
            "prioritize_conversation": True,
        },
        "medium": {
            "max_context_tokens": 3500,
            "max_turns": 15,
            "shell_output_max": 400,
            "reserve_for_response": 512,
            "prioritize_conversation": False,
        },
        "large": {
            "max_context_tokens": 6000,
            "max_turns": 30,
            "shell_output_max": 800,
            "reserve_for_response": 1024,
            "prioritize_conversation": False,
        },
    }
    
    return profiles.get(size, default_profiles.get(size, default_profiles["medium"]))


def get_model_profile(model_name: str | None = None) -> Dict[str, Any]:
    """Get model profile based on model size detection.
    
    Profiles:
    - small: <3B models (1b, 2b, 3b)
    - medium: 3B-8B models (7b, 8b)
    - large: >8B models or unknown
    
    Args:
        model_name: Optional model name for size detection
        
    Returns:
        Dict with profile settings:
        - max_context_tokens: Token budget for history
        - max_turns: Maximum conversation turns
        - shell_output_max: Max chars for shell output
        - reserve_for_response: Reserved tokens for model response
        - prioritize_conversation: Whether to prioritize user/assistant over shell
    """
    config = load_config()
    
    # Get context strategy
    strategy = config.get("context_strategy", "auto")
    
    # If manual, use global max_tokens
    if strategy == "manual":
        max_tokens = config.get("max_tokens", 2048)
        return {
            "max_context_tokens": max_tokens,
            "max_turns": 20,
            "shell_output_max": 500,
            "reserve_for_response": 512,
            "prioritize_conversation": False,
        }
    
    # Auto strategy - detect from model name
    if not model_name:
        # No model name, use medium profile as default
        return get_profile_by_size("medium", config)
    
    size = detect_model_size(model_name)
    return get_profile_by_size(size, config)
