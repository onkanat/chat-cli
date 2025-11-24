from __future__ import annotations

from typing import Optional

import ui as ui_mod
from rich.panel import Panel

from services.settings_service import determine_base_url, load_config
import lib.ollama_wrapper as ow
from services.models_service import list_models


def run(base_url: Optional[str] = None) -> None:
    config = load_config()
    resolved = determine_base_url(config, base_url)
    if resolved:
        ow.init_client(resolved)
    models = list_models()
    if not models:
        ui_mod.console.print("[yellow]No models found or ollama client unavailable.[/yellow]")
        return
    ui_mod.console.print(Panel("\n".join(models), title="Models", expand=False))
