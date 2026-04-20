"""Tests for AgentOrchestrator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Load orchestrator directly
spec = importlib.util.spec_from_file_location(
    "agent_orchestrator",
    Path(__file__).parent.parent / "lib" / "agent_orchestrator.py",
)
orchestrator_mod = importlib.util.module_from_spec(spec)
sys.modules["agent_orchestrator"] = orchestrator_mod

# Mock dependencies before loading
sys.modules["lib.command_executor"] = MagicMock()
sys.modules["lib.agent_utils"] = MagicMock()

spec.loader.exec_module(orchestrator_mod)
AgentOrchestrator = orchestrator_mod.AgentOrchestrator


def test_orchestrator_init():
    """Test orchestrator initialization."""
    orch = AgentOrchestrator(
        history=[],
        current_model="test-model",
        config={},
        plugin_manager=MagicMock(),
        analytics_manager=MagicMock(),
        ui_mod=MagicMock(),
        ollama_wrapper=MagicMock(),
        chat_context={},
    )

    assert orch.current_model == "test-model"
    assert orch.iteration_count == 0
    assert orch.json_retry_count == 0


def test_orchestrator_guard_rails():
    """Test guard rails constants."""
    assert AgentOrchestrator.MAX_ITERATIONS == 6
    assert AgentOrchestrator.MAX_JSON_RETRIES == 2
    assert AgentOrchestrator.MAX_REPEAT_LIMIT == 2


def test_orchestrator_blocked_commands():
    """Test blocked commands list."""
    assert "new_session" in AgentOrchestrator.BLOCKED_COMMANDS
    assert "run" in AgentOrchestrator.BLOCKED_COMMANDS
    assert "settings" in AgentOrchestrator.BLOCKED_COMMANDS


def test_orchestrator_methods_exist():
    """Test that orchestrator has required methods."""
    assert hasattr(AgentOrchestrator, "run")
    assert hasattr(AgentOrchestrator, "run_with_initial_reply")
    assert hasattr(AgentOrchestrator, "_get_reply")
    assert hasattr(AgentOrchestrator, "_process_reply")
    assert hasattr(AgentOrchestrator, "_execute_agent_command")
    assert hasattr(AgentOrchestrator, "_handle_no_command")


def test_json_retries_uses_correct_constant():
    """B1: Ensure MAX_JSON_RETRIES exists and MAX_AGENT_JSON_RETRIES does not (NameError guard)."""
    assert hasattr(AgentOrchestrator, "MAX_JSON_RETRIES")
    assert not hasattr(AgentOrchestrator, "MAX_AGENT_JSON_RETRIES")


def test_blocked_command_is_rejected():
    """B2: Verify BLOCKED_COMMANDS are actually enforced — plugin executor must NOT be called."""
    cap_mock = MagicMock()
    cap_mock.__enter__ = MagicMock(return_value=cap_mock)
    cap_mock.__exit__ = MagicMock(return_value=False)
    cap_mock.get.return_value = ""

    ui_mod = MagicMock()
    ui_mod.console.capture.return_value = cap_mock

    plugin_manager = MagicMock()
    plugin_manager.execute_command.return_value = False

    orch = AgentOrchestrator(
        history=[],
        current_model="test-model",
        config={},
        plugin_manager=plugin_manager,
        analytics_manager=MagicMock(),
        ui_mod=ui_mod,
        ollama_wrapper=MagicMock(),
        chat_context={},
    )

    for blocked_cmd in AgentOrchestrator.BLOCKED_COMMANDS:
        plugin_manager.reset_mock()
        result = orch._execute_agent_command(
            f"/{blocked_cmd}",
            f"reply text <call_cmd>/{blocked_cmd}</call_cmd>",
            f"<call_cmd>/{blocked_cmd}</call_cmd>",
        )
        plugin_manager.execute_command.assert_not_called(), (
            f"/{blocked_cmd} should be blocked but plugin_manager was called"
        )
        assert result is True, "blocked command should return True (loop continues)"


def test_run_returns_agent_run_result():
    """B6: run() must not return a bare bool — result must have AgentRunResult fields.

    Note: lib.agent_utils is mocked at module level in this test file, so AgentRunResult
    is a MagicMock callable. The key assertion is that run() no longer returns True/False.
    """
    # parse_agent_command must return no command so _handle_no_command is reached
    parsed_no_cmd = MagicMock()
    parsed_no_cmd.command = None
    parsed_no_cmd.invalid_matches = ()
    orchestrator_mod.parse_agent_command = MagicMock(return_value=parsed_no_cmd)
    orchestrator_mod.detect_json_tool_name = MagicMock(return_value=None)

    ui_mod = MagicMock()
    ui_mod.get_model_reply_sync.return_value = "Clean answer without call_cmd"
    ui_mod.get_active_route_label.return_value = "direct"

    orch = AgentOrchestrator(
        history=[],
        current_model="test-model",
        config={},
        plugin_manager=MagicMock(),
        analytics_manager=MagicMock(),
        ui_mod=ui_mod,
        ollama_wrapper=MagicMock(),
        chat_context={},
        stream=False,
    )

    result = orch.run("system prompt")
    # run() must not return a plain bool anymore
    assert not isinstance(result, bool), "run() must return AgentRunResult, not bool"
    # AgentRunResult fields must be accessible (MagicMock or real)
    assert hasattr(result, "success")
    assert hasattr(result, "stop_reason")
    assert hasattr(result, "iterations")
    assert hasattr(result, "last_command")


if __name__ == "__main__":
    try:
        test_orchestrator_init()
        test_orchestrator_guard_rails()
        test_orchestrator_blocked_commands()
        test_orchestrator_methods_exist()
        print("✓ All AgentOrchestrator tests passed")
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
