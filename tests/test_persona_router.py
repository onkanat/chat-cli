"""Auto-Router: get_best_persona() ve repl hook testleri."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plugin(personas: Dict[str, Any]):
    """Verilen persona sözlüğüyle PersonaSelectorPlugin oluştur."""
    from plugins.persona_selector import PersonaSelectorPlugin

    plugin = PersonaSelectorPlugin.__new__(PersonaSelectorPlugin)
    # minimal init
    plugin.name = "persona_selector"
    plugin.version = "0.0.0"
    plugin.description = "test"
    plugin.author = "test"
    plugin.persona_dir = Path("/tmp/persona_test")
    plugin.persona_file = plugin.persona_dir / "personas.json"
    plugin.config_path = Path("/tmp/persona_test_config.json")
    plugin._system_prompts_path = None
    plugin._using_skills_source = False
    plugin.personas = personas
    return plugin


ELECTRONICS_PERSONAS = {
    "electronics_analog": {
        "id": "electronics_analog",
        "name": "Analog Elektronik Uzmanı",
        "style": "Teknik",
        "tags": ["electronics", "analog", "circuit", "opamp", "devre"],
        "prompt": "Sen analog elektronik uzmanısın.",
    },
    "cpp_engineer": {
        "id": "cpp_engineer",
        "name": "C++ Mühendisi",
        "style": "Sistem programlama",
        "tags": ["c++", "cpp", "sistem", "embedded", "gömülü"],
        "prompt": "Sen C++ mühendisisin.",
    },
    "math_teacher": {
        "id": "math_teacher",
        "name": "Matematik Öğretmeni",
        "style": "Öğretici",
        "tags": ["matematik", "calculus", "türev", "integral"],
        "prompt": "Sen matematik öğretmenisin.",
    },
}


# ---------------------------------------------------------------------------
# Faz 2: get_best_persona() unit tests
# ---------------------------------------------------------------------------


class TestGetBestPersona:
    def test_electronics_prompt_returns_electronics_persona(self):
        plugin = _make_plugin(ELECTRONICS_PERSONAS)
        result = plugin.get_best_persona(
            "bir opamp devre tasarımı nasıl yapılır"
        )
        assert result == "electronics_analog"

    def test_cpp_prompt_returns_cpp_persona(self):
        plugin = _make_plugin(ELECTRONICS_PERSONAS)
        result = plugin.get_best_persona("c++ ile embedded sistem programlama")
        assert result == "cpp_engineer"

    def test_math_prompt_returns_math_persona(self):
        plugin = _make_plugin(ELECTRONICS_PERSONAS)
        result = plugin.get_best_persona("türev ve integral nasıl hesaplanır")
        assert result == "math_teacher"

    def test_irrelevant_prompt_returns_none(self):
        plugin = _make_plugin(ELECTRONICS_PERSONAS)
        # Tamamen alakasız mesaj → threshold geçilmemeli
        result = plugin.get_best_persona("bugün hava güzel")
        assert result is None

    def test_empty_personas_returns_none(self):
        plugin = _make_plugin({})
        result = plugin.get_best_persona("electronics devre tasarımı")
        assert result is None

    def test_threshold_filters_weak_matches(self):
        plugin = _make_plugin(ELECTRONICS_PERSONAS)
        # Çok yüksek threshold → hiçbir şey geçemez
        result = plugin.get_best_persona(
            "bir opamp devre tasarımı nasıl yapılır", threshold=999.0
        )
        assert result is None

    def test_low_threshold_returns_match(self):
        plugin = _make_plugin(ELECTRONICS_PERSONAS)
        # Çok düşük threshold → en küçük eşleşme bile geçer
        result = plugin.get_best_persona("devre", threshold=0.1)
        assert result is not None

    def test_returns_string_type(self):
        plugin = _make_plugin(ELECTRONICS_PERSONAS)
        result = plugin.get_best_persona("c++ gömülü sistem kodu")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Faz 1: select_persona.py'daki get_best_persona() unit tests
# ---------------------------------------------------------------------------


class TestSelectPersonaModule:
    """system_prompts/select_persona.py modülü testleri."""

    SP_PATH = Path(__file__).parent.parent.parent / "system_prompts"

    def _import_sp(self):
        """select_persona modülünü sys.path'e ekleyerek import et."""
        import sys

        sp_str = str(self.SP_PATH)
        if sp_str not in sys.path:
            sys.path.insert(0, sp_str)
        try:
            import importlib

            import select_persona as sp  # type: ignore[import]

            importlib.reload(sp)
            return sp
        except ImportError:
            pytest.skip("select_persona modülü bulunamadı")

    def test_get_best_persona_missing_file_returns_none(self):
        sp = self._import_sp()
        result = sp.get_best_persona(
            "bir devre tasarımı",
            persona_map_file="/nonexistent/path/persona_map.yaml",
        )
        assert result is None

    def test_get_best_persona_with_yaml(self, tmp_path):
        """Geçici YAML dosyasıyla temel işlevsellik testi."""
        try:
            import yaml  # noqa: F401
        except ImportError:
            pytest.skip("PyYAML kurulu değil")

        sp = self._import_sp()

        persona_map = {
            "personas": [
                {
                    "id": "math_expert",
                    "description": "Matematik uzmanı",
                    "tags": ["matematik", "calculus", "türev"],
                },
                {
                    "id": "code_expert",
                    "description": "Kod uzmanı",
                    "tags": ["python", "code", "debug"],
                },
            ]
        }
        yaml_file = tmp_path / "persona_map.yaml"
        import yaml as _yaml

        yaml_file.write_text(
            _yaml.dump(persona_map, allow_unicode=True), encoding="utf-8"
        )

        result = sp.get_best_persona(
            "türev integral matematik sorusu",
            persona_map_file=str(yaml_file),
        )
        assert result == "math_expert"

    def test_get_best_persona_below_threshold_returns_none(self, tmp_path):
        try:
            import yaml  # noqa: F401
        except ImportError:
            pytest.skip("PyYAML kurulu değil")

        sp = self._import_sp()
        import yaml as _yaml

        persona_map = {
            "personas": [
                {
                    "id": "math_expert",
                    "description": "Matematik",
                    "tags": ["matematik"],
                },
            ]
        }
        yaml_file = tmp_path / "persona_map.yaml"
        yaml_file.write_text(
            _yaml.dump(persona_map, allow_unicode=True), encoding="utf-8"
        )

        result = sp.get_best_persona(
            "matematik",
            persona_map_file=str(yaml_file),
            threshold=999.0,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Faz 4: repl/loop.py auto-router hook testleri (entegrasyon)
# ---------------------------------------------------------------------------


class TestAutoRouterHook:
    """config['auto_persona_routing'] toggle ve switch senaryoları."""

    def _run_minimal_loop_step(
        self,
        prompt: str,
        auto_routing: bool,
        current_persona: str | None,
        best_persona: str | None,
    ) -> str | None:
        """
        loop.py'deki auto-router mantığını izole eden simülasyon.
        Gerçek loop'u çağırmaz — sadece dallanma mantığını test eder.
        """
        chat_context: Dict[str, Any] = {}
        if current_persona:
            chat_context["persona"] = current_persona

        config = {"auto_persona_routing": auto_routing}

        persona_plugin = _make_plugin(ELECTRONICS_PERSONAS)
        # get_best_persona() mock'la
        persona_plugin.get_best_persona = MagicMock(  # noqa: E501
            return_value=best_persona
        )  # type: ignore[method-assign]
        persona_plugin._set_persona = (  # type: ignore
            MagicMock()
        )

        ui_mod = MagicMock()

        # Auto-Router mantığı (loop.py'den kopyalanmış)
        if config.get("auto_persona_routing") and persona_plugin:
            bid = persona_plugin.get_best_persona(prompt)
            if bid and bid != chat_context.get("persona"):
                persona_plugin._set_persona(bid, {})
                ui_mod.console.print(f"[dim]🔄 Persona: {bid}[/dim]")

        if persona_plugin._set_persona.called:  # type: ignore[union-attr]
            return persona_plugin._set_persona.call_args[0][0]
        return None

    def test_routing_disabled_no_switch(self):
        switched_to = self._run_minimal_loop_step(
            prompt="bir opamp devre tasarımı",
            auto_routing=False,
            current_persona=None,
            best_persona="electronics_analog",
        )
        assert switched_to is None

    def test_routing_enabled_switches_persona(self):
        switched_to = self._run_minimal_loop_step(
            prompt="bir opamp devre tasarımı",
            auto_routing=True,
            current_persona=None,
            best_persona="electronics_analog",
        )
        assert switched_to == "electronics_analog"

    def test_routing_enabled_same_persona_no_switch(self):
        """Zaten aktif persona en iyiyse tekrar switch olmaz."""
        switched_to = self._run_minimal_loop_step(
            prompt="bir opamp devre tasarımı",
            auto_routing=True,
            current_persona="electronics_analog",
            best_persona="electronics_analog",
        )
        assert switched_to is None

    def test_routing_enabled_no_match_no_switch(self):
        """IDF motoru None döndürürse (eşleşme yok) switch olmaz."""
        switched_to = self._run_minimal_loop_step(
            prompt="bugün hava güzel",
            auto_routing=True,
            current_persona=None,
            best_persona=None,
        )
        assert switched_to is None

    def test_routing_switches_from_one_to_another(self):
        """Farklı bir persona aktifken yeni eşleşme bulunursa switch olur."""
        switched_to = self._run_minimal_loop_step(
            prompt="c++ gömülü sistem kodu",
            auto_routing=True,
            current_persona="math_teacher",
            best_persona="cpp_engineer",
        )
        assert switched_to == "cpp_engineer"
