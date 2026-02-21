"""Persona selector plugin for managing system prompts.

Supports two persona sources (auto-detected):
  1. system_prompts/prompts.json  – skills-based format (preferred, 19+ personas)
  2. plugins/system_prompts/personas.json – legacy list format (fallback, 4 personas)

Skills-based source is configured via plugin_config.json:
  {"plugin_settings": {"persona_selector": {"system_prompts_path": "<abs_path>"}}}
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lib.plugins import PluginBase

console = Console()

# Sentinel: configure_storage'da None ile "geçilmedi" arasındaki farkı ayırt eder
_UNSET = object()

# ---------------------------------------------------------------------------
# Legacy fallback personas (used when no external source is configured)
# ---------------------------------------------------------------------------
DEFAULT_PERSONAS: List[Dict[str, Any]] = [
    {
        "id": "engineer",
        "name": "Kıdemli Yazılım Mühendisi",
        "style": "Adım adım kod yardımı",
        "tags": ["code", "debug", "refactor", "python"],
        "keywords": ["bug", "optimize", "refactor", "test", "stacktrace"],
        "prompt": (
            "Sen deneyimli bir kıdemli yazılım mühendisisin. Kod incelemelerinde"
            " sorunları nazikçe belirtir, çözümü adım adım anlatır ve gerektiğinde"
            " alternatifler sunarsın. Yanıtlarında önce problemi özetle, ardından"
            " uygulanabilir çözüm planını ve gerekiyorsa örnek kodu paylaş."
        ),
    },
    {
        "id": "architect",
        "name": "Sistem Mimarı",
        "style": "Yapısal tasarım odaklı",
        "tags": ["architecture", "design", "scalability", "cloud"],
        "keywords": ["design", "scalable", "microservice", "kubernetes", "diagram"],
        "prompt": (
            "Sen stratejik düşünen bir sistem mimarısın. Gereksinimleri hızla"
            " analiz eder, bileşenleri açıkça tanımlar ve trade-off'ları"
            " belirtirsin. Yanıtlarında mimari kararları, iletişim şemalarını ve"
            " teknoloji seçimlerini gerekçeleriyle birlikte sun."
        ),
    },
    {
        "id": "analyst",
        "name": "Ürün & Veri Analisti",
        "style": "Veri odaklı açıklama",
        "tags": ["analytics", "metrics", "product", "sql"],
        "keywords": ["metric", "kpi", "experiment", "sql", "analysis"],
        "prompt": (
            "Sen disiplinli bir ürün ve veri analistisin. Sorunları hipotezlere"
            " böler, ihtiyaç duyulan veriyi listeler ve yorumlarını sayılarla"
            " desteklersin. Yanıtlarında varsayımlarını, ölçümleri ve olası"
            " etkileri açıkça belirt."
        ),
    },
    {
        "id": "mentor",
        "name": "Dost Canlısı Mentor",
        "style": "Öğretici ve cesaretlendirici",
        "tags": ["education", "explanation", "beginner", "guidance"],
        "keywords": ["öğren", "neden", "temel", "tutorial", "nasıl"],
        "prompt": (
            "Sen sabırlı bir yazılım mentorusun. Yeni başlayanların sorularını"
            " nazikçe karşılar, karmaşık konuları basit örneklerle anlatır ve her"
            " adımın arkasındaki mantığı açıklar, gerekirse kontrol listesi"
            " verir."
        ),
    },
]


# ---------------------------------------------------------------------------
# IDF-weighted Turkish text scoring (ported from system_prompts/select_persona.py)
# ---------------------------------------------------------------------------

def _normalize_text(s: str) -> str:
    """Metni karşılaştırma için normalize et.

    - casefold: büyük/küçük harf farklarını azaltır
    - Türkçe 'ı' → 'i': klavye/yazım farklarını yakalar
    - aksan kaldırma: mühendislik ~ muhendislik
    """
    s = (s or "").casefold()
    s = s.replace("ı", "i")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s


def _tokenize(s: str) -> List[str]:
    """Normalize edilmiş token listesi üret. '+' karakteri korunur (c++)."""
    s = _normalize_text(s)
    s = re.sub(r"[^0-9a-z\+\s]", " ", s)
    return re.findall(r"[0-9a-z\+]+", s)


def _normalize_phrase(s: str) -> str:
    """Bir tag'i tutarlı bir 'phrase' anahtarına çevir."""
    return " ".join(_tokenize(s)).strip()


