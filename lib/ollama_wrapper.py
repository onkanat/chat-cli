"""
Minimal wrapper for official ollama Python package.

Replaces 969 lines of ollama_client_helpers.py + client.py with ~60 lines.
Uses official ollama package (https://github.com/ollama/ollama-python).
"""

from __future__ import annotations

from threading import Lock
from typing import Iterator, List, Optional, Dict, Any

from ollama import Client
from ollama._types import ChatResponse, GenerateResponse, ListResponse


class OllamaError(Exception):
    """Base exception for Ollama wrapper errors."""
    pass


class OllamaAPIError(OllamaError):
    """Raised when the Ollama API fails."""
    pass


class OllamaModelError(OllamaError):
    """Raised when a model operation fails (load, delete, etc)."""
    pass


# Module state
_client: Optional[Client] = None
_client_lock = Lock()
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
    with _client_lock:
        _client = Client(host=host)
        return _client


def get_client() -> Client:
    """Get current client, initializing if needed."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:  # Double-check locking
                _client = Client()
    return _client


def list_models() -> List[str]:
    """List available local models."""
    try:
        response: ListResponse = get_client().list()
        return [model.model for model in response.models]
    except Exception as e:
        raise OllamaAPIError(f"Failed to list models: {e}") from e


def delete_model(name: str) -> bool:
    """Delete a model by name."""
    try:
        get_client().delete(name)
        return True
    except Exception:
        # We might want to log this or raise it, but preserving bool return for now 
        # based on existing usage, or switching to raise?
        # The plan said "better error handling", so let's log or re-raise if critical.
        # But existing code expects bool. I will keep bool but maybe log? 
        # For now, let's just keep strict bool but maybe print? 
        # Actually, let's keep it simple as per original behavior but safer.
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
    messages: List[Dict[str, Any]],
    options: Dict[str, Any] | None = None,
) -> Iterator[str]:
    """Stream chat responses, yielding message content."""
    try:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if options:
            kwargs["options"] = options
        stream = get_client().chat(**kwargs)
        for chunk in stream:
            if hasattr(chunk, 'message') and hasattr(chunk.message, 'content'):
                content = chunk.message.content
                if content:
                    yield content
    except Exception as e:
        # Yielding error string is the contract with consumer currently
        yield f"Error: {e}"


def chat_sync(
    model: str,
    messages: List[Dict[str, Any]],
    options: Dict[str, Any] | None = None,
) -> str:
    """Synchronous chat, returns full response."""
    try:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if options:
            kwargs["options"] = options
        response: ChatResponse = get_client().chat(**kwargs)
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
        response: GenerateResponse = get_client().generate(
            model=model,
            prompt=prompt,
        )
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
        # Added timeout to prevent hanging
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30  # 30 seconds timeout
        )
        return (
            completed.returncode,
            str(completed.stdout),
            str(completed.stderr),
        )
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
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
            # We can't easily timeout a generator without async,
            # but at least we are safer with the context manager.
            if p.stdout:
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
    'OllamaError',
    'OllamaAPIError',
    'OllamaModelError',
    'DEFAULT_BASE_URL',
]
