from __future__ import annotations

from typing import Any, Dict

from lib.config import load_config as _load_config_impl, save_config as _save_config_impl


def load_config() -> Dict[str, Any]:
    return _load_config_impl()


def save_config(cfg: Dict[str, Any]) -> None:
    _save_config_impl(cfg)


def determine_base_url(config: Dict[str, Any], base_url_override: str | None) -> str | None:
    """Decide active base_url.

    Precedence:
    1) Explicit CLI override if provided
    2) Config server.active -> profiles[...] base_url if present
    3) None (library default)
    """
    if base_url_override:
        return base_url_override

    # Support both legacy `server` and current `ollama_servers` structures
    server = config.get("server", {})
    ollama_servers = config.get("ollama_servers", {})

    active = server.get("active") or ollama_servers.get("active")
    profiles = server.get("profiles", {}) or ollama_servers.get("profiles", {})
    if active and active in profiles:
        prof = profiles[active]
        bu = prof.get("base_url")
        if isinstance(bu, str) and bu.strip():
            return bu
    return None