def _ngrams(tokens: List[str], n: int) -> set:
    if n <= 1 or len(tokens) < n:
        return set()
    return {" ".join(tokens[i: i + n]) for i in range(len(tokens) - n + 1)}


def _build_tag_df(personas: Dict[str, Dict[str, Any]]) -> Counter:
    """Her tag'in kaç persona'da geçtiğini say (IDF için)."""
    tag_df: Counter = Counter()
    for persona in personas.values():
        raw_tags = persona.get("tags", []) or []
        norm_tags: set = set()
        for t in raw_tags:
            if isinstance(t, str) and t.strip():
                key = _normalize_phrase(t)
                if key:
                    norm_tags.add(key)
        tag_df.update(norm_tags)
    return tag_df


def _idf(tag_key: str, n_personas: int, tag_df: Counter) -> float:
    """Smoothed IDF: log((N+1)/(df+1)) + 1."""
    df = tag_df.get(tag_key, 0)
    return math.log((n_personas + 1) / (df + 1)) + 1.0


def _idf_score_personas(
    query: str,
    personas: Dict[str, Dict[str, Any]],
) -> List[Tuple[str, float, Optional[str]]]:
    """IDF ağırlıklı token+n-gram eşleşmesi ile persona skoru hesapla."""
    prompt_tokens = _tokenize(query)
    prompt_counts = Counter(prompt_tokens)
    prompt_unigrams = set(prompt_tokens)
    prompt_bigrams = _ngrams(prompt_tokens, 2)
    prompt_trigrams = _ngrams(prompt_tokens, 3)

    tag_df = _build_tag_df(personas)
    n_personas = len(personas)

    matches: List[Tuple[str, float, Optional[str]]] = []

    for persona_id, persona in personas.items():
        raw_tags = persona.get("tags", []) or []
        if not isinstance(raw_tags, list):
            continue

        total = 0.0
        highlight: Optional[str] = None

        for tag in raw_tags:
            if not isinstance(tag, str) or not tag.strip():
                continue

            tag_tokens = _tokenize(tag)
            tag_key = " ".join(tag_tokens).strip()
            if not tag_tokens or not tag_key:
                continue

            # Phrase match weights: trigram > bigram > unigram
            phrase_weight = 0.0
            if len(tag_tokens) >= 3 and tag_key in prompt_trigrams:
                phrase_weight = 3.5
            elif len(tag_tokens) == 2 and tag_key in prompt_bigrams:
                phrase_weight = 3.0
            elif len(tag_tokens) == 1 and tag_key in prompt_unigrams:
                phrase_weight = 2.0

            # Token match weight (fallback when no phrase match)
            token_weight = 0.0
            if phrase_weight == 0.0:
                for tt in tag_tokens:
                    if tt in prompt_unigrams:
                        token_weight += 1.0 + min(
                            0.5, 0.1 * max(0, prompt_counts[tt] - 1)
                        )

            w = phrase_weight if phrase_weight > token_weight else token_weight
            if w > 0:
                total += w * _idf(tag_key, n_personas, tag_df)
                if highlight is None:
                    highlight = tag

        if total > 0:
            matches.append((persona_id, total, highlight))

    matches.sort(key=lambda item: item[1], reverse=True)
    return matches


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

