"""
Minimal wrapper for official ollama Python package.

Replaces 969 lines of ollama_client_helpers.py + client.py with ~60 lines.
Uses official ollama package (https://github.com/ollama/ollama-python).
"""

from __future__ import annotations

from typing import Iterator, List, Optional

from ollama import Client
from ollama._types import ChatResponse, GenerateResponse, ListResponse


# Module state
_client: Optional[Client] = None
DEFAULT_BASE_URL = "http://localhost:11434"


def _normalize_host(host: str) -> str:
    """Normalize host by removing trailing slashes and '/api' suffix if present."""
    if not host:
        return DEFAULT_BASE_URL
    h = host.strip()
    while h.endswith("/"):
        h = h[:-1]
    if h.endswith("/api"):
        h = h[: -len("/api")]
    return h or DEFAULT_BASE_URL


def init_client(base_url: str | None = None) -> Client:
    """Initialize ollama client with optional custom base URL."""
    global _client
    host = _normalize_host(base_url or DEFAULT_BASE_URL)
    _client = Client(host=host)
    return _client


def get_client() -> Client:
    """Get current client, initializing if needed."""
    global _client
    if _client is None:
        _client = Client()
    return _client


def list_models() -> List[str]:
    """List available local models."""
    try:
        response: ListResponse = get_client().list()
        return [model.model for model in response.models]
    except Exception:
        return []


def delete_model(name: str) -> bool:
    """Delete a model by name."""
    try:
        get_client().delete(name)
        return True
    except Exception:
        return False


def load_model(name: str) -> bool:
    """Pull/load a model by name."""
    try:
        get_client().pull(name)
        return True
    except Exception:
        return False


def chat_stream(
    model: str,
    messages: list,
) -> Iterator[str]:
    """Stream chat responses, yielding message content."""
    try:
        stream = get_client().chat(model=model, messages=messages, stream=True)
        for chunk in stream:
            if hasattr(chunk, 'message') and hasattr(chunk.message, 'content'):
                content = chunk.message.content
                if content:
                    yield content
    except Exception as e:
        yield f"Error: {e}"


def chat_sync(
    model: str,
    messages: list,
) -> str:
    """Synchronous chat, returns full response."""
    try:
        response: ChatResponse = get_client().chat(model=model, messages=messages)
        return response.message.content
    except Exception as e:
        return f"Error: {e}"


def generate_stream(
    model: str,
    prompt: str,
) -> Iterator[str]:
    """Stream generate responses, yielding response text."""
    try:
        stream = get_client().generate(model=model, prompt=prompt, stream=True)
        for chunk in stream:
            if hasattr(chunk, 'response'):
                content = chunk.response
                if content:
                    yield content
    except Exception as e:
        yield f"Error: {e}"


def generate_sync(
    model: str,
    prompt: str,
) -> str:
    """Synchronous generate, returns full response."""
    try:
        response: GenerateResponse = get_client().generate(model=model, prompt=prompt)
        return response.response
    except Exception as e:
        return f"Error: {e}"


def set_current_model(name: str) -> bool:
    """
    Set current model (checks if model exists).
    
    Note: Official ollama package doesn't have explicit "set current" -
    this just verifies the model exists locally.
    """
    try:
        models = list_models()
        return name in models
    except Exception:
        return False


def run_ollama_cli(args: List[str]) -> tuple[int, str, str]:
    """
    Run ollama CLI command directly (fallback for special commands).
    Returns (returncode, stdout, stderr).
    """
    import shutil
    import subprocess
    
    if shutil.which("ollama") is None:
        return 127, "", "ollama CLI not found"
    cmd = ["ollama"] + args
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return (
            completed.returncode,
            str(completed.stdout),
            str(completed.stderr),
        )
    except Exception as exc:
        return 1, "", str(exc)


def run_ollama_cli_stream(args: List[str]) -> Iterator[str] | None:
    """
    Run ollama CLI command with streaming output.
    Returns iterator of lines or None if CLI not available.
    """
    import shutil
    import subprocess
    from subprocess import PIPE
    
    if shutil.which("ollama") is None:
        return None
    cmd = ["ollama"] + args
    try:
        with subprocess.Popen(
            cmd,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as p:
            for line in p.stdout:
                yield line.rstrip("\n")
            p.wait()
    except Exception:
        return None


# Export public API
__all__ = [
    'init_client',
    'get_client',
    'list_models',
    'delete_model',
    'load_model',
    'set_current_model',
    'chat_stream',
    'chat_sync',
    'generate_stream',
    'generate_sync',
    'run_ollama_cli',
    'run_ollama_cli_stream',
    'Client',
    'DEFAULT_BASE_URL',
]
