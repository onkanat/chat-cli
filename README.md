# 🤖 Ollama Chat CLI

Modern, modular terminal-based chat interface for Ollama with advanced features.

## ⚡ Quick Start

```bash
# macOS-first (önerilen)
python3 -m venv .chat
source .chat/bin/activate
pip install -r requirements.txt

# Run interactive chat
python3 main.py chat

# List available models
python3 main.py list-models-cmd

# Show all commands
python3 main.py --help
```

> EN: Use a virtual environment on externally-managed Python systems.
> TR: Dışarıdan yönetilen Python kurulumlarında mutlaka sanal ortam kullanın.

## 🎯 Key Features

- **Interactive REPL** with 20+ slash commands
- **Multi-line input** with readline support
- **Shell integration** with `!command` syntax
- **Plugin system** for extensibility (includes native `/file`, `persona` selection, and direct **/wiki** slash subcommands like `/wiki pin`, `/wiki search` via Omni-Daemon)
- **Persona Auto-Router (opt-in)**: incoming prompt'u IDF/N-gram skoruyla en uygun persona'ya otomatik yönlendirme
- **`/wiki save`**: son assistant yanıtını doğrudan `wiki/concepts/` altına kaydetme
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

```text
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
└── tests/          # Test suite
```

**Design Principles:**

- **main.py**: Bootstrap and command registration only
- **commands/**: Thin orchestration layer delegating to services
- **services/**: Business logic with stable APIs
- **lib/**: Core utilities and shared functionality
- **ui/**: Terminal interface components with Rich integration
- **plugins/**: Extensible plugin system with registry pattern

## 🔗 Companion Project: system_prompts

> [!NOTE]
> **`persona_selector` plugin**, aynı geliştirici tarafından yönetilen
> [`system_prompts`](../system_prompts) projesine **canlı bağlantıyla** bağlıdır.

- **Persona tanımları** → `../system_prompts/skills/<id>/SKILL.md`
- **Derlenmiş prompts** → `../system_prompts/prompts.json`
- **Etiket haritası** → `../system_prompts/persona_map.yaml`
- **Bağlantı config** → `plugin_config.json` » `plugin_settings.persona_selector.system_prompts_path`

**Bağımlılık notu:** `system_prompts` sadece `PyYAML>=6.0` gerektirir.
Bu bağımlılık `chat-cli/requirements.txt`'e eklenmiştir; iki proje **ayrı sanal ortam** kullanır, çakışma yoktur.

**Yeni persona sonrası güncelleme akışı:**

```bash
# system_prompts projesinde:
cd ../system_prompts
python scripts/skills_to_json.py     # prompts.json + persona_map.yaml günceller

# chat-cli'da (çalışırken bile):
/persona reload                       # değişiklikleri anında yükler
```

> [!WARNING]
> `plugin_config.json` içindeki `system_prompts_path` değeri mutlak yol içerir.
> `system_prompts` reposunu farklı bir klasöre taşırsanız bu değeri güncellemeyi unutmayın.

## 🧪 Testing

```bash
# Primary
python3 -m pytest tests/ -q

# Focused regression set (REPL + parser + plugins + wiki + persona router)
python3 -m pytest tests/test_agent_utils.py tests/test_faz2_command_executor.py tests/test_parse_utils.py tests/test_faz3_orchestrator.py tests/test_faz4_system_prompt.py tests/test_faz5_integration.py tests/test_faz6_plugin_executor.py tests/test_session_manager_fixes.py tests/test_faz21_user_path.py tests/test_tool_wiki.py tests/test_persona_router.py -q
```

## 🧠 Persona Auto-Router (Yeni)

`persona_selector` plugin'i, `system_prompts` kaynaklarından yüklenen persona etiketlerini
IDF + n-gram skorlama ile değerlendirir ve istenirse aktif personayı otomatik değiştirir.

`config.json`:

```json
{
	"auto_persona_routing": true
}
```

- `false` (default): manuel persona yönetimi (`/persona set ...`)
- `true`: her kullanıcı mesajında en iyi persona hesaplanır; farklıysa hot-swap yapılır

## 📝 Wiki Save Akışı

Yeni `/wiki save` komutu, son assistant yanıtını wiki sayfası olarak kaydeder.

```bash
# REPL içinde
/wiki save yeni_sayfa.md "Sayfa Başlığı"
```

Bu komut, modelin ürettiği son içeriği tekrar kopyalamadan hızlıca wiki'ye almayı sağlar.

## 🚀 Recent Changes (Omni-Architecture V2)

**Phase 3 Refactoring** - Thin Client & RAG Offloading:
- Transitioned `chat-cli` into a "Thin Client" architecture.
- Vector database hosting (Qdrant) and heavy logic moved to **Omni-Daemon**.
- Timeout thresholds optimized to support real-time streaming endpoint `/api/v1/stream`.
- Preserved local plugins (e.g. `persona_selector`, `/file read`).

See [docs/AGENTS.md](docs/AGENTS.md) for Refactoring history.

## 📝 License

MIT
