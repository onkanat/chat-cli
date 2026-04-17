from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentCommandParseResult:
    """Structured result for parsing an agent reply."""

    command: str | None
    full_match: str | None
    invalid_matches: tuple[str, ...]


CALL_CMD_PATTERN = re.compile(
    r"<call_cmd>\s*(/[^<]*?)\s*</call_cmd>",
    re.DOTALL | re.IGNORECASE,
)
ALL_CALL_CMD_PATTERN = re.compile(
    r"<call_cmd>\s*(.*?)\s*</call_cmd>",
    re.DOTALL | re.IGNORECASE,
)
JSON_TOOL_KEYS = ("tool", "command", "action", "name")


def normalize_agent_command(command: str) -> str:
    """Normalize a command extracted from <call_cmd> blocks."""
    return command.rstrip("> ").strip()


def parse_agent_command(reply: str) -> AgentCommandParseResult:
    """Extract the last valid slash command and invalid blocks from reply."""
    all_matches = [match.strip() for match in CALL_CMD_PATTERN.findall(reply) if match.strip()]
    invalid_matches = tuple(
        match.strip()
        for match in ALL_CALL_CMD_PATTERN.findall(reply)
        if match.strip() and not match.strip().startswith("/")
    )
    command = all_matches[-1] if all_matches else None
    if not command:
        return AgentCommandParseResult(
            command=None,
            full_match=None,
            invalid_matches=invalid_matches,
        )

    raw_search = re.search(
        r"<call_cmd>\s*" + re.escape(command) + r"\s*</call_cmd>",
        reply,
        re.DOTALL | re.IGNORECASE,
    )
    full_match = raw_search.group(0) if raw_search else f"<call_cmd>{command}</call_cmd>"
    return AgentCommandParseResult(
        command=normalize_agent_command(command),
        full_match=full_match,
        invalid_matches=invalid_matches,
    )


def detect_json_tool_name(reply: str) -> str | None:
    """Return hallucinated JSON tool name when reply looks like a tool payload."""
    clean_reply = reply.strip()
    if not (clean_reply.startswith("{") and clean_reply.endswith("}")):
        return None

    try:
        data = json.loads(clean_reply)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    for key in JSON_TOOL_KEYS:
        if key in data:
            value = data.get(key)
            return str(value or "unknown_tool")
    return None
