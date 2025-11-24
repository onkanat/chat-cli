"""Test system message compression."""

from __future__ import annotations

import lib.history as history_mod


def test_compress_system_message_english():
    """Test compressing English system messages."""
    full_msg = (
        "You are a senior Python developer with expertise in async programming, "
        "testing, and clean code. Always provide detailed explanations."
    )

    compressed = history_mod.compress_system_message(full_msg)

    # Should be much shorter
    assert len(compressed) < len(full_msg)
    assert len(compressed) < 100

    # Should contain core role
    assert "senior Python developer" in compressed or "Python developer" in compressed


def test_compress_system_message_turkish():
    """Test compressing Turkish system messages."""
    full_msg = (
        "Sen uzman bir programcısın. Kod yazma, hata ayıklama ve optimizasyon "
        "konularında yardımcı ol. Her zaman detaylı açıklamalar sun."
    )

    compressed = history_mod.compress_system_message(full_msg)

    # Should be shorter
    assert len(compressed) < len(full_msg)
    assert len(compressed) < 100

    # Should contain core role
    assert "uzman" in compressed or "programcı" in compressed


def test_compress_system_message_short_input():
    """Test that short messages are not compressed."""
    short_msg = "You are a helpful assistant"

    compressed = history_mod.compress_system_message(short_msg)

    # Should be unchanged
    assert compressed == short_msg


def test_compress_system_message_empty():
    """Test empty message handling."""
    assert history_mod.compress_system_message("") == ""
    assert history_mod.compress_system_message(None) is None


def test_build_model_messages_full_system_first_turn():
    """Test that first turn uses full system message."""
    history = [
        {"role": "user", "text": "Hello"},
    ]

    full_system = "You are a senior Python developer with expertise in async programming and testing."

    msgs = history_mod.build_model_messages_from_history(
        history,
        system_message=full_system,
        compress_system=True,  # Enabled, but should not compress on first turn
    )

    # Find system message
    system_msg = next((m for m in msgs if m["role"] == "system"), None)

    assert system_msg is not None
    # Should use full message (not compressed) because it's early in conversation
    assert len(system_msg["content"]) > 50


def test_build_model_messages_compressed_system_later_turn():
    """Test that later turns use compressed system message."""
    history = [
        {"role": "user", "text": "First"},
        {"role": "assistant", "text": "Response 1"},
        {"role": "user", "text": "Second"},
        {"role": "assistant", "text": "Response 2"},
        {"role": "user", "text": "Third"},
    ]

    full_system = (
        "You are a senior Python developer with expertise in async programming, "
        "testing, and clean code. Always provide detailed explanations and examples."
    )

    msgs = history_mod.build_model_messages_from_history(
        history,
        system_message=full_system,
        compress_system=True,
    )

    # Find system message
    system_msg = next((m for m in msgs if m["role"] == "system"), None)

    assert system_msg is not None
    # Should use compressed message (len(window) > 2)
    assert len(system_msg["content"]) < len(full_system)
    assert len(system_msg["content"]) < 100


def test_build_model_messages_no_compression_when_disabled():
    """Test that compression is disabled by default."""
    history = [
        {"role": "user", "text": "First"},
        {"role": "assistant", "text": "Response 1"},
        {"role": "user", "text": "Second"},
        {"role": "assistant", "text": "Response 2"},
        {"role": "user", "text": "Third"},
    ]

    full_system = (
        "You are a senior Python developer with expertise in async programming, "
        "testing, and clean code. Always provide detailed explanations and examples."
    )

    # Compression disabled (default)
    msgs = history_mod.build_model_messages_from_history(
        history,
        system_message=full_system,
        compress_system=False,  # Explicitly disabled
    )

    # Find system message
    system_msg = next((m for m in msgs if m["role"] == "system"), None)

    assert system_msg is not None
    # Should use full message always
    assert system_msg["content"] == full_system


def test_compression_token_savings():
    """Verify that compression actually saves tokens."""
    long_system = """You are a senior software engineer with 10+ years of experience
    in Python development, specializing in web frameworks, async programming,
    database design, API development, testing, and clean code practices.
    You always provide comprehensive explanations with code examples."""

    compressed = history_mod.compress_system_message(long_system)

    # Estimate tokens (rough: 4 chars per token)
    full_tokens = len(long_system) // 4
    compressed_tokens = len(compressed) // 4

    # Should save at least 60% of tokens
    savings_percent = ((full_tokens - compressed_tokens) / full_tokens) * 100
    assert savings_percent > 60
