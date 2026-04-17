"""Tests for SystemPromptManager."""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

# Load system_prompt_manager directly
spec = importlib.util.spec_from_file_location(
    "system_prompt_manager",
    Path(__file__).parent.parent / "lib" / "system_prompt_manager.py",
)
spm = importlib.util.module_from_spec(spec)
sys.modules["system_prompt_manager"] = spm
spec.loader.exec_module(spm)

SystemPromptBuilder = spm.SystemPromptBuilder
PersonaAdapter = spm.PersonaAdapter
PolicyManager = spm.PolicyManager
SystemPromptManager = spm.SystemPromptManager


def test_system_prompt_builder_user():
    """Test building user chat system message."""
    builder = SystemPromptBuilder("You are helpful.")
    msg = builder.build_user_system_message()
    assert msg == "You are helpful."


def test_system_prompt_builder_agent():
    """Test building agent system message."""
    builder = SystemPromptBuilder("You are helpful.")
    msg = builder.build_agent_system_message()
    assert "CRITICAL RULES" in msg
    assert "/help" in msg
    assert "/list" in msg


def test_system_prompt_builder_agent_with_custom_commands():
    """Test agent message with custom command registry."""
    builder = SystemPromptBuilder()
    custom_cmds = {"/custom": "Custom command"}
    msg = builder.build_agent_system_message(custom_cmds)
    assert "/custom: Custom command" in msg
    assert "/help" in msg  # Built-in still included


def test_persona_adapter_no_provider():
    """Test adapter with no persona provider."""
    adapter = PersonaAdapter()
    assert adapter.get_persona_prompt() is None


def test_persona_adapter_with_provider():
    """Test adapter with persona provider."""
    provider = MagicMock()
    provider.persona_prompt = "You are a pirate."
    adapter = PersonaAdapter(provider)
    assert adapter.get_persona_prompt() == "You are a pirate."


def test_persona_adapter_apply():
    """Test applying persona to system message."""
    adapter = PersonaAdapter()
    base = "You are helpful."
    persona = "You are a pirate."
    result = adapter.apply_persona(base, persona)
    assert result == persona


def test_persona_adapter_no_persona():
    """Test applying when no persona set."""
    adapter = PersonaAdapter()
    base = "You are helpful."
    result = adapter.apply_persona(base)
    assert result == base


def test_policy_manager_guard_rails():
    """Test policy manager constants."""
    policy = PolicyManager()
    assert policy.max_iterations == 6
    assert policy.max_json_retries == 2
    assert policy.max_repeat_limit == 2


def test_policy_manager_iteration_check():
    """Test iteration limit check."""
    policy = PolicyManager(max_iterations=5)
    assert not policy.should_stop_on_iteration(4)
    assert policy.should_stop_on_iteration(5)
    assert policy.should_stop_on_iteration(6)


def test_policy_manager_json_retry_check():
    """Test JSON retry limit check."""
    policy = PolicyManager(max_json_retries=3)
    assert not policy.should_stop_on_json_retry(2)
    assert policy.should_stop_on_json_retry(3)


def test_policy_manager_repeat_check():
    """Test repeat limit check."""
    policy = PolicyManager(max_repeat_limit=2)
    assert not policy.should_stop_on_repeat(2)
    assert policy.should_stop_on_repeat(3)


def test_unified_manager_user_mode():
    """Test unified manager in user mode."""
    manager = SystemPromptManager(base_message="You are helpful.")
    msg = manager.build_system_message(for_agent=False)
    assert msg == "You are helpful."


def test_unified_manager_agent_mode():
    """Test unified manager in agent mode."""
    manager = SystemPromptManager(base_message="Base message")
    msg = manager.build_system_message(for_agent=True)
    assert "Base message" in msg
    assert "CRITICAL RULES" in msg


def test_unified_manager_with_persona():
    """Test unified manager with persona."""
    provider = MagicMock()
    provider.persona_prompt = "You are a poet."
    manager = SystemPromptManager(
        base_message="Base",
        persona_provider=provider,
    )
    msg = manager.build_system_message()
    assert msg == "You are a poet."


def test_unified_manager_get_policy():
    """Test getting policy from manager."""
    manager = SystemPromptManager()
    policy = manager.get_policy()
    assert policy.max_iterations == 6


if __name__ == "__main__":
    tests = [
        test_system_prompt_builder_user,
        test_system_prompt_builder_agent,
        test_system_prompt_builder_agent_with_custom_commands,
        test_persona_adapter_no_provider,
        test_persona_adapter_with_provider,
        test_persona_adapter_apply,
        test_persona_adapter_no_persona,
        test_policy_manager_guard_rails,
        test_policy_manager_iteration_check,
        test_policy_manager_json_retry_check,
        test_policy_manager_repeat_check,
        test_unified_manager_user_mode,
        test_unified_manager_agent_mode,
        test_unified_manager_with_persona,
        test_unified_manager_get_policy,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    if failed == 0:
        print(f"✓ All {len(tests)} SystemPromptManager tests passed")
    else:
        print(f"✗ {failed}/{len(tests)} tests failed")
