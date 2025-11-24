# Context & Session Management Optimization Analizi

## 📊 Mevcut Durum Analizi

### 1. İki Farklı "History" Kavramı

#### A) `chat_history.json` - Model Context History
**Amaç**: Modelin sohbeti hatırlaması için minimal, optimize edilmiş context
**Nerede kullanılıyor**: 
- `build_model_messages_from_history()` - Modele gönderilen mesajlar
- `build_model_prompt_from_history_full()` - Eski API'ler için prompt
- Her model çağrısında token limiti içinde kalacak şekilde kesilir

**İçerik**:
```python
[
  {"role": "user", "text": "..."},
  {"role": "assistant", "text": "..."},
  {"role": "shell", "command": "ls", "output": "..."}
]
```

**Token Optimizasyonu**:
- `DEFAULT_MAX_CONTEXT_TOKENS = 3000` (env: OLLAMA_MAX_CONTEXT_TOKENS)
- `_trim_history_for_tokens()` - En son mesajlardan başlayıp geriye gider
- Shell output'lar summarize edilir (max 500 char)
- Traceback'ler özel işaretlenir ama full saklanır

#### B) `histories/YYYYMMDD_HHMMSS.json` - Session Archive
**Amaç**: Tam kayıt - user'ın geri dönüp inceleyebileceği complete session
**Nerede kullanılıyor**:
- `/new_session` menüsünden save/load/list/delete
- Archive amaçlı, model context'inde kullanılmıyor

**İçerik**:
```python
{
  "session_id": "20251118_120000",
  "created_at": "2025-11-18T12:00:00",
  "custom_name": "Python Debug Session",
  "model_used": "llama3.2",
  "persona": "engineer",
  "message_count": 45,
  "history": [
    # TÜM MESAJLAR - kesinti yok, summarize yok
    {"role": "user", "text": "..."},
    {"role": "shell", "command": "python test.py", "output": "500 satırlık traceback..."}
  ]
}
```

### 2. Sorunlu Noktalar - Küçük Modeller İçin

#### Problem 1: Shell Output Pollution
```python
# Örnek senaryo - pytest output
!python -m pytest tests/

# Output: 200+ satır test detayı
# Summarize: İlk 200 + son 200 char + error highlights
# Ancak yine de ~400-500 char modele gidiyor
```

**Etki**: Küçük modeller (1B-3B) için:
- Context window dolması (2K-4K token limiti)
- Gereksiz shell detayı yerine actual conversation'a token ayrılmalı
- Test sonuçları zaten ekranda görülüyor, modele gerek yok

#### Problem 2: System Message + Persona Stack
```python
# Config'den base system_message
config["system_message"] = "Sen uzman bir programcısın..."  # ~50-100 token

# Persona plugin aktifse üzerine yazılıyor
persona_prompt = """Sen senior bir Python developer'sın.
Özelliklerin: async programming, testing, clean code..."""  # ~150-200 token

# build_model_messages_from_history içinde:
msgs = [
    {"role": "system", "content": system_message},  # 150-200 token
    {"role": "user", "content": "user message"},
    {"role": "shell", "command": "...", "output": "..."},  # 400-500 token
    ...
]
```

**Etki**: 
- System message her request'te tekrar gönderiliyor
- Persona detaylı olunca tek başına 200 token
- 3000 token budget'ın %15-20'si system message'a gidiyor

#### Problem 3: Traceback Special Handling Ambiguity
```python
# history.py içinde
if _is_traceback(text):
    msgs.append({"role": "user", "content": f"[ERROR/TRACEBACK]\n{text}"})
```

**Sorun**:
- Traceback'ler summarize edilmiyor (shell output gibi)
- User inputta error paste ederse full olarak gidiyor
- 500 satırlık traceback → 2000+ token

### 3. Token Budget Breakdown - Örnek Senaryo

**Model**: Gemma 2B (context: 4096 token)
**Config**: max_context_tokens = 3000, reserve_for_response = 512

```
Total Budget: 3000 token
├─ System Message (persona): 180 token (6%)
├─ Recent History (10 messages): 1200 token (40%)
│  ├─ User messages: 400 token
│  ├─ Assistant responses: 600 token
│  └─ Shell outputs (summarized): 200 token
├─ Current User Input: 50 token (2%)
└─ Reserved for Response: 512 token (17%)
───────────────────────────────────────────
Actual Available: 1058 token for history (35%)
```

**Küçük model ile sorun**:
- 10 message'lık history = çok kısa sohbet (5 round-trip)
- Shell command çalıştırınca 2-3 turn'den fazlası unutuluyor
- User: "yukarda ne dedim?" → Model hatırlamıyor

## 🎯 Optimizasyon Stratejileri

### Strateji 1: Tiered Shell Output Handling
**Context-aware shell output truncation**

