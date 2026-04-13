"""
Wiki plugin for chat-cli (Omni-Context V2 Integration).

Provides direct slash commands for Wiki operations:
    /wiki pin <sayfa>                 - Pin a wiki page to context
    /wiki unpin                       - Clear active pinned pages
    /wiki search <sorgu>              - Semantic search over wiki
    /wiki open <satır_no>             - Open/inject a search result by its row number
    /wiki show <sayfa>                - Read a page's markdown in terminal without pinning
    /wiki add <dosya> <başlık> [içerik] - Create a new wiki page (opens multi-line prompt if no content)
    /wiki edit <dosya>                - Edit a wiki page (opens full file in multi-line prompt or system editor)
    /wiki delete <dosya>              - Delete a wiki page
    /wiki list                        - List all wiki files
    /wiki help                   - Show wiki command reference
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
from rich.prompt import Confirm
import threading

# Fallback multiline input
def _fallback_multiline(prompt: str) -> str:
    print(prompt)
    lines = []
    while True:
        try:
            line = input("... ")
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)


# Try to load input_handler from lib
try:
    from lib.input_handler import get_multiline_input as chat_multiline
except ImportError:
    chat_multiline = _fallback_multiline

console = Console()

_DEFAULTS: Dict[str, Any] = {
    "omni_daemon_url": "http://localhost:8000",
    "wiki_path": "/Users/hakankilicaslan/Git/LLMwiki",
    "auto_context": False,
    "context_top_k": 3,
    "request_timeout": 30,
    "default_editor": "vim",
}

class WikiPlugin(PluginBase):
    """Wiki management and Omni-Context V2 plugin."""

    def __init__(self):
        super().__init__()
        self.name = "WikiPlugin"
        self.version = "2.0.0"
        self.description = "Direct Wiki commands (Omni-Context V2)"
        self.author = "Omni-Context"
        self._cfg: Dict[str, Any] = dict(_DEFAULTS)
        self._auto_context: bool = False
        self._pinned_pages: List[Path] = []
        self._last_search_results: List[Dict] = []
        self._background_thread = None

    def get_commands(self) -> Dict[str, Callable]:
        return {
            "wiki": self._cmd_wiki,
        }

    def _cmd_wiki(self, args: List[str], context: Dict[str, Any]) -> None:
        if not args:
            self._cmd_help([], context)
            return

        subcmd = args[0].lower()
        sub_args = args[1:]

        routers = {
            "pin": self._cmd_pin,
            "unpin": self._cmd_unpin,
            "search": self._cmd_search,
            "open": self._cmd_open,
            "show": self._cmd_show,
            "add": self._cmd_add,
            "edit": self._cmd_edit,
            "delete": self._cmd_delete,
            "list": self._cmd_list,
            "lint": self._cmd_lint,
            "help": self._cmd_help,
        }

        if subcmd in routers:
            routers[subcmd](sub_args, context)
        else:
            console.print(f"[red]Bilinmeyen wiki alt-komutu:[/red] {subcmd}")
            self._cmd_help([], context)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": list(self.get_commands().keys()),
        }

    def on_load(self) -> None:
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
        console.print("[green]✓ Wiki plugin (V2) loaded! 📚[/green]")
        console.print("[dim]Type /wiki help for available commands.[/dim]")

    def before_chat_turn(self, user_message: str, context: Dict[str, Any]) -> None:
        injected_segments = []

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
    # HTTP helpers
    # ------------------------------------------------------------------

    def _base_url(self) -> str:
        return self._cfg.get("omni_daemon_url", _DEFAULTS["omni_daemon_url"]).rstrip("/")

    def _post(self, path: str, body: dict) -> Dict | None:
        url = self._base_url() + f"/api/v1{path}"
        try:
            resp = httpx.post(url, json=body, timeout=self._cfg.get("request_timeout", 30))
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            console.print(f"[red]Cannot connect to omni-daemon at {self._base_url()}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Request failed:[/red] {e}")
            return None

    def _api_wiki_search(self, query: str, top_k: int = 5) -> List[Dict] | None:
        data = self._post("/wiki/search", {"query": query, "top_k": top_k, "score_threshold": 0.0})
        if data is None:
            return None
        return data.get("results", [])
        
    def _api_wiki_index(self) -> None:
        """Call indexing asynchronously to avoid blocking the UI."""
        def run_index():
            self._post("/wiki/index", {})
        threading.Thread(target=run_index, daemon=True).start()

    # ------------------------------------------------------------------
    # File resolving
    # ------------------------------------------------------------------

    def _find_file(self, keyword: str) -> Optional[Path]:
        root_dir = Path(self._cfg.get("wiki_path", _DEFAULTS["wiki_path"]))
        if not root_dir.exists():
            return None
            
        keyword = str(keyword).lower().strip()
        if keyword.endswith(".md"):
            keyword = keyword[:-3]

        for folder in ["wiki/concepts", "wiki/entities", "wiki/sources", "raw"]:
            target = root_dir / folder / f"{keyword}.md"
            if target.exists():
                return target

        all_files = list(root_dir.rglob("*.md"))
        for p in all_files:
            if keyword in p.stem.lower() or keyword in p.name.lower():
                return p
        return None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _cmd_lint(self, args: List[str], context: Dict[str, Any]) -> None:
        console.print("[yellow]⚕️ Running Wiki health check via Omni-Daemon...[/yellow]")
        data = self._post("/wiki/lint", {})
        if data:
            report = data.get("report") or data.get("message") or str(data)
            console.print(Panel(Markdown(report), title="Wiki Lint Report"))
        else:
            console.print("[red]Daemon'dan lint raporu alınamadı veya bağlantı koptu.[/red]")

    def _cmd_pin(self, args: List[str], context: Dict[str, Any]) -> None:
        if not args:
            console.print("[yellow]Usage: /pin <sayfa>[/yellow]")
            return

        cmd = " ".join(args).lower()
        target = self._find_file(cmd)
        
        if not target:
            console.print(f"[red]Bulunamadı: {cmd}[/red]")
            return

        if target not in self._pinned_pages:
            self._pinned_pages.append(target)
            console.print(f"📌 [green]Bağlam eklendi (Pinned):[/green] {target.name}")
        else:
            console.print(f"[dim]Zaten pinli: {target.name}[/dim]")

    def _cmd_unpin(self, args: List[str], context: Dict[str, Any]) -> None:
        if not self._pinned_pages:
            console.print("[dim]Aktif pin yok.[/dim]")
            return
            
        if not args:
            self._pinned_pages.clear()
            console.print("[yellow]Tüm pinler temizlendi.[/yellow]")
            return
            
        cmd = " ".join(args).lower()
        target = self._find_file(cmd)
        if target in self._pinned_pages:
            self._pinned_pages.remove(target)
            console.print(f"📍 [yellow]Pin kaldırıldı:[/yellow] {target.name}")
        else:
            console.print(f"[red]Pinler arasında bulunamadı: {cmd}[/red]")

    def _cmd_search(self, args: List[str], context: Dict[str, Any]) -> None:
        if not args:
            console.print("[yellow]Usage: /search <sorgu>[/yellow]")
            return

        query = " ".join(args)
        top_k = self._cfg.get("context_top_k", 5)
        results = self._api_wiki_search(query, top_k=top_k)
        
        if results is None:
            return

        self._last_search_results = results  # Store for /open

        if not results:
            console.print("[yellow]Arama sonucu bulunamadı.[/yellow]")
            return

        table = Table(title=f"🔍 Search: {query}", show_header=True, header_style="bold blue")
        table.add_column("No", style="cyan", justify="right", width=4)
        table.add_column("Score", style="green", width=6)
        table.add_column("Dosya / Path", style="yellow")
        table.add_column("Özet (Snippet)", style="white")

        for i, item in enumerate(results, 1):
            score = item.get("score", 0)
            path = item.get("path", "")
            snippet = item.get("content", "").strip().replace("\n", " ")[:80] + "..."
            short_path = str(Path(path).name) if path else "unknown"
            table.add_row(str(i), f"{score:.2f}", short_path, snippet)

        console.print(table)
        console.print("[dim]İçeriği görmek / context'e almak için: /open <satır_no>[/dim]")

    def _cmd_open(self, args: List[str], context: Dict[str, Any]) -> None:
        if not args:
            console.print("[yellow]Usage: /open <satır_no>[/yellow]")
            return

        try:
            idx = int(args[0]) - 1
            if idx < 0 or idx >= len(self._last_search_results):
                raise ValueError
        except ValueError:
            console.print("[red]Geçersiz satır no.[/red]")
            return

        item = self._last_search_results[idx]
        path = item.get("path", "Unknown")
        content = item.get("content", "No content")
        
        console.print(Panel(Markdown(content), title=f"[bold blue]📄 {Path(path).name}[/bold blue]", expand=True))

        if "history" in context:
            context["history"].append({
                "role": "system",
                "text": f"Kullanıcı {Path(path).name} sayfasının/bölümünün içeriğini açtı:\n\n{content}",
            })
            console.print(f"[dim]✓ İçerik bağlama (context) eklendi.[/dim]")

    def _cmd_show(self, args: List[str], context: Dict[str, Any]) -> None:
        """Show full content of a wiki page.

        Accepts EITHER:
          /wiki show <satır_no>   – row number from the last /wiki search table
          /wiki show <sayfa_adı>  – keyword / page name (partial match OK)
        """
        if not args:
            console.print("[yellow]Usage: /wiki show <satır_no|sayfa_adı>[/yellow]")
            console.print("[dim]Örnek: /wiki show 2  veya  /wiki show raspberry[/dim]")
            return

        # ── Branch 1: numeric → use last search results ──────────────────
        if len(args) == 1 and args[0].isdigit():
            idx = int(args[0]) - 1
            if not self._last_search_results:
                console.print("[yellow]⚠️  Önce /wiki search <sorgu> ile arama yapın.[/yellow]")
                return
            if idx < 0 or idx >= len(self._last_search_results):
                console.print(
                    f"[red]Geçersiz satır no: {args[0]}  "
                    f"(1-{len(self._last_search_results)} arası)[/red]"
                )
                return

            item = self._last_search_results[idx]
            path_str = item.get("path", "")
            target = Path(path_str) if path_str else None

            # Prefer reading from disk for full content (search result may be truncated)
            content = None
            if target and target.exists():
                try:
                    content = target.read_text(encoding="utf-8")
                except Exception:
                    pass
            if content is None:
                content = item.get("content", "")

            if not content or not content.strip():
                console.print(f"[yellow]⚠️  Dosya boş:[/yellow] [dim]{path_str or '(bilinmiyor)'}[/dim]")
                return

            title = target.name if target else (path_str or f"Sonuç {args[0]}")
            console.print(Panel(Markdown(content), title=f"[bold blue]📄 {title}[/bold blue]", expand=True))
            return

        # ── Branch 2: keyword → find file by name ────────────────────────
        keyword = " ".join(args).lower()
        target = self._find_file(keyword)

        if not target:
            console.print(f"[red]Sayfa bulunamadı: {keyword}[/red]")
            console.print("[dim]İpucu: Önce /wiki search ile arama yapıp satır numarasını kullanabilirsiniz.[/dim]")
            return

        try:
            content = target.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Dosya okunamıyor {target}: {e}[/red]")
            return

        if not content.strip():
            console.print(f"[yellow]⚠️  Dosya boş:[/yellow] [dim]{target}[/dim]")
            return

        console.print(Panel(Markdown(content), title=f"[bold blue]📄 {target.name}[/bold blue]", expand=True))




    def _cmd_add(self, args: List[str], context: Dict[str, Any]) -> None:
        if len(args) < 2:
            console.print("[yellow]Usage: /add <dosya.md> \"Başlık\" [opsiyonel içerik][/yellow]")
            return

        filename = args[0]
        if not filename.endswith(".md"):
            filename += ".md"
            
        title = args[1]
        
        root_dir = Path(self._cfg.get("wiki_path", _DEFAULTS["wiki_path"]))
        target_path = root_dir / "wiki" / "concepts" / filename
        
        if target_path.exists():
            console.print(f"[red]Hata: {filename} zaten var. Düzenlemek için /edit kullanın.[/red]")
            return

        # Check if content was provided in the command line
        content = "\\n".join(args[2:]).replace("\\\\n", "\\n") if len(args) > 2 else ""
        
        if not content:
            console.print(f"[dim]Yeni sayfa: {filename} - Başlık: {title}[/dim]")
            console.print("[dim]İçeriği girin (Boş satırda Ctrl-D ile bitirin):[/dim]")
            content = chat_multiline(">>> ")
            
        full_content = f"# {title}\\n\\n{content}\\n"
        
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(full_content, encoding="utf-8")
            console.print(f"[green]✓ Sayfa oluşturuldu:[/green] {target_path}")
            self._api_wiki_index() # Async re-index so Omni-Daemon sees it
        except Exception as e:
            console.print(f"[red]Yazılamadı: {e}[/red]")

    def _cmd_edit(self, args: List[str], context: Dict[str, Any]) -> None:
        if not args:
            console.print("[yellow]Usage: /edit <sayfa>[/yellow]")
            return

        keyword = " ".join(args).lower()
        target = self._find_file(keyword)

        if not target:
            console.print(f"[red]Bulunamadı: {keyword}[/red]")
            return

        try:
            content = target.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Okunamıyor: {e}[/red]")
            return

        editor = os.environ.get("EDITOR") or self._cfg.get("default_editor", "vim")
        console.print(f"[dim]Opening {target.name} with {editor}...[/dim]")
        try:
            subprocess.call([editor, str(target)])
            self._api_wiki_index() # Re-index after edit
        except Exception as e:
            console.print(f"[red]Editör açılamadı: {e}[/red]")

    def _cmd_delete(self, args: List[str], context: Dict[str, Any]) -> None:
        if not args:
            console.print("[yellow]Usage: /delete <sayfa>[/yellow]")
            return

        keyword = " ".join(args).lower()
        target = self._find_file(keyword)

        if not target:
            console.print(f"[red]Bulunamadı: {keyword}[/red]")
            return

        if Confirm.ask(f"[bold red]Uyarı:[/bold red] '{target.name}' kalıcı olarak silinecek. Onaylıyor musunuz?", default=False):
            try:
                target.unlink()
                console.print(f"[green]✓ Silindi:[/green] {target.name}")
                if target in self._pinned_pages:
                    self._pinned_pages.remove(target)
                self._api_wiki_index()
            except Exception as e:
                console.print(f"[red]Silinemedi: {e}[/red]")
        else:
            console.print("[dim]İptal edildi.[/dim]")

    def _cmd_list(self, args: List[str], context: Dict[str, Any]) -> None:
        root_dir = Path(self._cfg.get("wiki_path", _DEFAULTS["wiki_path"]))
        if not root_dir.exists():
            console.print(f"[red]Wiki root bulunamadı: {root_dir}[/red]")
            return

        all_files = list(root_dir.rglob("*.md"))
        
        # Sadece wiki altındaki veya anlamlı .md dosyaları
        valid_files = [f for f in all_files if ".git" not in f.parts and "venv" not in f.parts]
        
        if not valid_files:
            console.print("[dim]Wiki'de bulunamadı.[/dim]")
            return
            
        table = Table(title=f"📚 Wiki Dizini ({len(valid_files)} dosya)", show_header=True, header_style="bold blue")
        table.add_column("Klasör", style="cyan")
        table.add_column("Dosya", style="green")
        
        # Sort and display
        for f in sorted(valid_files):
            try:
                rel = f.relative_to(root_dir)
                table.add_row(str(rel.parent), f.name)
            except ValueError:
                pass
                
        console.print(table)

    def _cmd_help(self, args: List[str], context: Dict[str, Any]) -> None:
        table = Table(title="📚 Wiki Komutları (Omni-Context V2)", show_header=True, header_style="bold blue")
        table.add_column("Komut", style="cyan")
        table.add_column("Kullanım", style="green")
        table.add_column("Açıklama", style="white")

        table.add_row("/wiki pin", "/wiki pin <sayfa>", "Sayfayı aktif bağlam (context) olarak işaretler")
        table.add_row("/wiki unpin", "/wiki unpin [sayfa]", "Aktif bağlamı kaldırır")
        table.add_row("/wiki search", "/wiki search <sorgu>", "Metin veya semantik wiki araması (Rich tablo döner)")
        table.add_row("/wiki open", "/wiki open <satır_no>", "search tablosundaki No'ya göre okur ve bağlama ekler")
        table.add_row("/wiki show", "/wiki show <satır_no|sayfa>", "Tam içeriği gösterir (arama no veya dosya adı)")
        table.add_row("/wiki add", "/wiki add <sayfa> <başlık>", "Yeni sayfa oluşturur (Rich prompt ile içerik ister)")
        table.add_row("/wiki edit", "/wiki edit <sayfa>", "Sayfayı sistem editöründe ($EDITOR) açar")
        table.add_row("/wiki delete", "/wiki delete <sayfa>", "Sayfayı kalıcı olarak siler (Onay ister)")
        table.add_row("/wiki list", "/wiki list", "Wiki dizinindeki tüm sayfaları listeler")
        table.add_row("/wiki help", "/wiki help", "Bu yardım menüsünü gösterir")

        console.print(table)
