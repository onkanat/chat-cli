# Agent System: `agent_utils.py` + `agent_orchestrator.py`

Bu belge, chat-cli'nin mevcut agent altyapısının çalışma biçimini, sınırlarını ve
genişletme noktalarını açıklamaktadır. Yeni sub-agent tasarımlarından önce referans
olarak okunması önerilir.

---

## 1. Modüller ve Sorumluluk Dağılımı

| Modül | Sorumluluk |
|---|---|
| `lib/agent_utils.py` | Regex/JSON parsing — model çıktısından komut çıkarma |
| `lib/agent_orchestrator.py` | Döngü yönetimi, komut yürütme, guard-rail'ler |

---

## 2. `lib/agent_utils.py`

### 2.1 Veri Yapısı

```python
@dataclass(frozen=True)
class AgentCommandParseResult:
    command: str | None       # Son geçerli /komut (None = komut yok)
    full_match: str | None    # <call_cmd>...</call_cmd> bloğunun ham metni
    invalid_matches: tuple    # / ile başlamayan geçersiz <call_cmd> blokları

@dataclass
class AgentRunResult:
    success: bool
    iterations: int
    stop_reason: str          # completed|max_iterations|repeat_limit|json_limit
    last_command: str | None
```

### 2.2 Protokol: `<call_cmd>` XML Tag

Model, bir slash komut çalıştırmak istediğinde şu sözdizimini kullanır:

```
<call_cmd>/komut argüman1 argüman2</call_cmd>
```

**Geçerli:** `/` ile başlayan komutlar (`/wiki search xyz`)  
**Geçersiz:** `/` olmayan içerik (`<call_cmd>python script.py</call_cmd>`) → `invalid_matches`'e düşer, uyarı verilir ama loop devam eder.

**Önemli:** Birden fazla `<call_cmd>` bloğu varsa sadece **sonuncusu** alınır.

### 2.3 `parse_agent_command(reply: str)`

```
reply (str)
  │
  ├─ CALL_CMD_PATTERN  → / ile başlayan tüm bloklar → last → command
  ├─ ALL_CALL_CMD_PATTERN → / olmayan bloklar → invalid_matches
  └─ raw_search → full_match (history'den temizlemek için)
```

### 2.4 `detect_json_tool_name(reply: str)`

Modelin tüm cevabı `{...}` ile başlayıp bitiyorsa ve içinde `tool/command/action/name`
key'lerinden biri varsa → "JSON tool hallucination" olarak işaretler.  
Sadece `str | None` döndürür; orchestrator kararı kendisi verir.

### 2.5 `normalize_agent_command(command: str)`

Sağdan `>` ve boşluk temizler. `<call_cmd>` regex'inden kaçan artıklar için
koruyucu temizlik katmanı.

---

## 3. `lib/agent_orchestrator.py`

### 3.1 Guard-Rail Sabitleri

| Sabit | Değer | Açıklama |
|---|---|---|
| `MAX_ITERATIONS` | 6 | Maksimum tur sayısı (komutlu veya komutsuz her tur sayılır) |
| `MAX_JSON_RETRIES` | 2 | Ard arda JSON hallucination toleransı |
| `MAX_REPEAT_LIMIT` | 2 | Aynı komutun üst üste kaç kez tekrar edebileceği |
| `BLOCKED_COMMANDS` | `{new_session, run, settings}` | Hiçbir zaman çalıştırılmayan komutlar |

`BLOCKED_COMMANDS`, `_execute_agent_command()` içinde aktif olarak kontrol edilir;
engellenen komutlar için hata mesajı yazılır ve komut çalıştırılmaz.

### 3.2 Bağımlılıklar (Constructor Parametreleri)

```
AgentOrchestrator(
  history          ← doğrudan referans, mutate edilir
  current_model    ← aktif Ollama model adı
  config           ← config.json içeriği (dict)
  plugin_manager   ← PluginManager instance'ı
  analytics_manager
  ui_mod           ← ui/console.py'deki modül
  ollama_wrapper   ← lib/ollama_wrapper.py
  chat_context     ← persona vb. oturum durumu
  max_context_tokens = 4000
  max_output_chars   = 2000
  stream             = True
)
```

