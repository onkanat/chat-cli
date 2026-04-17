"""Tests for parse_utils module."""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

# Load parse_utils directly to avoid lib.__init__.py dependencies
spec = importlib.util.spec_from_file_location(
    "parse_utils",
    Path(__file__).parent.parent / "lib" / "parse_utils.py",
)
parse_utils = importlib.util.module_from_spec(spec)
sys.modules["parse_utils"] = parse_utils
spec.loader.exec_module(parse_utils)

parse_command_string = parse_utils.parse_command_string
parse_run_args = parse_utils.parse_run_args
parse_settings_args = parse_utils.parse_settings_args
parse_search_args = parse_utils.parse_search_args
parse_plugin_args = parse_utils.parse_plugin_args
parse_export_args = parse_utils.parse_export_args


def test_parse_command_string_basic():
    """Test basic command parsing."""
    cmd, args = parse_command_string("/help")
    assert cmd == "help"
    assert args == []


def test_parse_command_string_with_args():
    """Test command parsing with arguments."""
    cmd, args = parse_command_string("/load llama2")
    assert cmd == "load"
    assert args == ["llama2"]


def test_parse_command_string_with_multiple_args():
    """Test command parsing with multiple arguments."""
    cmd, args = parse_command_string("/search query one two")
    assert cmd == "search"
    assert args == ["query", "one", "two"]


def test_parse_command_string_quoted():
    """Test command parsing with quoted strings."""
    cmd, args = parse_command_string('/run llama2 "hello world"')
    assert cmd == "run"
    assert args == ["llama2", "hello world"]


def test_parse_command_string_fallback():
    """Test fallback on shlex error."""
    # Unmatched quote causes shlex error, should use fallback
    cmd, args = parse_command_string("/run llama2 'unclosed")
    assert cmd == "run"
    assert args is not None  # Should have done fallback split


def test_parse_run_args_full():
    """Test /run with model and prompt."""
    model, prompt = parse_run_args(["llama2", "hello", "world"])
    assert model == "llama2"
    assert prompt == "hello world"


def test_parse_run_args_model_only():
    """Test /run with model only."""
    model, prompt = parse_run_args(["llama2"])
    assert model == "llama2"
    assert prompt is None


def test_parse_run_args_empty():
    """Test /run with no args."""
    model, prompt = parse_run_args([])
    assert model is None
    assert prompt is None


def test_parse_settings_args_key_value():
    """Test /settings with key and value."""
    key, value = parse_settings_args(["base_url", "http://localhost:11434"])
    assert key == "base_url"
    assert value == "http://localhost:11434"


def test_parse_settings_args_key_only():
    """Test /settings with key only."""
    key, value = parse_settings_args(["base_url"])
    assert key == "base_url"
    assert value is None


def test_parse_settings_args_empty():
    """Test /settings with no args."""
    key, value = parse_settings_args([])
    assert key is None
    assert value is None


def test_parse_search_args():
    """Test /search argument parsing."""
    query = parse_search_args(["machine", "learning", "models"])
    assert query == "machine learning models"


def test_parse_search_args_empty():
    """Test /search with no args."""
    query = parse_search_args([])
    assert query == ""


def test_parse_plugin_args_subcommand_with_arg():
    """Test /plugin subcommand with argument."""
    subcmd, args = parse_plugin_args(["info", "myplugin"])
    assert subcmd == "info"
    assert args == ["myplugin"]


def test_parse_plugin_args_subcommand_only():
    """Test /plugin subcommand only."""
    subcmd, args = parse_plugin_args(["list"])
    assert subcmd == "list"
    assert args == []


def test_parse_plugin_args_empty():
    """Test /plugin with no args."""
    subcmd, args = parse_plugin_args([])
    assert subcmd is None
    assert args == []


def test_parse_export_args_full():
    """Test /export with format and filename."""
    fmt, filename = parse_export_args(["json", "history.json"])
    assert fmt == "json"
    assert filename == "history.json"


def test_parse_export_args_format_only():
    """Test /export with format only."""
    fmt, filename = parse_export_args(["json"])
    assert fmt == "json"
    assert filename is None


def test_parse_export_args_empty():
    """Test /export with no args."""
    fmt, filename = parse_export_args([])
    assert fmt is None
    assert filename is None


if __name__ == "__main__":
    # Run tests
    import sys

    tests = [
        test_parse_command_string_basic,
        test_parse_command_string_with_args,
        test_parse_command_string_with_multiple_args,
        test_parse_command_string_quoted,
        test_parse_command_string_fallback,
        test_parse_run_args_full,
        test_parse_run_args_model_only,
        test_parse_run_args_empty,
        test_parse_settings_args_key_value,
        test_parse_settings_args_key_only,
        test_parse_settings_args_empty,
        test_parse_search_args,
        test_parse_search_args_empty,
        test_parse_plugin_args_subcommand_with_arg,
        test_parse_plugin_args_subcommand_only,
        test_parse_plugin_args_empty,
        test_parse_export_args_full,
        test_parse_export_args_format_only,
        test_parse_export_args_empty,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    if failed == 0:
        print(f"✓ All {len(tests)} parse_utils tests passed")
    else:
        print(f"✗ {failed}/{len(tests)} tests failed")
        sys.exit(1)
