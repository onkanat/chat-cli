# Copilot Instructions

Read `AGENTS.md` first. In this repository it is the primary workspace-instructions file; `docs/AGENTS.md` is only a pointer to it.

## Commands

```bash
# Setup / run
python3 -m venv .chat
source .chat/bin/activate
pip install -r requirements.txt
python3 main.py chat
python3 main.py list-models-cmd

# Tests
python3 -m pytest tests/ -q
python3 -m pytest tests/test_history_processing.py::test_function_name -q

# Lint / type-check (configured in pyproject.toml)
ruff check .
mypy .
```

## High-level architecture

- `main.py` is the Typer entrypoint and keeps backward-compatible re-exports that tests still import.
- `commands/` is intentionally thin. `commands/chat.py` delegates straight into `repl/loop.py`, which owns the interactive session lifecycle.
- `repl/loop.py` is the main control flow: load config, initialize Ollama, load plugins and analytics, handle `/...` slash commands and `!...` shell commands, append chat history, and dispatch normal turns through the agent/orchestration path.
- Normal chat turns flow through `SystemPromptManager` + `AgentOrchestrator`. Built-in slash commands are centralized in `lib/command_executor.py`; plugin commands are loaded dynamically through `lib/plugin_registry.py`.
- `services/` is a thin seam over lower-level modules such as `lib.ollama_wrapper` and `lib.config`. Keep business logic out of CLI entrypoints when possible.
- `lib/history.py`, `lib/message_builder.py`, `lib/shell_output.py`, and `lib/config.py` work together to turn full archived history into model-ready context using model-size profiles and shell-output summarization.
- `ui/` contains the Rich-based terminal experience; `plugins/` contains dynamically discovered slash-command plugins; `histories/` stores session files.

## Key conventions

- Preserve the thin-layer split: CLI/bootstrap in `main.py` and `commands/`, reusable logic in `services/` and `lib/`.
- Do not casually remove compatibility exports or underscore aliases from `main.py` or `lib/history.py`. Tests import `summarize_shell_output`, `_estimate_tokens`, `_trim_history_for_tokens`, `build_model_messages_from_history`, and rely on `_config_cache` access via `lib.history`.
- Keep the dual-history model intact: stored history keeps full events, including full shell output, while model context is built separately and may summarize or omit shell output based on model profile. Do not replace archived history with already-summarized text.
- Runtime config is split between root-level `config.json` and `plugin_config.json`. Many modules read these via `Path("config.json")` / `Path("plugin_config.json")`, so cwd-relative behavior matters in tests and scripts.
- Plugins are discovered from `plugins/*.py`, must subclass `lib.plugins.PluginBase`, and register slash commands through `get_commands()`. Plugin execution receives mutable `history`, `config`, and `chat_context`.
- Persona state lives in `chat_context` and is also persisted into `config.json`. Session creation/switching paths clear `chat_context`; preserve that behavior when changing session or persona flows.
- `plugins/persona_selector.py` can load personas from an external `system_prompts` checkout via `plugin_config.json`, but falls back to `plugins/system_prompts/personas.json`.
- Follow the existing error-handling style around external dependencies: prefer graceful degradation for Ollama, plugin loading, readline/input helpers, and file I/O instead of crashing the REPL.

## Related docs

- `AGENTS.md`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CONTEXT_OPTIMIZATION_ANALYSIS.md`
- `docs/FULL_README.md`
