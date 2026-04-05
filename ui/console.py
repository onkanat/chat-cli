from __future__ import annotations

import subprocess
from typing import Any, Dict, List, Iterator

from rich.console import Console

import lib.history as history_mod
import requests

console = Console()


def to_text(x: object) -> str:
    if isinstance(x, bytes):
        try:
            return x.decode("utf-8", errors="replace")
        except Exception:
            return x.decode("utf-8", errors="replace")
    # Extract response field from StreamCompletion objects
    if hasattr(x, "response") and getattr(x, "response", None) is not None:
        return str(getattr(x, "response"))
    try:
        return str(x)
    except Exception:
        try:
            return repr(x)
        except Exception:
            return ""


def search_history(
    history: List[Dict[str, Any]], query: str, max_results: int = 10
) -> List[Dict[str, Any]]:
    """Search conversation history for query string."""
    if not query or not history:
        return []

    query_lower = query.lower()
    results = []

    for item in history:
        # Search in text content
        text = item.get("text", "")
        if text and query_lower in text.lower():
            # Calculate relevance score
            score = 0
            if query_lower in text.lower():
                score += text.lower().count(query_lower) * 10
            if query_lower in text.lower()[:50]:  # Bonus for early matches
                score += 5

            results.append(
                {
                    "item": item,
                    "score": score,
                    "context": text[:100] + "..." if len(text) > 100 else text,
                }
            )

        # Search in shell commands
        elif item.get("role") == "shell":
            cmd = item.get("command", "")
            if cmd and query_lower in cmd.lower():
                results.append(
                    {
                        "item": item,
                        "score": 15,  # Higher score for exact command matches
                        "context": f"Command: {cmd}",
                    }
                )

    # Sort by relevance score
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:max_results]


import importlib


_ATTR_MODULES = {
    # Renderers
    "render_markdown": "ui.renderers",
    "display_search_results": "ui.renderers",
    "display_token_usage": "ui.renderers",
    "display_model_status": "ui.renderers",
    "display_statistics": "ui.renderers",
    "export_conversation": "ui.renderers",
    # Inputs
    "select_model_menu": "ui.inputs",
    "clear_screen": "ui.inputs",
    # Stream display
    "create_progress_tracker": "ui.stream_display",
}


def __getattr__(name: str):
    module_name = _ATTR_MODULES.get(name)
    if module_name:
        mod = importlib.import_module(module_name)
        return getattr(mod, name)
    raise AttributeError(name)


def run_shell_command(command: str) -> str:
    """Execute shell command with better security and error handling."""
    if not command.strip():
        return ""
    
    # Basic security check - this is still a shell, so we can't block everything,
    # but we can prevent obvious accidents or malicious pastes if desired.
    # For now, we'll just ensure it's not empty and handle timeouts.
    
    try:
        completed = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True,
            timeout=60  # 60s timeout
        )
        out = completed.stdout or completed.stderr
        return out
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds."
    except Exception as e:
        return f"Error running command: {e}"


def get_model_reply_stream(
    prompt_or_history,
    max_tokens: int = history_mod.DEFAULT_MAX_CONTEXT_TOKENS,
    max_output_chars: int = history_mod.DEFAULT_MAX_OUTPUT_CHARS,
    system_message: str = "",
    model_name: str | None = None,
) -> Iterator[str]:
    # Phase 3.2: Redirect generation to Omni-Daemon REST API
    try:
        # We find the last user message from history for the query, but we pass the full constructed text
        # usually full_prompt is basically just what the user typed + history format. We will use the simplest text.
        # Omni-Daemon expects the user's latest query mainly for embedding semantic search.
        latest_query = "Assistant prompt"
        if isinstance(prompt_or_history, list) and len(prompt_or_history) > 0:
            latest_query = prompt_or_history[-1].get("text", "")
        elif isinstance(prompt_or_history, str):
            latest_query = prompt_or_history

        url = "http://localhost:8000/api/v1/stream"
        payload = {
            "query": latest_query,
            "system_prompt": system_message,
            "model": model_name,
            "stream": True,
            "top_k": 5
        }
        
        with requests.post(url, json=payload, stream=True, timeout=(10.0, 600.0)) as resp:
            resp.raise_for_status()
            chunk_count = 0
            for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    # It's a plain text stream, we just yield the decoded text
                    # (Fallback in case it still says 'data: ' from accidental SSE structure)
                    chunk_str = chunk.replace('data: ', '')
                    if chunk_str:
                        chunk_count += 1
                        yield chunk_str
                        
            if chunk_count == 0:
                 yield "[No response from model]"
    except requests.exceptions.RequestException as e:
        yield f"[Omni-Daemon Error: {e}]"
    except Exception as e:
        yield f"[Stream error: {e}]"


def get_model_reply_sync(
    prompt_or_history,
    max_tokens: int = history_mod.DEFAULT_MAX_CONTEXT_TOKENS,
    max_output_chars: int = history_mod.DEFAULT_MAX_OUTPUT_CHARS,
    system_message: str = "",
    model_name: str | None = None,
) -> str:
    # Phase 3.2: Redirect generation to Omni-Daemon REST API
    try:
        latest_query = "Assistant prompt"
        if isinstance(prompt_or_history, list) and len(prompt_or_history) > 0:
            latest_query = prompt_or_history[-1].get("text", "")
        elif isinstance(prompt_or_history, str):
            latest_query = prompt_or_history

        url = "http://localhost:8000/api/v1/generate"
        payload = {
            "query": latest_query,
            "system_prompt": system_message,
            "model": model_name,
            "stream": False,
            "top_k": 5
        }

        resp = requests.post(url, json=payload, timeout=(10.0, 600.0))
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "[stub reply] (no ollama response)")
    except requests.exceptions.RequestException as e:
        return f"[Omni-Daemon Error: {e}]"
    except Exception:
        pass

    return "[stub reply] (no response)"
