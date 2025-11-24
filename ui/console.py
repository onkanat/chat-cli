from __future__ import annotations

import subprocess
from typing import Any, Dict, List

from rich.console import Console

import lib.history as history_mod
import lib.ollama_wrapper as ow

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
    try:
        completed = subprocess.run(command, shell=True, capture_output=True, text=True)
        out = completed.stdout or completed.stderr
        return out
    except Exception as e:
        return f"Error running command: {e}"


def get_model_reply_stream(
    prompt_or_history,
    max_tokens: int = history_mod.DEFAULT_MAX_CONTEXT_TOKENS,
    max_output_chars: int = history_mod.DEFAULT_MAX_OUTPUT_CHARS,
    system_message: str = "",
    model_name: str | None = None,
):
    if isinstance(prompt_or_history, list):
        history = prompt_or_history
        full_prompt = history_mod.build_model_prompt_from_history_full(
            history,
            max_tokens=max_tokens,
            max_output_chars=max_output_chars,
            system_message=system_message,
        )
    else:
        full_prompt = prompt_or_history

    msgs = None
    if isinstance(prompt_or_history, list):
        try:
            msgs = history_mod.build_model_messages_from_history(
                prompt_or_history,
                max_tokens=max_tokens,
                max_output_chars=max_output_chars,
                system_message=system_message,
                model_name=model_name,
            )
        except Exception:
            msgs = None

    # Use ollama_wrapper for streaming
    try:
        model = model_name
        if not model:
            models = ow.list_models()
            model = models[0] if models else None
        
        if not model:
            yield "[Error: No model available]"
            return
        
        # Try chat if we have messages, otherwise generate
        chunk_count = 0
        if msgs:
            for chunk in ow.chat_stream(model, msgs):
                chunk_count += 1
                yield to_text(chunk)
        else:
            for chunk in ow.generate_stream(model, full_prompt):
                chunk_count += 1
                yield to_text(chunk)
        
        # If no chunks received, yield error message
        if chunk_count == 0:
            yield "[No response from model]"
    except Exception as e:
        yield f"[Stream error: {e}]"


def get_model_reply_sync(
    prompt_or_history,
    max_tokens: int = history_mod.DEFAULT_MAX_CONTEXT_TOKENS,
    max_output_chars: int = history_mod.DEFAULT_MAX_OUTPUT_CHARS,
    system_message: str = "",
    model_name: str | None = None,
) -> str:
    if isinstance(prompt_or_history, list):
        history = prompt_or_history
        full_prompt = history_mod.build_model_prompt_from_history_full(
            history,
            max_tokens=max_tokens,
            max_output_chars=max_output_chars,
            system_message=system_message,
            model_name=model_name,
        )
    else:
        full_prompt = prompt_or_history

    # Use ollama_wrapper for sync generation
    try:
        models = ow.list_models()
        target_model = model_name or (models[0] if models else None)
        
        if target_model:
            # Build messages if we have history
            msgs = None
            if isinstance(prompt_or_history, list):
                try:
                    msgs = history_mod.build_model_messages_from_history(
                        prompt_or_history,
                        max_tokens=max_tokens,
                        max_output_chars=max_output_chars,
                        system_message=system_message,
                        model_name=model_name,
                    )
                except Exception:
                    msgs = None
            
            # Use chat if we have messages, otherwise generate
            if msgs:
                result = ow.chat_sync(target_model, msgs)
            else:
                result = ow.generate_sync(target_model, full_prompt)
            
            if result and not result.startswith("Error:"):
                return result.strip()
    except Exception:
        pass

    return "[stub reply] (no ollama response)"
