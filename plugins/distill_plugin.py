"""
distill_plugin.py — chat-cli plugin

Sohbeti (chat_history.json) Alpaca JSONL eğitim verisine ve distillation
raporuna dönüştürür. Wiki sayfası yazmaz — o görev wiki_plugin'e aittir.

Komutlar:
  /distill           → aktif chat_history.json'u distill et
  /distill session   → (alias) aktif oturumu distill et
  /distill status    → son üretilen dataset dosyalarını listele
  /distill help      → bu yardım mesajını göster
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Any

from lib.plugins import PluginBase
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


class DistillPlugin(PluginBase):
    """Plugin to trigger the LLMwiki distillation pipeline (chat → training data)."""

    def __init__(self) -> None:
        super().__init__()
        self.name = "DistillPlugin"
        self.version = "2.0.0"
        self.description = "Sohbeti Alpaca JSONL eğitim verisine dönüştürür (Distillation Pipeline)"
        self.author = "Antigravity Agent"
        self._cfg: Dict[str, Any] = {}

    # ── Plugin lifecycle ────────────────────────────────────────────────────

    def on_load(self) -> None:
        config_path = Path("plugin_config.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    all_cfg = json.load(f)
                self._cfg = all_cfg.get("plugin_settings", {}).get("distill_plugin", {})
            except Exception:
                pass
        console.print("[green]✓ Distill plugin loaded! ⚗️[/green]")

    def get_commands(self) -> Dict[str, Callable]:
        return {"distill": self._cmd_distill}

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": list(self.get_commands().keys()),
        }

    # ── Path resolution ─────────────────────────────────────────────────────

    def _llmwiki_path(self) -> Path:
        """Resolve LLMwiki root: plugin_config → sibling directory → absolute fallback."""
        configured = self._cfg.get("llmwiki_path")
        if configured:
            p = Path(configured)
            if p.exists():
                return p

        # Try sibling directory (../LLMwiki relative to chat-cli)
        sibling = Path(__file__).parent.parent.parent / "LLMwiki"
        if sibling.exists():
            return sibling

        # Last resort — known absolute path
        return Path("/Users/hakankilicaslan/Git/LLMwiki")

    def _script_path(self) -> Path:
        return self._llmwiki_path() / "scripts" / "distill_chats.py"

    def _dataset_dir(self) -> Path:
        """Read dataset_output_path from wiki_config.json."""
        wiki_cfg_path = self._llmwiki_path() / "wiki_config.json"
        if wiki_cfg_path.exists():
            try:
                with open(wiki_cfg_path, "r", encoding="utf-8") as f:
                    wcfg = json.load(f)
                return self._llmwiki_path() / wcfg.get("dataset_output_path", "datasets")
            except Exception:
                pass
        return self._llmwiki_path() / "datasets"

    # ── Commands router ─────────────────────────────────────────────────────

    def _cmd_distill(self, args: List[str], context: Dict[str, Any]) -> None:
        subcmd = args[0].lower() if args else "session"

        if subcmd in ("session", "run", ""):
            self._run_distill(context)
        elif subcmd == "status":
            self._cmd_status()
        elif subcmd == "help":
            self._cmd_help()
        else:
            console.print(f"[yellow]Bilinmeyen alt-komut:[/yellow] {subcmd}")
            self._cmd_help()

    # ── Distill core (async) ─────────────────────────────────────────────────

    def _run_distill(self, context: Dict[str, Any]) -> None:
        script = self._script_path()
        if not script.exists():
            console.print(f"[red]Distillation script bulunamadı: {script}[/red]")
            return

        # Determine Ollama URL and model from active chat session
        cfg = context.get("config", {})
        from services.settings_service import determine_base_url
        ollama_url = determine_base_url(cfg, None) or "http://localhost:11434"
        current_model = context.get("current_model") or cfg.get("llm_model", "gemma3:latest")

        # Determine history file: context → config → wiki_config → default
        history_file = (
            cfg.get("history_file")
            or self._history_from_wiki_config()
            or str(Path(__file__).parent.parent / "chat_history.json")
        )

        cmd_args = [
            sys.executable, str(script),
            "--url", ollama_url,
            "--model", current_model,
            "--history", history_file,
        ]

        console.print(
            "[bold green]🚀 Distillation Pipeline başlatılıyor…[/bold green] "
            "[dim](arka planda çalışıyor, You: promptunu bloke etmez)[/dim]"
        )
        console.print(
            f"[dim]Model: {current_model} | History: {Path(history_file).name}[/dim]"
        )

        def _run_bg() -> None:
            try:
                process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # merge stderr into stdout
                    text=True,
                    bufsize=1,
                )
                output_lines: List[str] = []
                assert process.stdout is not None
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        output_lines.append(line)
                        console.print(f"[dim cyan]  ⚗ {line}[/dim cyan]")

                process.wait()
                if process.returncode == 0:
                    console.print("\n[bold green]✓ Distillation tamamlandı![/bold green]")
                    console.print(
                        f"[dim]Çıktılar → {self._dataset_dir()}[/dim]\n"
                        "[dim]Detay için /distill status yazın.[/dim]"
                    )
                else:
                    console.print(
                        f"\n[bold red]✗ Distillation hatayla tamamlandı "
                        f"(returncode={process.returncode})[/bold red]"
                    )
            except Exception as e:
                console.print(f"[bold red]Distillation arka plan hatası:[/bold red] {e}")

        threading.Thread(target=_run_bg, daemon=True).start()

    def _history_from_wiki_config(self) -> str | None:
        wiki_cfg = self._llmwiki_path() / "wiki_config.json"
        if wiki_cfg.exists():
            try:
                with open(wiki_cfg, "r", encoding="utf-8") as f:
                    return json.load(f).get("chat_history_path")
            except Exception:
                pass
        return None

    # ── Status command ───────────────────────────────────────────────────────

    def _cmd_status(self) -> None:
        dataset_dir = self._dataset_dir()
        if not dataset_dir.exists():
            console.print(f"[yellow]Dataset dizini bulunamadı: {dataset_dir}[/yellow]")
            return

        files = sorted(dataset_dir.glob("dataset_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            console.print("[yellow]Henüz üretilmiş dataset dosyası yok.[/yellow]")
            return

        table = Table(
            title=f"⚗️  Distillation Datasets ({len(files)} dosya)",
            show_header=True,
            header_style="bold blue",
        )
        table.add_column("Dosya", style="cyan")
        table.add_column("Satır", style="green", justify="right")
        table.add_column("Boyut", style="yellow", justify="right")
        table.add_column("Son Değişiklik", style="white")

        for f in files[:20]:  # Show at most 20
            try:
                lines = sum(1 for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip())
            except Exception:
                lines = -1
            size_kb = f.stat().st_size / 1024
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            table.add_row(f.name, str(lines), f"{size_kb:.1f} KB", mtime)

        console.print(table)

        # Also show distilled reports
        distilled_dir = self._llmwiki_path() / "wiki" / "distilled"
        if distilled_dir.exists():
            reports = list(distilled_dir.glob("report_*.md"))
            if reports:
                console.print(f"[dim]📄 {len(reports)} distillation raporu → {distilled_dir}[/dim]")

    # ── Help command ─────────────────────────────────────────────────────────

    def _cmd_help(self) -> None:
        table = Table(title="⚗️  Distill Komutları", show_header=True, header_style="bold blue")
        table.add_column("Komut", style="cyan")
        table.add_column("Açıklama", style="white")
        table.add_row("/distill", "Aktif chat_history.json'u distill eder (eğitim verisi üretir)")
        table.add_row("/distill session", "(Alias) Aynı işlem")
        table.add_row("/distill status", "Son üretilen dataset dosyalarını listeler")
        table.add_row("/distill help", "Bu yardım menüsünü gösterir")
        console.print(table)
        console.print(
            Panel(
                "[yellow]Not:[/yellow] Distill = sohbet → eğitim verisi (JSONL)\n"
                "Wiki'ye özetleme için [cyan]/wiki ingest-session[/cyan] komutunu kullanın.",
                title="ℹ️  Pipeline Ayrımı",
            )
        )
