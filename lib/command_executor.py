"""
Unified command executor for built-in slash commands.

This module centralizes all built-in slash command handlers used by both
the normal REPL path and the autonomous agent path. Each handler is a pure
function that takes a CommandContext and returns a CommandResult.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Load parse_utils directly to avoid lib package initialization
_parse_spec = importlib.util.spec_from_file_location(
    "parse_utils_direct",
    Path(__file__).parent / "parse_utils.py",
)
_parse_module = importlib.util.module_from_spec(_parse_spec)
_parse_spec.loader.exec_module(_parse_module)

parse_run_args = _parse_module.parse_run_args
parse_settings_args = _parse_module.parse_settings_args
parse_search_args = _parse_module.parse_search_args
parse_plugin_args = _parse_module.parse_plugin_args
parse_export_args = _parse_module.parse_export_args


@dataclass(frozen=True)
class CommandContext:
    """Immutable context passed to all command handlers."""
    
    history: list[dict[str, Any]]
    current_model: str | None
    plugin_manager: Any  # PluginManager type
    config: dict[str, Any]
    analytics_manager: Any  # AnalyticsManager type
    ui_mod: Any  # ui module
    ollama_wrapper: Any  # ow module
    chat_context: dict[str, Any]  # persona, etc.


@dataclass
class CommandResult:
    """Result of command execution."""
    
    success: bool
    output: str = ""
    state_changes: dict[str, Any] = None  # e.g., {"current_model": "new_model"}
    error: str | None = None
    requires_reload: bool = False  # e.g., after /settings
    
    def __post_init__(self):
        if self.state_changes is None:
            self.state_changes = {}


# ============================================================================
# BUILT-IN COMMAND HANDLERS
# ============================================================================

def handle_list(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /list or /models command: show available models."""
    from services.models_service import list_models
    
    models = list_models()
    if not models:
        return CommandResult(
            success=True,
            output="No models available.",
        )
    
    output_lines = ["Available Models:"]
    for model_name in models:
        output_lines.append(f"- {model_name}")
    
    return CommandResult(
        success=True,
        output="\n".join(output_lines),
    )


