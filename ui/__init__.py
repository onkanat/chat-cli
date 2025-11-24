"""UI package convenience exports and dynamic attribute proxying.

This module makes ``import ui as ui_mod`` behave like the previous flat ``ui.py``
by proxying to the submodules and exposing common helpers like ``console``.
"""

from ui import inputs  # noqa: F401
from ui import renderers  # noqa: F401
from ui import stream_display  # noqa: F401

import importlib
_ui_console_mod = importlib.import_module("ui.console")
console = _ui_console_mod.console


def __getattr__(name: str):
    # Delegate dynamic attribute resolution to ui.console
    return getattr(_ui_console_mod, name)
