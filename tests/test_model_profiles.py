"""Test model profile detection and context optimization."""

from __future__ import annotations

import json
import pytest

import lib.history as history_mod


@pytest.fixture(autouse=True)
def clear_config_cache():
    """Clear config cache before each test."""
    history_mod._config_cache = None
    yield
    history_mod._config_cache = None


def test_get_model_profile_small_models():
    """Test profile detection for small models (1B-3B)."""
    small_models = [
        "gemma:2b",
        "llama3.2:1b",
        "qwen2.5-coder:1.5b-base",
        "phi:2.7b",
    ]

    for model in small_models:
        profile = history_mod.get_model_profile(model)
        assert profile["max_context_tokens"] == 2000
        assert profile["max_turns"] == 8
        assert profile["shell_output_max"] == 150
        assert profile["reserve_for_response"] == 300
        assert profile["prioritize_conversation"] is True


def test_get_model_profile_medium_models():
    """Test profile detection for medium models (4B-8B)."""
    medium_models = [
        "llama3.2:8b",
        "mistral:7b",
        "qwen2.5:7b",
        "deepseek-r1:7b",
    ]

    for model in medium_models:
        profile = history_mod.get_model_profile(model)
        assert profile["max_context_tokens"] == 3500
        assert profile["max_turns"] == 15
        assert profile["shell_output_max"] == 400
        assert profile["reserve_for_response"] == 512
        assert profile["prioritize_conversation"] is False


def test_get_model_profile_large_models():
    """Test profile detection for large models (>8B)."""
    large_models = [
        "llama3:70b",
        "mixtral:8x7b",
        "qwen2.5:14b",
        "deepseek-r1:14b",
        "unknown-model",  # Unknown should default to large
    ]

    for model in large_models:
        profile = history_mod.get_model_profile(model)
        assert profile["max_context_tokens"] == 6000
        assert profile["max_turns"] == 30
        assert profile["shell_output_max"] == 800
        assert profile["reserve_for_response"] == 1024
        assert profile["prioritize_conversation"] is False


def test_get_model_profile_none():
    """Test profile when no model name provided."""
    profile = history_mod.get_model_profile(None)
    # Should default to medium
    assert profile["max_context_tokens"] == 3500
    assert profile["max_turns"] == 15


def test_build_model_messages_with_profile():
    """Test that build_model_messages_from_history uses model profile."""
    history = [
        {"role": "user", "text": "Hello" * 100},  # ~500 chars
        {"role": "assistant", "text": "Hi there" * 100},
        {"role": "user", "text": "Question" * 100},
        {"role": "assistant", "text": "Answer" * 100},
    ]

    # Small model should trim more aggressively
    msgs_small = history_mod.build_model_messages_from_history(
        history,
        model_name="gemma:2b",
    )

    # Large model should keep more
    msgs_large = history_mod.build_model_messages_from_history(
        history,
        model_name="llama3:70b",
    )

    # Both should have system message
    assert msgs_small[0]["role"] == "system"
    assert msgs_large[0]["role"] == "system"

    # Large model should potentially keep more messages
    # (though in this case both might keep all due to short messages)
    assert len(msgs_small) >= 1  # At least system message
    assert len(msgs_large) >= 1


def test_profile_config_loading(tmp_path, monkeypatch):
    """Test that profiles are loaded from config.json."""
    # Create temporary config
    config_data = {
        "context_strategy": "auto",
        "model_profiles": {
            "small": {
                "max_context_tokens": 1500,
                "max_turns": 5,
                "shell_output_max": 100,
                "reserve_for_response": 200,
                "prioritize_conversation": True,
            }
        }
    }

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Clear cache
    history_mod._config_cache = None

    # Get profile for small model
    profile = history_mod.get_model_profile("gemma:2b")

    # Should use custom values from config
    assert profile["max_context_tokens"] == 1500
    assert profile["max_turns"] == 5
    assert profile["shell_output_max"] == 100


def test_manual_context_strategy(tmp_path, monkeypatch):
    """Test manual context strategy ignores model size."""
    config_data = {
        "context_strategy": "manual",
        "max_tokens": 5000,
    }

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))

    monkeypatch.chdir(tmp_path)
    history_mod._config_cache = None

    # All models should get same profile with manual strategy
    profile_small = history_mod.get_model_profile("gemma:2b")
    profile_large = history_mod.get_model_profile("llama3:70b")

    assert profile_small["max_context_tokens"] == 5000
    assert profile_large["max_context_tokens"] == 5000
