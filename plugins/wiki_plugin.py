"""
Wiki plugin for chat-cli.

Provides /wiki commands that communicate with omni-daemon's wiki endpoints:

    /wiki status            — Wiki statistics from omni-daemon
    /wiki search <query>    — Semantic search over wiki pages
    /wiki ingest <path>     — Trigger LLM wiki-page generation for a file
    /wiki lint              — LLM health-check of the wiki
    /wiki status            — Wiki statistics from omni-daemon
    /wiki search <query>    — Semantic search over wiki pages
    /wiki ingest <path>     — Trigger LLM wiki-page generation for a file
    /wiki lint              — LLM health-check of the wiki
    /wiki open <page>       — Print a wiki page's markdown to the terminal
    /wiki edit <page>       — Open a wiki page in the system $EDITOR
    /wiki pin <page>        — Pin a wiki page to the current chat session context
    /wiki link <src> <tgt>  — Manually create a wiki-link between two pages
    /wiki context on|off    — Inject relevant wiki passages into every chat turn
"""

from __future__ import annotations

import json
import httpx
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Callable, Any, Optional

from lib.plugins import PluginBase
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

console = Console()

# --------------------------------------------------------------------------- #
# Default config (overridden by plugin_config.json)
# --------------------------------------------------------------------------- #
_DEFAULTS: Dict[str, Any] = {
    "omni_daemon_url": "http://localhost:8000",
    "wiki_path": "/Users/hakankilicaslan/Git/LLMwiki",
    "auto_context": False,
    "context_top_k": 3,
    "request_timeout": 30,
    "default_editor": "vim",
}


