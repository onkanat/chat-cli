# Development Guidelines for Ollama Chat CLI

## Build/Lint/Test Commands
- **Install dependencies**: `pip install -r requirements.txt` (use venv for externally-managed environments)
- **Run tests**: `python3 -m pytest tests/ -q`
- **Run single test**: `python3 -m pytest tests/test_history_processing.py::test_function_name`
- **Run application**: `python3 main.py chat`
- **List models**: `python3 main.py list-models-cmd`

## Code Style Guidelines

### Imports & Structure
- Use `from __future__ import annotations` at top of all Python files
- Group imports: standard library, third-party, local modules (in that order)
- Use type hints consistently (Python 3.8+ style with `str | None` syntax)
- Modular architecture with clear separation of concerns

### Naming Conventions
- Functions: `snake_case` with descriptive names
- Variables: `snake_case`, avoid single letters except loop counters
- Constants: `UPPER_SNAKE_CASE`
- Private functions: prefix with `_` underscore
- Module-level variables: snake_case with leading underscore for private state

### Error Handling
- Use try/except blocks for external dependencies (ollama clients, file I/O, subprocess)
- Return fallback values (None, empty list, False) rather than raising for user-facing operations
- Graceful degradation when ollama clients unavailable
- Silent failure for non-critical operations (config writes, etc.)

### Code Organization
- **main.py**: Typer CLI bootstrap and command registration (225 lines)
- **commands/**: CLI command handlers (thin orchestration layer)
- **services/**: Business logic layer (server profiles, settings, models)
- **lib/**: Core utilities (history, config, ollama_wrapper, session_manager)
- **ui/**: Terminal UI components (console, inputs, renderers, stream_display)
- **plugins/**: Plugin system with registry and example plugins
- **analytics/**: Usage tracking and reporting

### Testing
- Test history processing functions thoroughly (token estimation, truncation)
- Mock external dependencies in tests (ollama clients, file system)
- Focus on core logic: shell output summarization, context management
- Tests import functions from main.py for backward compatibility
- Use pytest with `-q` flag for concise output

### Dependencies
- **Core**: `ollama>=0.6.1`, `typer[all]`, `rich`, `markdown`
- **Optional**: `tiktoken` for better token estimation (with fallback)
- **File operations**: Use `pathlib.Path` with UTF-8 encoding
- **Configuration**: JSON-based with smart caching and auto-reload

### Key Patterns
- **Stream responses** when possible, fall back to sync for compatibility
- **Model profiles**: Auto-detect model size (small/medium/large) for optimized settings
- **Context management**: Smart truncation with token estimation and summarization
- **Plugin system**: Registry-based with persona selector example
- **Configuration**: Cached with mtime tracking for auto-reload
- **Rich UI**: Terminal interface with markdown support and colored status indicators
- **Session management**: Persistent conversation history with JSON storage

### File I/O Patterns
- Use `pathlib.Path` for all file operations
- UTF-8 encoding explicitly specified
- Graceful handling of missing files (return defaults)
- Atomic writes where possible for configuration files

### Type Hints
- Use `str | None` syntax (Python 3.8+)
- Import `Any, Dict, List` from typing as needed
- Return types explicitly declared for public functions
- Optional types used extensively for configuration values