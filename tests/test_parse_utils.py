"""Tests for parse_utils module."""

from __future__ import annotations

import importlib.util
import sys
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
parse_natural_language_command = parse_utils.parse_natural_language_command


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


def test_parse_natural_language_plugins_list_tr():
    """TR doğal dil plugin liste isteği /plugins'e map edilmelidir."""
    result = parse_natural_language_command("plugin listesini yazdır")
    assert result == ("plugins", [])


def test_parse_natural_language_plugins_available_tr():
    """TR doğal dil mevcut plugin isteği /plugins-available olmalıdır."""
    result = parse_natural_language_command("mevcut eklentileri listele")
    assert result == ("plugins-available", [])


def test_parse_natural_language_help_run_tr():
    """TR doğal dil help çalıştırma isteği /help'e map edilmelidir."""
    result = parse_natural_language_command("help komutunu çalıştır")
    assert result == ("help", [])


def test_parse_natural_language_regular_chat_returns_none():
    """Normal sohbet içeriği komut olarak algılanmamalıdır."""
    result = parse_natural_language_command(
        "chat-cli local de çalışan bir chat programıdır"
    )
    assert result is None


def test_parse_natural_language_quoted_slash_help_tr():
    """Tırnaklı '/help' çalıştırma isteği /help'e map edilmelidir."""
    result = parse_natural_language_command("'/help' komutunu çalıştır")
    assert result == ("help", [])


def test_parse_natural_language_explicit_plugins_available_command():
    """Açık /plugins-available komut referansı doğru map edilmelidir."""
    result = parse_natural_language_command(
        "lütfen /plugins-available komutunu çalıştır"
    )
    assert result == ("plugins-available", [])


def test_parse_natural_language_only_slash_help_mention():
    """Tek başına /help referansı doğal komut niyeti sayılmalıdır."""
    result = parse_natural_language_command(" '/help' ")
    assert result == ("help", [])


def test_parse_natural_language_wiki_phrase_returns_none():
    """Wiki arama ifadeleri plugin komutu olarak zorla map edilmemelidir."""
    result = parse_natural_language_command("LLMWiki'de ara ve özetle")
    assert result is None


def test_parse_natural_language_daemon_phrase_returns_none():
    """Daemon sorguları doğal komut eşleyici tarafından yakalanmamalıdır."""
    result = parse_natural_language_command(
        "omni-daemon bağlantısını kontrol et"
    )
    assert result is None


def test_parse_natural_language_embedded_wiki_add_command():
    """Cümle içinde geçen /wiki add komutu parse edilmelidir."""
    result = parse_natural_language_command(
        (
            "Verilen örnek ile bir şablon oluştur "
            "/wiki add yeni_sayfa.md \"Sayfa Başlığı\" Bu sayfa"
        )
    )
    assert result == (
        "wiki",
        ["add", "yeni_sayfa.md", "Sayfa Başlığı", "Bu", "sayfa"],
    )


def test_parse_natural_language_embedded_wiki_save_command():
    """Cümle içinde geçen /wiki save komutu parse edilmelidir."""
    result = parse_natural_language_command(
        (
            "tamam şimdi /wiki save yeni_sayfa.md "
            "\"Sayfa Başlığı\" komutunu çalıştır"
        )
    )
    assert result == (
        "wiki",
        ["save", "yeni_sayfa.md", "Sayfa Başlığı", "komutunu", "çalıştır"],
    )


def test_parse_natural_language_bare_wiki_add_command():
    """Başta kullanılan wiki add formu da komut olarak algılanmalıdır."""
    result = parse_natural_language_command(
        "wiki add yeni_sayfa.md \"Sayfa Başlığı\" İçerik"
    )
    assert result == (
        "wiki",
        ["add", "yeni_sayfa.md", "Sayfa Başlığı", "İçerik"],
    )


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
        test_parse_natural_language_plugins_list_tr,
        test_parse_natural_language_plugins_available_tr,
        test_parse_natural_language_help_run_tr,
        test_parse_natural_language_regular_chat_returns_none,
        test_parse_natural_language_quoted_slash_help_tr,
        test_parse_natural_language_explicit_plugins_available_command,
        test_parse_natural_language_only_slash_help_mention,
        test_parse_natural_language_wiki_phrase_returns_none,
        test_parse_natural_language_daemon_phrase_returns_none,
        test_parse_natural_language_embedded_wiki_add_command,
        test_parse_natural_language_embedded_wiki_save_command,
        test_parse_natural_language_bare_wiki_add_command,
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
