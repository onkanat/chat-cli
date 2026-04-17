"""System prompt building and management with persona and policy integration."""

from __future__ import annotations

from typing import Any


AGENT_POLICY = """
CRITICAL RULES FOR AUTONOMOUS AGENT:
1. You MUST ONLY use internal slash commands starting with '/'.
2. If the user asks you to list commands, run a tool, or use a command (e.g. "run /help"), YOU MUST output the <call_cmd> tags immediately! Do not type out fake responses.
3. Access real-time command tools. Use EXACTLY the following available commands when you need to act:
{AVAILABLE_COMMANDS}
4. Do NOT output JSON format for tools (e.g. {"tool": "run_command", ...}). JSON tool calls are NOT supported and will fail. ONLY use the XML-style <call_cmd> tags!

The system will run the command, pause your generation, and append the output to the chat history. You must then continue answering based on the output.
"""

BUILTIN_COMMANDS = {
    "/list": "List available Ollama models",
    "/models": "List available Ollama models (alias for /list)",
    "/model": "Interactive model selection menu",
    "/load <name>": "Set current model (must be downloaded first)",
    "/pull <name>": "Download model from Ollama library",
    "/delete <name>": "Delete a downloaded model",
    "/run <model> <prompt>": "Run a model with a prompt (CLI fallback)",
    "/settings": "Configure model parameters (temperature, num_ctx, num_gpu)",
    "/search <query>": "Search conversation history",
    "/clear": "Clear the terminal screen",
    "/export <file> [format]": "Export conversation as markdown/json/txt",
    "/stats": "Show conversation statistics",
    "/analytics": "Show detailed analytics dashboard",
    "/monitor": "Start real-time monitoring",
    "/report [file]": "Generate analytics report",
    "/plugins": "List loaded plugins",
    "/plugins-available": "List available plugins to load",
    "/plugin-load <name>": "Load a plugin dynamically",
    "/plugin-unload <name>": "Unload a plugin",
    "/plugin-info <name>": "Show plugin information",
    "/new_session": "Session management (create, list, switch, delete)",
    "/theme <name>": "Change color theme (default/dark/light)",
    "/save <file>": "Save history to file",
    "/load_history <file>": "Load history from file",
    "/help": "Show help for all commands",
    "/exit": "Save history and exit the REPL",
}


class SystemPromptBuilder:
    """Build and manage system prompts for chat and agent modes."""

    def __init__(self, base_message: str = ""):
        """
        Initialize with optional base system message.

        Args:
            base_message: Base system message (e.g., from config)
        """
        self.base_message = base_message

    def build_user_system_message(self) -> str:
        """
        Build system message for normal user chat mode.

        Returns:
            System message for regular chat
        """
        return self.base_message

    def build_agent_system_message(
        self,
        command_registry: dict[str, str] | None = None,
    ) -> str:
        """
        Build system message for autonomous agent mode.

        Includes policy rules and available commands.

        Args:
            command_registry: Dict of {command: description}

        Returns:
            System message with agent policy and commands
        """
        # Merge built-in commands with provided registry
        all_commands = dict(BUILTIN_COMMANDS)
        if command_registry:
            all_commands.update(command_registry)

        # Format command list
        cmd_list = "\n".join(
            f"- {cmd}: {desc}"
            for cmd, desc in all_commands.items()
        )

        # Build policy with command list
        policy = AGENT_POLICY.replace(
            "{AVAILABLE_COMMANDS}", cmd_list
        )

        # Combine base message + policy
        if self.base_message:
            return self.base_message + "\n\n" + policy
        else:
            return policy


class PersonaAdapter:
    """Integrate persona/character into system prompts."""

    def __init__(self, persona_provider: Any = None):
        """
        Initialize with optional persona provider.

        Args:
            persona_provider: Object with persona_prompt attribute
        """
        self.persona_provider = persona_provider

    def get_persona_prompt(self) -> str | None:
        """
        Get current persona prompt.

        Returns:
            Persona prompt string, or None if no persona set
        """
        if (
            self.persona_provider
            and hasattr(self.persona_provider, "persona_prompt")
        ):
            return self.persona_provider.persona_prompt
        return None

    def apply_persona(
        self,
        system_prompt: str,
        persona_prompt: str | None = None,
    ) -> str:
        """
        Apply persona to system prompt (persona takes precedence).

        Args:
            system_prompt: Base system prompt
            persona_prompt: Optional persona override

        Returns:
            Final system prompt with persona applied
        """
        # Use provided persona or get from provider
        final_persona = persona_prompt or self.get_persona_prompt()

        if final_persona:
            # Persona replaces base message entirely
            return final_persona
        else:
            # No persona, use base message
            return system_prompt


class PolicyManager:
    """Manage agent execution policies and constraints."""

    def __init__(
        self,
        max_iterations: int = 6,
        max_json_retries: int = 2,
        max_repeat_limit: int = 2,
    ):
        """
        Initialize policy manager with guard rails.

        Args:
            max_iterations: Max agent loop iterations
            max_json_retries: Max JSON hallucination retries
            max_repeat_limit: Max repeated command limit
        """
        self.max_iterations = max_iterations
        self.max_json_retries = max_json_retries
        self.max_repeat_limit = max_repeat_limit

    def get_policy_text(self) -> str:
        """Get policy as formatted text."""
        return f"""
AGENT EXECUTION POLICY:
- Max iterations: {self.max_iterations}
- Max JSON retries: {self.max_json_retries}
- Max repeat limit: {self.max_repeat_limit}
"""

    def should_stop_on_iteration(
        self, current_iteration: int
    ) -> bool:
        """Check if iteration limit exceeded."""
        return current_iteration >= self.max_iterations

    def should_stop_on_json_retry(
        self, retry_count: int
    ) -> bool:
        """Check if JSON retry limit exceeded."""
        return retry_count >= self.max_json_retries

    def should_stop_on_repeat(
        self, repeat_count: int
    ) -> bool:
        """Check if repeat limit exceeded."""
        return repeat_count > self.max_repeat_limit


class SystemPromptManager:
    """Unified manager for system prompts with persona and policy."""

    def __init__(
        self,
        base_message: str = "",
        persona_provider: Any = None,
        policy: PolicyManager | None = None,
    ):
        """
        Initialize unified system prompt manager.

        Args:
            base_message: Base system message from config
            persona_provider: Provider with persona_prompt attribute
            policy: PolicyManager instance (creates default if None)
        """
        self.builder = SystemPromptBuilder(base_message)
        self.persona = PersonaAdapter(persona_provider)
        self.policy = policy or PolicyManager()

    def build_system_message(
        self,
        for_agent: bool = False,
        command_registry: dict[str, str] | None = None,
        persona_prompt: str | None = None,
    ) -> str:
        """
        Build final system message.

        Args:
            for_agent: Build for agent mode (includes policy)
            command_registry: Command list {cmd: desc}
            persona_prompt: Optional persona override

        Returns:
            Final system message
        """
        # Build base message
        if for_agent:
            base = self.builder.build_agent_system_message(
                command_registry
            )
        else:
            base = self.builder.build_user_system_message()

        # Apply persona if available
        return self.persona.apply_persona(base, persona_prompt)

    def get_policy(self) -> PolicyManager:
        """Get policy manager."""
        return self.policy