`history` bir **referans** olarak geçirilir; tüm `history.append(...)` çağrıları
doğrudan `repl/loop.py`'deki orijinal listeyi değiştirir.

### 3.3 Çalışma Akışı: `run()` / `_run_loop()`

```
run(system_message)
  │
  └─ _run_loop(system_message, initial_reply=None)
       └─ while agent_running [max MAX_ITERATIONS tur]:
       │
       ├─ _get_reply(system_message)
       │    ├─ stream=True  → _get_reply_stream()
       │    └─ stream=False → _get_reply_sync()
       │
       └─ _process_reply(reply)
            │
            ├─ parse_agent_command(reply)
            │    ├─ command bulundu → _execute_agent_command()
            │    │    ├─ Tekrar kontrolü (MAX_REPEAT_LIMIT)
            │    │    ├─ BLOCKED_COMMANDS kontrolü
            │    │    ├─ history'ye assistant entry ekle
            │    │    ├─ çıktı yakalama: io.StringIO + Rich console.capture()
            │    │    ├─ plugin_manager.execute_command() dene
            │    │    ├─ Yoksa execute_command() (built-in)
            │    │    ├─ history'ye system entry ekle (output)
            │    │    └─ return True  ← loop devam eder
            │    │
            │    └─ command yok → _handle_no_command()
            │         ├─ detect_json_tool_name()
            │         │    └─ hallucination → error msg + history + return True/False
            │         └─ temiz cevap → history'ye assistant ekle + return False
            │                                                          ▲
            └─────────────────────────────────────────────────── loop biter

  └─ AgentRunResult(success, iterations, stop_reason, last_command)
```

### 3.4 `run_with_initial_reply()`

`run()` ile özdeş ama ilk tur için model çağrısı yapılmaz; dışarıdan verilen
`initial_reply` ile başlar. Kullanım: `repl/loop.py`'de streaming yanıt dışarıda
üretilip ardından agent loop'a verildiği senaryolar.

### 3.5 Streaming Özel Davranışları

`_get_reply_stream()` içinde iki önemli davranış:

1. **Erken duruş:** `</call_cmd>` token'ı görülür görülmez chunk döngüsü kırılır
   (`break`). Bu sayede model cevabın geri kalanını üretmeden komut çalıştırılır.
   **Yan etki:** `</call_cmd>` sonrasındaki metin kaybolur.

2. **Think token temizliği:** `</think>` buffer'da görünürse o noktanın öncesindeki
   her şey silinir. `<think>` açılış etiketi olmadan `</think>` gelen modeller için
   koruma. Tüm `parts` listesi de sıfırlanır.

### 3.6 Komut Yürütme: İki Katman

```
_execute_agent_command()
  │
  ├─ 1. plugin_manager.execute_command(c_cmd, c_args, legacy_context)
  │       ← Önce plugin'ler denenir
  │
  └─ 2. execute_command(c_cmd, c_args, cmd_ctx)    ← lib/command_executor.py
          ← Built-in komutlar
```

Komut çıktısı iki kanaldan toplanır:

- `io.StringIO` ile `print()`/stdout
- `ui_mod.console.capture()` ile Rich `console.print()`

Birleştirilmiş çıktı `history`'ye `role: system` olarak yazılır.

### 3.7 History Mutasyonu

Her tur history'ye şu entry'ler eklenir:

| Tur Durumu | Eklenen Entry'ler |
|---|---|
| Komutlu tur | `role:assistant` (temiz reply) + `role:system` (komut çıktısı) |
| Temiz cevap (son tur) | `role:assistant` |
| JSON hallucination | `role:assistant` (ham JSON) + `role:system` (hata mesajı) |
| Guard-rail tetiklenince | `role:system` (uyarı mesajı) |

`role:system` entry'leri model context builder'da (`lib/message_builder.py`) açıkça
`[System]: ...` prefiksiyle işlenir (`build_prompt_from_history()` ve
`build_messages_from_history()`).

---

## 4. Bilinen Sınırlar ve Eksiklikler

### 4.1 Scratchpad yok
Gemini'nin `codebase-investigator.ts`'indeki gibi tur-tur güncellenen bir dahili
durum (checklist, sorular, bulgular) mevcut değil. Agent bir turda ne öğrendiğini
bir sonraki tura taşıyamaz; yalnızca history üzerinden dolaylı bağlam aktarır.

