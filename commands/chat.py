from __future__ import annotations

from repl.loop import run_chat


def run(
    history_file: str,
    base_url: str | None,
    stream: bool,
    max_context_tokens: int,
    max_output_chars: int,
) -> None:
    run_chat(
        history_file=history_file,
        base_url=base_url,
        stream=stream,
        max_context_tokens=max_context_tokens,
        max_output_chars=max_output_chars,
    )
