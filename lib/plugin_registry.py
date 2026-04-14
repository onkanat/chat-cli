from __future__ import annotations

from typing import Dict, List, Any, Callable
from pathlib import Path
import json
import importlib.util
from rich.console import Console
from rich.table import Table

# Import PluginBase from existing plugins.py to keep a single base class type
from lib.plugins import PluginBase

console = Console()

DEFAULT_PLUGINS_DIR = Path("plugins")
PLUGIN_CONFIG = Path("plugin_config.json")


class PluginManager:
    """Manages plugin loading, unloading, and execution."""

    def __init__(self, plugins_dir: Path = DEFAULT_PLUGINS_DIR):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, PluginBase] = {}
        self.command_registry: Dict[str, tuple[PluginBase, Callable]] = {}
        self.config = self.load_config()
        self.ensure_plugins_directory()

    def ensure_plugins_directory(self) -> None:
        """Create plugins directory if it doesn't exist."""
        self.plugins_dir.mkdir(exist_ok=True)

        # Create example plugin if directory is empty
        if not any(self.plugins_dir.iterdir()):
            self.create_example_plugin()

    def create_example_plugin(self) -> None:
        """Create an example plugin for demonstration."""
        example_plugin = '''"""
Example plugin for Ollama Chat CLI.

This plugin demonstrates how to create custom commands.
"""

from lib.plugins import PluginBase
from typing import Dict, List, Callable, Any
from rich.console import Console

console = Console()

class ExamplePlugin(PluginBase):
    """Example plugin with custom commands."""
    
    def __init__(self):
        super().__init__()
        self.name = "ExamplePlugin"
        self.version = "1.0.0"
        self.description = "Example plugin with custom commands"
        self.author = "Ollama Chat CLI"
    
    def get_commands(self) -> Dict[str, Callable]:
        return {
            "hello": self.hello_command,
            "calc": self.calc_command,
            "time": self.time_command
        }
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": list(self.get_commands().keys())
        }
    
    def hello_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """Say hello to the user."""
        name = " ".join(args) if args else "World"
        console.print(f"[green]Hello, {name}! 👋[/green]")
    
    def calc_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """Simple calculator."""
        if len(args) != 3:
            console.print("[yellow]Usage: /calc <num1> <op> <num2>[/yellow]")
            console.print("[dim]Example: /calc 5 + 3[/dim]")
            return
        
        try:
            num1, op, num2 = float(args[0]), args[1], float(args[2])
            if op == "+":
                result = num1 + num2
            elif op == "-":
                result = num1 - num2
            elif op == "*":
                result = num1 * num2
            elif op == "/":
                result = num1 / num2
            else:
                console.print(f"[red]Unknown operator: {op}[/red]")
                return
            
            console.print(f"[green]Result: {num1} {op} {num2} = {result}[/green]")
        except ValueError:
            console.print("[red]Invalid numbers provided[/red]")
        except ZeroDivisionError:
            console.print("[red]Cannot divide by zero[/red]")
    
    def time_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """Show current time."""
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"[blue]Current time: {current_time} 🕐[/blue]")
    
    def on_load(self) -> None:
        console.print(f"[green]✓ Example plugin loaded! 🚀[/green]")
    
    def on_unload(self) -> None:
        console.print(f"[yellow]📤 Example plugin unloaded[/yellow]")
'''

        example_file = self.plugins_dir / "example_plugin.py"
        with open(example_file, "w") as f:
            f.write(example_plugin)

        console.print(f"[dim]Created example plugin: {example_file}[/dim]")

    def load_config(self) -> Dict[str, Any]:
        """Load plugin configuration."""
        if PLUGIN_CONFIG.exists():
            try:
                with open(PLUGIN_CONFIG, "r") as f:
                    return json.load(f)
            except Exception:
                pass

        return {"enabled_plugins": [], "plugin_settings": {}, "auto_load": True}

    def save_config(self) -> None:
        """Save plugin configuration."""
        try:
            with open(PLUGIN_CONFIG, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def discover_plugins(self) -> List[str]:
        """Discover available plugin files."""
        plugins = []
        for file_path in self.plugins_dir.glob("*.py"):
            if file_path.name != "__init__.py":
                plugins.append(file_path.stem)
        return plugins

    def load_plugin(self, plugin_name: str) -> bool:
        """Load a specific plugin."""
        if plugin_name in self.plugins:
            console.print(f"[yellow]Plugin '{plugin_name}' already loaded[/yellow]")
            return True

        plugin_file = self.plugins_dir / f"{plugin_name}.py"
        if not plugin_file.exists():
            console.print(f"[red]Plugin file not found: {plugin_file}[/red]")
            return False

        try:
            # Load plugin module
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find plugin class
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                try:
                    if isinstance(attr, type) and issubclass(attr, PluginBase) and attr != PluginBase:
                        plugin_class = attr
                        break
                except Exception:
                    # Skip attributes that cause issubclass issues
                    continue

            if not plugin_class:
                console.print(f"[red]No valid plugin class found in {plugin_file}[/red]")
                return False

            # Instantiate plugin
            plugin_instance = plugin_class()

            # Register commands
            commands = plugin_instance.get_commands()
            for cmd_name, cmd_func in commands.items():
                self.command_registry[cmd_name] = (plugin_instance, cmd_func)

            # Store plugin
            self.plugins[plugin_name] = plugin_instance

            # Call on_load
            plugin_instance.on_load()

            # Update config
            if plugin_name not in self.config["enabled_plugins"]:
                self.config["enabled_plugins"].append(plugin_name)
                self.save_config()

            console.print(f"[green]✓ Loaded plugin:[/green] [white]{plugin_name}[/white]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Failed to load plugin {plugin_name}:[/red] {e}")
            return False

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a specific plugin."""
        if plugin_name not in self.plugins:
            console.print(f"[yellow]Plugin '{plugin_name}' not loaded[/yellow]")
            return False

        try:
            plugin = self.plugins[plugin_name]

            # Remove commands from registry
            commands = plugin.get_commands()
            for cmd_name in commands.keys():
                if cmd_name in self.command_registry:
                    del self.command_registry[cmd_name]

            # Call on_unload
            plugin.on_unload()

            # Remove plugin
            del self.plugins[plugin_name]

            # Update config
            if plugin_name in self.config["enabled_plugins"]:
                self.config["enabled_plugins"].remove(plugin_name)
                self.save_config()

            console.print(f"[green]✓ Unloaded plugin:[/green] [white]{plugin_name}[/white]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Failed to unload plugin {plugin_name}:[/red] {e}")
            return False

    def load_all_plugins(self) -> None:
        """Load all enabled plugins."""
        if not self.config.get("auto_load", True):
            return

        discovered = self.discover_plugins()
        enabled = self.config.get("enabled_plugins", [])

        # Load enabled plugins first
        for plugin_name in enabled:
            if plugin_name in discovered:
                self.load_plugin(plugin_name)

        # Auto-load example plugin if no plugins are loaded
        if not self.plugins and "example_plugin" in discovered:
            self.load_plugin("example_plugin")

    def execute_command(self, command: str, args: List[str], context: Dict[str, Any]) -> bool:
        """Execute a plugin command."""
        if command not in self.command_registry:
            return False

        plugin, cmd_func = self.command_registry[command]

        try:
            # Execute command
            cmd_func(args, context)

            # Notify plugin
            plugin.on_command_executed(command, args)
            return True

        except Exception as e:
            console.print(f"[red]❌ Error executing command {command}:[/red] {e}")
            return False

    def list_plugins(self) -> None:
        """List all loaded plugins."""
        if not self.plugins:
            console.print("[yellow]No plugins loaded[/yellow]")
            return

        table = Table(title="🔌 Loaded Plugins", show_header=True, header_style="bold blue")
        table.add_column("Plugin", style="cyan", width=20)
        table.add_column("Version", style="green", width=10)
        table.add_column("Description", style="white", width=30)
        table.add_column("Commands", style="yellow", width=20)

        for plugin_name, plugin in self.plugins.items():
            commands = ", ".join(f"/{cmd}" for cmd in plugin.get_commands().keys())
            table.add_row(plugin_name, plugin.version, plugin.description, commands or "None")

        console.print(table)

    def list_available_plugins(self) -> None:
        """List all available plugins (loaded and unloaded)."""
        discovered = self.discover_plugins()
        loaded = set(self.plugins.keys())

        table = Table(title="🔌 Available Plugins", show_header=True, header_style="bold blue")
        table.add_column("Plugin", style="cyan", width=20)
        table.add_column("Status", style="green", width=10)
        table.add_column("Description", style="white", width=30)

        for plugin_name in discovered:
            if plugin_name == "__pycache__":
                continue

            status = "✅ Loaded" if plugin_name in loaded else "⏸️ Available"
            status_style = "green" if plugin_name in loaded else "yellow"

            # Get description if loaded
            if plugin_name in loaded:
                description = self.plugins[plugin_name].description
            else:
                description = "Not loaded"

            table.add_row(plugin_name, f"[{status_style}]{status}[/{status_style}]", description)

        console.print(table)

    def get_plugin_info(self, plugin_name: str) -> None:
        """Show detailed information about a plugin."""
        if plugin_name not in self.plugins:
            console.print(f"[red]Plugin '{plugin_name}' not loaded[/red]")
            return

        plugin = self.plugins[plugin_name]
        info = plugin.get_info()

        console.print(f"\n[bold blue]🔌 {info['name']}[/bold blue]")
        console.print(f"[dim]Version:[/dim] [green]{info['version']}[/green]")
        console.print(f"[dim]Author:[/dim] [cyan]{info['author']}[/cyan]")
        console.print(f"[dim]Description:[/dim] [white]{info['description']}[/white]")

        if info.get("commands"):
            console.print("[dim]Commands:[/dim]")
            for cmd in info["commands"]:
                console.print(f"  [yellow]/{cmd}[/yellow]")

    def get_all_commands(self) -> Dict[str, str]:
        """Get all available plugin commands with descriptions."""
        commands = {}
        for cmd_name, (plugin, cmd_func) in self.command_registry.items():
            # Extract first line of docstring as description
            desc = "No description provided"
            if cmd_func.__doc__:
                desc = cmd_func.__doc__.strip().split("\n")[0]
            commands[cmd_name] = desc
        return commands
