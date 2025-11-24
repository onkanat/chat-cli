from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .manager import AnalyticsManager

console = Console()


def display_analytics_dashboard(analytics: AnalyticsManager) -> None:
    """Display comprehensive analytics dashboard in single line format."""
    stats = analytics.get_detailed_stats()

    # Display in single line format
    dashboard_line = (
        f"📊 Analytics: "
        f"Msgs:{stats['total_messages']} "
        f"Tokens:{stats['total_tokens']} "
        f"AvgTime:{stats['avg_response_time']:.1f}s "
        f"Sessions:{stats['total_sessions']}"
    )

    console.print(dashboard_line)

    # Model usage table
    if stats["models_used"]:
        model_table = Table(title="🤖 Model Usage", show_header=True, header_style="bold blue")
        model_table.add_column("Model", style="cyan", width=20)
        model_table.add_column("Messages", style="green", width=10)
        model_table.add_column("Tokens", style="yellow", width=10)
        model_table.add_column("Avg Response", style="magenta", width=15)

        for model, model_stats in stats["models_used"].items():
            model_table.add_row(
                model,
                str(model_stats["count"]),
                str(model_stats["tokens"]),
                f"{model_stats['avg_response_time']:.2f}s",
            )

        console.print(model_table)
        console.print()

    # Command usage table
    if stats["commands_used"]:
        cmd_table = Table(title="⌨️ Command Usage", show_header=True, header_style="bold blue")
        cmd_table.add_column("Command", style="cyan", width=20)
        cmd_table.add_column("Usage Count", style="green", width=15)
        cmd_table.add_column("Frequency", style="yellow", width=15)

        total_cmds = sum(stats["commands_used"].values())
        for cmd, count in sorted(stats["commands_used"].items(), key=lambda x: x[1], reverse=True):
            frequency = f"{(count / total_cmds * 100):.1f}%"
            cmd_table.add_row(f"/{cmd}", str(count), frequency)

        console.print(cmd_table)
        console.print()

    # Last 7 days usage
    if stats["last_7_days"]:
        daily_table = Table(title="📅 Last 7 Days Usage", show_header=True, header_style="bold blue")
        daily_table.add_column("Date", style="cyan", width=15)
        daily_table.add_column("Messages", style="green", width=10)
        daily_table.add_column("Tokens", style="yellow", width=10)

        for date, usage in sorted(stats["last_7_days"].items(), reverse=True):
            daily_table.add_row(date, str(usage["messages"]), str(usage["tokens"]))

        console.print(daily_table)


def display_real_time_monitoring(analytics: AnalyticsManager) -> None:
    """Display real-time monitoring information."""
    console.print(
        Panel(
            "[bold green]🔴 LIVE MONITORING[/bold green]\n"
            "Tracking messages, response times, and usage patterns...",
            title="📊 Real-time Analytics",
            border_style="green",
        )
    )


def generate_analytics_report(analytics: AnalyticsManager, filename: str = "analytics_report.md") -> bool:
    """Generate comprehensive analytics report."""
    try:
        stats = analytics.get_detailed_stats()

        report = f"""# 📊 Analytics Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 📈 Summary Statistics

- **Total Messages:** {stats["total_messages"]}
- **Total Tokens:** {stats["total_tokens"]}
- **Average Response Time:** {stats["avg_response_time"]:.2f}s
- **Total Sessions:** {stats["total_sessions"]}

## 🤖 Model Usage Analysis

"""

        for model, model_stats in stats["models_used"].items():
            report += f"""### {model}
- Messages: {model_stats["count"]}
- Tokens: {model_stats["tokens"]}
- Average Response Time: {model_stats["avg_response_time"]:.2f}s

"""

        report += f"""## ⌨️ Command Usage

Most used command: **/{stats["most_used_command"] or "None"}**

"""

        for cmd, count in sorted(stats["commands_used"].items(), key=lambda x: x[1], reverse=True)[:10]:
            report += f"- /{cmd}: {count} times\n"

        report += """
## 📅 Recent Usage (Last 7 Days)

"""

        for date, usage in sorted(stats["last_7_days"].items(), reverse=True):
            report += f"- **{date}:** {usage['messages']} messages, {usage['tokens']} tokens\n"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)

        return True
    except Exception as e:
        console.print(f"[red]❌ Report generation failed:[/red] {e}")
        return False
