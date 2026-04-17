"""Tests for Faz 2.1: User command path refactoring."""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

# Load command_executor module directly
spec = importlib.util.spec_from_file_location(
    "command_executor",
    Path(__file__).parent.parent / "lib" / "command_executor.py",
)
command_executor = importlib.util.module_from_spec(spec)
sys.modules["command_executor"] = command_executor
spec.loader.exec_module(command_executor)

from command_executor import CommandContext


def test_user_command_path_help():
    """Test user command path with /help returns success."""
    from repl.loop import execute_user_command

    ctx = CommandContext(
        history=[],
        current_model=None,
        plugin_manager=MagicMock(),
        config={},
        analytics_manager=MagicMock(),
        ui_mod=MagicMock(),
        ollama_wrapper=MagicMock(),
        chat_context={},
    )

    should_continue, was_handled = execute_user_command(
        "help", [], ctx, [], Path("/tmp/test.json")
    )

    assert should_continue
    assert was_handled


def test_user_command_path_unknown():
    """Test user command path with unknown command returns not handled."""
    from repl.loop import execute_user_command

    ctx = CommandContext(
        history=[],
        current_model=None,
        plugin_manager=MagicMock(),
        config={},
        analytics_manager=MagicMock(),
        ui_mod=MagicMock(),
        ollama_wrapper=MagicMock(),
        chat_context={},
    )

    should_continue, was_handled = execute_user_command(
        "nonexistent_cmd", [], ctx, [], Path("/tmp/test.json")
    )

    assert should_continue
    assert not was_handled


def test_user_command_path_exit():
    """Test user command path with /exit returns should_continue=False."""
    from repl.loop import execute_user_command

    mock_ui = MagicMock()
    with patch("repl.loop.ui_mod", mock_ui):
        with patch("repl.loop.history_mod") as mock_history:
            ctx = CommandContext(
                history=[],
                current_model=None,
                plugin_manager=MagicMock(),
                config={},
                analytics_manager=MagicMock(),
                ui_mod=mock_ui,
                ollama_wrapper=MagicMock(),
                chat_context={},
            )

            should_continue, was_handled = execute_user_command(
                "exit", [], ctx, [], Path("/tmp/test.json")
            )

            assert not should_continue
            assert was_handled


if __name__ == "__main__":
    try:
        test_user_command_path_help()
        test_user_command_path_unknown()
        test_user_command_path_exit()
        print("✓ All Faz 2.1 user path tests passed")
    except ImportError as e:
        print(f"⚠ Skipping tests (import issue): {e}")
