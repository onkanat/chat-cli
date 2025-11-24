"""Test dual history - full for archive, optimized for model."""

from __future__ import annotations

from pathlib import Path
import tempfile

import lib.history as history_mod


def test_optimize_history_item_shell_output():
    """Test that shell items are optimized for model context."""
    item = {
        "role": "shell",
        "command": "ls -la",
        "output": "file1.txt\nfile2.txt\nfile3.txt\n" * 100  # Long output
    }
    optimized = history_mod.optimize_history_item_for_model(item, model_name="gemma:2b")

    # Original should be unchanged
    assert len(item["output"]) > 500

    # Optimized should be shorter or omitted
    assert len(optimized["output"]) < len(item["output"]) or "[Output omitted" in optimized["output"]


def test_optimize_history_item_preserves_other_roles():
    """Test that user/assistant items are not modified."""
    user_item = {"role": "user", "text": "Hello" * 100}
    assistant_item = {"role": "assistant", "text": "Hi there" * 100}

    optimized_user = history_mod.optimize_history_item_for_model(user_item)
    optimized_assistant = history_mod.optimize_history_item_for_model(assistant_item)

    # Should be identical for non-shell items
    assert optimized_user == user_item
    assert optimized_assistant == assistant_item


def test_build_model_history_from_full():
    """Test building optimized history from full history."""
    full_history = [
        {"role": "user", "text": "Run ls"},
        {"role": "shell", "command": "ls", "output": "file1.txt\nfile2.txt" * 50},
        {"role": "user", "text": "Run test"},
        {"role": "shell", "command": "pytest", "output": "PASSED" * 100},
        {"role": "assistant", "text": "All good"},
    ]

    model_history = history_mod.build_model_history_from_full(full_history, model_name="gemma:2b")

    # Should have same length
    assert len(model_history) == len(full_history)

    # Shell outputs should be optimized
    assert len(model_history[1]["output"]) < len(full_history[1]["output"]
                                                 ) or "[omitted" in model_history[1]["output"].lower()

    # Other items unchanged
    assert model_history[0] == full_history[0]
    assert model_history[4] == full_history[4]


def test_save_history_preserves_full_data():
    """Test that save_history writes full (unoptimized) data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history = [
            {"role": "user", "text": "Test"},
            {"role": "shell", "command": "ls", "output": "x" * 1000},  # Long output
        ]

        path = Path(tmpdir) / "test_history.json"
        history_mod.save_history(history, path)

        # Load and verify full data is preserved
        loaded = history_mod.load_history(path)

        assert len(loaded) == 2
        assert loaded[1]["output"] == "x" * 1000  # Full output preserved


def test_create_new_session_preserves_full_data():
    """Test that create_new_session saves full shell outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Temporarily override SESSIONS_DIR
        original_dir = history_mod.SESSIONS_DIR
        history_mod.SESSIONS_DIR = Path(tmpdir) / "histories"

        try:
            history = [
                {"role": "user", "text": "Command"},
                {"role": "shell", "command": "python test.py", "output": "y" * 2000},
            ]

            session_id = history_mod.create_new_session(
                history,
                custom_name="Test Session",
                model_used="gemma:2b",
            )

            # Load session and verify full data
            loaded_history = history_mod.load_session(session_id)

            assert len(loaded_history) == 2
            assert loaded_history[1]["output"] == "y" * 2000  # Full output in archive

        finally:
            history_mod.SESSIONS_DIR = original_dir


def test_model_context_uses_optimized_data():
    """Test that build_model_messages uses optimized shell outputs."""
    history = [
        {"role": "user", "text": "List files"},
        {"role": "shell", "command": "ls", "output": "file1\nfile2\nfile3\n" * 50},
        {"role": "user", "text": "What did you see?"},
    ]

    # Build messages for model (should be optimized)
    msgs = history_mod.build_model_messages_from_history(
        history,
        model_name="gemma:2b",  # Small model
    )

    # Find shell output in messages
    shell_output = None
    for msg in msgs:
        if "Shell output:" in msg.get("content", ""):
            shell_output = msg["content"]
            break

    # Should be optimized (omitted or truncated)
    assert shell_output is not None
    original_size = len("file1\nfile2\nfile3\n" * 50)
    if "[Output omitted" not in shell_output:
        # If not omitted, should be truncated
        assert len(shell_output) < original_size


def test_dual_history_flow():
    """Test complete flow: save full, load full, build optimized for model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create history with large shell output
        full_history = [
            {"role": "user", "text": "Run command"},
            {"role": "shell", "command": "pytest tests/", "output": "." * 5000},
            {"role": "assistant", "text": "Tests passed"},
        ]

        # Save to file (should preserve full data)
        path = Path(tmpdir) / "history.json"
        history_mod.save_history(full_history, path)

        # Load back
        loaded_history = history_mod.load_history(path)
        assert loaded_history[1]["output"] == "." * 5000  # Full data

        # Build model context (should be optimized)
        model_msgs = history_mod.build_model_messages_from_history(
            loaded_history,
            model_name="gemma:2b",
        )

        # Find shell output in model messages
        shell_msg = None
        for msg in model_msgs:
            if "Shell output:" in msg.get("content", ""):
                shell_msg = msg["content"]
                break

        # Model context should have optimized output
        assert shell_msg is not None
        assert len(shell_msg) < 5000  # Optimized, not full
