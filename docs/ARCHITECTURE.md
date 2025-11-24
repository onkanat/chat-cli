# 🤖 Ollama Chat CLI - Advanced Terminal Interface

Modern, modüler ve terminal odaklı bir Ollama sohbet arayüzü. Çok satırlı giriş, zengin slash komutları, temel analytics ve plugin sistemi gibi bileşenler içerir. Bu belge, _mevcut kod tabanının gerçek yeteneklerini_ yansıtacak şekilde güncellendi.

## 🚀 Özellik Özeti

### Context Optimization System (YENİ!)

- **Model Profilleri**: Küçük (1B-3B), orta (4B-8B) ve büyük (>8B) modeller için otomatik optimize edilmiş context limitleri
- **Smart Shell Output**: Bilgilendirici komutlar (ls, cat) model'e gönderilmez, hatalar otomatik extract edilir
- **Dual History**: Archive'de tam data, model context'inde optimize edilmiş data
- **Compressed System Messages**: Uzun sistem mesajları sonraki turnlarda otomatik kısaltılır
- **3x Daha Fazla Hafıza**: Küçük modeller (Gemma 2B, Qwen 1.5B) için 5-6 turn yerine 15-20 turn hatırlama

### Model Yönetimi

- Etkileşimli model seçimi menüsü (`/model`).
- Varsayılan modeli kaydetme ve tekrar kullanma.
- Sıcaklık ve max token ayarlarını `/settings` menüsünden değiştirme.
- Yerel/uzak Ollama sunucuları arasında profil bazlı geçiş.

### Girdi ve Shell Deneyimi

- Tek satır varsayılan, satır sonuna `\` ekleyerek çok satırlı moda geçiş.
- Arrow tuşlarıyla komut geçmişi (readline destekli).
- `!<cmd>` ile terminal komutları çalıştırma; çıktı panel olarak gösterilir ve geçmişe `role: shell` kaydı düşer.
- Otomatik mod tespiti veya context-aware completion _bulunmaz_.

### UI ve Akış

- Rich paneller ile asistan yanıtları ve shell çıktıları.
- Streaming modunda ilerleme çubuğu ve karakter bazlı ilerleme güncellemesi.
- Yaklaşık token kullanımı tek satırlık özetle gösterilir.
- `/theme` komutu tercih edilen temayı config dosyasına yazar; şu an terminal renkleri Rich varsayılanıdır.

### Arama, Export ve Analytics

- `/search <query>` komutu; kullanıcı, asistan ve shell kayıtlarında arama yapar.
- `/export <dosya> [format]` ile markdown/json/txt dışa aktarma.
- `/stats` komutu yüklenen geçmişten mesaj sayılarını çıkarır.
- Analytics yöneticisi komut kullanımlarını ve oturum olaylarını kaydeder; ayrıntılı token/mesaj istatistikleri için ek geliştirme gerekir.

### Plugin Sistemi

- `plugins/` klasöründen yüklenen PluginBase türevleri slash komutları ekleyebilir.
- `example_plugin` otomatik olarak oluşturulur ve yüklenebilir.
- `/plugin-load`, `/plugin-unload`, `/plugin-info`, `/plugins`, `/plugins-available` komutları hazır.
- Bazı gelişmiş özellikler (ör. persona yönetimi) yalnızca ilgili plugin yüklüyse aktiftir.

#### Persona Selector (system_prompt eklentisi)

- `plugins/persona_selector.py` sistemi varsayılan olarak yüklenir ve `plugins/system_prompts/personas.json` içindeki şablonları okur.
- `/persona list` mevcut personas listesini tabloda gösterir, `/persona set <id>` seçim yapar ve sistem mesajını sohbet süresince override eder.
- `/persona clear` varsayılan sistem mesajına döner, `/persona info <id>` seçilen şablonun tam prompt içeriğini panelde gösterir.
- `/suggest <problem cümlesi>` veya `/persona suggest <prompt>` komutları, sorguya göre en uygun personas önerilerini listeler.
- Seçilen persona kimliği `config.json` → `persona.current_persona` alanına kaydedilir; yeniden başlatınca otomatik uygulanır.

## 🎮 Multi-line Input Kullanımı

**Tek Satır Modu (Varsayılan):**

```bash
You: Merhaba dünya
# Enter → tek satır gönderilir
```

**Çok Satır Modu:**

```bash
You: Merhaba dünya\
>>> Bu ikinci satır
>>> Bu üçüncü satır
>>> 
📝 Sent 3 lines
```

**İpuçları:**

- Çok satırdan çıkmak için boş satır gönderin.
- Komut geçmişi hem tek hem çok satır girdileri saklar.
- Otomatik mod algılama olmadığı için `\` kullanımı manuel yapılmalıdır.

## 📌 Durum Özeti

- README artık yalnızca _uygulanan_ özellikleri anlatır; geçmişteki "smart input" veya "context-aware completion" gibi ifadeler kaldırıldı.
- Tema seçimi config dosyasında tutulur fakat farklı Rich temaları uygulanmaz.
- Analytics paneli komut ve oturum kayıtlarını gösterir; toplam mesaj/token değerleri, manuel olarak `analytics.json` güncellenmedikçe 0 kalabilir.
- Gerçek zamanlı monitoring paneli statik bir bilgilendirme ekranıdır; dış kaynaklardan veri çekmez.

## 🛠️ Kurulum

### Gereksinimler

```bash
Python 3.8+
ollama (resmi Python paketi) ve/veya Ollama CLI
```

### Ortam Hazırlığı

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 🔌 Ollama entegrasyonu (YENİ)

Bu proje artık resmi Ollama Python kütüphanesini (`ollama>=0.6.1`) kullanır. Eski `ollama-python` bağımlılığı kaldırıldı. Entegrasyon, küçük bir `ollama_wrapper.py` modülü üzerinden yapılır ve şu yetenekleri sağlar:

- Model listeleme: `ow.list_models()`
- Model indirme: `ow.load_model(name)` (pull)
- Model silme: `ow.delete_model(name)`
- Sohbet (stream): `ow.chat_stream(model, messages)`
- Tam yanıta kadar bekleme (sync): `ow.chat_sync(model, messages)`
- Tamamlama (generate) stream/sync: `ow.generate_stream(...)` / `ow.generate_sync(...)`
- CLI passthrough: `ow.run_ollama_cli(args)` / `ow.run_ollama_cli_stream(args)`
- Sunucu ayarı: `ow.init_client(base_url)` (otomatik olarak sondaki `/api` ekini temizler)

Çevre değişkenleri:

- `OLLAMA_BASE_URL`: `http://localhost:11434` gibi (wrapper `/api` son ekini otomatik temizler)
- `OLLAMA_API_KEY`: (Opsiyonel) Ollama Cloud API için

