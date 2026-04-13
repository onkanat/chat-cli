from __future__ import annotations

import re
import pytest
from unittest.mock import patch, MagicMock

from repl.loop import sanitize_prompt, _parse_run_args

def test_sanitize_prompt():
    """Test string sanitization for incoming user inputs."""
    # Slashes command commands are completely removed by sanitize_prompt
    assert sanitize_prompt("/list   ") == ""
    assert sanitize_prompt("/wiki   search  \nSome other text") == "Some other text"
    # Normal text should mostly stay the same
    assert sanitize_prompt("Normal text\n") == "Normal text"
    assert sanitize_prompt("   leading spaces") == "leading spaces"

def test_parse_run_args():
    """Test parsing initial CLI arguments for the run loop."""
    assert _parse_run_args([]) == (None, None)
    assert _parse_run_args(["gemma2"]) == ("gemma2", None)
    assert _parse_run_args(["my-model", "--prompt", "hello"]) == ("my-model", "hello")
    # If the first argument is a flag, parse_run_args currently captures it as the model name.
    # We just document the existing behavior of the function.
    assert _parse_run_args(["--prompt", "hello"]) == ("--prompt", "hello")

@patch("repl.loop.history_mod.load_history")
@patch("repl.loop.history_mod.save_history")
@patch("repl.loop.ow")
@patch("repl.loop.ui_mod.console.print")
@patch("repl.loop.ui_mod.select_model_menu")
def test_run_chat_exit_command(mock_select_menu, mock_print, mock_ollama, mock_save, mock_load):
    """Test the /exit slash command breaks the run loop correctly."""
    from repl.loop import run_chat

    # Provide the input "/exit"
    with patch("repl.loop.input_handler.enhanced_input_multiline", return_value="/exit"):
        mock_ollama.detect_active_model.return_value = "fake-model"
        mock_select_menu.return_value = "fake-model"
        # Since it exits on the first input, the loop terminates without error
        run_chat("dummy_history.json", None, False, 4000, 2000)

    assert mock_save.called
    assert mock_print.called

@patch("repl.loop.history_mod.load_history")
@patch("repl.loop.history_mod.save_history")
@patch("repl.loop.ow")
@patch("repl.loop.ui_mod.console.print")
@patch("repl.loop.ui_mod.select_model_menu")
def test_run_chat_clear_command(mock_select_menu, mock_print, mock_ollama, mock_save, mock_load):
    """Test the /clear slash command resets context."""
    from repl.loop import run_chat

    # Input sequence: /clear then /exit so we don't have an infinite loop
    inputs = ["/clear", "/exit"]
    def mock_input(*args, **kwargs):
        return inputs.pop(0)

    with patch("repl.loop.input_handler.enhanced_input_multiline", side_effect=mock_input):
        # Provide some existing history
        mock_load.return_value = [{"role": "user", "text": "old data"}]
        mock_ollama.detect_active_model.return_value = "fake-model"
        mock_select_menu.return_value = "fake-model"

        run_chat("dummy_history.json", None, False, 4000, 2000)

        # Check that clear message was triggered
        printed_texts = [call.args[0] for call in mock_print.mock_calls if call.args]
        assert any("cleared" in str(line).lower() or "temizlendi" in str(line).lower() for line in printed_texts)


# ── call_cmd extraction regression tests ────────────────────────────────────
# These tests mirror the fixed extraction logic in repl/loop.py.
# Root bug: model may mention "<call_cmd>" as prose in reasoning text, causing
# the old naive re.search to grab garbled content instead of the real command.

# The pattern anchors to '/' at the start of the captured content and
# disallows '<' inside – this prevents an unclosed prose mention like
# "output in <call_cmd> tags" from swallowing a later real command.
CALL_CMD_RE = re.compile(r"<call_cmd>\s*(/[^<]*?)\s*</call_cmd>", re.DOTALL | re.IGNORECASE)


def _extract_valid_cmd(reply: str) -> str | None:
    """Mirror of the fixed extraction logic in repl/loop.py."""
    matches = [m.strip() for m in CALL_CMD_RE.findall(reply) if m.strip()]
    return matches[-1] if matches else None


def test_call_cmd_simple():
    """A clean <call_cmd>/list</call_cmd> should be extracted."""
    reply = "<call_cmd>/list</call_cmd>"
    assert _extract_valid_cmd(reply) == "/list"


def test_call_cmd_ignores_prose_mention():
    """Model mentions '<call_cmd>' as text in reasoning -> must be ignored."""
    reply = (
        "We need to output in <call_cmd> tags exactly. So we call /help.\n"
        "The format: <call_cmd>/help</call_cmd>"
    )
    assert _extract_valid_cmd(reply) == "/help"


def test_call_cmd_prefers_last_valid():
    """When the model explains then acts, pick the *last* valid command."""
    reply = (
        "First attempt: <call_cmd>/list</call_cmd>\n"
        "Better choice: <call_cmd>/wiki help</call_cmd>"
    )
    assert _extract_valid_cmd(reply) == "/wiki help"


def test_call_cmd_no_valid_commands():
    """No slash-command in any block -> returns None."""
    reply = "Must output in <call_cmd> tags exactly. No real command here."
    assert _extract_valid_cmd(reply) is None


def test_call_cmd_with_args():
    """Commands with arguments are extracted fully."""
    reply = "<call_cmd>/wiki search transformer architecture</call_cmd>"
    assert _extract_valid_cmd(reply) == "/wiki search transformer architecture"
