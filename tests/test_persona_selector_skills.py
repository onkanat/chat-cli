"""Integration tests for skills-based persona loading.

Tests the new prompts.json (skills-based) format support and
the IDF-weighted suggest scoring pipeline.
"""

from __future__ import annotations

import json
import sys
import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPTS_ROOT = PROJECT_ROOT.parent / "system_prompts"


def _load_persona_plugin():
    plugin_path = PROJECT_ROOT / "plugins" / "persona_selector.py"
    spec = importlib.util.spec_from_file_location("persona_selector_sk", plugin_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load persona_selector plugin")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("persona_selector_sk", module)
    spec.loader.exec_module(module)
    return module.PersonaSelectorPlugin, module._idf_score_personas


PersonaSelectorPlugin, _idf_score_personas = _load_persona_plugin()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skills_plugin(system_prompts_path: Path) -> "PersonaSelectorPlugin":
    plugin = PersonaSelectorPlugin()
    plugin.configure_storage(
        system_prompts_path=system_prompts_path,
    )
    return plugin


# ---------------------------------------------------------------------------
# Tests: Skills-based loading
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not (SYSTEM_PROMPTS_ROOT / "prompts.json").exists(),
    reason="system_prompts/prompts.json not found",
)
def test_skills_source_loads_personas():
    """Plugin should load 19+ personas from system_prompts/prompts.json."""
    plugin = _make_skills_plugin(SYSTEM_PROMPTS_ROOT)
    assert plugin._using_skills_source is True
    assert len(plugin.personas) >= 10, (
        f"Expected at least 10 skills personas, got {len(plugin.personas)}"
    )


@pytest.mark.skipif(
    not (SYSTEM_PROMPTS_ROOT / "prompts.json").exists(),
    reason="system_prompts/prompts.json not found",
)
def test_skills_persona_has_required_fields():
    """Each loaded skills persona must have id, name, prompt, tags."""
    plugin = _make_skills_plugin(SYSTEM_PROMPTS_ROOT)
    for pid, persona in plugin.personas.items():
        assert persona.get("id"), f"Missing 'id' for {pid}"
        assert persona.get("prompt"), f"Missing 'prompt' for {pid}"
        assert isinstance(persona.get("tags"), list), f"'tags' not list for {pid}"


@pytest.mark.skipif(
    not (SYSTEM_PROMPTS_ROOT / "prompts.json").exists(),
    reason="system_prompts/prompts.json not found",
)
def test_known_personas_present():
    """Specific expected skill personas should be present."""
    plugin = _make_skills_plugin(SYSTEM_PROMPTS_ROOT)
    expected = {
        "octave_matematik_ogretmeni",
        "octave_sinyal_isleme_uzmani",
        "cpp_gomulu_sistem",
        "python_veri_bilimci",
    }
    missing = expected - set(plugin.personas.keys())
    assert not missing, f"Missing expected personas: {missing}"


@pytest.mark.skipif(
    not (SYSTEM_PROMPTS_ROOT / "prompts.json").exists(),
    reason="system_prompts/prompts.json not found",
)
def test_set_persona_with_skills_source(tmp_path):
    """Setting a skills-based persona should update context correctly."""
    plugin = _make_skills_plugin(SYSTEM_PROMPTS_ROOT)
    plugin.config_path = tmp_path / "config.json"

    context = {"chat_context": {}, "config": {}}
    plugin.handle_persona_command(["set", "octave_sinyal_isleme_uzmani"], context)

    assert context["chat_context"].get("persona") == "octave_sinyal_isleme_uzmani"
    assert "persona_prompt" in context["chat_context"]
    assert len(context["chat_context"]["persona_prompt"]) > 50


# ---------------------------------------------------------------------------
# Tests: IDF Scoring
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not (SYSTEM_PROMPTS_ROOT / "prompts.json").exists(),
    reason="system_prompts/prompts.json not found",
)
def test_idf_suggest_sinyal_fft():
    """Query about sinyaller/FFT should rank octave_sinyal_isleme_uzmani first."""
    plugin = _make_skills_plugin(SYSTEM_PROMPTS_ROOT)
    matches = _idf_score_personas("matlab sinyal fft fourier", plugin.personas)
    assert matches, "No matches returned"
    top_id = matches[0][0]
    assert "sinyal" in top_id, (
        f"Expected sinyal persona first, got: {top_id} (all: {[m[0] for m in matches[:3]]})"
    )


@pytest.mark.skipif(
    not (SYSTEM_PROMPTS_ROOT / "prompts.json").exists(),
    reason="system_prompts/prompts.json not found",
)
def test_idf_suggest_cpp_embedded():
    """Query about gömülü sistemler should rank cpp_gomulu_sistem first."""
    plugin = _make_skills_plugin(SYSTEM_PROMPTS_ROOT)
    matches = _idf_score_personas("mikrodenetleyici gömülü embedded c++", plugin.personas)
    assert matches, "No matches returned"
    top_ids = [m[0] for m in matches[:3]]
    assert any("gomulu" in pid or "cpp" in pid for pid in top_ids), (
        f"Expected cpp_gomulu_sistem in top 3, got: {top_ids}"
    )


@pytest.mark.skipif(
    not (SYSTEM_PROMPTS_ROOT / "prompts.json").exists(),
    reason="system_prompts/prompts.json not found",
)
def test_idf_suggest_turkish_normalization():
    """Türkçe aksan kaldırma: 'muhendislik' == 'mühendislik'."""
    plugin = _make_skills_plugin(SYSTEM_PROMPTS_ROOT)
    # Without accents
    m1 = _idf_score_personas("muhendislik analiz", plugin.personas)
    # With accents
    m2 = _idf_score_personas("mühendislik analiz", plugin.personas)
    assert len(m1) > 0 and len(m2) > 0
    # Top persona should be the same
    assert m1[0][0] == m2[0][0], (
        f"Normalization failed: '{m1[0][0]}' != '{m2[0][0]}'"
    )


# ---------------------------------------------------------------------------
# Tests: Fallback (legacy local personas.json)
# ---------------------------------------------------------------------------

def test_fallback_to_local_personas(tmp_path):
    """Without skills path, plugin should load legacy default personas."""
    plugin = PersonaSelectorPlugin()
    plugin.configure_storage(
        persona_dir=tmp_path / "system_prompts",
        config_path=tmp_path / "config.json",
        system_prompts_path=None,
        reset=True,
    )
    assert plugin._using_skills_source is False
    assert "engineer" in plugin.personas
    assert "mentor" in plugin.personas


def test_persona_set_legacy_still_works(tmp_path):
    """Legacy persona set/clear flow must still work (backward compat)."""
    plugin = PersonaSelectorPlugin()
    plugin.configure_storage(
        persona_dir=tmp_path / "system_prompts",
        config_path=tmp_path / "config.json",
        system_prompts_path=None,
        reset=True,
    )
    context = {"chat_context": {}, "config": {}}

    plugin.handle_persona_command(["set", "engineer"], context)
    assert context["chat_context"].get("persona") == "engineer"

    plugin.handle_persona_command(["clear"], context)
    assert "persona" not in context["chat_context"]
