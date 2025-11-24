from __future__ import annotations

from typing import Iterable, List, Dict, Any

from lib import ollama_wrapper as ow


# Thin wrappers around ollama_wrapper to keep a stable seam

def list_models() -> List[str]:
    return ow.list_models()


def set_current_model(name: str) -> bool:
    return ow.set_current_model(name)


def load_model(name: str) -> bool:
    return ow.load_model(name)


def delete_model(name: str) -> bool:
    return ow.delete_model(name)


def chat_stream(model: str, messages: List[Dict[str, Any]]) -> Iterable[str]:
    for chunk in ow.chat_stream(model, messages):
        yield getattr(chunk, "response", str(chunk))


def generate_stream(model: str, prompt: str) -> Iterable[str]:
    for chunk in ow.generate_stream(model, prompt):
        yield getattr(chunk, "response", str(chunk))
