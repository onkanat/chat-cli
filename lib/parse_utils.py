"""Unified argument parsing utilities for both user and agent command paths."""

from __future__ import annotations

import shlex


def parse_command_string(input_str: str) -> tuple[str, list[str]]:
    """
    Parse a command string into command and arguments.

    Safely handles shlex errors with fallback to simple split.

    Args:
        input_str: Raw command string (e.g., '/load model-name')

    Returns:
        Tuple of (command, args)
        - command: Command name without leading slash (e.g., 'load')
        - args: List of argument strings
    """
    input_str = input_str.strip()

    # Try shlex for quoted string support
    try:
        parts = shlex.split(input_str)
    except ValueError:
        # Fallback: simple whitespace split
        parts = input_str.split()

    if not parts:
        return "", []

    # Extract command (remove leading slash if present)
    cmd = parts[0].lstrip("/")
    args = parts[1:]

    return cmd, args


def parse_run_args(args: list[str]) -> tuple[str | None, str | None]:
    """
    Parse /run command arguments into model and prompt.

    Handles:
    - `/run model prompt text...` → (model, "prompt text...")
    - `/run model` → (model, None)
    - `/run` → (None, None)

    Args:
        args: Arguments after /run command

    Returns:
        Tuple of (model_name, prompt_text)
        - model_name: Model to use, or None if not provided
        - prompt_text: Prompt string, or None if not provided
    """
    if not args:
        return None, None

    model = args[0] if args else None
    prompt = " ".join(args[1:]) if len(args) > 1 else None

    return model, prompt


def parse_settings_args(args: list[str]) -> tuple[str | None, str | None]:
    """
    Parse /settings command arguments into key and value.

    Handles:
    - `/settings key value` → (key, value)
    - `/settings key` → (key, None)
    - `/settings` → (None, None)

    Args:
        args: Arguments after /settings command

    Returns:
        Tuple of (key, value)
        - key: Setting key name, or None
        - value: Setting value, or None
    """
    if not args:
        return None, None

    key = args[0] if args else None
    value = " ".join(args[1:]) if len(args) > 1 else None

    return key, value


def parse_search_args(args: list[str]) -> str:
    """
    Parse /search command arguments into a query string.

    Args:
        args: Arguments after /search command

    Returns:
        Query string (space-joined args), or empty string
    """
    return " ".join(args) if args else ""


def parse_plugin_args(args: list[str]) -> tuple[str | None, list[str]]:
    """
    Parse /plugin command arguments into plugin name and sub-args.

    Handles:
    - `/plugin info name` → (info, [name])
    - `/plugin list` → (list, [])
    - `/plugin` → (None, [])

    Args:
        args: Arguments after /plugin command

    Returns:
        Tuple of (subcommand, remaining_args)
    """
    if not args:
        return None, []

    subcommand = args[0]
    remaining = args[1:] if len(args) > 1 else []

    return subcommand, remaining


def parse_export_args(args: list[str]) -> tuple[str | None, str | None]:
    """
    Parse /export command arguments into format and filename.

    Handles:
    - `/export json filename.json` → (json, filename.json)
    - `/export json` → (json, None)
    - `/export` → (None, None)

    Args:
        args: Arguments after /export command

    Returns:
        Tuple of (format, filename)
    """
    if not args:
        return None, None

    fmt = args[0]
    filename = args[1] if len(args) > 1 else None

    return fmt, filename
