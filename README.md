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
main.py              # Typer CLI bootstrap and command registration (225 lines)
├── commands/        # CLI command handlers (thin orchestration layer)
│   ├── list_models.py
│   ├── save_history.py
│   └── chat.py
├── services/        # Business logic layer
│   ├── server_profiles.py    # Server configuration management
│   ├── settings_service.py   # Settings management
│   └── models_service.py     # Model operations
├── lib/            # Core utilities
│   ├── history.py           # History processing and context management
│   ├── config.py            # Configuration handling
│   ├── ollama_wrapper.py    # Ollama client wrapper
│   ├── session_manager.py   # Session persistence
│   └── ...
├── ui/             # Terminal UI components
│   ├── console.py          # Rich console utilities
│   ├── inputs.py           # User input handling
│   ├── renderers.py        # Output formatting
│   └── stream_display.py   # Streaming response display
├── plugins/        # Plugin system with registry
├── analytics/      # Usage tracking and reporting
├── repl/           # Interactive REPL loop
└── tests/          # Test suite (44 tests passing)
```

**Design Principles:**
- **main.py**: Bootstrap and command registration only
- **commands/**: Thin orchestration layer delegating to services
- **services/**: Business logic with stable APIs
- **lib/**: Core utilities and shared functionality
- **ui/**: Terminal interface components with Rich integration
- **plugins/**: Extensible plugin system with registry pattern

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
