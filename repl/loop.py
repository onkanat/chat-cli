from __future__ import annotations

import copy
import shlex
from datetime import datetime
from pathlib import Path
from typing import List

from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.console import Group

import ui as ui_mod
import analytics
import lib.history as history_mod
import lib.ollama_wrapper as ow
from lib.plugin_registry import PluginManager

from services.settings_service import determine_base_url, load_config, save_config
from services.models_service import list_models, set_current_model, load_model, delete_model
from ui.settings_menus import settings_menu

try:
    import lib.input_handler as input_handler  # type: ignore
except Exception:
    try:
        import input_handler  # type: ignore
    except Exception:  # pragma: no cover - optional enhancement
        input_handler = None  # type: ignore


CURRENT_MODEL: str | None = None


def sanitize_prompt(s: str) -> str:
    """Remove slash commands and traceback noise from prompt."""
    traceback_indicators = ("Traceback (most recent...", "File \"", ")\n ")
    if any(indicator in s for indicator in traceback_indicators):
        return s
    lines = [ln for ln in s.splitlines() if not ln.lstrip().startswith("/")]
    cleaned = "\n".join(lines).strip()
    return cleaned


def _parse_run_args(args: List[str]) -> tuple[str | None, str | None]:
    """Parse model and prompt from a `run` style args list."""
    if not args:
        return None, None
    model = None
    prompt = None
    parts = list(args)
    if parts[0] == "run":
        parts = parts[1:]
    if parts:
        model = parts[0]
    for i, part in enumerate(parts):
        if part.startswith("--prompt="):
            prompt = part.split("=", 1)[1]
            break
        if part in {"--prompt", "-p"} and i + 1 < len(parts):
            prompt = parts[i + 1]
            break
    if prompt is None and len(parts) > 1:
        prompt = " ".join(parts[1:])
    return model, prompt


def _format_colored_status(prefix: str, value: str) -> str:
    """Return a standardized status line with a colored prefix."""
    return f"{prefix} [white]{value}[/white]"


def _format_session_entry(session: dict) -> str:
    """Build a single line showing session metadata."""
    marker = "👉" if session.get("is_current") else "  "
    name = session.get("custom_name", session["session_id"])
    model_name = session.get("model_used", "Unknown")
    return (
        f"{marker} [cyan]{session['session_id']}[/cyan] - "
        f"[white]{name}[/white] ([dim]{model_name}[/dim])"
    )


