from __future__ import annotations

from pathlib import Path
import lib.history as history_mod


def run(path: str) -> None:
    history_mod.save_history([], Path(path))
