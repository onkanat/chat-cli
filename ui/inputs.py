from __future__ import annotations

from typing import List

from rich.console import Console

console = Console()


def select_model_menu(models: List[str], current_model: str | None = None) -> str | None:
    """Interactive model selection menu."""
    if not models:
        console.print("[yellow]No models available.[/yellow]")
        return None

    # Actual current model is not tracked by the official client; show app's choice
    actual_current = None

    console.print("\n[bold blue]Available Models:[/bold blue]")

    for i, model in enumerate(models, 1):
        # Show status indicators
        if model == current_model:
            marker = "👉"
            status = "[green]✓ Current[/green]"
        elif model == actual_current:
            marker = "🔷"
            status = "[blue]● Active[/blue]"
        else:
            marker = "  "
            status = "[dim]○ Available[/dim]"

        console.print(f"{marker} [cyan]{i}[/cyan]. [white]{model}[/white] {status}")

    console.print(f"\n[bold]App current model:[/bold] [green]{current_model or 'None'}[/green]")
    if actual_current:
        if actual_current != current_model:
            console.print(
                f"[bold]Ollama active model:[/bold] [blue]{actual_current}[/blue] "
                f"[yellow](⚠️  Mismatch!)[/yellow]"
            )
        else:
            console.print(f"[bold]Ollama active model:[/bold] [blue]{actual_current}[/blue] [green]✓ Synced[/green]")
    else:
        console.print("[bold]Ollama active model:[/bold] [dim]None (no model currently loaded)[/dim]")
    console.print("[dim]Enter number to select, or press Enter to use current[/dim]")

    try:
        choice = input("Select model (number): ").strip()
        if not choice:
            return current_model

        choice_num = int(choice)
        if 1 <= choice_num <= len(models):
            selected = models[choice_num - 1]
            console.print(f"[green]✓ Selected:[/green] [white]{selected}[/white]")
            return selected
        else:
            console.print(f"[red]Invalid selection. Please enter 1-{len(models)}[/red]")
            return current_model
    except (ValueError, KeyboardInterrupt, EOFError):
        return current_model


def clear_screen() -> None:
    """Clear the terminal screen."""
    import os

    os.system("cls" if os.name == "nt" else "clear")
