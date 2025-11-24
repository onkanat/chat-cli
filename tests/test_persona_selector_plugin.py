from __future__ import annotations

import json
from pathlib import Path

import importlib.util
import sys


def _load_persona_plugin() -> type:
    project_root = Path(__file__).resolve().parents[1]
    plugin_path = project_root / "plugins" / "persona_selector.py"
    spec = importlib.util.spec_from_file_location("persona_selector_test", plugin_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load persona_selector plugin")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("persona_selector_test", module)
    spec.loader.exec_module(module)
    return module.PersonaSelectorPlugin


PersonaSelectorPlugin = _load_persona_plugin()


def _setup_plugin(tmp_path: Path) -> PersonaSelectorPlugin:
    plugin = PersonaSelectorPlugin()
    plugin.configure_storage(
        persona_dir=tmp_path / "system_prompts",
        config_path=tmp_path / "config.json",
        reset=True,
    )
    return plugin


def test_persona_set_updates_context_and_config(tmp_path):
    plugin = _setup_plugin(tmp_path)
    context = {"chat_context": {}, "config": {}}

    plugin.handle_persona_command(["set", "engineer"], context)

    assert context["chat_context"].get("persona") == "engineer"
    assert "persona_prompt" in context["chat_context"]

    saved_config = json.loads(plugin.config_path.read_text(encoding="utf-8"))
    assert saved_config["persona"]["current_persona"] == "engineer"


def test_persona_clear_resets_context_and_config(tmp_path):
    plugin = _setup_plugin(tmp_path)
    context = {"chat_context": {}, "config": {}}

    plugin.handle_persona_command(["set", "engineer"], context)
    plugin.handle_persona_command(["clear"], context)

    assert "persona" not in context["chat_context"]
    assert "persona_prompt" not in context["chat_context"]

    saved_config = json.loads(plugin.config_path.read_text(encoding="utf-8"))
    assert saved_config["persona"]["current_persona"] is None
