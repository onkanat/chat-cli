"""Test smart shell output summarization."""

from __future__ import annotations

import lib.history as history_mod


def test_is_safe_to_drop_info_commands():
    """Test that informational commands are detected correctly."""
    # Should be safe to drop
    assert history_mod._is_safe_to_drop("ls", "file1.txt\nfile2.txt") is True
    assert history_mod._is_safe_to_drop("ls -la", "drwxr-xr-x ...") is True
    assert history_mod._is_safe_to_drop("cat file.txt", "some content") is True
    assert history_mod._is_safe_to_drop("pwd", "/home/user") is True
    assert history_mod._is_safe_to_drop("echo hello", "hello") is True

    # Should NOT be safe to drop (errors)
    assert history_mod._is_safe_to_drop("ls", "ls: cannot access 'file': No such file") is False
    assert history_mod._is_safe_to_drop("cat", "cat: file.txt: Permission denied") is False

    # Should NOT be safe to drop (action commands)
    assert history_mod._is_safe_to_drop("python test.py", "output") is False
    assert history_mod._is_safe_to_drop("git commit", "committed") is False


def test_has_errors():
    """Test error detection in output."""
    assert history_mod._has_errors("Error: something went wrong") is True
    assert history_mod._has_errors("Exception: ValueError") is True
    assert history_mod._has_errors("Traceback (most recent call last)") is True
    assert history_mod._has_errors("FAILED tests/test.py") is True
    assert history_mod._has_errors("Fatal: cannot proceed") is True
    assert history_mod._has_errors("Permission denied") is True
    assert history_mod._has_errors("No such file or directory") is True

    # No errors
    assert history_mod._has_errors("Success: all tests passed") is False
    assert history_mod._has_errors("Normal output") is False
    assert history_mod._has_errors("") is False


def test_extract_error_summary():
    """Test extracting only error lines."""
    output = """
Running tests...
test_one PASSED
test_two PASSED
test_three FAILED - AssertionError: expected 5, got 3
test_four PASSED
ERROR: Some other error occurred
All done.
"""

    summary = history_mod._extract_error_summary(output, max_chars=200)

    # Should contain error lines
    assert "FAILED" in summary
    assert "ERROR" in summary

    # Should NOT contain PASSED lines
    assert "test_one PASSED" not in summary
    assert "test_two PASSED" not in summary


def test_summarize_shell_output_smart_archive():
    """Test that archive context keeps full output."""
    long_output = "x" * 1000

    result = history_mod.summarize_shell_output_smart(
        command="python script.py",
        output=long_output,
        context_role="archive",
        max_chars=100,
    )

    # Should keep full output for archive
    assert result == long_output
    assert len(result) == 1000


def test_summarize_shell_output_smart_model_info_commands():
    """Test that info commands are omitted for model context."""
    # ls command with normal output
    result = history_mod.summarize_shell_output_smart(
        command="ls -la",
        output="file1.txt\nfile2.txt\nfile3.txt",
        context_role="model",
        max_chars=500,
    )

    assert result == "[Output omitted - visible in terminal]"

    # cat command with normal output
    result = history_mod.summarize_shell_output_smart(
        command="cat file.txt",
        output="some file content here",
        context_role="model",
        max_chars=500,
    )

    assert result == "[Output omitted - visible in terminal]"


def test_summarize_shell_output_smart_model_errors():
    """Test that errors are extracted for model context."""
    error_output = """
Running tests...
test_one PASSED
test_two FAILED - AssertionError
test_three PASSED
ERROR: Something went wrong
More output here
"""

    result = history_mod.summarize_shell_output_smart(
        command="python -m pytest",
        output=error_output,
        context_role="model",
        max_chars=200,
    )

    # Should extract only error lines
    assert "FAILED" in result
    assert "ERROR" in result
    # Should not contain PASSED lines
    assert "test_one PASSED" not in result


def test_summarize_shell_output_smart_model_short():
    """Test that short outputs are kept as-is."""
    short_output = "Success!"

    result = history_mod.summarize_shell_output_smart(
        command="python script.py",
        output=short_output,
        context_role="model",
        max_chars=500,
    )

    assert result == short_output


def test_summarize_shell_output_smart_model_action_commands():
    """Test that action commands (not info) get standard summarization."""
    long_output = "x" * 1000

    result = history_mod.summarize_shell_output_smart(
        command="python script.py",
        output=long_output,
        context_role="model",
        max_chars=200,
    )

    # Should be summarized (not full, not omitted)
    assert len(result) < 1000
    assert len(result) > 0
    assert "[truncated" in result.lower() or "omitted" in result.lower()


def test_build_model_messages_uses_smart_shell():
    """Test that build_model_messages_from_history uses smart shell output."""
    history = [
        {"role": "user", "text": "Run ls"},
        {"role": "shell", "command": "ls", "output": "file1.txt\nfile2.txt\nfile3.txt"},
        {"role": "user", "text": "What files?"},
    ]

    msgs = history_mod.build_model_messages_from_history(
        history,
        model_name="gemma:2b",  # Small model
    )

    # Find shell output message
    shell_output = None
    for msg in msgs:
        if msg.get("role") == "user" and "Shell output:" in msg.get("content", ""):
            shell_output = msg["content"]
            break

    # Should be omitted for model context
    assert shell_output is not None
    assert "[Output omitted" in shell_output or "file1.txt" not in shell_output


def test_build_model_messages_keeps_error_output():
    """Test that error outputs are kept."""
    history = [
        {"role": "user", "text": "Run test"},
        {"role": "shell", "command": "python test.py", "output": "Error: test failed\nTraceback...\nmore errors"},
        {"role": "user", "text": "Fix it"},
    ]

    msgs = history_mod.build_model_messages_from_history(
        history,
        model_name="gemma:2b",
    )

    # Find shell output message
    shell_output = None
    for msg in msgs:
        if msg.get("role") == "user" and "Shell output:" in msg.get("content", ""):
            shell_output = msg["content"]
            break

    # Error output should be extracted
    assert shell_output is not None
    assert "Error" in shell_output or "error" in shell_output.lower()
