from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "ui" / "console.py"
SPEC = importlib.util.spec_from_file_location(
    "ui_console_under_test",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
UI_CONSOLE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = UI_CONSOLE
SPEC.loader.exec_module(UI_CONSOLE)

_build_omni_query = UI_CONSOLE._build_omni_query
_auto_disable_omni_on_agent_error = (
    UI_CONSOLE._auto_disable_omni_on_agent_error
)
_looks_like_noisy_response = UI_CONSOLE._looks_like_noisy_response


def test_context_dependent_followup_is_enriched() -> None:
    history = [
        {
            "role": "user",
            "text": (
                "bir roket fırlatma üssünde çalışacak agentları belirle, "
                "hesaplar octave ile simüle edilecek"
            ),
        },
        {"role": "assistant", "text": "Tamam, rol dağılımı yapıyorum."},
        {
            "role": "user",
            "text": "Bağlamı kontrol et roket fırlatma üssü ve görevler.",
        },
    ]
    config = {
        "omni_context_enrichment": True,
        "omni_context_turns": 2,
        "omni_context_chars": 800,
    }

    query = _build_omni_query(history, config)

    assert "Sohbet bağlamı" in query
    assert "agentları belirle" in query
    assert "Bağlamı kontrol et roket fırlatma üssü ve görevler." in query


def test_non_followup_query_is_not_enriched() -> None:
    history = [
        {
            "role": "user",
            "text": "roket fırlatma üssü için görev dağılımını çıkar",
        },
    ]
    config = {"omni_context_enrichment": True}

    query = _build_omni_query(history, config)

    assert query == "roket fırlatma üssü için görev dağılımını çıkar"


def test_enrichment_can_be_disabled() -> None:
    history = [
        {"role": "user", "text": "roket görev planı"},
        {"role": "assistant", "text": "Tamam"},
        {"role": "user", "text": "Bağlamı kontrol et"},
    ]
    config = {"omni_context_enrichment": False}

    query = _build_omni_query(history, config)

    assert query == "Bağlamı kontrol et"
    assert "Sohbet bağlamı" not in query


def test_string_prompt_passthrough() -> None:
    config = {"omni_context_enrichment": True}

    query = _build_omni_query("tek satır prompt", config)

    assert query == "tek satır prompt"


def test_agent_error_fallback_switches_to_direct() -> None:
    """_auto_disable_omni_on_agent_error sets route=direct and saves prev."""
    from unittest.mock import patch

    config = {"generation_route": "omni", "omni_agent_error_fallback": True}

    with patch("lib.config.save_config") as mock_save:
        _auto_disable_omni_on_agent_error(config)

    assert config["generation_route"] == "direct"
    assert config.get("omni_previous_route") == "omni"
    mock_save.assert_called_once()


def test_agent_error_fallback_noop_when_already_direct() -> None:
    """When already direct, previous route is not overwritten."""
    from unittest.mock import patch

    config = {
        "generation_route": "direct",
        "omni_previous_route": "auto",
        "omni_agent_error_fallback": True,
    }

    with patch("lib.config.save_config"):
        _auto_disable_omni_on_agent_error(config)

    # Should remain direct, previous_route unchanged
    assert config["generation_route"] == "direct"
    assert config.get("omni_previous_route") == "auto"


# ---------------------------------------------------------------------------
# Noise detection tests
# ---------------------------------------------------------------------------

def test_rag_bleed_structural_pattern_detected() -> None:
    """Structural RAG bleed patterns are flagged as noisy."""
    response = (
        "Context:\nHere is the retrieved document about CAN-FD...\n"
        "Based on the provided context, CAN-FD is a..."
    )
    assert _looks_like_noisy_response(
        "roket fırlatma üssü görevleri", response, {}
    ) is True


def test_clean_response_not_flagged() -> None:
    """Normal on-topic response is not flagged."""
    response = (
        "Roket fırlatma üssü için 5 agent planladım: "
        "Hesaplama, Simülasyon, İzleme, Komuta, Lojistik."
    )
    assert _looks_like_noisy_response(
        "roket fırlatma üssü için agent planla", response, {}
    ) is False


def test_keyword_noise_hit_when_not_in_query() -> None:
    """User-defined noise keyword in response but not in query → noisy."""
    config = {"omni_noise_keywords": ["CAN-FD", "uçuş kontrol"]}
    response = (
        "CAN-FD protokolü uçuş kontrol sistemlerinde kullanılır."
    )
    assert _looks_like_noisy_response(
        "roket simülasyonu için octave kodu", response, config
    ) is True


def test_keyword_not_flagged_when_in_query() -> None:
    """Noise keyword present in query too → not flagged."""
    config = {"omni_noise_keywords": ["CAN-FD"]}
    response = "CAN-FD frame yapısı şöyledir..."
    assert _looks_like_noisy_response(
        "CAN-FD protokolünü açıkla", response, config
    ) is False
