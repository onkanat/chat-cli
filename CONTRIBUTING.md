# Contributing

Thanks for contributing to `chat-cli`.

## Quick start

- EN: Use the project virtual environment.
- TR: Proje sanal ortamını kullanın.

1. Create and activate env:
   - `python3 -m venv .chat`
   - `source .chat/bin/activate`
2. Install deps:
   - `pip install -r requirements.txt`
3. Run checks before PR:
   - `ruff check .`
   - `mypy .`
   - `python3 -m pytest tests/ -q`

## Pull request rules

- Keep changes small and focused.
- Preserve backward-compatible exports used by tests.
- Add or update tests when behavior changes.
- Update docs when command behavior changes.
