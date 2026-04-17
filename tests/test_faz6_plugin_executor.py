"""Tests for PluginCommandExecutor and PluginExecutionContext."""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

# Load plugin_executor directly
spec = importlib.util.spec_from_file_location(
    "plugin_executor",
    Path(__file__).parent.parent / "lib" / "plugin_executor.py",
)
pe = importlib.util.module_from_spec(spec)
sys.modules["plugin_executor"] = pe
spec.loader.exec_module(pe)

PluginCommandExecutor = pe.PluginCommandExecutor
PluginExecutionContext = pe.PluginExecutionContext


def test_plugin_executor_init():
    """Test plugin executor initialization."""
    mgr = MagicMock()
    executor = PluginCommandExecutor(mgr)
    assert executor.plugin_manager is mgr


def test_plugin_executor_execute_success():
    """Test successful plugin command execution."""
    mgr = MagicMock()
    mgr.execute_command.return_value = True

    executor = PluginCommandExecutor(mgr)
    result = executor.execute(
        "wiki",
        ["search", "test"],
        {"ui_mod": MagicMock()},
    )

    assert result is True
    mgr.execute_command.assert_called_once()


def test_plugin_executor_execute_unknown():
    """Test unknown plugin command."""
    mgr = MagicMock()
    mgr.execute_command.return_value = False

    executor = PluginCommandExecutor(mgr)
    result = executor.execute(
        "unknown",
        [],
        {"ui_mod": MagicMock()},
    )

    assert result is False


def test_plugin_executor_error_handling():
    """Test error handling during plugin execution."""
    mgr = MagicMock()
    mgr.execute_command.side_effect = RuntimeError("Plugin failed")

    executor = PluginCommandExecutor(mgr)
    ui_mock = MagicMock()
    result = executor.execute(
        "bad",
        [],
        {"ui_mod": ui_mock},
    )

    assert result is False
    # Should print error to UI
    ui_mock.console.print.assert_called_once()


def test_plugin_executor_startup_plugin_success():
    """Test startup plugin execution success."""
    mgr = MagicMock()
    mgr.execute_command.return_value = True

    executor = PluginCommandExecutor(mgr)
    executor.execute_startup_plugin(
        "persona",
        ["set", "pirate"],
        {"ui_mod": MagicMock()},
    )

    mgr.execute_command.assert_called_once()


def test_plugin_executor_startup_plugin_failure_ignored():
    """Test startup plugin failure is silently ignored."""
    mgr = MagicMock()
    mgr.execute_command.side_effect = Exception("Failed")

    executor = PluginCommandExecutor(mgr)
    # Should not raise, should silently fail
    executor.execute_startup_plugin(
        "persona",
        ["set", "pirate"],
        {"ui_mod": MagicMock()},
    )


def test_plugin_executor_has_plugin():
    """Test checking if plugin exists."""
    mgr = MagicMock()
    mgr.plugins = {"wiki": MagicMock(), "persona": MagicMock()}

    executor = PluginCommandExecutor(mgr)
    assert executor.has_plugin("wiki") is True
    assert executor.has_plugin("unknown") is False


def test_plugin_executor_get_commands():
    """Test getting all plugin commands."""
    mgr = MagicMock()
    mgr.get_all_commands.return_value = {
        "wiki": "Wiki search",
        "persona": "Persona management",
    }

    executor = PluginCommandExecutor(mgr)
    cmds = executor.get_plugin_commands()
    assert "wiki" in cmds
    assert "persona" in cmds


def test_execution_context_builder_chain():
    """Test context builder chaining."""
    ctx = (
        PluginExecutionContext()
        .with_history([])
        .with_model("llama2")
        .with_analytics(MagicMock())
        .with_ui(MagicMock())
        .with_ollama(MagicMock())
        .with_chat_context({"persona": "pirate"})
        .with_config({"system_message": "test"})
        .build()
    )

    assert ctx["history"] == []
    assert ctx["current_model"] == "llama2"
    assert "persona" in ctx["chat_context"]


def test_execution_context_partial():
    """Test context builder with partial fields."""
    ctx = (
        PluginExecutionContext()
        .with_history([])
        .with_model("mistral")
        .build()
    )

    assert ctx["history"] == []
    assert ctx["current_model"] == "mistral"
    assert "ui_mod" not in ctx


def test_execution_context_empty():
    """Test empty context."""
    ctx = PluginExecutionContext().build()
    assert ctx == {}


def test_plugin_executor_no_plugins_attr():
    """Test has_plugin when plugin_manager has no plugins attr."""
    mgr = MagicMock(spec=[])  # No attributes
    executor = PluginCommandExecutor(mgr)
    assert executor.has_plugin("any") is False


def test_plugin_executor_no_get_all_commands():
    """Test get_plugin_commands when method missing."""
    mgr = MagicMock(spec=[])  # No methods
    executor = PluginCommandExecutor(mgr)
    cmds = executor.get_plugin_commands()
    assert cmds == {}


def test_execution_context_build_is_copy():
    """Test that build() returns independent dict."""
    ctx_builder = PluginExecutionContext().with_model("llama2")
    ctx1 = ctx_builder.build()
    ctx2 = ctx_builder.build()

    # Modify first dict
    ctx1["current_model"] = "mistral"

    # Second dict should be unchanged
    assert ctx2["current_model"] == "llama2"


if __name__ == "__main__":
    tests = [
        test_plugin_executor_init,
        test_plugin_executor_execute_success,
        test_plugin_executor_execute_unknown,
        test_plugin_executor_error_handling,
        test_plugin_executor_startup_plugin_success,
        test_plugin_executor_startup_plugin_failure_ignored,
        test_plugin_executor_has_plugin,
        test_plugin_executor_get_commands,
        test_execution_context_builder_chain,
        test_execution_context_partial,
        test_execution_context_empty,
        test_plugin_executor_no_plugins_attr,
        test_plugin_executor_no_get_all_commands,
        test_execution_context_build_is_copy,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    if failed == 0:
        print(f"✓ All {len(tests)} plugin executor tests passed")
    else:
        print(f"✗ {failed}/{len(tests)} plugin executor tests failed")