def handle_model(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /model command: interactive model selection menu."""
    from services.models_service import list_models
    
    models = list_models()
    selected_model = ctx.ui_mod.select_model_menu(models, ctx.current_model)
    
    if selected_model and selected_model != ctx.current_model:
        config = copy.deepcopy(ctx.config)
        config["default_model"] = selected_model
        return CommandResult(
            success=True,
            output=f"Model changed to: {selected_model}",
            state_changes={"current_model": selected_model, "config": config},
        )
    
    return CommandResult(
        success=True,
        output="Model selection cancelled.",
    )


def handle_load(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /load command: set current model."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /load <model_name>",
        )
    
    from services.models_service import set_current_model
    
    name = args[0]
    ok = set_current_model(name)
    
    if ok:
        return CommandResult(
            success=True,
            output=f"Model set to: {name}",
            state_changes={"current_model": name},
        )
    else:
        return CommandResult(
            success=False,
            error=f"Failed to set model: {name}. Make sure it's downloaded first with /pull.",
        )


def handle_pull(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /pull command: download model."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /pull <model_name>",
        )
    
    from services.models_service import load_model
    
    name = args[0]
    ok = load_model(name)
    
    if ok:
        return CommandResult(
            success=True,
            output=f"Model downloaded: {name}",
        )
    else:
        return CommandResult(
            success=False,
            error=f"Failed to download model: {name}",
        )


def handle_delete(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /delete, /rm, /remove commands: delete model."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /delete <model_name>",
        )
    
    from services.models_service import delete_model
    
    name = args[0]
    ok = delete_model(name)
    
    if ok:
        return CommandResult(
            success=True,
            output=f"Deleted model: {name}",
        )
    else:
        return CommandResult(
            success=False,
            error=f"Failed to delete model: {name}",
        )


def handle_save(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /save command: save history to file."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /save <filename>",
        )
    
    import lib.history as history_mod
    
    filename = args[0]
    try:
        history_mod.save_history(ctx.history, Path(filename))
        return CommandResult(
            success=True,
            output=f"History saved to: {filename}",
        )
    except Exception as e:
        return CommandResult(
            success=False,
            error=f"Failed to save history: {e}",
        )


def handle_load_history(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /load_history command: load history from file."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /load_history <filename>",
        )
    
    import lib.history as history_mod
    
    filename = args[0]
    try:
        loaded_history = history_mod.load_history(Path(filename))
        # Clear current history and populate with loaded
        ctx.history.clear()
        ctx.history.extend(loaded_history)
        return CommandResult(
            success=True,
            output=f"History loaded from: {filename}",
            state_changes={"history_reloaded": True},
        )
    except Exception as e:
        return CommandResult(
            success=False,
            error=f"Failed to load history: {e}",
        )


def handle_clear(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /clear command: clear terminal screen."""
    ctx.ui_mod.clear_screen()
    return CommandResult(
        success=True,
        output="Screen cleared",
    )


def handle_search(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /search command: search conversation history."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /search <query>",
        )
    
    query = " ".join(args)
    results = ctx.ui_mod.search_history(ctx.history, query)
    ctx.ui_mod.display_search_results(results, query)
    
    return CommandResult(
        success=True,
        output=f"Search results for: {query}",
    )


def handle_export(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /export command: export conversation."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /export <filename> [format]\nFormats: markdown (default), json, txt",
        )
    
    filename = args[0]
    format_type = args[1] if len(args) > 1 else "markdown"
    
    if ctx.ui_mod.export_conversation(ctx.history, filename, format_type):
        return CommandResult(
            success=True,
            output=f"Conversation exported to: {filename}",
        )
    else:
        return CommandResult(
            success=False,
            error="Failed to export conversation",
        )


def handle_stats(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /stats command: display conversation statistics."""
    ctx.ui_mod.display_statistics(ctx.history)
    return CommandResult(
        success=True,
        output="Statistics displayed",
    )


def handle_analytics(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /analytics command: display analytics dashboard."""
    import analytics
    
    analytics.display_analytics_dashboard(ctx.analytics_manager)
    return CommandResult(
        success=True,
        output="Analytics dashboard displayed",
    )


def handle_monitor(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /monitor command: start real-time monitoring."""
    import analytics
    
    analytics.display_real_time_monitoring(ctx.analytics_manager)
    return CommandResult(
        success=True,
        output="Real-time monitoring started",
    )


def handle_report(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /report command: generate analytics report."""
    import analytics
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_report = f"analytics_report_{timestamp}.json"
    filename = args[0] if args else default_report
    
    if analytics.generate_analytics_report(ctx.analytics_manager, filename):
        return CommandResult(
            success=True,
            output=f"Analytics report saved to: {filename}",
        )
    else:
        return CommandResult(
            success=False,
            error="Failed to generate report",
        )


def handle_plugins(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /plugins command: list loaded plugins."""
    loaded_plugins = sorted(ctx.plugin_manager.plugins.keys())
    
    if not loaded_plugins:
        return CommandResult(
            success=True,
            output="No plugins loaded.",
        )
    
    output_lines = ["Loaded plugins:"]
    for plugin_name in loaded_plugins:
        output_lines.append(f"- {plugin_name}")
    
    return CommandResult(
        success=True,
        output="\n".join(output_lines),
    )


def handle_plugins_available(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /plugins-available command: list available plugins."""
    available_plugins = sorted(ctx.plugin_manager.discover_plugins())
    
    if not available_plugins:
        return CommandResult(
            success=True,
            output="No plugins available.",
        )
    
    output_lines = ["Available plugins:"]
    for plugin_name in available_plugins:
        output_lines.append(f"- {plugin_name}")
    
    return CommandResult(
        success=True,
        output="\n".join(output_lines),
    )


def handle_plugin_info(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /plugin-info command: show plugin information."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /plugin-info <plugin_name>",
        )
    
    plugin_name = args[0]
    plugin = ctx.plugin_manager.plugins.get(plugin_name)
    
    if plugin is None:
        return CommandResult(
            success=False,
            error=f"Plugin '{plugin_name}' is not loaded.",
        )
    
    info = plugin.get_info()
    output_lines = [
        f"Plugin: {info['name']}",
        f"Version: {info['version']}",
        f"Author: {info['author']}",
        f"Description: {info['description']}",
        "Commands:",
    ]
    for cmd_name in info.get("commands", []):
        output_lines.append(f"- /{cmd_name}")
    
    return CommandResult(
        success=True,
        output="\n".join(output_lines),
    )


def handle_plugin_load(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /plugin-load command: load a plugin."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /plugin-load <plugin_name>",
        )
    
    plugin_name = args[0]
    try:
        ctx.plugin_manager.load_plugin(plugin_name)
        return CommandResult(
            success=True,
            output=f"Plugin loaded: {plugin_name}",
        )
    except Exception as e:
        return CommandResult(
            success=False,
            error=f"Failed to load plugin: {e}",
        )


def handle_plugin_unload(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /plugin-unload command: unload a plugin."""
    if not args:
        return CommandResult(
            success=False,
            error="Usage: /plugin-unload <plugin_name>",
        )
    
    plugin_name = args[0]
    try:
        ctx.plugin_manager.unload_plugin(plugin_name)
        return CommandResult(
            success=True,
            output=f"Plugin unloaded: {plugin_name}",
        )
    except Exception as e:
        return CommandResult(
            success=False,
            error=f"Failed to unload plugin: {e}",
        )


def handle_settings(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /settings command: configure model parameters."""
    from services.settings_service import determine_base_url, load_config, save_config
    from ui.settings_menus import settings_menu
    
    current_config = copy.deepcopy(ctx.config)
    before_snapshot = copy.deepcopy(current_config)
    before_base_url = determine_base_url(current_config, None)
    
    updated_config = settings_menu(current_config)
    save_config(updated_config)
    
    after_base_url = determine_base_url(updated_config, None)
    output_msg = "Settings saved"
    
    requires_reload = False
    if after_base_url != before_base_url:
        output_msg += f" (server switched to {after_base_url})"
        requires_reload = True
    
    return CommandResult(
        success=True,
        output=output_msg,
        state_changes={"config": updated_config},
        requires_reload=requires_reload,
    )


def handle_theme(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /theme command: change color theme."""
    from services.settings_service import load_config, save_config
    
    if args:
        theme_name = args[0].lower()
        valid_themes = ["default", "dark", "light"]
        if theme_name in valid_themes:
            cfg = copy.deepcopy(ctx.config)
            cfg["theme"] = theme_name
            save_config(cfg)
            return CommandResult(
                success=True,
                output=f"Theme changed to: {theme_name}",
                state_changes={"config": cfg},
            )
        else:
            return CommandResult(
                success=False,
                error=f"Invalid theme: {theme_name}. Available: {', '.join(valid_themes)}",
            )
    else:
        current_theme = ctx.config.get("theme", "default")
        output = f"Current theme: {current_theme}\nAvailable: default, dark, light"
        return CommandResult(
            success=True,
            output=output,
        )


def handle_help(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /help command: show help for all commands."""
    help_lines = [
        "Available Commands:",
        "/list, /models - List available Ollama models",
        "/model - Interactive model selection",
        "/load <name> - Set current model",
        "/pull <name> - Download model",
        "/delete <name> - Delete model",
        "/run <model> <prompt> - Run model with prompt",
        "/settings - Configure parameters",
        "/search <query> - Search history",
        "/clear - Clear screen",
        "/export <file> [format] - Export conversation",
        "/stats - Show statistics",
        "/analytics - Analytics dashboard",
        "/monitor - Real-time monitoring",
        "/report [file] - Generate report",
        "/plugins - List loaded plugins",
        "/plugins-available - List available plugins",
        "/plugin-load <name> - Load plugin",
        "/plugin-unload <name> - Unload plugin",
        "/plugin-info <name> - Show plugin info",
        "/theme <name> - Change theme",
        "/save <file> - Save history",
        "/load_history <file> - Load history",
        "/new_session - Session management",
        "/help - Show this help",
        "/exit - Exit and save",
    ]
    
    return CommandResult(
        success=True,
        output="\n".join(help_lines),
    )


def handle_run(args: list[str], ctx: CommandContext) -> CommandResult:
    """Handle /run command: run a model with a prompt.

    Note: This is limited in agent context. Agent should use /load + chat.
    """
    return CommandResult(
        success=False,
        error=(
            "The /run command is not available for agents. "
            "Use /load to set a model and continue chatting."
        ),
    )


# Handler registry mapping command names to handler functions
COMMAND_HANDLERS: dict[str, callable] = {
    "list": handle_list,
    "models": handle_list,  # Alias
    "model": handle_model,
    "load": handle_load,
    "pull": handle_pull,
    "delete": handle_delete,
    "rm": handle_delete,  # Alias
    "remove": handle_delete,  # Alias
    "save": handle_save,
    "save_history": handle_save,  # Alias
    "load_history": handle_load_history,
    "clear": handle_clear,
    "search": handle_search,
    "export": handle_export,
    "stats": handle_stats,
    "analytics": handle_analytics,
    "monitor": handle_monitor,
    "report": handle_report,
    "plugins": handle_plugins,
    "plugins-available": handle_plugins_available,
    "plugin-info": handle_plugin_info,
    "plugin-load": handle_plugin_load,
    "plugin-unload": handle_plugin_unload,
    "settings": handle_settings,
    "theme": handle_theme,
    "help": handle_help,
    "h": handle_help,  # Alias
}


def execute_command(
    command: str,
    args: list[str],
    ctx: CommandContext,
) -> CommandResult:
    """
    Execute a built-in command.
    
    Args:
        command: Command name (without leading slash)
        args: Command arguments
        ctx: Execution context with all dependencies
    
    Returns:
        CommandResult with success status, output, and any state changes
    """
    # Remove leading slash if present
    if command.startswith("/"):
        command = command[1:]
    
    handler = COMMAND_HANDLERS.get(command)
    if handler:
        return handler(args, ctx)
    
    return CommandResult(
        success=False,
        error=f"Unknown command: {command}",
    )
