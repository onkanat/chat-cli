from __future__ import annotations
import os
import subprocess
import sys
from typing import Dict, List, Callable, Any
from lib.plugins import PluginBase
from rich.console import Console
from services.settings_service import determine_base_url

console = Console()

class DistillPlugin(PluginBase):
    """Plugin to trigger the LLMwiki distillation pipeline."""
    
    def __init__(self):
        super().__init__()
        self.name = "DistillPlugin"
        self.version = "1.0.0"
        self.description = "Triggers the LLMwiki distillation pipeline"
        self.author = "Antigravity Agent"
        self.script_path = "/Users/hakankilicaslan/Git/LLMwiki/scripts/distill_chats.py"
    
    def get_commands(self) -> Dict[str, Callable]:
        return {
            "distill": self.distill_command
        }

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": list(self.get_commands().keys())
        }
    
    def distill_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """Triggers the conversation distillation pipeline to generate knowledge and training data."""
        console.print("[bold green]🚀 Launching Conversation Distillation Pipeline...[/bold green]")
        
        if not os.path.exists(self.script_path):
            console.print(f"[red]Error: Distillation script not found at {self.script_path}[/red]")
            return
            
        try:
            # Dynamically determine the URL and model from the current chat session
            config = context.get("config", {})
            ollama_url = determine_base_url(config, None) or "http://localhost:11434"
            current_model = context.get("current_model") or config.get("llm_model", "gemma3:latest")
            
            # Prepare arguments
            cmd_args = [sys.executable, self.script_path]
            cmd_args.extend(["--url", ollama_url])
            cmd_args.extend(["--model", current_model])
            
            process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            console.print("[dim]Distillation in progress... Please wait.[/dim]")
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                console.print("[bold green]✓ Distillation completed successfully![/bold green]")
                console.print(f"[dim]{stdout}[/dim]")
            else:
                console.print("[bold red]Error during distillation:[/bold red]")
                console.print(f"[red]{stderr}[/red]")
                
        except Exception as e:
            console.print(f"[bold red]Failed to execute distillation script:[/bold red] {e}")

    def on_load(self) -> None:
        console.print("[green]✓ Distill plugin loaded! ⚗️[/green]")
