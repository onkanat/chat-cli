from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "lib" / "agent_utils.py"
SPEC = importlib.util.spec_from_file_location(
    "agent_utils_under_test", MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
AGENT_UTILS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AGENT_UTILS
SPEC.loader.exec_module(AGENT_UTILS)

detect_json_tool_name = AGENT_UTILS.detect_json_tool_name
parse_agent_command = AGENT_UTILS.parse_agent_command


def test_parse_agent_command_picks_last_valid_match() -> None:
    reply = (
        "Düşünüyorum <call_cmd>not a command</call_cmd> sonra "
        "<call_cmd>/list</call_cmd> en sonda <call_cmd>/help</call_cmd>"
    )
    result = parse_agent_command(reply)

    assert result.command == "/help"
    assert result.full_match == "<call_cmd>/help</call_cmd>"
    assert result.invalid_matches == ("not a command",)


def test_parse_agent_command_returns_empty_when_no_valid_command() -> None:
    result = parse_agent_command("<call_cmd>json tool</call_cmd>")

    assert result.command is None
    assert result.full_match is None
    assert result.invalid_matches == ("json tool",)


def test_detect_json_tool_name_finds_tool_payload() -> None:
    reply = '{"tool": "run_command", "args": ["/help"]}'

    assert detect_json_tool_name(reply) == "run_command"


def test_detect_json_tool_name_ignores_non_tool_json() -> None:
    reply = '{"message": "hello"}'

    assert detect_json_tool_name(reply) is None