Hızlı örnekler:

```bash
# Modelleri listele
python main.py list-models-cmd

# Python içinden
python -c "import ollama_wrapper as ow; print(ow.list_models())"
```

REPL içinde sohbet yolu, mesajlar mevcutsa resmi `ollama.chat(stream=True)` akışını kullanır; aksi halde `generate(stream=True)` ile çalışır. Sunucu adresi `--base-url` ya da `OLLAMA_BASE_URL` ile ayarlanabilir.

## 🎮 Kullanım

### CLI giriş noktaları

```bash
# Sohbeti başlat
python main.py chat

# Mevcut modelleri listele
python main.py list-models-cmd

# Yardım
python main.py --help
```

## 🔍 REPL Komutları

### REPL Model Yönetimi

```bash
/model                     # Model seçimi
/settings                  # Parametre menüsü
/theme <default|dark|light>
/list veya /models         # Modelleri yazdır
/load <model>              # Modeli aktif et
/pull <model>              # Model indir
/delete <model>            # Model sil
```

### REPL Arama, Export ve Analytics

```bash
/search <query>            # Geçmişte arama
/clear                     # Ekranı temizle
/export <dosya> [format]   # markdown/json/txt export
/stats                     # Geçmiş tabanlı istatistik
/analytics                 # Analytics dashboard
/report [dosya]            # Analytics raporu
/monitor                   # Canlı izleme paneli
```

### REPL Plugin ve Sistem Komutları

```bash
/plugins                   # Yüklü pluginler
/plugins-available         # Dosya sistemindeki pluginler
/plugin-load <ad>          # Plugin yükle
/plugin-unload <ad>        # Plugin kaldır
/plugin-info <ad>          # Plugin detayları
/new_session               # Oturum yönetim menüsü
/save <dosya>              # Geçmiş kaydet
/load_history <dosya>      # Geçmiş yükle
/exit veya /quit           # Kaydedip çık
/help                      # Komut özetleri
```

### Oturum Yönetimi (Session Management)

```bash
/new_session               # Oturum menüsü açar
```

Oturum menüsü içinde:
- **Yeni oturum oluştur**: Mevcut sohbeti `histories/` klasörüne kaydeder ve temiz bir sohbet başlatır
- **Oturum listele**: Kaydedilmiş tüm oturumları tarih, isim, model ve mesaj sayısıyla gösterir
- **Oturum yükle**: Daha önce kaydedilmiş bir oturumu geri yükler
- **Oturum sil**: Seçilen oturumu `histories/` klasöründen kalıcı olarak siler

