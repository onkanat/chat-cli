# Development Guidelines for Ollama Chat CLI

## Quick Start (Build / Test / Run)

### macOS-first (önerilen)

- `python3 -m venv .chat`
- `source .chat/bin/activate`
- `pip install -r requirements.txt`
- `python3 -m pytest tests/ -q`
- `python3 main.py chat`

### Alternative shortcuts

- Run single test: `python3 -m pytest tests/test_history_processing.py::test_function_name`
- List models: `python3 main.py list-models-cmd`

> EN: Use a virtual environment on externally-managed Python systems.
> TR: Dışarıdan yönetilen Python kurulumlarında mutlaka sanal ortam kullanın.

## Architecture Snapshot

- `main.py`: Typer CLI entry and command registration
- `commands/`: thin command orchestration
- `services/`: business logic (models/settings/server profiles)
- `lib/`: core utilities (history, config cache, wrappers, session manager)
- `ui/`: Rich terminal rendering/input/stream display
- `plugins/`: dynamic plugin loading and command registry
- `repl/`: main interaction loop (plugins + analytics + history integration)

Deep dives (link, don’t embed):

- `docs/ARCHITECTURE.md`
- `docs/CONTEXT_OPTIMIZATION_ANALYSIS.md`
- `docs/FULL_README.md`

## Code Style and Conventions

- Use `from __future__ import annotations` at the top of Python files.
- Keep imports grouped: stdlib → third-party → local modules.
- Use explicit type hints (`str | None` style).
- Naming:
	- functions/variables: `snake_case`
	- constants: `UPPER_SNAKE_CASE`
	- private names: leading `_`
- Prefer `pathlib.Path` and UTF-8 for file I/O.
- For external dependencies (ollama/file I/O/subprocess), prefer graceful fallback behavior over user-facing crashes.

## Testing Conventions

- Primary: `python3 -m pytest tests/ -q`
- Mock external dependencies where possible.
- Keep compatibility with tests importing re-exported functions from `main.py`.
- If tests depend on config caching behavior, clear module-level cache around tests (see `tests/test_model_profiles.py`).

## Dependencies and Gotchas

- Core: `ollama>=0.6.1`, `typer[all]`, `rich`, `markdown`, `PyYAML>=6.0`
- Optional: `tiktoken` (fallback token estimation exists)
- Plugin config source: `plugin_config.json`

### External dependency: `system_prompts`

`plugins/persona_selector.py` can read personas from external `../system_prompts` via:

- `plugin_config.json` → `plugin_settings.persona_selector.system_prompts_path`

If path is missing/invalid, plugin falls back to:

- `plugins/system_prompts/personas.json` (legacy default personas)

If persona metadata/tags are missing, verify:

- `PyYAML` installed
- `system_prompts/scripts/skills_to_json.py` was run
- `/persona reload` executed in chat-cli

## Documentation Map

- `README.md`: quick-start and core commands
- `docs/FULL_README.md`: comprehensive feature reference
- `docs/ARCHITECTURE.md`: architecture and component boundaries
- `docs/CONTEXT_OPTIMIZATION_ANALYSIS.md`: context/history strategy
- `docs/FINETUNING_8GB.md`: low-memory fine-tuning guide
