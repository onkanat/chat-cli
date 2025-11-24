from main import (
    summarize_shell_output,
    _estimate_tokens,
    _trim_history_for_tokens,
    build_model_messages_from_history,
)


def make_long_text(prefix: str = "line", n_lines: int = 2000) -> str:
    return "\n".join(f"{prefix} {i}" for i in range(n_lines))


def test_summarize_shell_output_truncates_and_highlights():
    long = make_long_text("info", 1000)
    # insert some lines that should be detected as highlights
    long += "\nERROR: something failed\nusage: foo [options]\n"
    s = summarize_shell_output(long, max_chars=500)
    assert "[truncated" in s or "[highlights]" in s
    # highlights should appear
    assert "ERROR: something failed" in s
    assert len(s) < len(long)


def test_estimate_tokens_heuristic():
    txt = "a" * 400
    toks = _estimate_tokens(txt)
    # heuristic is roughly len/4
    assert toks >= 80
    assert toks <= 120


def test_trim_history_for_tokens_keeps_recent():
    # create many user turns each ~200 chars
    history = []
    for i in range(30):
        history.append({"role": "user", "text": "x" * 200})
    # set a small max token budget so only a few recent turns fit
    trimmed = _trim_history_for_tokens(
        history, max_tokens=200, reserve_for_response=10
    )
    assert len(trimmed) < len(history)
    # last element of trimmed should equal last of original
    assert trimmed[-1]["text"] == history[-1]["text"]


def test_build_model_messages_summarizes_shell_output():
    big_output = make_long_text("output", 2000)
    history = [
        {"role": "user", "text": "run something"},
        {"role": "shell", "command": "man ls", "output": big_output},
    ]
    msgs = build_model_messages_from_history(
        history, max_turns=10, max_tokens=2000
    )
    # Expect a system + user + user(shell) messages
    contents = "\n".join(m["content"] for m in msgs if m.get("content"))
    assert "Shell command executed: man ls" in contents
    assert "Shell output:\n" in contents
    # the shell output included should be much shorter than original
    assert len(contents) < len(big_output)