Oturum dosyaları `histories/YYYYMMDD_HHMMSS.json` formatında saklanır ve her oturum şu metadata'yı içerir:
- Oturum ID (timestamp-based)
- Özel isim (opsiyonel)
- Kullanılan model
- Aktif persona (varsa)
- Oluşturma tarihi
- Mesaj sayısı
- Tam sohbet geçmişi

### Context Optimization Detayları

**Model Profil Sistemi**:
- Model adından otomatik boyut tespiti (gemma:2b → small, llama3:8b → medium)
- Her profil farklı token budget, turn limiti ve shell output limiti kullanır
- Küçük modeller için agresif optimizasyon, büyük modeller için rahat limitler

**Smart Shell Output**:
- `ls`, `cat`, `pwd` gibi bilgilendirici komutların çıktıları model'e gitmez
- Hatalar otomatik detect edilir ve sadece error satırları extract edilir
- Archive dosyalarında tam output korunur, model sadece özet görür

**Token Tasarrufu**:
```
Gemma 2B - Önce:
├─ System: 180 token (6%)
├─ Shell: 500 token (17%)
├─ Conversation: 1200 token (40%) → 5-6 turn
└─ Reserved: 512 token (17%)

Gemma 2B - Sonra:
├─ System: 50 token (2.5%)
├─ Shell: 20 token (1%)
├─ Conversation: 1650 token (82%) → 18-20 turn
└─ Reserved: 300 token (15%)
```

### Shell Entegrasyonu

```bash
!ls -la
!python script.py
!npm install paket
```

Shell çıktısı yüksek olduğunda tüm içerik geçmişe yazılır; model bağlamına eklenirken `history.summarize_shell_output` devreye girer.

## 📊 Analytics ve Monitoring

- `analytics.AnalyticsManager` oturum başlatma/bitirme, komut kullanım sayıları ve günlük toplamlara odaklanır.
- `analytics.json` dosyası, CLI kapatıldığında güncel verileri içerir.
- `/analytics` komutu tablo bazlı özetler, `/report` markdown formatında rapor üretir.
- Mesaj başına token/yanıt süresi ölçümü varsayılan olarak yapılmaz; gerekirse `track_message` çağrıları ekleyerek genişletebilirsiniz.

## 🔌 Plugin Sistemi

- Tüm pluginler `plugins` klasöründe bulunur; `PluginBase` soyut sınıfından türetilir.
- `PluginManager` klasörü tarar, komutları kaydeder, `on_load` / `on_unload` kancalarını tetikler.
- Plugin komutları normal slash komutlarıyla aynı adıma tabidir; tanımlı değilse ana REPL "Unknown slash command" mesajı üretir.
- Plugin'ler çalışma zamanında `plugin_manager.execute_command` üzerinden `context` nesnesi (history, config, analytics vb.) alır.

## ⚙️ Konfigürasyon Dosyaları

### `config.json`

```json
{
  "default_model": "gemma3:1b-it-qat",
  "system_message": "Sen uzman bir programcısın...",
  "temperature": 0.7,
  "max_tokens": 2048,
  "theme": "default",
  "context_strategy": "auto",
  "compress_system_message": false,
  "model_profiles": {
    "small": {
      "max_context_tokens": 2000,
      "max_turns": 8,
      "shell_output_max": 150,
      "reserve_for_response": 300,
      "prioritize_conversation": true
    },
    "medium": {
      "max_context_tokens": 3500,
      "max_turns": 15,
      "shell_output_max": 400,
      "reserve_for_response": 512,
      "prioritize_conversation": false
    },
    "large": {
      "max_context_tokens": 6000,
      "max_turns": 30,
      "shell_output_max": 800,
      "reserve_for_response": 1024,
      "prioritize_conversation": false
    }
  },
  "ollama_servers": {
    "active": "local",
    "profiles": {
      "local": {
        "label": "Localhost",
        "base_url": "http://localhost:11434/api"
      },
      "remote": {
        "label": "LAN Server",
        "base_url": "http://192.168.1.14:11434/api"
      }
    }
  }
}
```

### `analytics.json`

```jsonc
{
  "sessions": [...],
  "total_messages": 0,
  "total_tokens": 0,
  "commands_used": {
    "help": 8,
    "settings": 9,
    "shell": 1
  }
}
```

### `plugin_config.json`

```json
{
  "enabled_plugins": ["example_plugin"],
  "plugin_settings": {},
  "auto_load": true
}
```

## 🧪 Testler

Projede kapsamlı bir test seti bulunmaktadır (45 test). Çalıştırmak için:

```bash
python -m pytest -q tests/
```

## 🏗️ Proje Yapısı