class PersonaSelectorPlugin(PluginBase):
    """Manage personas that override the system prompt.

    Loads personas from system_prompts/prompts.json (skills-based, 19+ personas)
    when configured, otherwise falls back to plugins/system_prompts/personas.json.
    """

    # ---- Init ---------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()
        self.name = "persona_selector"
        self.version = "0.4.0"
        self.description = "System prompt personas ve öneriler (skills entegrasyonu)"
        self.author = "Ollama Chat CLI"

        # Legacy local store (fallback)
        self.persona_dir = Path("plugins/system_prompts")
        self.persona_file = self.persona_dir / "personas.json"
        self.config_path = Path("config.json")

        # Skills-based external source (from plugin_config.json)
        self._system_prompts_path: Optional[Path] = self._read_system_prompts_path()
        self._using_skills_source: bool = False

        self.personas: Dict[str, Dict[str, Any]] = {}
        self._ensure_store()

    def _read_system_prompts_path(self) -> Optional[Path]:
        """plugin_config.json'dan system_prompts_path ayarını oku."""
        try:
            plugin_cfg_path = Path("plugin_config.json")
            if plugin_cfg_path.exists():
                with open(plugin_cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                raw = (
                    cfg.get("plugin_settings", {})
                    .get("persona_selector", {})
                    .get("system_prompts_path")
                )
                if raw:
                    return Path(raw)
        except Exception:
            pass
        return None

    # ---- Plugin metadata ----------------------------------------------------

    def get_commands(self) -> Dict[str, Callable]:
        return {
            "persona": self.handle_persona_command,
            "suggest": self.handle_suggest_command,
        }

    def get_info(self) -> Dict[str, Any]:
        source = (
            str(self._system_prompts_path) if self._using_skills_source else "local"
        )
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": ["/persona", "/suggest"],
            "persona_count": len(self.personas),
            "source": source,
        }

    # ---- Public helpers (useful for tests) ----------------------------------

    def configure_storage(
        self,
        *,
        persona_dir: Optional[Path] = _UNSET,  # type: ignore[assignment]
        config_path: Optional[Path] = _UNSET,  # type: ignore[assignment]
        system_prompts_path: Optional[Path] = _UNSET,  # type: ignore[assignment]
        reset: bool = False,
    ) -> None:
        """Override storage paths (mainly for tests).

        Pass ``system_prompts_path=None`` explicitly to disable the skills
        source and force fallback to local personas.json.
        """
        if persona_dir is not _UNSET:
            self.persona_dir = persona_dir  # type: ignore[assignment]
            self.persona_file = persona_dir / "personas.json"  # type: ignore[operator]
        if config_path is not _UNSET:
            self.config_path = config_path  # type: ignore[assignment]
        if system_prompts_path is not _UNSET:
            # None → explicitly disable skills source
            self._system_prompts_path = system_prompts_path  # type: ignore[assignment]
        if reset and self.persona_file.exists():
            self.persona_file.unlink()
        self._ensure_store()

    def reload_personas(self) -> None:
        self._load_personas()

    # ---- Command handlers ---------------------------------------------------

    def handle_persona_command(
        self, args: List[str], context: Dict[str, Any]
    ) -> None:
        if not args:
            self._render_persona_list(context)
            return

        sub = args[0].lower()
        if sub in {"list", "ls"}:
            self._render_persona_list(context)
        elif sub == "set" and len(args) > 1:
            self._set_persona(args[1], context)
        elif sub == "clear":
            self._clear_persona(context)
        elif sub == "info" and len(args) > 1:
            self._render_persona_info(args[1])
        elif sub == "suggest" and len(args) > 1:
            self._render_suggestions(" ".join(args[1:]))
        elif sub == "reload":
            self.reload_personas()
            src = "skills" if self._using_skills_source else "local"
            console.print(
                f"[green]✓ Personas reloaded[/green] [dim]({len(self.personas)} personas, source: {src})[/dim]"
            )
        else:
            console.print(
                "[yellow]Usage: /persona (list|set <id>|info <id>|clear|suggest <prompt>|reload)[/yellow]"
            )

    def handle_suggest_command(
        self, args: List[str], context: Dict[str, Any]
    ) -> None:
        del context
        if not args:
            console.print(
                "[yellow]Usage: /suggest <problem veya hedef cümlesi>[/yellow]"
            )
            return
        self._render_suggestions(" ".join(args))

    # ---- Core behavior ------------------------------------------------------

    def _set_persona(self, persona_id: str, context: Dict[str, Any]) -> None:
        persona = self.personas.get(persona_id)
        if not persona:
            console.print(f"[red]❌ Persona bulunamadı:[/red] {persona_id}")
            return

        prompt = persona.get("prompt", "").strip()
        chat_context = context.get("chat_context")
        if chat_context is not None:
            chat_context["persona"] = persona_id
            chat_context["persona_prompt"] = prompt
            chat_context["persona_label"] = persona.get("name")
            chat_context["persona_tags"] = persona.get("tags", [])

        config = context.get("config")
        updated_config = self._update_config_persona(config, persona_id)
        if config is None and updated_config is not None:
            context["config"] = updated_config

        preview = prompt[:120] + ("..." if len(prompt) > 120 else "")
        console.print(
            f"[green]✓ Persona aktifleştirildi:[/green] [white]{persona.get('name')}[/white]\n[dim]{preview}[/dim]"
        )

    def _clear_persona(self, context: Dict[str, Any]) -> None:
        chat_context = context.get("chat_context")
        if chat_context is not None:
            chat_context.pop("persona", None)
            chat_context.pop("persona_prompt", None)
            chat_context.pop("persona_label", None)
            chat_context.pop("persona_tags", None)

        config = context.get("config")
        updated_config = self._update_config_persona(config, None)
        if config is None and updated_config is not None:
            context["config"] = updated_config

        console.print(
            "[green]✓ Persona temizlendi. Varsayılan sistem mesajı kullanılacak.[/green]"
        )

    def _render_persona_list(self, context: Dict[str, Any]) -> None:
        active_persona = self._get_active_persona_id(context)
        src_label = "skills" if self._using_skills_source else "local"
        table = Table(
            title=f"🧠 Personas [{len(self.personas)} • {src_label}]",
            header_style="bold blue",
        )
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Ad", style="white")
        table.add_column("Stil", style="magenta")
        table.add_column("Etiketler", style="yellow")

        for persona_id, persona in self.personas.items():
            marker = "👉 " if persona_id == active_persona else "   "
            tags = ", ".join(persona.get("tags", [])[:4]) or "-"
            table.add_row(
                f"{marker}{persona_id}",
                persona.get("name", persona_id.replace("_", " ").title()),
                persona.get("style", "-"),
                tags,
            )

        console.print(table)

    def _render_persona_info(self, persona_id: str) -> None:
        persona = self.personas.get(persona_id)
        if not persona:
            console.print(f"[red]❌ Persona bulunamadı:[/red] {persona_id}")
            return

        panel_text = (
            f"[bold]{persona.get('name', persona_id)}[/bold]\n"
            f"Stil: [cyan]{persona.get('style', '-')}[/cyan]\n"
            f"Etiketler: [yellow]{', '.join(persona.get('tags', [])) or '-'}[/yellow]\n\n"
            f"[dim]Sistem Mesajı:[/dim]\n{persona.get('prompt', '').strip()[:600]}"
        )
        console.print(Panel(panel_text, title=f"Persona · {persona_id}"))

    def _render_suggestions(self, query: str) -> None:
        matches = _idf_score_personas(query, self.personas)
        if not matches:
            console.print("[yellow]Uygun persona önerisi bulunamadı.[/yellow]")
            return

        table = Table(title="🔍 Persona Önerileri (IDF)", header_style="bold blue")
        table.add_column("ID", style="cyan", width=30)
        table.add_column("Ad", style="white", width=24)
        table.add_column("Skor", style="green", width=8)
        table.add_column("Öne Çıkan Etiket", style="yellow")

        for persona_id, score, highlight in matches[:4]:
            persona = self.personas[persona_id]
            table.add_row(
                persona_id,
                persona.get("name", persona_id.replace("_", " ").title()),
                f"{score:.1f}",
                highlight or ", ".join(persona.get("tags", [])[:3]),
            )

        console.print(table)

    # ---- Persistence helpers ------------------------------------------------

    def _ensure_store(self) -> None:
        """Skills-based source varsa onu kullan, yoksa legacy store'a düş."""
        if self._try_load_skills_source():
            return
        # Fallback: legacy personas.json
        self.persona_dir.mkdir(parents=True, exist_ok=True)
        if not self.persona_file.exists():
            self._write_default_personas()
        self._load_personas()

    def _try_load_skills_source(self) -> bool:
        """system_prompts/prompts.json'u yükle. Başarılıysa True döner."""
        if self._system_prompts_path is None:
            return False

        prompts_file = self._system_prompts_path / "prompts.json"
        persona_map_file = self._system_prompts_path / "persona_map.yaml"

        if not prompts_file.exists():
            console.print(
                f"[yellow]⚠ prompts.json bulunamadı: {prompts_file}[/yellow]"
            )
            return False

        try:
            with open(prompts_file, "r", encoding="utf-8") as f:
                raw: Dict[str, Any] = json.load(f)
        except Exception as exc:
            console.print(
                f"[red]❌ prompts.json okunamadı:[/red] {exc}"
            )
            return False

        # Load tags from persona_map.yaml if available
        tag_map: Dict[str, List[str]] = {}
        desc_map: Dict[str, str] = {}
        if persona_map_file.exists():
            try:
                import yaml  # type: ignore[import]
                with open(persona_map_file, "r", encoding="utf-8") as f:
                    pm = yaml.safe_load(f)
                for entry in pm.get("personas", []):
                    pid = entry.get("id", "")
                    tag_map[pid] = entry.get("tags", [])
                    desc_map[pid] = entry.get("description", "")
            except Exception:
                pass  # tags optional

        personas: Dict[str, Dict[str, Any]] = {}
        for key, obj in raw.items():
            persona_id = obj.get("persona_id", key)
            meta = obj.get("metadata", {})
            prompt = obj.get("system_prompt", "")
            if not persona_id or not prompt:
                continue
            personas[persona_id] = {
                "id": persona_id,
                "name": persona_id.replace("_", " ").title(),
                "style": meta.get("description", "-")[:60],
                "tags": tag_map.get(persona_id, []),
                "keywords": [],
                "prompt": prompt,
                "description": desc_map.get(persona_id, meta.get("description", "")),
                "author": meta.get("author", ""),
                "version": meta.get("version", 1.0),
            }

        if not personas:
            return False

        self.personas = personas
        self._using_skills_source = True
        return True

    def _write_default_personas(self) -> None:
        try:
            with open(self.persona_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_PERSONAS, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            console.print(f"[red]❌ Personas kaydedilemedi:[/red] {exc}")

    def _load_personas(self) -> None:
        """Legacy personas.json (list ya da dict) yükle."""
        try:
            with open(self.persona_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            console.print(
                f"[red]❌ Personas yüklenemedi, varsayılanlar kullanılacak:[/red] {exc}"
            )
            data = DEFAULT_PERSONAS

        if isinstance(data, list):
            iterable = data
        elif isinstance(data, dict):
            iterable = data.values()
        else:
            iterable = DEFAULT_PERSONAS

        personas: Dict[str, Dict[str, Any]] = {}
        for item in iterable:
            persona_id = item.get("id")
            prompt = item.get("prompt")
            if not persona_id or not prompt:
                continue
            personas[persona_id] = {
                "id": persona_id,
                "name": item.get("name", persona_id.title()),
                "style": item.get("style", "-"),
                "tags": item.get("tags", []),
                "keywords": item.get("keywords", []),
                "prompt": prompt,
            }
        self.personas = personas
        self._using_skills_source = False

    def _update_config_persona(
        self, config: Optional[Dict[str, Any]], persona_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        data = config
        if data is None:
            try:
                if self.config_path.exists():
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    data = {}
            except Exception:
                data = {}

        persona_section = data.setdefault("persona", {})
        persona_section["current_persona"] = persona_id
        persona_section["last_updated"] = datetime.now(timezone.utc).isoformat()

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            console.print(f"[red]❌ Config kaydedilemedi:[/red] {exc}")

        return data

    def _get_active_persona_id(self, context: Dict[str, Any]) -> Optional[str]:
        chat_ctx = context.get("chat_context") or {}
        if chat_ctx.get("persona"):
            return chat_ctx["persona"]

        config = context.get("config")
        persona_cfg = (config or {}).get("persona")
        if persona_cfg and persona_cfg.get("current_persona"):
            return persona_cfg["current_persona"]

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("persona", {}).get("current_persona")
        except Exception:
            return None
