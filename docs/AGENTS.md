# Development Guidelines for Ollama Chat CLI

## Build/Test Commands
- **Run tests**: `python -m pytest -q tests/`
- **Run single test**: `python -m pytest -q tests/test_history_processing.py::test_function_name`
- **Install dependencies**: `pip install -r requirements.txt`
- **Run application**: `python main.py chat`

## Code Style Guidelines

### Imports & Structure
- Use `from __future__ import annotations` at top of all Python files
- Group imports: standard library, third-party, local modules
- Use type hints consistently (Python 3.8+ style with `str | None` syntax)
- Modular architecture: separate concerns into dedicated modules

### Naming Conventions
- Functions: `snake_case` with descriptive names
- Variables: `snake_case`, avoid single letters except loop counters
- Constants: `UPPER_SNAKE_CASE`
- Private functions: prefix with `_` underscore

### Error Handling
- Use try/except blocks for external dependencies (ollama clients, subprocess)
- Return fallback values (None, empty list, False) rather than raising
- Graceful degradation when ollama clients unavailable

### Code Organization
- Client logic in `client.py` and `ollama_client_helpers.py`
- History processing in `history.py`
- UI/rendering in `ui.py`
- Main CLI orchestration in `main.py`

### Testing
- Test history processing functions thoroughly
- Mock external dependencies in tests
- Focus on token estimation and truncation logic

### Dependencies
- Core: `ollama-python`, `typer[all]`, `rich`, `markdown`
- Optional: `tiktoken` for better token estimation
- Fallback to CLI when Python clients unavailable

### Key Patterns
- Stream responses when possible, fall back to sync
- Support both message-based and prompt-based APIs
- Summarize long shell outputs to control context size
- Use Rich for terminal UI with markdown support
