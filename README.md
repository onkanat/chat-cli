# 🤖 Ollama Chat CLI

Modern, modular terminal-based chat interface for Ollama with advanced features.

## ⚡ Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run interactive chat
python main.py chat

# List available models
python main.py list-models-cmd

# Show all commands
python main.py --help
```

## 🎯 Key Features

- **Interactive REPL** with 20+ slash commands
- **Multi-line input** with readline support
- **Shell integration** with `!command` syntax
- **Plugin system** for extensibility
- **Analytics & monitoring** built-in
- **Session management** for conversation history
- **Model profiles** with optimized context handling
- **Smart streaming** with Rich panels

## 📚 Documentation

- [Full Documentation](docs/FULL_README.md) - Complete features and usage guide
- [Architecture Guide](docs/ARCHITECTURE.md) - System design and layers
- [Development Notes](docs/AGENTS.md) - Refactoring history and decisions
- [Context Optimization](docs/CONTEXT_OPTIMIZATION_ANALYSIS.md) - Memory strategies

## 🏗️ Architecture

```
main.py              # Typer CLI bootstrap (648 lines)
├── services/        # Business logic layer (86 lines)
│   ├── server_profiles.py    # Configuration constants
│   ├── settings_service.py   # Config I/O
│   └── models_service.py     # Model operations
├── commands/        # CLI command handlers (49 lines)
│   ├── list_models.py
│   ├── save_history.py
│   └── chat.py
├── repl/           # Interactive REPL (745 lines)
│   └── loop.py     # Main loop, slash commands
├── plugins/        # Plugin system
├── analytics/      # Analytics engine
└── tests/          # Test suite (45 tests)
```

**Design Principles:**
- Services layer provides stable API over config/ollama_wrapper
- Commands layer delegates to services/repl (thin orchestration)
- REPL layer handles user interaction and slash commands
- Main.py stays focused on bootstrap and command registration

## 🧪 Testing

```bash
# Run all tests (45 passing)
pytest tests/

# Run with coverage
pytest --cov=. tests/
```

## 🚀 Recent Changes (v0.3.0-beta)

**Phase 2 Refactoring** - Modular architecture:
- Extracted services/commands/repl layers
- Reduced main.py from 1477 → 648 lines (56%)
- Clean separation of concerns
- All tests passing, zero lint errors

See [docs/AGENTS.md](docs/AGENTS.md) for refactoring details.

## 📝 License

MIT