class WikiPlugin(PluginBase):
    """Wiki management and auto-context plugin for chat-cli."""

    def __init__(self):
        super().__init__()
        self.name = "WikiPlugin"
        self.version = "1.1.0"
        self.description = "Interact and manage LLMwiki via omni-daemon & Obsidian style"
        self.author = "Omni-Context"
        self._cfg: Dict[str, Any] = dict(_DEFAULTS)
        self._auto_context: bool = False
        self._pinned_pages: List[Path] = []

    # ------------------------------------------------------------------
    # PluginBase interface
    # ------------------------------------------------------------------

    def get_commands(self) -> Dict[str, Callable]:
        return {"wiki": self.wiki_command}

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": ["wiki"],
        }

    def on_load(self) -> None:
        # Merge plugin_config.json settings if present
        config_path = Path("plugin_config.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as fh:
                    all_cfg = json.load(fh)
                overrides = all_cfg.get("plugin_settings", {}).get("wiki_plugin", {})
                self._cfg.update(overrides)
            except Exception:
                pass

        self._auto_context = self._cfg.get("auto_context", False)
        console.print("[green]✓ Wiki plugin loaded! 📚[/green]")
        if self._auto_context:
            console.print("[dim]  Auto-context: [green]ON[/green][/dim]")

    def on_unload(self) -> None:
        console.print("[yellow]📤 Wiki plugin unloaded[/yellow]")

    # ------------------------------------------------------------------
    # Auto-context hook (called by chat-cli if it supports pre-turn hooks)
    # ------------------------------------------------------------------

    def before_chat_turn(self, user_message: str, context: Dict[str, Any]) -> None:
        """
        Injects auto-context query results AND pinned pages into the context history.
        """
        injected_segments = []

        # 1. Handle Pinned Pages (Static Context)
        if self._pinned_pages:
            pinned_text = []
            for path in self._pinned_pages:
                try:
                    content = path.read_text(encoding="utf-8")
                    pinned_text.append(f"### [pinned] {path.name}\n\n{content}")
                except Exception:
                    continue
            if pinned_text:
                injected_segments.append(
                    "**[STATIC CONTEXT]** The following pages are pinned by the user for this session:\n\n"
                    + "\n\n---\n\n".join(pinned_text)
                )

        # 2. Handle Auto-Context (Semantic Context)
        if self._auto_context:
            top_k = self._cfg.get("context_top_k", 3)
            results = self._api_wiki_search(user_message, top_k=top_k)
            if results:
                passages = []
                for item in results:
                    path = item.get("path", "")
                    content = item.get("content", "").strip()
                    score = item.get("score", 0)
                    passages.append(f"**[wiki]** `{path}` (score: {score:.2f})\n\n{content}")
                
                injected_segments.append(
                    "**[DYNAMIC CONTEXT]** Relevant excerpts from your wiki:\n\n"
                    + "\n\n---\n\n".join(passages)
                )

        if injected_segments and "history" in context:
            full_system_msg = "\n\n========================================\n\n".join(injected_segments)
            context["history"].append({"role": "system", "text": full_system_msg})

    # ------------------------------------------------------------------
    # /wiki dispatcher
    # ------------------------------------------------------------------

    def wiki_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """Handle /wiki <subcommand> [args...]."""
        if not args:
            self._print_help()
            return

        sub = args[0].lower()
        rest = args[1:]

        dispatch = {
            "status":  self._cmd_status,
            "search":  self._cmd_search,
            "ingest":  self._cmd_ingest,
            "index":   self._cmd_index,
            "lint":    self._cmd_lint,
            "open":    self._cmd_open,
            "edit":    self._cmd_edit,
            "pin":     self._cmd_pin,
            "link":    self._cmd_link,
            "context": self._cmd_context,
        }

        handler = dispatch.get(sub)
        if handler is None:
            console.print(f"[red]Unknown subcommand: {sub}[/red]")
            self._print_help()
        else:
            handler(rest, context)

    # ------------------------------------------------------------------
    # Subcommands
    # ------------------------------------------------------------------

    def _cmd_status(self, args: List[str], context: Dict[str, Any]) -> None:
        """Show wiki statistics."""
        data = self._get("/wiki/status")
        if data is None:
            return

        table = Table(title="📚 Wiki Status", show_header=True, header_style="bold blue")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Wiki pages", str(data.get("wiki_page_count", "?")))
        table.add_row("Raw files", str(data.get("raw_file_count", "?")))
        table.add_row("LLM model", str(data.get("llm_model", "?")))
        table.add_row("Auto-ingest", "✅ on" if data.get("auto_ingest_enabled") else "⏸️ off")
        table.add_row("Wiki path", str(data.get("wiki_path", "?")))
        table.add_row("Last log entry", str(data.get("last_log_entry", "—")))
        table.add_row("Auto-context (plugin)", "✅ on" if self._auto_context else "⏸️ off")
        table.add_row("Pinned pages", str(len(self._pinned_pages)))

        console.print(table)

    def _cmd_search(self, args: List[str], context: Dict[str, Any]) -> None:
        """Semantic search over wiki pages."""
        if not args:
            console.print("[yellow]Usage: /wiki search <query>[/yellow]")
            return

        query = " ".join(args)
        top_k = self._cfg.get("context_top_k", 5)
        results = self._api_wiki_search(query, top_k=top_k)
        if results is None:
            return

        if not results:
            console.print("[yellow]No wiki pages matched your query.[/yellow]")
            return

        console.print(f"\n[bold blue]🔍 Wiki search:[/bold blue] [white]{query}[/white]\n")
        for i, item in enumerate(results, 1):
            score = item.get("score", 0)
            path = item.get("path", "")
            snippet = item.get("content", "").strip()[:300]
            console.print(
                Panel(
                    f"[dim]{snippet}…[/dim]",
                    title=f"[cyan]{i}. {Path(path).name}[/cyan]  [green](score: {score:.2f})[/green]",
                    expand=False,
                )
            )

        # Also inject into conversation context so the model can reference them
        if "history" in context and results:
            joined = "\n\n---\n\n".join(
                f"`{r.get('path', '')}` (score: {r.get('score', 0):.2f})\n{r.get('content', '')}"
                for r in results
            )
            context["history"].append({
                "role": "system",
                "text": f"User searched the wiki for: «{query}». Top results:\n\n{joined}",
            })

    def _cmd_ingest(self, args: List[str], context: Dict[str, Any]) -> None:
        """Manually trigger wiki page generation for a file."""
        if not args:
            console.print("[yellow]Usage: /wiki ingest <file_path>[/yellow]")
            return

        file_path = str(Path(args[0]).expanduser().resolve())
        console.print(f"[dim]Ingesting: {file_path}[/dim]")
        data = self._post("/wiki/ingest", {"file_path": file_path})
        if data is None:
            return

        if data.get("ok"):
            console.print(f"[green]✓ Wiki page created:[/green] [white]{data.get('wiki_page')}[/white]")
            console.print(f"[dim]  Slug: {data.get('slug')}[/dim]")
        else:
            console.print(f"[red]✗ Ingest failed:[/red] {data.get('reason', 'unknown error')}")

    def _cmd_index(self, args: List[str], context: Dict[str, Any]) -> None:
        """Trigger bulk indexing of LLMwiki."""
        console.print("[dim]Starting wiki bulk indexing (this may take a moment)…[/dim]")
        data = self._post("/wiki/index", {})
        if data is None:
            return

        if data.get("ok"):
            indexed = data.get("indexed_count", 0)
            skipped = data.get("skipped_count", 0)
            errors = data.get("error_count", 0)
            console.print(f"[green]✓ Bulk indexing complete![/green]")
            console.print(f"[dim]  Indexed: {indexed} | Skipped: {skipped} | Errors: {errors}[/dim]")
        else:
            console.print("[red]✗ Bulk indexing failed.[/red]")

    def _cmd_lint(self, args: List[str], context: Dict[str, Any]) -> None:
        """Run LLM health-check on the wiki."""
        console.print("[dim]Running wiki lint (LLM call — may take a moment)…[/dim]")
        data = self._post("/wiki/lint", {})
        if data is None:
            return

        pages = data.get("pages_checked", "?")
        report = data.get("report", "No report returned.")
        console.print(
            Panel(
                Markdown(report),
                title=f"[bold blue]🩺 Wiki Lint Report[/bold blue] — [dim]{pages} pages checked[/dim]",
                expand=True,
            )
        )

        if "history" in context:
            context["history"].append({
                "role": "system",
                "text": f"Wiki lint report ({pages} pages checked):\n\n{report}",
            })

    def _find_file(self, keyword: str) -> Optional[Path]:
        """Find a file in the wiki root matching keyword substring."""
        root_dir = Path(self._cfg.get("wiki_path", _DEFAULTS["wiki_path"]))
        if not root_dir.exists():
            return None
        
        # Priority 1: Exact slug match in wiki/concepts or wiki/sources
        for folder in ["wiki/concepts", "wiki/sources", "wiki/entities"]:
            target = root_dir / folder / f"{keyword}.md"
            if target.exists():
                return target

        # Priority 2: Substring match in names
        all_files = list(root_dir.rglob("*.md")) + list(root_dir.rglob("*.txt"))
        for p in all_files:
            if keyword in p.name.lower() or keyword in str(p.relative_to(root_dir)).lower():
                return p
        return None

    def _cmd_open(self, args: List[str], context: Dict[str, Any]) -> None:
        """Print a wiki page to the terminal."""
        if not args:
            console.print("[yellow]Usage: /wiki open <page_name_or_slug>[/yellow]")
            return

        keyword = args[0].lower()
        target = self._find_file(keyword)

        if not target:
            console.print(f"[red]No file found matching: {keyword}[/red]")
            return

        try:
            content = target.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Cannot read {target}: {e}[/red]")
            return

        rel = target.relative_to(Path(self._cfg.get("wiki_path", _DEFAULTS["wiki_path"])))
        console.print(
            Panel(
                Markdown(content),
                title=f"[bold blue]📄 {rel}[/bold blue]",
                expand=True,
            )
        )

        if "history" in context:
            context["history"].append({
                "role": "system",
                "text": f"User opened wiki page `{rel}`:\n\n{content}",
            })

    def _cmd_edit(self, args: List[str], context: Dict[str, Any]) -> None:
        """Open a wiki page in the system editor."""
        if not args:
            console.print("[yellow]Usage: /wiki edit <page_name_or_slug>[/yellow]")
            return

        keyword = args[0].lower()
        target = self._find_file(keyword)

        if not target:
            console.print(f"[red]No file found matching: {keyword}[/red]")
            return

        editor = os.environ.get("EDITOR") or self._cfg.get("default_editor", "vim")
        console.print(f"[dim]Opening {target.name} with {editor}...[/dim]")
        try:
            subprocess.call([editor, str(target)])
        except Exception as e:
            console.print(f"[red]Failed to launch editor: {e}[/red]")

    def _cmd_pin(self, args: List[str], context: Dict[str, Any]) -> None:
        """Pin/unpin a page to the current session context: /wiki pin [page|list|clear]"""
        if not args:
            console.print("[yellow]Usage: /wiki pin <page_name> | list | clear[/yellow]")
            return

        cmd = args[0].lower()
        if cmd == "list":
            if not self._pinned_pages:
                console.print("[dim]No pages pinned.[/dim]")
            for p in self._pinned_pages:
                console.print(f"📌 [cyan]{p.name}[/cyan]")
            return
        
        if cmd == "clear":
            self._pinned_pages = []
            console.print("[yellow]Pinned pages cleared.[/yellow]")
            return

        target = self._find_file(cmd)
        if not target:
            console.print(f"[red]No file found matching: {cmd}[/red]")
            return

        if target in self._pinned_pages:
            self._pinned_pages.remove(target)
            console.print(f"📍 [yellow]Unpinned:[/yellow] {target.name}")
        else:
            self._pinned_pages.append(target)
            console.print(f"📌 [green]Pinned to context:[/green] {target.name}")

    def _cmd_link(self, args: List[str], context: Dict[str, Any]) -> None:
        """Manually add a wiki-link from one page to another: /wiki link <source> <target>"""
        if len(args) < 2:
            console.print("[yellow]Usage: /wiki link <source_page> <target_page>[/yellow]")
            return

        src_kw, tgt_kw = args[0].lower(), args[1].lower()
        src_file = self._find_file(src_kw)
        tgt_file = self._find_file(tgt_kw)

        if not src_file:
            console.print(f"[red]Source page not found: {src_kw}[/red]")
            return
        if not tgt_file:
            console.print(f"[red]Target page not found: {tgt_kw}[/red]")
            return

        # Simple append of the wiki-link to the source file
        link_str = f"\n\n- Related: [[{tgt_file.stem}]]\n"
        try:
            with open(src_file, "a", encoding="utf-8") as f:
                f.write(link_str)
            console.print(f"[green]✓ Linked [[{src_file.stem}]] -> [[{tgt_file.stem}]][/green]")
        except Exception as e:
            console.print(f"[red]Linking failed: {e}[/red]")

    def _cmd_context(self, args: List[str], context: Dict[str, Any]) -> None:
        """Toggle auto-context injection: /wiki context on|off"""
        if not args or args[0].lower() not in ("on", "off"):
            state = "[green]ON[/green]" if self._auto_context else "[red]OFF[/red]"
            console.print(f"[dim]Auto-context is currently {state}[/dim]")
            console.print("[yellow]Usage: /wiki context on|off[/yellow]")
            return

        self._auto_context = args[0].lower() == "on"
        state = "[green]ON[/green]" if self._auto_context else "[red]OFF[/red]"
        console.print(f"[bold]Wiki auto-context:[/bold] {state}")

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _base_url(self) -> str:
        return self._cfg.get("omni_daemon_url", _DEFAULTS["omni_daemon_url"]).rstrip("/")

    def _timeout(self) -> int:
        return int(self._cfg.get("request_timeout", 30))

    def _get(self, path: str) -> Dict | None:
        url = self._base_url() + f"/api/v1{path}"
        try:
            resp = httpx.get(url, timeout=self._timeout())
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            console.print(f"[red]Cannot connect to omni-daemon at {self._base_url()}[/red]")
            console.print("[dim]Is omni-daemon running? (uvicorn src.main:app)[/dim]")
            return None
        except Exception as e:
            console.print(f"[red]Request failed:[/red] {e}")
            return None

    def _post(self, path: str, body: dict) -> Dict | None:
        url = self._base_url() + f"/api/v1{path}"
        try:
            resp = httpx.post(url, json=body, timeout=self._timeout())
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            console.print(f"[red]Cannot connect to omni-daemon at {self._base_url()}[/red]")
            console.print("[dim]Is omni-daemon running? (uvicorn src.main:app)[/dim]")
            return None
        except Exception as e:
            console.print(f"[red]Request failed:[/red] {e}")
            return None

    def _api_wiki_search(self, query: str, top_k: int = 5) -> List[Dict] | None:
        data = self._post("/wiki/search", {"query": query, "top_k": top_k})
        if data is None:
            return None
        return data.get("results", [])

    # ------------------------------------------------------------------
    # Help text
    # ------------------------------------------------------------------

    @staticmethod
    def _print_help() -> None:
        table = Table(title="📚 /wiki commands", show_header=True, header_style="bold blue")
        table.add_column("Command", style="cyan", width=30)
        table.add_column("Description", style="white")

        table.add_row("/wiki status", "Wiki istatistiklerini göster")
        table.add_row("/wiki search <sorgu>", "Sementik arama yap")
        table.add_row("/wiki ingest <dosya>", "Dosyayı wiki'ye ingest et")
        table.add_row("/wiki pin <sayfa>", "Sayfayı sabitle (context)")
        table.add_row("/wiki open <sayfa>", "Sayfayı terminalde oku")
        table.add_row("/wiki edit <sayfa>", "Sayfayı editörde aç")
        table.add_row("/wiki link <s1> <s2>", "İki sayfa arasında bağ kur")
        table.add_row("/wiki lint", "Wiki sağlık kontrolü")
        table.add_row("/wiki context on|off", "Otomatik context enjeksiyonu")

        console.print(table)

