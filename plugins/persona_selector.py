"""Persona selector plugin for managing system prompts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lib.plugins import PluginBase

console = Console()

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


class PersonaSelectorPlugin(PluginBase):
    """Manage personas that override the system prompt."""

    def __init__(self) -> None:
        super().__init__()
        self.name = "persona_selector"
        self.version = "0.3.0"
        self.description = "System prompt personas ve öneriler"
        self.author = "Ollama Chat CLI"
        self.persona_dir = Path("plugins/system_prompts")
        self.persona_file = self.persona_dir / "personas.json"
        self.config_path = Path("config.json")
        self.personas: Dict[str, Dict[str, Any]] = {}
        self._ensure_store()

    # ------------------------------------------------------------------
    # Plugin metadata
    # ------------------------------------------------------------------
    def get_commands(self) -> Dict[str, Callable]:
        return {
            "persona": self.handle_persona_command,
            "suggest": self.handle_suggest_command,
        }

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": ["/persona", "/suggest"],
        }

    # ------------------------------------------------------------------
    # Public helpers (useful for tests)
    # ------------------------------------------------------------------
    def configure_storage(
        self,
        *,
        persona_dir: Optional[Path] = None,
        config_path: Optional[Path] = None,
        reset: bool = False,
    ) -> None:
        """Override storage paths for personas or config (mainly for tests)."""

        if persona_dir is not None:
            self.persona_dir = persona_dir
            self.persona_file = persona_dir / "personas.json"
        if config_path is not None:
            self.config_path = config_path
        if reset and self.persona_file.exists():
            self.persona_file.unlink()
        self._ensure_store()

    def reload_personas(self) -> None:
        self._load_personas()

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    def handle_persona_command(self, args: List[str], context: Dict[str, Any]) -> None:
        if not args:
            self._render_persona_list(context)
            return

        sub = args[0].lower()
        if sub in {"list", "ls"}:
            self._render_persona_list(context)
        elif sub == "set" and len(args) > 1:
            persona_id = args[1]
            self._set_persona(persona_id, context)
        elif sub == "clear":
            self._clear_persona(context)
        elif sub == "info" and len(args) > 1:
            self._render_persona_info(args[1])
        elif sub == "suggest" and len(args) > 1:
            query = " ".join(args[1:])
            self._render_suggestions(query)
        elif sub == "reload":
            self.reload_personas()
            console.print("[green]✓ Personas reloaded[/green]")
        else:
            console.print(
                "[yellow]Usage: /persona (list|set <id>|info <id>|clear|suggest <prompt>|reload)[/yellow]"
            )

    def handle_suggest_command(self, args: List[str], context: Dict[str, Any]) -> None:
        del context
        if not args:
            console.print("[yellow]Usage: /suggest <problem or hedef cümlesi>[/yellow]")
            return
        query = " ".join(args)
        self._render_suggestions(query)

    # ------------------------------------------------------------------
    # Core behavior
    # ------------------------------------------------------------------
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

        console.print("[green]✓ Persona temizlendi. Varsayılan sistem mesajı kullanılacak.[/green]")

    def _render_persona_list(self, context: Dict[str, Any]) -> None:
        active_persona = self._get_active_persona_id(context)
        table = Table(title="🧠 Personas", header_style="bold blue")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Ad", style="white")
        table.add_column("Stil", style="magenta")
        table.add_column("Etiketler", style="yellow")

        for persona_id, persona in self.personas.items():
            marker = "👉 " if persona_id == active_persona else "   "
            tags = ", ".join(persona.get("tags", [])) or "-"
            table.add_row(
                f"{marker}{persona_id}",
                persona.get("name", persona_id.title()),
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
            f"[bold]{persona.get('name')}[/bold]\n"
            f"Stil: [cyan]{persona.get('style', '-')}[/cyan]\n"
            f"Etiketler: [yellow]{', '.join(persona.get('tags', [])) or '-'}[/yellow]\n\n"
            f"[dim]Sistem Mesajı:[/dim]\n{persona.get('prompt', '').strip()}"
        )
        console.print(Panel(panel_text, title=f"Persona · {persona_id}"))

    def _render_suggestions(self, query: str) -> None:
        matches = self._score_personas(query)
        if not matches:
            console.print("[yellow]Uygun persona önerisi bulunamadı.[/yellow]")
            return

        table = Table(title="🔍 Persona Önerileri", header_style="bold blue")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Ad", style="white", width=24)
        table.add_column("Skor", style="green", width=8)
        table.add_column("Öne Çıkan Etiket", style="yellow")

        for persona_id, score, highlight in matches[:4]:
            persona = self.personas[persona_id]
            table.add_row(
                persona_id,
                persona.get("name", persona_id.title()),
                f"{score:.1f}",
                highlight or ", ".join(persona.get("tags", [])),
            )

        console.print(table)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _ensure_store(self) -> None:
        self.persona_dir.mkdir(parents=True, exist_ok=True)
        if not self.persona_file.exists():
            self._write_default_personas()
        self._load_personas()

    def _write_default_personas(self) -> None:
        try:
            with open(self.persona_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_PERSONAS, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            console.print(f"[red]❌ Personas kaydedilemedi:[/red] {exc}")

    def _load_personas(self) -> None:
        try:
            with open(self.persona_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            console.print(f"[red]❌ Personas yüklenemedi, varsayılanlar kullanılacak:[/red] {exc}")
            data = DEFAULT_PERSONAS

        personas: Dict[str, Dict[str, Any]] = {}
        if isinstance(data, list):
            iterable = data
        elif isinstance(data, dict):
            iterable = data.values()
        else:
            iterable = DEFAULT_PERSONAS

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

    # ------------------------------------------------------------------
    # Suggestion helpers
    # ------------------------------------------------------------------
    def _score_personas(self, query: str) -> List[Tuple[str, float, Optional[str]]]:
        prompt_lower = query.lower()
        matches: List[Tuple[str, float, Optional[str]]] = []
        for persona_id, persona in self.personas.items():
            score = 0.0
            highlight: Optional[str] = None
            for kw in persona.get("keywords", []):
                if kw.lower() in prompt_lower:
                    score += 1.5
                    highlight = kw
            for tag in persona.get("tags", []):
                if tag.lower() in prompt_lower:
                    score += 1.0
                    highlight = highlight or tag
            if persona_id in prompt_lower:
                score += 0.5
            if score > 0:
                matches.append((persona_id, score, highlight))

        matches.sort(key=lambda item: item[1], reverse=True)
        return matches
