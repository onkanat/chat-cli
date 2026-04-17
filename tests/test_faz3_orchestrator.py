"""Tests for AgentOrchestrator."""

from __future__ import annotations

import sys
import importlib.util
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