### 4.2 Sub-agent / ayrışık scope yok
Tek `AgentOrchestrator` instance'ı doğrudan oturum history'sini mutate eder.
Gemini'deki gibi bir sub-agent ayrı bir tarih penceresiyle çalışamaz; tüm ara
adımlar kalıcı olarak `chat_history.json`'a yazılır.

### 4.3 Token hesabı gerçek değil
`estimated_tokens = char_count // 4` — streaming token sayımı yaklaşık.
`prompt_tokens=0` olarak sabitlenmiş; toplam kullanım takibi eksik.

### 4.4 Structured output sınırlı
`run()` artık `AgentRunResult` döndürse de bu yapı minimaldir; JSON-schema/Pydantic
doğrulamalı, görev-tipine göre zenginleştirilmiş bir çıktı sözleşmesi henüz yok.

### 4.5 `success` alanı semantik olarak kaba
Mevcut implementasyonda `AgentRunResult.success` pratikte her durumda `True`
döndürülür; guard-rail nedeniyle duran akışlarda başarısızlık/sınırlı başarı
ayrımı `stop_reason` üzerinden yapılır.

---

## 5. Genişletme Noktaları

| Hedef | Nereye Eklenecek | Not |
|---|---|---|
| Scratchpad / internal state | `AgentOrchestrator.__init__` + yeni `role:"agent_scratch"` | Modele gönderilmemeli; `message_builder.py` filtreli geçmeli |
| Sub-agent scope | `HistoryInvestigator` gibi ayrı class | Kendi `history_window` listesiyle, ana history'ye sadece sonuç ekler |
| Structured output v2 | `AgentRunResult` + şema doğrulama katmanı | Alan bazlı tipli sonuçlar (ör. `errors`, `warnings`, `actions`) |
| Token bütçesi doğruluğu | `_get_reply_stream()` sonunda `lib/history.py::estimate_tokens()` çağrısı | Mevcut `char//4` yerine |

---

## 6. `repl/loop.py` Entegrasyon Noktası

```python
# loop.py ~L834-L875
orchestrator = AgentOrchestrator(
    history=history,          # ← doğrudan referans
    current_model=CURRENT_MODEL,
    config=config,
    plugin_manager=plugin_manager,
    analytics_manager=analytics_manager,
    ui_mod=ui_mod,
    ollama_wrapper=ow,
    chat_context=chat_context,
    max_context_tokens=max_context_tokens,
    max_output_chars=max_output_chars,
    stream=stream,
)
orchestrator.run(system_message)
```

Her kullanıcı mesajı için yeni bir `AgentOrchestrator` instance'ı oluşturulur;
iteration sayaçları `run()` başında sıfırlanır.

---

## 7. Son Değişiklikler (2026-04-19)

- **B1 (JSON retry guard):** `_handle_no_command()` içinde yanlış sabit adı
  (`MAX_AGENT_JSON_RETRIES`) kaldırıldı, `MAX_JSON_RETRIES` kullanımı doğrulandı.
- **B2 (Blocked command guard):** `_execute_agent_command()` içinde
  `BLOCKED_COMMANDS` aktif enforce edildi; engellenen komutlar çalıştırılmıyor.
- **B3 (System role aktarımı):** `lib/message_builder.py` tarafında
  `role:system` girdileri model bağlamına `[System]: ...` prefiksiyle taşınıyor.
- **B4 (Çıktı yakalama):** Komut çıktısı artık hem `io.StringIO` (stdout) hem
  `console.capture()` (Rich) üzerinden toplanıp birleştiriliyor.
- **B5 (Loop refactor):** `run()` ve `run_with_initial_reply()` ortak akışı
  `_run_loop()` metoduna alındı; duplikasyon azaltıldı.
- **B6 (Structured result):** Orchestrator dönüş tipi `bool` yerine
  `AgentRunResult` oldu (`success`, `iterations`, `stop_reason`, `last_command`).

### Test doğrulaması

- `tests/test_faz3_orchestrator.py`
- `tests/test_agent_utils.py`
- `tests/test_faz6_plugin_executor.py`

Son çalıştırmada ilgili testler **25 passed** sonucu verdi.
