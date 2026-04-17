"""Unified argument parsing utilities for both user and agent command paths."""

from __future__ import annotations

import re
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


def parse_natural_language_command(
    input_str: str,
) -> tuple[str, list[str]] | None:
    """
    Detect simple natural-language requests that should map to slash commands.

    This intentionally supports only a small, safe subset to avoid accidental
    command execution from general conversation text.

    Supported mappings:
    - plugin list requests -> /plugins
    - available plugin list requests -> /plugins-available
    - help requests -> /help
    - explicit /wiki add|save mentions -> /wiki add|save ...
    """
    if not input_str:
        return None

    text = input_str.strip()
    if not text or text.startswith("/") or text.startswith("!"):
        return None

    normalized = text.lower()

    # Embedded explicit wiki command mention inside natural language, e.g.
    # "... /wiki add yeni_sayfa.md \"Başlık\" ..."
    wiki_match = re.search(r"(?<!\w)/wiki\s+(add|save)\b", normalized)
    if wiki_match:
        embedded_cmd = text[wiki_match.start():].strip()
        cmd, args = parse_command_string(embedded_cmd)
        if cmd == "wiki" and args and args[0] in {"add", "save"}:
            return cmd, args

    # Accept bare imperative forms that begin with "wiki add|save".
    if re.match(r"^\s*wiki\s+(add|save)\b", normalized):
        cmd, args = parse_command_string(text)
        if cmd == "wiki" and args and args[0] in {"add", "save"}:
            return cmd, args

    # Explicit slash command mention in natural language, e.g.
    # "'/help' komutunu çalıştır" or "lütfen /plugins".
    explicit_match = re.search(
        r"(?<!\w)/(help|plugins(?:-available)?)\b",
        normalized,
    )

    list_verbs = (
        "liste",
        "list",
        "yazdır",
        "yazdir",
        "göster",
        "goster",
        "print",
        "show",
        "display",
    )
    run_verbs = (
        "çalıştır",
        "calistir",
        "run",
        "execute",
    )
    plugin_words = (
        "plugin",
        "plugins",
        "eklenti",
        "eklentiler",
    )

    has_plugin_word = any(word in normalized for word in plugin_words)
    has_list_verb = any(verb in normalized for verb in list_verbs)
    has_run_verb = any(verb in normalized for verb in run_verbs)

    if explicit_match:
        explicit_cmd = explicit_match.group(1)
        only_command_mention = bool(
            re.fullmatch(
                r"[\s'\"`]*/(?:help|plugins(?:-available)?)[\s'\"`]*",
                normalized,
            )
        )
        if (
            only_command_mention
            or has_run_verb
            or has_list_verb
            or "komut" in normalized
            or "command" in normalized
        ):
            return explicit_cmd, []

    if has_plugin_word and has_list_verb:
        available_words = (
            "available",
            "kullanılabilir",
            "kullanilabilir",
            "mevcut",
            "yüklenebilir",
            "yuklenebilir",
        )
        if any(word in normalized for word in available_words):
            return "plugins-available", []
        return "plugins", []

    # Keep help intent strict to imperative forms to reduce false positives.
    help_word = bool(re.search(r"\b(help|yardım|yardim)\b", normalized))
    asks_for_help = normalized in {"help", "yardım", "yardim"}
    if help_word and (has_run_verb or has_list_verb or asks_for_help):
        return "help", []

    return None