```python
def summarize_shell_output_smart(
    text: str | None,
    context_role: str = "model",  # "model" | "archive"
    max_chars: int = 500
) -> str:
    """
    context_role:
    - "model": Agresif summarize - sadece success/error bilgisi
    - "archive": Full output - session save için
    """
    if context_role == "archive":
        return text or ""
    
    if not text or len(text) < 100:
        return text or ""
    
    # Check if command is just informational (ls, cat, etc.)
    if _is_safe_to_drop(text):
        return "[Output omitted - visible in terminal]"
    
    # Extract only errors/warnings
    if _has_errors_only(text):
        return _extract_error_summary(text, max_chars=200)
    
    # Standard summarize for other outputs
    return summarize_shell_output(text, max_chars=max_chars)
```

**Kazanç**: Shell output token kullanımı %70 azalır

### Strateji 2: Dynamic Context Window
**Model'e göre otomatik ayarlama**

```python
# config.json
{
  "context_strategy": "auto",  # "auto" | "manual"
  "model_profiles": {
    "small": {  # <3B models
      "max_context_tokens": 2000,
      "max_turns": 8,
      "shell_output_max": 150,
      "prioritize_conversation": true
    },
    "medium": {  # 3B-7B
      "max_context_tokens": 3500,
      "max_turns": 15,
      "shell_output_max": 400,
      "prioritize_conversation": false
    },
    "large": {  # 7B+
      "max_context_tokens": 6000,
      "max_turns": 30,
      "shell_output_max": 800,
      "prioritize_conversation": false
    }
  }
}

def get_model_profile(model_name: str) -> dict:
    # Parse model size from name
    if any(x in model_name.lower() for x in ["1b", "2b", "3b"]):
        return config["model_profiles"]["small"]
    elif any(x in model_name.lower() for x in ["7b", "8b"]):
        return config["model_profiles"]["medium"]
    else:
        return config["model_profiles"]["large"]
```

**Kazanç**: Küçük modeller için %40 daha fazla conversation history

### Strateji 3: Lazy System Message Loading
**System message'ı sadece gerektiğinde cache'le**

```python
# Option A: System message'ı ilk mesajda göm, sonra exclude
def build_model_messages_optimized(
    history: List[Dict],
    system_message: str,
    include_system: bool = True,  # İlk call: True, sonrası: False
):
    msgs = []
    if include_system or len(history) == 0:
        msgs.append({"role": "system", "content": system_message})
    # ... rest of history
```

**Sorun**: Ollama her request'i stateless kabul eder, çalışmaz

**Option B**: Compress system message after first turn
```python
def compress_system_message(full_prompt: str) -> str:
    """Persona detaylarını kısalt"""
    # "Sen senior Python developer'sın. Özelliklerin: X, Y, Z..."
    # → "Senior Python developer"
    return extract_core_role(full_prompt)  # ~20 token
```

**Kazanç**: System message %70 küçülür (180 → 50 token)

### Strateji 4: Smart History Prioritization
**Önemli mesajları koru, filler'ları at**

```python
def _score_message_importance(item: dict) -> int:
    """0-10 arası önem skoru"""
    role = item.get("role")
    
    # Error/traceback → yüksek önem
    if role == "user" and _is_traceback(item.get("text", "")):
        return 10
    
    # Shell command with error → yüksek önem
    if role == "shell" and _has_errors(item.get("output", "")):
        return 9
    
    # Successful shell (ls, cat) → düşük önem
    if role == "shell" and _is_informational(item.get("command", "")):
        return 3
    
    # User questions → orta önem
    if role == "user":
        return 7
    
    # Assistant → orta önem
    if role == "assistant":
        return 6
    
    return 5

def _trim_history_smart(history: List[Dict], max_tokens: int):
    """Skor bazlı trim - önemli mesajları koru"""
    scored = [(item, _score_message_importance(item)) for item in history]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # High-score messages'ı kesinlikle al
    must_keep = [item for item, score in scored if score >= 8]
    
    # Kalan budget'ı düşük skorlulara dağıt
    # ...
```

**Kazanç**: Critical context korunur, noise atılır

### Strateji 5: Session vs Context Separation
**Archive'de her şey, model'de sadece gerekli**

```python
def save_to_session(history_item: dict, session_archive: list):
    """Full save - no truncation"""
    session_archive.append(history_item)

def save_to_model_context(history_item: dict, model_context: list):
    """Optimized save for model"""
    optimized = history_item.copy()
    
    if history_item["role"] == "shell":
        # Archive'de full, model'de summary
        optimized["output"] = summarize_shell_output_smart(
            history_item["output"],
            context_role="model",
            max_chars=150
        )
    
    model_context.append(optimized)
```

**Yapısal değişiklik**: İki ayrı history list
- `session_history` → Full, archives/ için
- `model_history` → Optimized, modele giderken

## 🏆 Önerilen Çözüm - Hybrid Approach

### Implementasyon Planı

#### Faz 1: Model Profile System (En Etkili + Kolay)
1. `config.json`'a model profilleri ekle
2. `get_model_profile()` fonksiyonu - model name'den size çıkar
3. `build_model_messages_from_history()` profil parametrelerini kullan
4. `/settings` menüsünde profile override

