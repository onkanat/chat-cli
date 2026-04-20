"""
Kiwix Hotspot Plugin for chat-cli.
Enables accessing offline ZIM libraries (Wikipedia, etc.) served via kiwix-serve.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from rich.console import Console
from rich.table import Table

from lib.plugins import PluginBase

console = Console()

class KiwixPlugin(PluginBase):
    """Plugin to interact with Kiwix Hotspot/Server."""

    def __init__(self):
        super().__init__()
        self.name = "KiwixPlugin"
        self.version = "1.1.0"
        self.description = "Access offline .zim libraries via Kiwix Hotspot"
        self.author = "Hakan Kilicaslan"

        # Default config
        self._config = {
            "kiwix_url": "http://192.168.1.6:9999",
            "fallback_url": "http://localhost:9999",
            "timeout": 10
        }
        self._navbar_cache = {}  # Cache for library navbars
        self._load_plugin_config()

    def _load_plugin_config(self):
        """Load settings from plugin_config.json."""
        config_path = Path("plugin_config.json")
        if config_path.exists():
            try:
                all_cfg = json.loads(config_path.read_text())
                plugin_cfg = all_cfg.get("plugin_settings", {}).get("kiwix_plugin", {})
                self._config.update(plugin_cfg)
            except Exception:
                pass

    def get_commands(self) -> Dict[str, Callable]:
        return {
            "kiwix": self.kiwix_command
        }

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": ["kiwix"]
        }

    def kiwix_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """
        Kiwix Hotspot commands.
        Usage:
            /kiwix list                - List available ZIM libraries
            /kiwix search <query>      - Search across all libraries
            /kiwix open <zim_id>/<url> - Open and inject an article into context
            /kiwix info                - Show server status
        """
        if not args:
            console.print("[yellow]Usage: /kiwix <list|search|open|info> [args][/yellow]")
            return

        subcmd = args[0].lower()
        subargs = args[1:]

        if subcmd == "list":
            self._cmd_list()
        elif subcmd == "search":
            self._cmd_search(subargs)
        elif subcmd == "open":
            self._cmd_open(subargs, context)
        elif subcmd == "info":
            self._cmd_info()
        else:
            console.print(f"[red]Unknown Kiwix subcommand: {subcmd}[/red]")

    def _get_base_url(self) -> Optional[str]:
        """Try primary then fallback URL."""
        urls = [self._config["kiwix_url"], self._config["fallback_url"]]
        timeout = self._config.get("timeout", 5)

        for url in urls:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    return url.rstrip("/")
            except Exception:
                continue
        return None

    def _cmd_info(self):
        """Show Kiwix server information."""
        base = self._get_base_url()
        if not base:
            console.print("[red]❌ Kiwix server not reachable.[/red]")
            console.print(f"Tried: {self._config['kiwix_url']} and {self._config['fallback_url']}")
            return

        console.print(f"[green]✅ Kiwix server active:[/green] {base}")
        try:
            # Try to get some version/stats if kiwix-serve supports it
            # Simple stats check
            resp = requests.get(f"{base}/catalog/v2/entries", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                count = len(data) if isinstance(data, list) else 0
                console.print(f"[blue]Available Libraries:[/blue] {count}")
        except Exception:
            pass

    def _cmd_list(self):
        """List available ZIM libraries."""
        base = self._get_base_url()
        if not base:
            console.print("[red]Kiwix server unreachable.[/red]")
            return

        try:
            import xml.etree.ElementTree as ET
            resp = requests.get(f"{base}/catalog/v2/entries", timeout=10)
            resp.raise_for_status()

            root = ET.fromstring(resp.text)
            # Atom namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            entries = root.findall('atom:entry', ns)

            table = Table(title="📚 Kiwix Libraries", show_header=True, header_style="bold magenta")
            table.add_column("ID", style="cyan")
            table.add_column("Title", style="white")
            table.add_column("Articles", justify="right")
            table.add_column("Language", justify="center")

            for entry in entries:
                # Extract ID from urn:uuid:...
                raw_id = entry.find('atom:id', ns).text
                lib_id = raw_id.split(':')[-1] if ':' in raw_id else raw_id

                title = entry.find('atom:title', ns).text
                count = entry.find('atom:articleCount', ns)
                count_text = count.text if count is not None else "?"
                lang = entry.find('atom:language', ns)
                lang_text = lang.text if lang is not None else "?"

                table.add_row(lib_id, title, count_text, lang_text)

            console.print(table)
            console.print("[dim]Use '/kiwix search <query>' to find articles.[/dim]")
        except Exception as e:
            console.print(f"[red]Failed to fetch catalog: {e}[/red]")

    def _cmd_search(self, args: List[str]):
        """Search across libraries using local metadata search."""
        if not args:
            console.print("[yellow]Usage: /kiwix search <query>[/yellow]")
            return

        base = self._get_base_url()
        if not base: return

        query = " ".join(args).lower()
        console.print(f"[dim]Searching Kiwix libraries for:[/dim] [white]'{query}'[/white]...")

        try:
            # 1. Get library IDs
            import xml.etree.ElementTree as ET
            cat_resp = requests.get(f"{base}/catalog/v2/entries", timeout=10)
            cat_resp.raise_for_status()
            cat_root = ET.fromstring(cat_resp.text)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            libraries = []
            for entry in cat_root.findall('atom:entry', ns):
                raw_id = entry.find('atom:id', ns).text
                lib_id = raw_id.split(':')[-1] if ':' in raw_id else raw_id
                title = entry.find('atom:title', ns).text
                libraries.append({"id": lib_id, "title": title})

            if not libraries:
                console.print("[yellow]No libraries found to search in.[/yellow]")
                return

            all_matches = []

            for lib in libraries:
                lib_id = lib["id"]
                # 2. Get/Cache navbar
                if lib_id not in self._navbar_cache:
                    nav_url = f"{base}/content/{lib_id}/navbar.json"
                    try:
                        resp = requests.get(nav_url, timeout=5)
                        if resp.status_code == 200:
                            self._navbar_cache[lib_id] = resp.json()
                        else:
                            self._navbar_cache[lib_id] = None
                    except Exception:
                        self._navbar_cache[lib_id] = None

                navbar = self._navbar_cache[lib_id]
                if navbar:
                    # 3. Recursive search in navbar
                    matches = self._find_in_navbar(navbar.get("children", []), query, lib_id)
                    all_matches.extend(matches)

            if not all_matches:
                console.print("[yellow]No results found in article titles.[/yellow]")
                return

            table = Table(title=f"🔍 Search Results: {query}")
            table.add_column("#", justify="right")
            table.add_column("Title", style="green")
            table.add_column("Library", style="blue")
            table.add_column("Path (ID)", style="dim")

            # Sort by relevance (simple: if query is at start of title)
            all_matches.sort(key=lambda x: (not x[1].lower().startswith(query), x[1]))

            for i, (path, title, lib_title) in enumerate(all_matches[:25], 1):
                table.add_row(str(i), title, lib_title, path)

            console.print(table)
            console.print("[dim]Use '/kiwix open <path>' to read an article.[/dim]")

        except Exception as e:
            console.print(f"[red]Search error: {e}[/red]")

    def _find_in_navbar(self, children: List[Dict], query: str, lib_id: str) -> List[tuple]:
        """Recursively search for query in navbar tree."""
        matches = []
        for child in children:
            name = child.get("name", "")
            href = child.get("href")

            if query in name.lower() and href:
                # Format path for /kiwix open
                path = f"{lib_id}/{href}"
                matches.append((path, name, lib_id))

            if "children" in child:
                matches.extend(self._find_in_navbar(child["children"], query, lib_id))
        return matches

    def _cmd_open(self, args: List[str], context: Dict[str, Any]):
        """Open an article and inject into context."""
        if not args:
            console.print("[yellow]Usage: /kiwix open <zim_id>/A/Title.html[/yellow]")
            return

        base = self._get_base_url()
        if not base: return

        path = args[0]
        if not path.startswith("/"):
            path = "/content/" + path

        url = f"{base}{path}"
        console.print(f"[dim]Fetching:[/dim] [white]{url}[/white]...")

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            html = resp.text

            # Clean HTML to Text
            text = self._html_to_text(html)
            title_match = re.search(r'<title>([^<]+)</title>', html, re.I)
            title = title_match.group(1) if title_match else path.split("/")[-1]

            # Display preview
            console.print(f"\n[bold green]📖 {title}[/bold green]")
            console.print("-" * 40)
            preview = text[:1000] + ("..." if len(text) > 1000 else "")
            console.print(preview)
            console.print("-" * 40)

            # Inject into context
            history = context.get("history", [])
            history.append({
                "role": "system",
                "text": f"Kiwix Article Context ({title}):\n\n{text[:10000]}"  # Limit to 10k chars
            })
            console.print(f"[blue]✓ Article '{title}' injected into chat context ({len(text)} chars).[/blue]")

        except Exception as e:
            console.print(f"[red]Failed to open article: {e}[/red]")

    def _html_to_text(self, html: str) -> str:
        """Rudimentary HTML to Text converter."""
        # Remove scripts and styles
        text = re.sub(r'<(script|style|header|footer|nav)[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
        # Handle line breaks
        text = re.sub(r'<(br|p|div|li)[^>]*>', '\n', text, flags=re.I)
        # Remove all remaining tags
        text = re.sub(r'<[^>]+>', '', text)
        # Unescape common entities
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        # Clean up whitespace
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        return text.strip()

    def on_load(self) -> None:
        console.print("[green]✓ Kiwix Hotspot plugin loaded! 📚[/green]")
