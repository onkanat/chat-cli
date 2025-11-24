#!/usr/bin/env python3
"""Ollama Chat CLI - Terminal-based chat interface with Ollama."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import typer

# Import modular components
import lib.history as history_mod
from lib.history import (
    summarize_shell_output,
    _estimate_tokens,
    _trim_history_for_tokens,
    build_model_messages_from_history,
)


from services.server_profiles import (
    DEFAULT_SERVER_CONFIG,
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_REMOTE_BASE_URL,
)


from ui.settings_menus import (
    settings_menu,
    server_settings_menu,
    _ensure_server_profiles,
    _get_server_profiles,
    _set_active_server,
    _set_server_base_url,
    _validate_base_url,
    _determine_base_url,
    _server_switch_menu,
    _server_edit_prompt,
)

# Constants
DEFAULT_HISTORY = Path("chat_history.json")
DEFAULT_CONFIG = Path("config.json")
CURRENT_MODEL: str | None = None
app = typer.Typer()


# Re-export functions for backward compatibility with tests
__all__ = [
    "summarize_shell_output",
    "_estimate_tokens",
    "_trim_history_for_tokens",
    "build_model_messages_from_history",
]


def _parse_run_args(args: List[str]) -> tuple[str | None, str | None]:
    """Parse model and prompt from a `run` style args list."""
    if not args:
        return None, None
    model = None
    prompt = None
    parts = list(args)
    if parts[0] == "run":
        parts = parts[1:]
    if parts:
        model = parts[0]
    for i, part in enumerate(parts):
        if part.startswith("--prompt="):
            prompt = part.split("=", 1)[1]
            break
        if part in {"--prompt", "-p"} and i + 1 < len(parts):
            prompt = parts[i + 1]
            break
    if prompt is None and len(parts) > 1:
        prompt = " ".join(parts[1:])
    return model, prompt


def _format_colored_status(prefix: str, value: str) -> str:
    """Return a standardized status line with a colored prefix."""
    return f"{prefix} [white]{value}[/white]"


def _format_session_entry(session: dict) -> str:
    """Build a single line showing session metadata."""
    marker = "👉" if session.get("is_current") else "  "
    name = session.get("custom_name", session["session_id"])
    model_name = session.get("model_used", "Unknown")
    return (
        f"{marker} [cyan]{session['session_id']}[/cyan] - "
        f"[white]{name}[/white] ([dim]{model_name}[/dim])"
    )


def load_config() -> dict:
    """Load configuration from file."""
    if DEFAULT_CONFIG.exists():
        try:
            with open(DEFAULT_CONFIG, "r") as f:
                data = json.load(f)
                return _ensure_server_profiles(data)
        except Exception:
            pass
    return _ensure_server_profiles({})


def save_config(config: dict) -> None:
    """Save configuration to file."""
    try:
        data = _ensure_server_profiles(config)
        with open(DEFAULT_CONFIG, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def sanitize_prompt(text: str | None) -> str:
    """Lightweight sanitization for user prompts.

    - Strip surrounding whitespace
    - Remove any standalone lines that start with '/' (slash commands)
        - If the entire prompt starts with a slash and no other content,
            return empty
    - Preserve tracebacks and error messages as regular user content
    """
    if not text:
        return ""
    s = text.strip()

    # Check if this looks like a traceback or error message
    # If so, preserve it completely as user content
    traceback_indicators = [
        "Traceback (most recent call last):",
        "Traceback:",
        "Error:",
        "Exception:",
        'File "',
        "line ",
        "in <module>",
    ]

    # If any traceback indicators are found, preserve the content
    if any(indicator in s for indicator in traceback_indicators):
        return s

    # remove lines beginning with '/'
    lines = [ln for ln in s.splitlines() if not ln.lstrip().startswith("/")]
    cleaned = "\n".join(lines).strip()
    return cleaned


@app.command()
def list_models_cmd(
    base_url: str = typer.Option(
        None,
        "--base-url",
        envvar="OLLAMA_BASE_URL",
        help="Ollama base URL (overrides env).",
    ),
) -> None:
    """List available models (uses ollama client if present)."""
    from commands.list_models import run as run_list_models

    run_list_models(base_url)


@app.command()
def chat(
    history_file: str = typer.Option(
        str(DEFAULT_HISTORY),
        help="Path to history file",
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        envvar="OLLAMA_BASE_URL",
        help="Ollama base URL (overrides env)",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Stream model output in REPL",
    ),
    max_context_tokens: int = typer.Option(
        history_mod.DEFAULT_MAX_CONTEXT_TOKENS,
        "--max-context-tokens",
        envvar="OLLAMA_MAX_CONTEXT_TOKENS",
        help="Maximum context tokens to include from history",
    ),
    max_output_chars: int = typer.Option(
        history_mod.DEFAULT_MAX_OUTPUT_CHARS,
        "--max-output-chars",
        envvar="OLLAMA_MAX_OUTPUT_CHARS",
        help="Max characters of shell output to include before summarizing",
    ),
) -> None:
    """Start an interactive chat REPL. '/' = service cmds, '!' = shell cmds."""
    from commands.chat import run as run_chat

    run_chat(
        history_file=history_file,
        base_url=base_url,
        stream=stream,
        max_context_tokens=max_context_tokens,
        max_output_chars=max_output_chars,
    )


@app.command()
def save_history_cmd(path: str = typer.Argument(str(DEFAULT_HISTORY))):
    """Save an empty history file (helper)."""
    from commands.save_history import run as run_save_history

    run_save_history(path)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
