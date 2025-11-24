from __future__ import annotations

import re

# Env defaults
DEFAULT_MAX_OUTPUT_CHARS = int(
    __import__("os").getenv("OLLAMA_MAX_OUTPUT_CHARS", "500")
)


def is_traceback(text: str) -> bool:
    """Check if text appears to be a traceback or error message.
    
    Args:
        text: Text to check for traceback patterns
        
    Returns:
        True if text contains traceback indicators
    """
    if not text:
        return False

    traceback_indicators = [
        "Traceback (most recent call last):",
        "Traceback:",
        "Error:",
        "Exception:",
        "ZeroDivisionError:",
        "TypeError:",
        "ValueError:",
        "KeyError:",
        "AttributeError:",
        "ImportError:",
        "ModuleNotFoundError:",
        "FileNotFoundError:",
        "PermissionError:",
        "ConnectionError:",
        "TimeoutError:",
        "RuntimeError:",
        "SyntaxError:",
        "IndentationError:",
        "NameError:",
        "UnboundLocalError:",
    ]

    # Check for common traceback patterns
    for indicator in traceback_indicators:
        if indicator in text:
            return True

    # Check for file line patterns (common in tracebacks)
    if re.search(r'File\s+"[^"]+",\s+line\s+\d+', text):
        return True

    # Check for "in <module>" pattern
    if "in <module>" in text:
        return True

    return False


def is_safe_to_drop(command: str, output: str) -> bool:
    """Check if shell output is informational and can be omitted for model context.
    
    These are commands whose output is visible in terminal and don't need
    to be sent to the model (e.g., ls, cat, echo).
    
    Args:
        command: Shell command that was executed
        output: Command output
        
    Returns:
        True if output can be safely omitted from model context
    """
    if not command or not output:
        return False

    cmd_lower = command.lower().strip()

    # Info commands that don't need model analysis
    info_commands = ["ls", "dir", "cat", "echo", "pwd", "date", "whoami", "id"]

    # Check if command starts with info command
    for cmd in info_commands:
        if cmd_lower.startswith(cmd + " ") or cmd_lower == cmd:
            # But keep if output has errors
            if has_errors(output):
                return False
            return True

    return False


def has_errors(text: str) -> bool:
    """Check if text contains error indicators.
    
    Args:
        text: Text to check for errors
        
    Returns:
        True if error indicators found
    """
    if not text:
        return False

    error_indicators = [
        "error:",
        "exception:",
        "traceback",
        "failed",
        "fatal:",
        "cannot",
        "permission denied",
        "not found",
        "no such file",
    ]

    text_lower = text.lower()
    return any(indicator in text_lower for indicator in error_indicators)


def extract_error_summary(text: str, max_chars: int = 200) -> str:
    """Extract only error/warning lines from output.
    
    Args:
        text: Full output text
        max_chars: Maximum characters to return
        
    Returns:
        Error summary or truncated text
    """
    if not text:
        return ""

    lines = text.split("\n")
    error_lines = []

    for line in lines:
        line_lower = line.lower()
        if any(word in line_lower for word in ["error", "exception", "warning", "failed", "traceback"]):
            error_lines.append(line)
            if len("\n".join(error_lines)) > max_chars:
                break

    if not error_lines:
        # No explicit errors found, return first and last few lines
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n...[truncated]"

    result = "\n".join(error_lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n...[truncated]"

    return result


def summarize_output(
    text: str | None, max_chars: int = DEFAULT_MAX_OUTPUT_CHARS
) -> str:
    """Standard shell output summarization.
    
    Keeps head and tail with highlights of errors/warnings/usage.
    
    Args:
        text: Shell output text
        max_chars: Maximum characters to keep
        
    Returns:
        Summarized text
    """
    if not text:
        return ""
    s = str(text)
    if len(s) <= max_chars:
        return s
    head = s[: max(200, int(max_chars / 4))]
    tail = s[-max(200, int(max_chars / 4)):]
    omitted = len(s) - (len(head) + len(tail))
    highlights = re.findall(r"(?im)^.*(?:error|usage|warning).*$", s)
    highlights = highlights[:3]
    summary = head + "\n...[truncated, omitted {} chars]...\n".format(omitted) + tail
    if highlights:
        summary += "\n\n[highlights]\n" + "\n".join(highlights)
    return summary


def summarize_smart(
    command: str,
    output: str | None,
    context_role: str = "model",
    max_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> str:
    """Smart shell output summarization based on context.
    
    Context-aware truncation that handles:
    - Archive context: keeps everything
    - Model context: aggressive truncation based on command type
    - Informational commands: omitted for model
    - Errors: extracts error lines only
    
    Args:
        command: The shell command that was executed
        output: The command output
        context_role: "model" (aggressively truncate) or "archive" (keep full)
        max_chars: Maximum characters to keep
        
    Returns:
        Summarized or full output based on context_role
    """
    if not output:
        return ""

    # Archive context: keep everything
    if context_role == "archive":
        return output

    # Model context: apply smart truncation
    output_str = str(output)

    # Check if it's safe to drop (informational commands) - do this before short check
    if is_safe_to_drop(command, output_str):
        return "[Output omitted - visible in terminal]"

    # Very short output: keep as is
    if len(output_str) < 100:
        return output_str

    # Has errors: extract only error lines
    if has_errors(output_str):
        return extract_error_summary(output_str, max_chars=max_chars)

    # Default: use standard summarization
    return summarize_output(output_str, max_chars=max_chars)
