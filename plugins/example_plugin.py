"""
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
        console.print("[green]✓ Example plugin loaded! 🚀[/green]")
    
    def on_unload(self) -> None:
        console.print("[yellow]📤 Example plugin unloaded[/yellow]")