**Effort**: 2-3 saat
**Etki**: %40 token tasarrufu küçük modellerde

#### Faz 2: Smart Shell Output (Orta Etki + Orta Zorluk)
1. `summarize_shell_output_smart()` - context-aware truncation
2. Shell komut kategorileri (info/action/error)
3. Error-only extraction
4. Terminal-visible outputs → "[omitted]"

**Effort**: 3-4 saat
**Etki**: %30 token tasarrufu shell-heavy sessions'da

#### Faz 3: Dual History (Yüksek Etki + Yüksek Zorluk)
1. `session_history` vs `model_history` split
2. Her history item iki yerde saklan (biri full, biri optimized)
3. Session save → full history
4. Model request → optimized history
5. Refactor: main.py içindeki history usages

**Effort**: 6-8 saat
**Etki**: %50+ token tasarrufu, complete accuracy korunur

#### Faz 4: Compressed System Message (Düşük Etki + Düşük Zorluk)
1. Persona plugin → `get_compressed_prompt()` ekle
2. İlk call: full prompt, sonrası: compressed
3. Compressed: Sadece role name (5-10 kelime)

**Effort**: 1-2 saat
**Etki**: %15 token tasarrufu system message'dan

## 📈 Beklenen Sonuçlar

### Şu Anki Durum (Gemma 2B)
```
3000 token budget
- System: 180 (6%)
- History: ~1200 (40%) → 5-6 turn
- Shell: ~500 (17%)
- Reserve: 512 (17%)
- Available: ~608 (20%)
```

### Faz 1 Sonrası (Profile System)
```
2000 token budget (small profile)
- System: 180 (9%)
- History: ~1200 (60%) → 10-12 turn
- Shell: ~150 (8%)
- Reserve: 300 (15%)
- Available: ~170 (8%)
```

### Faz 1+2 Sonrası (+ Smart Shell)
```
2000 token budget
- System: 180 (9%)
- History: ~1400 (70%) → 14-16 turn
- Shell: ~50 (2.5%)
- Reserve: 300 (15%)
- Available: ~70 (3.5%)
```

### Faz 1+2+3 Sonrası (+ Dual History)
```
2000 token budget
- System: 180 (9%)
- History: ~1600 (80%) → 18-20 turn
- Shell: ~20 (1%)
- Reserve: 300 (15%)
- Available: ~-100 (model auto-trim)
```

### Faz 1+2+3+4 Sonrası (All Optimizations)
```
2000 token budget
- System: 50 (2.5%)
- History: ~1650 (82%) → 20-25 turn
- Shell: ~20 (1%)
- Reserve: 300 (15%)
- Available: ~-20 (optimal pack)
```

## 🔧 Uygulama Önceliği

1. **ŞİMDİ**: Faz 1 (Model Profile) - Hızlı kazanç
2. **SONRA**: Faz 2 (Smart Shell) - Shell-heavy use case'ler için
3. **GELECEK**: Faz 4 (Compressed System) - Kolay win
4. **OPSİYONEL**: Faz 3 (Dual History) - Major refactor, high reward

## 💡 Ek İyileştirmeler

### A) User Feedback on Context
```python
# Streaming başında göster
"📊 Context: 12 messages, 1.8K tokens (90% of 2K budget)"
"⚠️  Context nearly full - consider /new_session"
```

### B) Auto-Session on Context Full
```python
if estimated_tokens > max_tokens * 0.95:
    ui_mod.console.print("[yellow]Context nearly full. Creating new session...[/yellow]")
    session_id = create_new_session(history, auto_name=True)
    history.clear()
```

### C) Smart /clear Command
```python
# Şu anki /clear: history.clear() → her şey kaybolur
# Yeni: /clear --keep-important
#   → Sadece errors/tracebacks korunur
#   → 20-25 turn → 3-4 critical message
```

## 📝 Test Senaryoları

### Test 1: Small Model Heavy Shell Usage
```bash
# Gemma 2B
python main.py chat
# 20 shell command çalıştır
# Context dolmasın
# Conversation history 10+ turn korunsun
```

### Test 2: Session Archive Integrity
```bash
# Session save yap
# Full shell outputs kayıtlı olsun
# Load edince truncate olmasın
# Export → markdown tam olsun
```

### Test 3: Large Model No Regression
```bash
# Llama 70B
# Optimizasyonlar büyük modelleri etkilemesin
# Full history korunsun
```

## 🎬 Sonuç

**Kök Problem**: `chat_history.json` hem model context hem archive olarak kullanılıyor

**Optimal Çözüm**: 
- Model context: Agresif optimize, profil-bazlı
- Session archive: Full data, user referansı için
- İki ayrı stream, tek UI

**İlk Adım**: Model Profile System (Faz 1) → Hızlı, etkili, geri dönüşü kolay
