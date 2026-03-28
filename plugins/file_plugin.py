"""
File operations plugin for Ollama Chat CLI.

Allows reading and writing files. Deletion and copying are explicitly disabled.
"""

from lib.plugins import PluginBase
from typing import Dict, List, Callable, Any
from rich.console import Console
from pathlib import Path

console = Console()

class FilePlugin(PluginBase):
    """File operations plugin for reading and writing files."""
    
    def __init__(self):
        super().__init__()
        self.name = "FilePlugin"
        self.version = "1.0.0"
        self.description = "Read and write files functionality for the model"
        self.author = "Ollama Chat CLI"
    
    def get_commands(self) -> Dict[str, Callable]:
        return {
            "file": self.file_command
        }
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": list(self.get_commands().keys())
        }
    
    def file_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """Handle /file command."""
        if not args:
            console.print("[yellow]Usage: /file <read|write> <path> [content][/yellow]")
            return
            
        action = args[0].lower()
        if action == "read":
            self._read_file(args[1:], context)
        elif action == "write":
            self._write_file(args[1:], context)
        else:
            console.print(f"[red]Unknown action: {action}. Supported actions: read, write[/red]")
            
    def _read_file(self, args: List[str], context: Dict[str, Any]) -> None:
        if not args:
            console.print("[yellow]Usage: /file read <path>[/yellow]")
            return
            
        file_path = Path(args[0])
        try:
            if not file_path.exists():
                console.print(f"[red]File not found: {file_path}[/red]")
                return
            if not file_path.is_file():
                console.print(f"[red]Not a file: {file_path}[/red]")
                return
                
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            console.print(f"[green]File loaded: {file_path}[/green]")
            console.print("[dim]--- Content start ---[/dim]")
            
            # Print a snippet to the console
            display_content = content if len(content) < 1000 else content[:1000] + "\n...[truncated for display]..."
            console.print(display_content)
            console.print("[dim]--- Content end ---[/dim]")
            
            # Truncate content for the model context if it's absurdly large (e.g. over 20k chars)
            max_chars = 20000
            if len(content) > max_chars:
                model_content = content[:max_chars] + f"\n...[File truncated due to size. Omitted {len(content) - max_chars} characters]"
                console.print(f"[yellow]Warning: File is too large, it has been truncated to {max_chars} characters for the model context.[/yellow]")
            else:
                model_content = content
            
            # Add to conversation history to let the model read the result
            if "history" in context:
                context["history"].append({
                    "role": "system",
                    "text": f"User used a plugin to read the file: {file_path}. Content:\n```\n{model_content}\n```\n"
                })
            
        except Exception as e:
            console.print(f"[red]Error reading file: {str(e)}[/red]")
            
    def _write_file(self, args: List[str], context: Dict[str, Any]) -> None:
        if len(args) < 2:
            console.print("[yellow]Usage: /file write <path> <content>[/yellow]")
            return
            
        file_path = Path(args[0])
        content = " ".join(args[1:])
        
        try:
            # Ensure parent directories exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            console.print(f"[green]Successfully wrote to file: {file_path}[/green]")
            
            if "history" in context:
                context["history"].append({
                    "role": "system",
                    "text": f"User used a plugin to successfully write to file: {file_path}"
                })
        except Exception as e:
            console.print(f"[red]Error writing file: {str(e)}[/red]")

    def on_load(self) -> None:
        console.print("[green]✓ File plugin loaded! 📂[/green]")
    
    def on_unload(self) -> None:
        console.print("[yellow]📤 File plugin unloaded[/yellow]")
