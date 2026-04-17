"""Agent orchestration logic for autonomous command execution."""

from __future__ import annotations

import io
import sys
import shlex
from typing import Any

from lib.command_executor import execute_command, CommandContext
from lib.agent_utils import detect_json_tool_name, parse_agent_command


class AgentOrchestrator:
    """Manages autonomous agent loop execution and command handling."""

    # Guard rails to prevent infinite loops
    MAX_ITERATIONS = 6
    MAX_JSON_RETRIES = 2
    MAX_REPEAT_LIMIT = 2
    BLOCKED_COMMANDS = {"new_session", "run", "settings"}

    def __init__(
        self,
        history: list[dict[str, Any]],
        current_model: str | None,
        config: dict[str, Any],
        plugin_manager: Any,
        analytics_manager: Any,
        ui_mod: Any,
        ollama_wrapper: Any,
        chat_context: dict[str, Any],
        max_context_tokens: int = 4000,
        max_output_chars: int = 2000,
        stream: bool = True,
    ):
        """Initialize orchestrator with execution context."""
        self.history = history
        self.current_model = current_model
        self.config = config
        self.plugin_manager = plugin_manager
        self.analytics_manager = analytics_manager
        self.ui_mod = ui_mod
        self.ollama_wrapper = ollama_wrapper
        self.chat_context = chat_context
        self.max_context_tokens = max_context_tokens
        self.max_output_chars = max_output_chars
        self.stream = stream

        # Iteration tracking
        self.iteration_count = 0
        self.json_retry_count = 0
        self.last_command: str | None = None
        self.repeated_command_count = 0

    def run(self, system_message: str) -> bool:
        """
        Execute agent loop.

        Args:
            system_message: System message for the model

        Returns:
            True if completed successfully
        """
        agent_running = True
        self.iteration_count = 0
        self.json_retry_count = 0
        self.last_command = None
        self.repeated_command_count = 0

        while agent_running:
            if self.iteration_count >= self.MAX_ITERATIONS:
                warn_msg = (
                    "Agent stopped after reaching the maximum number "
                    "of autonomous steps."
                )
                self.ui_mod.console.print(
                    f"[yellow]{warn_msg}[/yellow]"
                )
                self.history.append({"role": "system", "text": warn_msg})
                break

            self.iteration_count += 1
            agent_running = False

            # Get reply from model
            reply = self._get_reply(system_message)

            # Parse and process reply
            agent_running = self._process_reply(reply, agent_running)

        return True

    def run_with_initial_reply(
        self,
        initial_reply: str,
        system_message: str,
    ) -> bool:
        """
        Execute agent loop with an initial reply already generated.

        Args:
            initial_reply: First model reply (already generated)
            system_message: System message for the model

        Returns:
            True if completed successfully
        """
        agent_running = True
        self.iteration_count = 0
        self.json_retry_count = 0
        self.last_command = None
        self.repeated_command_count = 0

        reply = initial_reply

        while agent_running:
            if self.iteration_count >= self.MAX_ITERATIONS:
                warn_msg = (
                    "Agent stopped after reaching the maximum number "
                    "of autonomous steps."
                )
                self.ui_mod.console.print(
                    f"[yellow]{warn_msg}[/yellow]"
                )
                self.history.append({"role": "system", "text": warn_msg})
                break

            self.iteration_count += 1
            agent_running = False

            # Process current reply
            agent_running = self._process_reply(reply, agent_running)

            # Get next reply if needed
            if agent_running:
                reply = self._get_reply(system_message)

        return True

    def _get_reply(self, system_message: str) -> str:
        """Get next reply from model."""
        if self.stream:
            return self._get_reply_stream(system_message)
        else:
            return self._get_reply_sync(system_message)

    def _get_reply_stream(self, system_message: str) -> str:
        """Get streaming reply from model."""
        parts = []
        buffer = ""
        char_count = 0

        route_label = self.ui_mod.get_active_route_label(
            self.history,
            self.current_model,
        )
        model_status = (
            f"🤖 {self.current_model or 'Unknown'} ({route_label})"
        )
        self.ui_mod.console.print(f"[blue]{model_status}[/blue]")

        # Build progress tracker
        from rich.panel import Panel
        from rich.markdown import Markdown
        from rich.live import Live
        from rich.console import Group

        progress = self.ui_mod.create_progress_tracker()
        task = progress.add_task("Generating response...", total=100)

        import time

        last_update_time = 0
        update_frequency = 0.1
        chunk_counter = 0

        panel = Panel(
            Markdown(buffer),
            title="Assistant (streaming)",
            expand=True,
        )
        renderable = Group(panel, progress)

        with Live(
            renderable,
            console=self.ui_mod.console,
            refresh_per_second=8,
        ) as live:
            for chunk in self.ui_mod.get_model_reply_stream(
                self.history,
                max_tokens=self.max_context_tokens,
                max_output_chars=self.max_output_chars,
                system_message=system_message,
                model_name=self.current_model,
            ):
                parts.append(chunk)
                buffer = "".join(parts)
                char_count += len(chunk)
                chunk_counter += 1

                progress.update(
                    task, advance=min(len(chunk) * 2, 8)
                )

                current_time = time.time()
                if chunk_counter >= 15 or (
                    current_time - last_update_time
                ) >= update_frequency:
                    try:
                        md_content = Markdown(buffer)
                        panel = Panel(
                            md_content,
                            title="Assistant (streaming)",
                            expand=True,
                        )
                        live.update(Group(panel, progress))
                        last_update_time = current_time
                        chunk_counter = 0
                    except Exception:
                        pass

                if "</call_cmd>" in buffer:
                    break

            progress.update(task, completed=100)
            live.update(
                Group(
                    Panel(
                        Markdown(buffer),
                        title="Assistant",
                        expand=True,
                    ),
                    progress,
                )
            )

        estimated_tokens = char_count // 4
        self.ui_mod.display_token_usage(
            prompt_tokens=0,
            response_tokens=estimated_tokens,
            max_tokens=self.max_context_tokens,
        )
        self.ui_mod.console.print()

        return "".join(parts)

    def _get_reply_sync(self, system_message: str) -> str:
        """Get synchronous reply from model."""
        return self.ui_mod.get_model_reply_sync(
            self.history,
            max_tokens=self.max_context_tokens,
            max_output_chars=self.max_output_chars,
            system_message=system_message,
            model_name=self.current_model,
        )

    def _process_reply(self, reply: str, agent_running: bool) -> bool:
        """
        Process model reply for commands or hallucinations.

        Returns:
            True if agent should continue running
        """
        parsed = parse_agent_command(reply)

        if parsed.invalid_matches:
            self.ui_mod.console.print(
                f"[dim yellow]⚠️  Agent ignored "
                f"{len(parsed.invalid_matches)} non-command "
                f"<call_cmd> block(s) in reply.[/dim yellow]"
            )

        if parsed.command:
            return self._execute_agent_command(
                parsed.command, reply, parsed.full_match
            )
        else:
            return self._handle_no_command(reply)

    def _execute_agent_command(
        self,
        cmd_str: str,
        reply: str,
        full_match: str,
    ) -> bool:
        """
        Execute a command parsed from agent reply.

        Returns:
            True if agent should continue
        """
        # Check for repeat
        if cmd_str == self.last_command:
            self.repeated_command_count += 1
        else:
            self.repeated_command_count = 1
            self.last_command = cmd_str

        if self.repeated_command_count > self.MAX_REPEAT_LIMIT:
            warn_msg = (
                "Agent stopped because it repeated the same "
                f"command too many times: {cmd_str}"
            )
            self.ui_mod.console.print(f"[yellow]{warn_msg}[/yellow]")
            self.history.append({"role": "system", "text": warn_msg})
            return False

        self.json_retry_count = 0

        self.ui_mod.console.print(
            f"\n[bold magenta]🛠️ Agent Executing:[/bold magenta] "
            f"[cyan]{cmd_str}[/cyan]"
        )

        # Remove command from reply and add to history
        clean_reply = reply.replace(full_match, "").strip()
        if clean_reply:
            self.history.append(
                {
                    "role": "assistant",
                    "text": clean_reply + f"\n[Agent Executed: {cmd_str}]",
                }
            )
        else:
            self.history.append(
                {
                    "role": "assistant",
                    "text": f"[Agent Executed: {cmd_str}]",
                }
            )

        # Capture execution output
        cap_buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = cap_buffer

        try:
            if cmd_str.startswith("!"):
                print(
                    "Error: Shell commands (!) are strictly "
                    "forbidden for the Agent. Please use only "
                    "/ slash commands."
                )
            else:
                # Parse command
                try:
                    c_parts = shlex.split(cmd_str)
                    c_cmd = c_parts[0]
                    c_args = c_parts[1:]
                except Exception:
                    c_cmd = cmd_str.split()[0]
                    c_args = cmd_str.split()[1:]

                if c_cmd.startswith("/"):
                    c_cmd = c_cmd[1:]

                # Try plugin first
                legacy_context = {
                    "history": self.history,
                    "current_model": self.current_model,
                    "analytics_manager": self.analytics_manager,
                    "ui_mod": self.ui_mod,
                    "ollama_wrapper": self.ollama_wrapper,
                    "chat_context": self.chat_context,
                    "config": self.config,
                }

                if not self.plugin_manager.execute_command(
                    c_cmd, c_args, legacy_context
                ):
                    # Try built-in executor
                    cmd_ctx = CommandContext(
                        history=self.history,
                        current_model=self.current_model,
                        plugin_manager=self.plugin_manager,
                        config=self.config,
                        analytics_manager=self.analytics_manager,
                        ui_mod=self.ui_mod,
                        ollama_wrapper=self.ollama_wrapper,
                        chat_context=self.chat_context,
                    )
                    result = execute_command(c_cmd, c_args, cmd_ctx)
                    if result.success:
                        print(result.output)
                    else:
                        print(f"Error: {result.error}")
                        if (
                            result.error
                            == "Unknown command: unknown"
                        ):
                            print(
                                "Terminal tools like python, bash, sh "
                                "are FORBIDDEN! Only use loaded plugin "
                                "commands or safe built-in commands."
                            )
        except Exception as e:
            print(f"Execution failed: {e}")
        finally:
            sys.stdout = old_stdout

        ext_out = cap_buffer.getvalue().strip()
        if not ext_out:
            ext_out = (
                "Command executed successfully "
                "(no text output returned to stdout)."
            )

        self.ui_mod.console.print(
            f"[dim]{ext_out[:200]}"
            f"{'...' if len(ext_out) > 200 else ''}[/dim]\n"
        )
        self.history.append(
            {"role": "system", "text": f"Agent Command Output:\n{ext_out}"}
        )

        return True

    def _handle_no_command(self, reply: str) -> bool:
        """
        Handle reply with no command (check for JSON hallucinations).

        Returns:
            True if agent should continue
        """
        # Check for JSON tool hallucinations
        tool_name = detect_json_tool_name(reply)
        if tool_name:
            self.json_retry_count += 1
            self.history.append(
                {"role": "assistant", "text": reply}
            )
            self.ui_mod.console.print(
                f"\n[bold red]⚠️ Agent hallucinated JSON "
                f"Tool:[/bold red] [white]{tool_name}[/white]"
            )
            err_msg = (
                "System Error: JSON tools are NOT supported here. "
                "Use `<call_cmd>/command_name args</call_cmd>` "
                "to execute internal commands. Do NOT use JSON."
            )
            self.history.append({"role": "system", "text": err_msg})
            self.ui_mod.console.print(f"[dim]{err_msg}[/dim]\n")

            if self.json_retry_count >= self.MAX_AGENT_JSON_RETRIES:
                warn_msg = (
                    "Agent stopped after repeated JSON tool "
                    "hallucinations."
                )
                self.ui_mod.console.print(
                    f"[yellow]{warn_msg}[/yellow]"
                )
                self.history.append(
                    {"role": "system", "text": warn_msg}
                )
                return False
            else:
                return True
        else:
            self.json_retry_count = 0
            if not self.stream:
                self.ui_mod.render_markdown(reply)
            self.history.append(
                {"role": "assistant", "text": reply}
            )
            return False