def run_chat(
    history_file: str,
    base_url: str | None,
    stream: bool,
    max_context_tokens: int,
    max_output_chars: int,
) -> None:
    global CURRENT_MODEL

    config = load_config()
    active_base_url = determine_base_url(config, base_url)
    if active_base_url:
        ow.init_client(active_base_url)

    # Load configuration and set default model
    if config.get("default_model") and not CURRENT_MODEL:
        CURRENT_MODEL = config["default_model"]

    # Initialize enhanced input handler if available
    command_history = None
    try:
        if input_handler is not None:
            command_history = input_handler.CommandHistory()
            input_handler.setup_readline(command_history)
    except Exception:
        pass

    # Get available models and handle selection
    models = list_models()
    if not models:
        ui_mod.console.print("[yellow]No models found. Please install a model first.[/yellow]")
        return

    # Model selection menu
    selected_model = ui_mod.select_model_menu(models, CURRENT_MODEL)
    if selected_model and selected_model != CURRENT_MODEL:
        CURRENT_MODEL = selected_model
        # Save to config
        config["default_model"] = CURRENT_MODEL
        save_config(config)
        ui_mod.console.print(f"[green]✓ Model set to:[/green] [white]{CURRENT_MODEL}[/white]")
        ui_mod.console.print("[dim]💾 Saved as default model[/dim]")

    hpath = Path(history_file)
    history = history_mod.load_history(hpath) if hpath.exists() else []

    # Initialize analytics and plugins
    analytics_manager = analytics.AnalyticsManager()
    plugin_manager = PluginManager()
    plugin_manager.load_all_plugins()
    session_id = analytics_manager.start_session(CURRENT_MODEL or "unknown")

    server_label = active_base_url or "(default)"
    panel_text = (
        f"Ollama Chat REPL — Model: [green]{CURRENT_MODEL}[/green] — "
        f"Session: [cyan]{session_id}[/cyan] — Server: [magenta]{server_label}[/magenta] — "
        f"Plugins: [magenta]{len(plugin_manager.plugins)}[/magenta] — type /help for commands."
    )
    ui_mod.console.print(Panel(panel_text, title="Ollama CLI"))

    # Initialize persona context
    chat_context = {}
    persona_plugin = None
    if "persona_selector" in plugin_manager.plugins:
        persona_plugin = plugin_manager.plugins["persona_selector"]
        # Load persona from config if available
        if config.get("persona", {}).get("current_persona"):
            persona_id = config["persona"]["current_persona"]
            plugin_manager.execute_command("persona", ["set", persona_id], {"chat_context": chat_context})

    try:
        while True:
            try:
                if command_history and input_handler is not None and hasattr(input_handler, "enhanced_input_multiline"):
                    prompt = input_handler.enhanced_input_multiline("You: ", command_history)
                elif input_handler is not None and hasattr(input_handler, "get_multiline_input"):
                    prompt = input_handler.get_multiline_input("You: ")
                else:
                    prompt = input("You: ")
            except EOFError:
                break
            if not prompt.strip():
                continue

            if prompt.startswith("!"):
                command = prompt[1:].strip()
                if not command:
                    ui_mod.console.print("[yellow]Usage: !<shell command>[/yellow]")
                    continue
                analytics_manager.track_command("shell")
                ui_mod.console.print(f"[dim]$ {command}[/dim]")
                shell_output = ui_mod.run_shell_command(command)
                display_text = shell_output.strip() if shell_output else "(no output)"
                ui_mod.console.print(Panel(display_text or "(no output)", title=f"Shell: {command}", expand=True))
                history.append({
                    "role": "shell",
                    "command": command,
                    "output": shell_output,
                    "timestamp": datetime.now().isoformat(),
                })
                continue

            if prompt.startswith("/"):
                parts = shlex.split(prompt)
                cmd = parts[0][1:]
                args = parts[1:]
                analytics_manager.track_command(cmd)

                if cmd in ("list", "models"):
                    models = list_models()
                    if not models:
                        ui_mod.console.print("[yellow]No models found or ollama unavailable.[/yellow]")
                    else:
                        ui_mod.console.print(Panel("\n".join(models), title="Models"))
                    continue
                elif cmd == "load" and args:
                    name = args[0]
                    ok = set_current_model(name)
                    if ok:
                        CURRENT_MODEL = name
                        cfg = load_config()
                        cfg["default_model"] = name
                        save_config(cfg)
                        ui_mod.console.print(f"[green]✓ Model set to:[/green] [white]{name}[/white]")
                        ui_mod.console.print("[dim]💾 Saved as default model[/dim]")
                    else:
                        ui_mod.console.print(f"[red]❌ Failed to set model:[/red] [white]{name}[/white]")
                        ui_mod.console.print("[yellow]💡 Make sure the model is downloaded first with /pull[/yellow]")
                    continue
                elif cmd == "pull" and args:
                    name = args[0]
                    ok = load_model(name)
                    if ok:
                        ui_mod.console.print("[green]✓ Model downloaded:[/green] [white]{name}[/white]")
                    else:
                        ui_mod.console.print("[red]❌ Failed to download model[/red]")
                    continue
                elif cmd in ("delete", "rm", "remove") and args:
                    name = args[0]
                    ok = delete_model(name)
                    ui_mod.console.print("[green]Deleted[/green]" if ok else "[red]Failed to delete model[/red]")
                    continue
                elif cmd == "run":
                    model_arg, prompt_arg = _parse_run_args(args)
                    if model_arg:
                        CURRENT_MODEL = model_arg
                    if not prompt_arg:
                        if not CURRENT_MODEL:
                            ui_mod.console.print("[red]No model selected.[/red]")
                            ui_mod.console.print(
                                "[yellow]Use `/run <model> <prompt>` or "
                                "<model>` to set the default model.[/yellow]"
                            )
                            continue
                        prompt_arg = input(f"Prompt for model '{CURRENT_MODEL}': ")

                    model_to_use = CURRENT_MODEL
                    if not model_to_use:
                        ui_mod.console.print("[red]No model selected to run.[/red]")
                        continue

                    prompt_arg = sanitize_prompt(prompt_arg)
                    try:
                        gen = ow.generate_stream(model_to_use, prompt_arg)
                        buffer = ""
                        panel = Panel(Markdown(buffer), title=f"run {model_to_use} (stream)", expand=True)
                        with Live(panel, console=ui_mod.console, refresh_per_second=6) as live:
                            for chunk in gen:
                                buffer += chunk if isinstance(chunk, str) else str(chunk)
                                panel = Panel(Markdown(buffer), title=f"run {model_to_use} (stream)", expand=True)
                                live.update(panel)
                    except Exception as e:
                        ui_mod.console.print(Panel(f"Error: {e}", title="ollama error"))
                    continue
                elif cmd in ("save", "save_history") and args:
                    history_mod.save_history(history, Path(args[0]))
                    ui_mod.console.print(f"[green]✓ History saved to:[/green] [white]{args[0]}[/white]")
                    continue
                elif cmd == "load_history" and args:
                    history = history_mod.load_history(Path(args[0]))
                    ui_mod.console.print(f"[green]✓ History loaded from:[/green] [white]{args[0]}[/white]")
                    continue
                elif cmd in ("exit", "quit"):
                    last_assistant = None
                    for item in reversed(history):
                        if item.get("role") == "assistant" and item.get("text"):
                            last_assistant = item.get("text")
                            break
                    if last_assistant:
                        ui_mod.console.print(Panel(Markdown(last_assistant), title="Last assistant reply", expand=True))
                    ui_mod.console.print("\nExiting via slash command. Saving history...")
                    history_mod.save_history(history, hpath)
                    return
                elif cmd == "model":
                    models = list_models()
                    selected_model = ui_mod.select_model_menu(models, CURRENT_MODEL)
                    if selected_model and selected_model != CURRENT_MODEL:
                        CURRENT_MODEL = selected_model
                        cfg = load_config()
                        cfg["default_model"] = CURRENT_MODEL
                        save_config(cfg)
                        ui_mod.console.print(f"[green]✓ Model changed to:[/green] [white]{CURRENT_MODEL}[/white]")
                        ui_mod.console.print("[dim]💾 Saved as default model[/dim]")
                    continue
                elif cmd == "settings":
                    current_config = load_config()
                    before_snapshot = copy.deepcopy(current_config)
                    before_base_url = determine_base_url(current_config, base_url)
                    updated_config = settings_menu(current_config)
                    save_config(updated_config)
                    config = updated_config
                    if updated_config != before_snapshot:
                        ui_mod.console.print("[green]💾 Settings saved[/green]")
                    after_base_url = determine_base_url(updated_config, base_url)
                    if after_base_url != before_base_url:
                        ow.init_client(after_base_url)
                        active_base_url = after_base_url
                        ui_mod.console.print(
                            f"[green]🌐 Active server switched to:[/green] "
                            f"[white]{after_base_url}[/white]"
                        )
                    continue
                elif cmd == "search":
                    if not args:
                        ui_mod.console.print("[yellow]Usage: /search <query>[/yellow]")
                        ui_mod.console.print("[dim]Example: /search python[/dim]")
                        continue
                    query = " ".join(args)
                    results = ui_mod.search_history(history, query)
                    ui_mod.display_search_results(results, query)
                    continue
                elif cmd == "clear":
                    ui_mod.clear_screen()
                    ui_mod.console.print("[green]✓ Screen cleared[/green]")
                    continue
                elif cmd == "export":
                    if not args:
                        ui_mod.console.print("[yellow]Usage: /export <filename> [format][/yellow]")
                        ui_mod.console.print("[dim]Formats: markdown (default), json, txt[/dim]")
                        ui_mod.console.print("[dim]Example: /export chat.md markdown[/dim]")
                        continue
                    filename = args[0]
                    format_type = args[1] if len(args) > 1 else "markdown"
                    if ui_mod.export_conversation(history, filename, format_type):
                        ui_mod.console.print(f"[green]✓ Conversation exported to:[/green] [white]{filename}[/white]")
                    else:
                        ui_mod.console.print("[red]❌ Failed to export conversation[/red]")
                    continue
                elif cmd == "stats":
                    ui_mod.display_statistics(history)
                    continue
                elif cmd == "analytics":
                    analytics.display_analytics_dashboard(analytics_manager)
                    continue
                elif cmd == "monitor":
                    analytics.display_real_time_monitoring(analytics_manager)
                    continue
                elif cmd == "report":
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    default_report = f"analytics_report_{timestamp}.json"
                    filename = args[0] if args else default_report
                    if analytics.generate_analytics_report(analytics_manager, filename):
                        ui_mod.console.print(f"[green]✓ Analytics report saved to:[/green] [white]{filename}[/white]")
                    else:
                        ui_mod.console.print("[red]❌ Failed to generate report[/red]")
                    continue
                elif cmd == "plugins":
                    plugin_manager.list_plugins()
                    continue
                elif cmd == "plugins-available":
                    plugin_manager.list_available_plugins()
                    continue
                elif cmd.startswith("plugin-load"):
                    if args:
                        plugin_manager.load_plugin(args[0])
                    else:
                        ui_mod.console.print("[yellow]Usage: /plugin-load <plugin_name>[/yellow]")
                    continue
                elif cmd.startswith("plugin-unload"):
                    if args:
                        plugin_manager.unload_plugin(args[0])
                    else:
                        ui_mod.console.print("[yellow]Usage: /plugin-unload <plugin_name>[/yellow]")
                    continue
                elif cmd.startswith("plugin-info"):
                    if args:
                        plugin_manager.get_plugin_info(args[0])
                    else:
                        ui_mod.console.print("[yellow]Usage: /plugin-info <plugin_name>[/yellow]")
                    continue
                elif cmd in ("help", "h"):
                    help_text = (
                        "/list - list models\n"
                        "/model - interactive model selection menu\n"
                        "!<cmd> - run a shell command and store the output\n"
                        "/settings - configure model parameters (temperature, tokens)\n"
                        "/search <query> - search conversation history\n"
                        "/clear - clear the terminal screen\n"
                        "/export <filename> [format] - export conversation (markdown/json/txt)\n"
                        "/stats - show conversation statistics\n"
                        "/analytics - show detailed analytics dashboard\n"
                        "/monitor - start real-time monitoring\n"
                        "/report [filename] - generate analytics report\n"
                        "/plugins - list loaded plugins\n"
                        "/plugins-available - list available plugins\n"
                        "/plugin-load <name> - load a plugin\n"
                        "/plugin-unload <name> - unload a plugin\n"
                        "/plugin-info <name> - show plugin information\n"
                        "/new_session - session management (create, list, switch, delete)\n"
                    )
                    if persona_plugin:
                        help_text += (
                            "/persona - manage personas (list, set <id>, clear, info <id>, suggest <prompt>)\n"
                            "/suggest <prompt> - suggest personas based on your prompt\n"
                        )
                    help_text += (
                        "/theme <name> - quick theme change (default/dark/light)\n"
                        "/load <name> - set current model (must be downloaded first)\n"
                        "/pull <name> - download new model from ollama library\n"
                        "/delete | /rm | /remove <name> - delete model\n"
                        "/run <model> <prompt...> - run model (CLI fallback)\n"
                        "/save <file> - save history to file\n"
                        "/load_history <file> - load history from file\n"
                        "/exit | /quit - save and exit the REPL\n"
                        "/help - show this help message"
                    )
                    ui_mod.console.print(help_text)
                    continue
                elif cmd.startswith("new_session"):
                    if not args:
                        ui_mod.console.print("\n[bold blue]📁 Session Management[/bold blue]")
                        ui_mod.console.print("1. Create new session")
                        ui_mod.console.print("2. List sessions")
                        ui_mod.console.print("3. Switch session")
                        ui_mod.console.print("4. Delete session")
                        ui_mod.console.print("5. Back to chat")
                        try:
                            choice = input("\nSelect option (1-5): ").strip()
                            if choice == "1":
                                custom_name = input("Enter session name (optional): ").strip() or None
                                persona_value = chat_context.get("persona") if chat_context else None
                                new_session_id = history_mod.create_new_session(
                                    history=history,
                                    custom_name=custom_name,
                                    model_used=CURRENT_MODEL,
                                    persona=persona_value,
                                )
                                ui_mod.console.print(
                                    _format_colored_status(
                                        "[green]✓ Created session:[/green]",
                                        new_session_id,
                                    )
                                )
                            elif choice == "2":
                                sessions = history_mod.list_sessions()
                                if not sessions:
                                    ui_mod.console.print("[yellow]No sessions found[/yellow]")
                                else:
                                    ui_mod.console.print("\n[bold]Available Sessions:[/bold]")
                                    for session in sessions:
                                        ui_mod.console.print(_format_session_entry(session))
                            elif choice == "3":
                                session_id = input("Enter session ID: ").strip()
                                new_history = history_mod.load_session(session_id)
                                if new_history != []:
                                    history.clear()
                                    history.extend(new_history)
                                    ui_mod.console.print(
                                        _format_colored_status(
                                            "[green]✓ Switched to session:[/green]",
                                            session_id,
                                        )
                                    )
                                else:
                                    ui_mod.console.print(
                                        _format_colored_status(
                                            "[red]❌ Session not found:[/red]",
                                            session_id,
                                        )
                                    )
                            elif choice == "4":
                                session_id = input("Enter session ID to delete: ").strip()
                                if history_mod.delete_session(session_id):
                                    ui_mod.console.print(
                                        _format_colored_status(
                                            "[green]✓ Deleted session:[/green]",
                                            session_id,
                                        )
                                    )
                                else:
                                    ui_mod.console.print(
                                        _format_colored_status(
                                            "[red]❌ Session not found:[/red]",
                                            session_id,
                                        )
                                    )
                        except (KeyboardInterrupt, EOFError):
                            ui_mod.console.print("\n[yellow]⚠️  Session management cancelled[/yellow]")
                    else:
                        sub_cmd = args[0]
                        if sub_cmd == "create":
                            custom_name = " ".join(args[1:]) if len(args) > 1 else None
                            persona_value = chat_context.get("persona") if chat_context else None
                            new_session_id = history_mod.create_new_session(
                                history=history,
                                custom_name=custom_name,
                                model_used=CURRENT_MODEL,
                                persona=persona_value,
                            )
                            ui_mod.console.print(
                                _format_colored_status(
                                    "[green]✓ Created session:[/green]",
                                    new_session_id,
                                )
                            )
                        elif sub_cmd == "list":
                            sessions = history_mod.list_sessions()
                            if not sessions:
                                ui_mod.console.print("[yellow]No sessions found[/yellow]")
                            else:
                                ui_mod.console.print("\n[bold]Available Sessions:[/bold]")
                                for session in sessions:
                                    ui_mod.console.print(_format_session_entry(session))
                        elif sub_cmd == "switch":
                            if len(args) > 1:
                                session_id = args[1]
                                new_history = history_mod.load_session(session_id)
                                if new_history != []:
                                    history.clear()
                                    history.extend(new_history)
                                    ui_mod.console.print(
                                        f"[green]✓ Switched to session:[/green] "
                                        f"[white]{session_id}[/white]"
                                    )
                                else:
                                    ui_mod.console.print(f"[red]❌ Session not found:[/red] [white]{session_id}[/white]")
                            else:
                                ui_mod.console.print("[yellow]Usage: /new_session switch <session_id>[/yellow]")
                        elif sub_cmd == "delete":
                            if len(args) > 1:
                                session_id = args[1]
                                if history_mod.delete_session(session_id):
                                    ui_mod.console.print(
                                        f"[green]✓ Deleted session:[/green] "
                                        f"[white]{session_id}[/white]"
                                    )
                                else:
                                    ui_mod.console.print(f"[red]❌ Session not found:[/red] [white]{session_id}[/white]")
                            else:
                                ui_mod.console.print("[yellow]Usage: /new_session delete <session_id>[/yellow]")
                        else:
                            ui_mod.console.print(f"[yellow]Unknown subcommand:[/yellow] {sub_cmd}")
                            ui_mod.console.print("[dim]Available: create, list, switch, delete[/dim]")
                    continue
                elif cmd == "theme":
                    if args:
                        theme_name = args[0].lower()
                        valid_themes = ["default", "dark", "light"]
                        if theme_name in valid_themes:
                            cfg = load_config()
                            cfg["theme"] = theme_name
                            save_config(cfg)
                            ui_mod.console.print(f"[green]✓ Theme changed to:[/green] [white]{theme_name}[/white]")
                        else:
                            ui_mod.console.print(f"[red]❌ Invalid theme:[/red] [white]{theme_name}[/white]")
                            ui_mod.console.print(f"[dim]Available themes:[/dim] [cyan]{', '.join(valid_themes)}[/cyan]")
                    else:
                        cfg = load_config()
                        current_theme = cfg.get("theme", "default")
                        ui_mod.console.print(f"[dim]Current theme:[/dim] [cyan]{current_theme}[/cyan]")
                        ui_mod.console.print("[dim]Available themes:[/dim] [cyan]default, dark, light[/cyan]")
                    continue
                else:
                    context = {
                        "history": history,
                        "current_model": CURRENT_MODEL,
                        "analytics_manager": analytics_manager,
                        "ui_mod": ui_mod,
                        "ollama_wrapper": ow,
                        "chat_context": chat_context,
                        "config": config,
                    }
                    if plugin_manager.execute_command(cmd, args, context):
                        continue
                    ui_mod.console.print(f"[yellow]Unknown slash command:[/yellow] {cmd}")
                    continue

            history.append({"role": "user", "text": prompt})
            if stream:
                parts: List[str] = []
                buffer = ""
                char_count = 0
                model_status = f"🤖 {CURRENT_MODEL or 'Unknown'} (streaming...)"
                ui_mod.console.print(f"[blue]{model_status}[/blue]")

                # Build a single Live with both the panel and progress to avoid flicker
                progress = ui_mod.create_progress_tracker()
                task = progress.add_task("Generating response...", total=100)

                panel = Panel(Markdown(buffer), title="Assistant (streaming)", expand=True)
                renderable = Group(panel, progress)

                with Live(renderable, console=ui_mod.console, refresh_per_second=8) as live:
                    system_message = config.get("system_message", "")
                    if persona_plugin and chat_context.get("persona_prompt"):
                        system_message = chat_context["persona_prompt"]
                    for chunk in ui_mod.get_model_reply_stream(
                        history,
                        max_tokens=max_context_tokens,
                        max_output_chars=max_output_chars,
                        system_message=system_message,
                        model_name=CURRENT_MODEL,
                    ):
                        parts.append(chunk)
                        buffer = "".join(parts)
                        char_count += len(chunk)
                        progress.update(task, advance=min(len(chunk) * 2, 10))
                        panel = Panel(Markdown(buffer), title="Assistant (streaming)", expand=True)
                        live.update(Group(panel, progress))
                    # complete and render final
                    progress.update(task, completed=100)
                    live.update(Group(Panel(Markdown(buffer), title="Assistant", expand=True), progress))

                estimated_tokens = char_count // 4
                ui_mod.display_token_usage(
                    prompt_tokens=len(prompt) // 4,
                    response_tokens=estimated_tokens,
                    max_tokens=max_context_tokens,
                )
                reply = "".join(parts)
                ui_mod.console.print()
                history.append({"role": "assistant", "text": reply})
            else:
                system_message = config.get("system_message", "")
                if persona_plugin and chat_context.get("persona_prompt"):
                    system_message = chat_context["persona_prompt"]
                reply = ui_mod.get_model_reply_sync(
                    history,
                    max_tokens=max_context_tokens,
                    max_output_chars=max_output_chars,
                    system_message=system_message,
                    model_name=CURRENT_MODEL,
                )
                history.append({"role": "assistant", "text": reply})
                ui_mod.render_markdown(reply)

    except KeyboardInterrupt:
        ui_mod.console.print("\nExiting. Saving history...")
        history_mod.save_history(history, hpath)
        analytics_manager.end_session(session_id)