```text
.
├── main.py
├── ollama_wrapper.py
├── ui.py
├── history.py
├── analytics.py
├── input_handler.py
├── plugins.py
├── plugins/
│   └── example_plugin.py
├── tests/
│   └── test_history_processing.py
├── config.json
├── analytics.json
├── plugin_config.json
└── README.md
```

Notlar:
- `client.py` ve `ollama_client_helpers.py` kaldırılmıştır. Tüm Ollama entegrasyonu `ollama_wrapper.py` üzerinden sağlanır.

## 🤝 Katkı

1. Depoyu fork edin.
2. Yeni bir dal açın: `git checkout -b feature/xyz`.
3. Değişiklikleri yapıp testleri çalıştırın.
4. Anlamlı commit mesajıyla kaydedin.
5. Pull request açın ve yaptığınız güncellemeleri açıklayın.

## 📄 Lisans

MIT Lisansı; detaylar için `LICENSE` dosyasına bakabilirsiniz.

---

## 🏗️ Architecture (v0.3.0-beta)

### Modular Layer Design

The codebase follows a clean 4-layer architecture:

#### 1. **Bootstrap Layer** (`main.py` - 225 lines)
- Typer CLI application setup
- Command registration (`@app.command()`)
- Helper functions (settings menu, server management)
- Configuration utilities

**Responsibilities:**
- Initialize Typer app
- Register commands
- Provide shared utilities
- Backward compatibility exports for tests

#### 2. **Services Layer** (`services/` - 89 lines)
- **server_profiles.py** (18 lines): Configuration constants and defaults
- **settings_service.py** (35 lines): Config I/O, base URL resolution
- **models_service.py** (33 lines): Model operations façade over ollama_wrapper

**Responsibilities:**
- Provide stable API over config/ollama_wrapper
- Decouple business logic from implementation details
- Centralize configuration management

**Design Pattern:** Façade pattern - simple interface over complex subsystems

#### 3. **Commands Layer** (`commands/` - 49 lines)
- **list_models.py** (22 lines): Model listing command
- **save_history.py** (8 lines): History save command
- **chat.py** (19 lines): Chat REPL launcher

**Responsibilities:**
- Thin orchestration of services and REPL
- Parameter extraction from CLI
- Delegation to appropriate layers

**Design Pattern:** Command pattern - encapsulate requests as objects

#### 4. **REPL Layer** (`repl/loop.py` - 634 lines)
- Complete interactive REPL implementation
- 20+ slash commands (`/list`, `/model`, `/settings`, etc.)
- Shell command integration (`!command`)
- Plugin system integration
- Streaming and sync chat modes
- Session and persona management

**Responsibilities:**
- User interaction loop
- Input handling (multiline, readline)
- Command parsing and dispatch
- Chat streaming with Rich panels
- Analytics tracking

### Data Flow

```
User Input
    ↓
main.py (Typer command)
    ↓
commands/ (orchestration)
    ↓
    ├─→ services/ (business logic)
    │       ↓
    │   ollama_wrapper → Ollama API
    │
    └─→ repl/loop.py (interactive)
            ↓
        ├─→ services/ (models, config)
        ├─→ plugins/ (extensibility)
        ├─→ analytics/ (tracking)
        └─→ ui/ (rendering)
```

### Key Design Decisions

1. **Modular architecture**: Clear separation of concerns with dedicated directories
   - lib/ for core utilities, ui/ for terminal components, services/ for business logic
   - Tests can import directly without sys.path hacks

2. **Services as façade**: Stable API over volatile dependencies
   - Changes to lib/ollama_wrapper don't cascade
   - Easy to mock for testing

3. **REPL in separate module**: Isolation of complex interactive logic
   - 634 lines of slash commands don't clutter main.py
   - Can be tested independently

4. **Commands as thin layer**: Minimal orchestration
   - Average 16 lines per command
   - Just parameter extraction and delegation

### Refactoring History

**Phase 1** (Analytics/Plugins/UI):
- Modularized analytics, plugins, ui subsystems
- Backward compatibility maintained

**Phase 2** (Services/Commands/REPL):
- Created 3 new layers (services, commands, repl)
- Reduced main.py from 1477 → 225 lines (85% reduction)
- Migrated 20+ slash commands to repl/loop.py
- All 7 tests passing, zero lint errors

**Phase 3** (File Organization):
- Cleaned root directory (removed temp files)
- Updated .gitignore (histories/, backups)
- Moved docs to docs/ subdirectory
- Created concise root README.md

### Testing

- 7 test files covering core functionality
- Test coverage maintained through refactoring
- Integration tests via pytest fixtures

### Future Improvements

- Extract helper functions from main.py to utils/
- Add type hints to all public APIs
- Increase test coverage for services/commands/repl
- Document plugin API
