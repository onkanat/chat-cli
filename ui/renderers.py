from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()


def render_markdown(text: str) -> None:
    md = Markdown(text)
    console.print(md)


def display_search_results(results: List[Dict[str, Any]], query: str) -> None:
    """Display search results in a formatted way."""
    if not results:
        console.print(f"[yellow]No results found for:[/yellow] [white]'{query}'[/white]")
        return

    console.print(f"\n[bold blue]🔍 Search Results for:[/bold blue] [white]'{query}'[/white]")
    console.print(f"[dim]Found {len(results)} result(s)[/dim]\n")

    for i, result in enumerate(results, 1):
        item = result["item"]
        role = item.get("role", "unknown")

        # Role indicator
        role_emoji = {"user": "👤", "assistant": "🤖", "shell": "💻"}.get(role, "📝")

        console.print(f"[cyan]{i}[/cyan]. {role_emoji} [bold]{role.title()}[/bold]")

        if role == "shell":
            cmd = item.get("command", "")
            console.print(f"   [dim]Command:[/dim] [white]{cmd}[/white]")
        else:
            context = result["context"]
            # Escape Rich markup tags in context to prevent conflicts
            safe_context = context.replace("[", "\\[")
            console.print(f"   [dim]Context:[/dim] [white]{safe_context}[/white]")

        console.print(f"   [dim]Score:[/dim] [green]{result['score']}[/green]")
        console.print()


def display_token_usage(prompt_tokens: int, response_tokens: int, max_tokens: int = 2048) -> None:
    """Display token usage information in single line format."""
    total_tokens = prompt_tokens + response_tokens
    usage_percent = (total_tokens / max_tokens) * 100

    # Color code usage
    if usage_percent > 90:
        status_icon = "🔴"
    elif usage_percent > 70:
        status_icon = "🟡"
    else:
        status_icon = "🟢"

    # Display in single line format
    usage_line = (
        f"📊 Tokens: P:{prompt_tokens} R:{response_tokens} "
        f"T:{total_tokens}/{max_tokens} ({usage_percent:.1f}%) "
        f"{status_icon} {usage_percent:.1f}%"
    )

    console.print(usage_line)


def display_model_status(model: str, is_streaming: bool = False) -> None:
    """Display current model status."""
    status = "🔄 Streaming" if is_streaming else "✅ Ready"
    status_color = "green" if not is_streaming else "blue"

    status_panel = Panel(
        f"[bold]Model:[/bold] {model}\n[bold]Status:[/bold] [{status_color}]{status}[/{status_color}]",
        title="🤖 Model Status",
        border_style=status_color,
    )
    console.print(status_panel)


def display_statistics(history: List[Dict[str, Any]]) -> None:
    """Display conversation statistics."""
    if not history:
        console.print("[yellow]No conversation history available.[/yellow]")
        return

    # Calculate statistics
    total_messages = len(history)
    user_messages = len([h for h in history if h.get("role") == "user"])
    assistant_messages = len([h for h in history if h.get("role") == "assistant"])
    shell_commands = len([h for h in history if h.get("role") == "shell"])

    # Calculate total characters
    total_chars = sum(len(h.get("text", "")) for h in history)

    # Create statistics table
    table = Table(title="📊 Conversation Statistics", show_header=True, header_style="bold blue")
    table.add_column("Metric", style="cyan", width=25)
    table.add_column("Value", style="green", width=15)
    table.add_column("Percentage", style="yellow", width=15)

    table.add_row("Total Messages", str(total_messages), "100%")
    table.add_row("User Messages", str(user_messages), f"{(user_messages / total_messages * 100):.1f}%")
    table.add_row("Assistant Messages", str(assistant_messages), f"{(assistant_messages / total_messages * 100):.1f}%")
    table.add_row("Shell Commands", str(shell_commands), f"{(shell_commands / total_messages * 100):.1f}%")
    table.add_row("Total Characters", str(total_chars), "-")

    if total_messages > 0:
        avg_chars = total_chars // total_messages
        table.add_row("Avg Characters/Message", str(avg_chars), "-")

    console.print(table)


def export_conversation(history: List[Dict[str, Any]], filename: str, format_type: str = "markdown") -> bool:
    """Export conversation history to file."""
    try:
        if format_type == "markdown":
            content = "# Conversation History\n\n"
            for item in history:
                role = item.get("role", "unknown")
                if role == "user":
                    content += f"## 👤 User\n{item.get('text', '')}\n\n"
                elif role == "assistant":
                    content += f"## 🤖 Assistant\n{item.get('text', '')}\n\n"
                elif role == "shell":
                    cmd = item.get("command", "")
                    out = item.get("output", "")
                    content += f"## 💻 Shell Command\n```bash\n{cmd}\n```\n\n**Output:**\n```\n{out}\n```\n\n"
                else:
                    content += f"## 📝 {role.title()}\n{item.get('text', '')}\n\n"

        elif format_type == "json":
            import json

            content = json.dumps(history, indent=2)

        elif format_type == "txt":
            content = ""
            for item in history:
                role = item.get("role", "unknown")
                timestamp = item.get("timestamp", "")
                content += f"[{role.upper()}] {timestamp}\n"
                if role == "shell":
                    content += f"Command: {item.get('command', '')}\n"
                    content += f"Output: {item.get('output', '')}\n"
                else:
                    content += f"{item.get('text', '')}\n"
                content += "-" * 50 + "\n\n"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        return True
    except Exception as e:
        console.print(f"[red]❌ Export failed:[/red] {e}")
        return False
