"""Tests for unified command executor (Faz 2)."""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

# Load command_executor module directly
spec = importlib.util.spec_from_file_location(
    "command_executor",
    Path(__file__).parent.parent / "lib" / "command_executor.py",
)
command_executor = importlib.util.module_from_spec(spec)
sys.modules["command_executor"] = command_executor
spec.loader.exec_module(command_executor)

from command_executor import (
    CommandContext,
    CommandResult,
    execute_command,
)


def test_execute_command_help():
    """Test /help command execution."""
    mock_ui = MagicMock()
    mock_manager = MagicMock()

    ctx = CommandContext(
        history=[],
        current_model=None,
        plugin_manager=mock_manager,
        config={},
        analytics_manager=MagicMock(),
        ui_mod=mock_ui,
        ollama_wrapper=MagicMock(),
        chat_context={},
    )

    result = execute_command("help", [], ctx)

    assert result.success
    assert "Available Commands" in result.output
    assert "/list" in result.output


def test_execute_command_unknown():
    """Test unknown command returns error."""
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

    result = execute_command("unknown_cmd", [], ctx)

    assert not result.success
    assert "Unknown command" in result.error


def test_execute_command_with_slash():
    """Test command with leading slash is handled."""
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

    # Should strip the leading slash
    result = execute_command("/help", [], ctx)

    assert result.success
    assert "Available Commands" in result.output


def test_command_result_state_changes():
    """Test CommandResult.state_changes default value."""
    result = CommandResult(success=True, output="test")

    assert result.state_changes is not None
    assert result.state_changes == {}


def test_command_result_error():
    """Test CommandResult error field."""
    result = CommandResult(
        success=False,
        error="Test error",
    )

    assert not result.success
    assert result.error == "Test error"
    assert result.output == ""


if __name__ == "__main__":
    test_execute_command_help()
    test_execute_command_unknown()
    test_execute_command_with_slash()
    test_command_result_state_changes()
    test_command_result_error()
    print("✓ All Faz 2 executor tests passed")
