"""Plugin command executor with isolation and error handling."""

from __future__ import annotations

from typing import Any


class PluginCommandExecutor:
    """Execute plugin commands with error isolation and context wrapping."""

    def __init__(
        self,
        plugin_manager: Any,
    ):
        """
        Initialize plugin executor.

        Args:
            plugin_manager: PluginManager instance
        """
        self.plugin_manager = plugin_manager

    def execute(
        self,
        command: str,
        args: list[str],
        context: dict[str, Any],
    ) -> bool:
        """
        Execute a plugin command with error isolation.

        Args:
            command: Command name (without /)
            args: Command arguments
            context: Execution context dict

        Returns:
            True if command executed, False if unknown
        """
        try:
            return self._call_plugin(command, args, context)
        except Exception as e:
            # Log error but don't crash REPL
            self._handle_plugin_error(command, e, context)
            return False

    def _call_plugin(
        self,
        command: str,
        args: list[str],
        context: dict[str, Any],
    ) -> bool:
        """Call plugin manager safely."""
        return self.plugin_manager.execute_command(
            command, args, context
        )

    def _handle_plugin_error(
        self,
        command: str,
        error: Exception,
        context: dict[str, Any],
    ) -> None:
        """Handle errors from plugin execution."""
        # Get UI module from context if available
        ui_mod = context.get("ui_mod")
        if ui_mod:
            ui_mod.console.print(
                f"[red]Plugin error (/{command}): {error}[/red]"
            )

    def execute_startup_plugin(
        self,
        command: str,
        args: list[str],
        context: dict[str, Any],
    ) -> None:
        """
        Execute plugin at startup (persona loading).

        Non-critical - failures don't block startup.

        Args:
            command: Command name
            args: Command arguments
            context: Execution context
        """
        try:
            self._call_plugin(command, args, context)
        except Exception:
            # Silently ignore startup plugin failures
            pass

    def has_plugin(self, command: str) -> bool:
        """Check if plugin command exists."""
        return (
            hasattr(self.plugin_manager, "plugins")
            and command in self.plugin_manager.plugins
        )

    def get_plugin_commands(self) -> dict[str, str]:
        """
        Get all plugin commands and descriptions.

        Returns:
            Dict of {command: description}
        """
        if hasattr(self.plugin_manager, "get_all_commands"):
            return self.plugin_manager.get_all_commands()
        return {}


class PluginExecutionContext:
    """Builder for plugin execution context."""

    def __init__(self):
        """Initialize context builder."""
        self._context: dict[str, Any] = {}

    def with_history(self, history: list[dict]) -> PluginExecutionContext:
        """Add history."""
        self._context["history"] = history
        return self

    def with_model(self, model: str | None) -> PluginExecutionContext:
        """Add current model."""
        self._context["current_model"] = model
        return self

    def with_analytics(self, mgr: Any) -> PluginExecutionContext:
        """Add analytics manager."""
        self._context["analytics_manager"] = mgr
        return self

    def with_ui(self, ui: Any) -> PluginExecutionContext:
        """Add UI module."""
        self._context["ui_mod"] = ui
        return self

    def with_ollama(self, ow: Any) -> PluginExecutionContext:
        """Add Ollama wrapper."""
        self._context["ollama_wrapper"] = ow
        return self

    def with_chat_context(self, ctx: dict) -> PluginExecutionContext:
        """Add chat context (persona, etc.)."""
        self._context["chat_context"] = ctx
        return self

    def with_config(self, config: dict) -> PluginExecutionContext:
        """Add config dict."""
        self._context["config"] = config
        return self

    def build(self) -> dict[str, Any]:
        """Build the context dict."""
        return dict(self._context)
