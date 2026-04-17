from __future__ import annotations

import logging
import subprocess
import uuid
import importlib
from typing import Any, Dict, List, Iterator

from rich.console import Console

import lib.history as history_mod
import lib.message_builder as message_builder
import lib.ollama_wrapper as ow
import requests
from services.settings_service import determine_base_url, load_config

console = Console()
logger = logging.getLogger(__name__)


def _normalize_route_mode(config: Dict[str, Any]) -> str:
    mode = str(config.get("generation_route", "omni")).strip().lower()
    if mode not in {"omni", "auto", "direct"}:
        return "omni"
    return mode


def _normalize_generation_options(
    config: Dict[str, Any],
    *,
    max_tokens: int,
) -> Dict[str, Any]:
    options: Dict[str, Any] = {}

    perf = config.get("performance", {})

    temperature = perf.get("temperature")
    if temperature is None:
        temperature = config.get("temperature")
    if isinstance(temperature, (int, float)):
        options["temperature"] = max(0.0, min(2.0, float(temperature)))

    cap_value = perf.get("num_ctx") or config.get("direct_num_ctx_cap", 4096)
    if not isinstance(cap_value, int):
        cap_value = 4096
    cap_value = max(512, min(32768, cap_value))

    if max_tokens > 0:
        options["num_ctx"] = max(512, min(max_tokens, cap_value))

    num_gpu = perf.get("num_gpu")
    if isinstance(num_gpu, int):
        options["num_gpu"] = num_gpu

    num_thread = perf.get("num_thread")
    if isinstance(num_thread, int) and num_thread > 0:
        options["num_thread"] = num_thread

    parallel = perf.get("parallel")
    if isinstance(parallel, int) and parallel > 0:
        options["parallel"] = parallel

    num_keep = perf.get("num_keep")
    if isinstance(num_keep, int) and num_keep > 0:
        options["num_keep"] = num_keep

    return options


def _looks_like_memory_error(text: str) -> bool:
    if not text:
        return False
    normalized = text.lower()
    return (
        "memory layout cannot be allocated" in normalized
        or "cannot allocate memory" in normalized
        or "out of memory" in normalized
        or "requires more system memory" in normalized
        or "than is available" in normalized
    )


def _normalize_omni_base_url(config: Dict[str, Any]) -> str:
    base = str(config.get("omni_base_url", "http://localhost:8000")).strip()
    if not base:
        return "http://localhost:8000"
    return base.rstrip("/")


def _auto_disable_omni_on_agent_error(config: Dict[str, Any]) -> None:
    """Persist a switch to 'direct' route when agent error fallback fires."""
    try:
        from lib.config import save_config as _save_config
        current = str(config.get("generation_route", "omni")).lower()
        if current != "direct":
            config["omni_previous_route"] = current
        config["generation_route"] = "direct"
        _save_config(config)
        logger.warning(
            "omni_agent_error_fallback: "
            "generation_route switched to direct and saved"
        )
    except Exception:
        logger.exception("omni_agent_error_fallback save failed")


def _normalize_top_k(config: Dict[str, Any]) -> int:
    value = config.get("omni_top_k", 5)
    if not isinstance(value, int):
        return 5
    return max(1, min(20, value))


def _extract_latest_query(prompt_or_history: Any) -> str:
    """Extract the latest user-facing query text."""
    if isinstance(prompt_or_history, list):
        for item in reversed(prompt_or_history):
            if not isinstance(item, dict):
                continue
            if item.get("role") != "user":
                continue
            text = str(item.get("text", "")).strip()
            if text:
                return text
        return ""
    return str(prompt_or_history or "").strip()


def _is_context_dependent_query(text: str) -> bool:
    """Heuristic to detect follow-up prompts that depend on prior turns."""
    if not text:
        return False

    normalized = text.strip().casefold()
    normalized = normalized.replace("ı", "i")

    # Kısa ve takip niteliğindeki komutlar bağlama daha çok bağımlıdır.
    if len(normalized) <= 140:
        cues = (
            "bağlam",
            "baglam",
            "devam et",
            "continue",
            "buna gore",
            "buna göre",
            "gorevleri baslat",
            "görevleri başlat",
            "planla",
            "simdi",
            "şimdi",
            "tamam",
        )
        if any(cue in normalized for cue in cues):
            return True

    return False


def _collect_recent_user_context(
    prompt_or_history: Any,
    *,
    max_items: int,
    max_chars: int,
) -> str:
    """Collect previous user turns (excluding latest) as context hints."""
    if not isinstance(prompt_or_history, list):
        return ""

    # locate latest user index
    latest_user_index: int | None = None
    for idx in range(len(prompt_or_history) - 1, -1, -1):
        item = prompt_or_history[idx]
        if isinstance(item, dict) and item.get("role") == "user":
            latest_user_index = idx
            break

    if latest_user_index is None:
        return ""

    snippets: List[str] = []
    for idx in range(latest_user_index - 1, -1, -1):
        item = prompt_or_history[idx]
        if not isinstance(item, dict):
            continue
        if item.get("role") != "user":
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        snippets.append(text)
        if len(snippets) >= max_items:
            break

    if not snippets:
        return ""

    snippets.reverse()
    lines = [f"- {snippet}" for snippet in snippets]
    joined = "\n".join(lines)
    if len(joined) > max_chars:
        joined = joined[-max_chars:]
    return joined


def _build_omni_query(prompt_or_history: Any, config: Dict[str, Any]) -> str:
    """Build query sent to Omni with optional context enrichment."""
    latest_query = _extract_latest_query(prompt_or_history)
    if not latest_query:
        return "Assistant prompt"

    if not bool(config.get("omni_context_enrichment", True)):
        return latest_query

    if not _is_context_dependent_query(latest_query):
        return latest_query

    max_items_raw = config.get("omni_context_turns", 2)
    max_chars_raw = config.get("omni_context_chars", 600)

    if not isinstance(max_items_raw, int):
        max_items_raw = 2
    if not isinstance(max_chars_raw, int):
        max_chars_raw = 600

    max_items = max(1, min(5, max_items_raw))
    max_chars = max(200, min(2000, max_chars_raw))

    hint = _collect_recent_user_context(
        prompt_or_history,
        max_items=max_items,
        max_chars=max_chars,
    )
    if not hint:
        return latest_query

    return (
        f"{latest_query}\n\n"
        "[Sohbet bağlamı - önceki kullanıcı mesajları]\n"
        f"{hint}"
    )


def _should_emit_failover_messages(config: Dict[str, Any]) -> bool:
    return bool(config.get("show_failover_messages", False))


def _should_prefer_direct_for_chat(
    prompt_or_history: Any,
    config: Dict[str, Any],
    route_mode: str,
) -> bool:
    if route_mode == "omni":
        return False
    if not isinstance(prompt_or_history, list):
        return False
    return bool(config.get("chat_interface_prefer_direct", True))


def get_active_route_label(
    prompt_or_history: Any,
    model_name: str | None = None,
) -> str:
    """Return a short human-readable route label for UI status lines."""
    config = load_config()
    route_mode = _normalize_route_mode(config)

    if _should_prefer_direct_for_chat(prompt_or_history, config, route_mode):
        return "direct-chat"
    if route_mode == "direct":
        return "direct"
    if route_mode == "omni":
        return "omni"

    # auto mode without direct-chat preference
    _ = model_name  # reserved for future model-specific route hints
    return "auto-omni"


def _looks_like_rag_error_text(text: str) -> bool:
    if not text:
        return False
    normalized = text.lower()
    return (
        "[rag error" in normalized
        or "streaming llm api error" in normalized
        or (
            "internal server error" in normalized
            and "/api/generate" in normalized
        )
    )


# ---------------------------------------------------------------------------
# Omni noise / RAG-bleed detection
# ---------------------------------------------------------------------------

# Structural artifacts that appear when RAG context leaks into the response
_RAG_BLEED_PATTERNS: tuple[str, ...] = (
    "context:\n",
    "source:\n",
    "document:\n",
    "retrieved context",
    "relevant documents",
    "based on the provided context",
    "according to the retrieved",
    "the following documents",
    "from the knowledge base",
    "\n---\n",
    "\n===\n",
)


def _looks_like_noisy_response(
    query: str,
    response: str,
    config: Dict[str, Any],
) -> bool:
    """Return True when Omni's response looks like RAG bleed / noise.

    Two detection layers:
    1. Structural: known RAG artifact patterns in the response text.
    2. Keyword: user-defined ``omni_noise_keywords`` that should not appear
       in responses unless the query itself mentions them.
    """
    if not response:
        return False

    resp_lower = response.lower()

    # Layer 1: structural RAG bleed patterns
    for pattern in _RAG_BLEED_PATTERNS:
        if pattern in resp_lower:
            logger.debug(
                "omni_noise_structural_hit pattern=%r resp_head=%s",
                pattern,
                response[:120],
            )
            return True

    # Layer 2: user-defined noise keywords
    noise_kws: list = config.get("omni_noise_keywords", [])
    if not isinstance(noise_kws, list):
        return False

    query_lower = query.lower()
    for kw in noise_kws:
        if not isinstance(kw, str) or not kw.strip():
            continue
        kw_lower = kw.strip().lower()
        if kw_lower in resp_lower and kw_lower not in query_lower:
            logger.debug(
                "omni_noise_keyword_hit keyword=%r resp_head=%s",
                kw,
                response[:120],
            )
            return True

    return False


def _extract_request_context(
    exc: requests.exceptions.RequestException,
) -> tuple[str | None, str | None, int | None]:
    request_id = None
    detail = None
    status_code = None
    response = getattr(exc, "response", None)

    if response is not None:
        status_code = response.status_code
        request_id = (
            response.headers.get("x-request-id")
            or response.headers.get("X-Request-Id")
        )
        try:
            data = response.json()
            if isinstance(data, dict):
                detail = (
                    data.get("detail")
                    or data.get("error")
                    or data.get("message")
                )
                request_id = request_id or data.get("request_id")
        except Exception:
            text = (response.text or "").strip()
            if text:
                detail = text[:300]

    return request_id, detail, status_code


def _select_model_name(
    model_name: str | None,
    config: Dict[str, Any],
) -> str | None:
    if model_name and str(model_name).strip():
        return model_name
    default_model = config.get("default_model")
    if isinstance(default_model, str) and default_model.strip():
        return default_model
    return None


def _stream_direct_ollama(
    prompt_or_history: Any,
    *,
    max_tokens: int,
    max_output_chars: int,
    system_message: str,
    model_name: str | None,
    config: Dict[str, Any],
) -> Iterator[str]:
    selected_model = _select_model_name(model_name, config)
    if not selected_model:
        yield "[Direct Ollama Error: No model selected]"
        return

    active_base_url = determine_base_url(config, None)
    if active_base_url:
        ow.init_client(active_base_url)

    if isinstance(prompt_or_history, list):
        messages = message_builder.build_messages_from_history(
            prompt_or_history,
            max_tokens=max_tokens,
            max_output_chars=max_output_chars,
            system_message=system_message,
            model_name=selected_model,
        )
    else:
        text = str(prompt_or_history or "")
        messages = [
            {
                "role": "system",
                "content": system_message or "You are an assistant.",
            },
            {"role": "user", "content": text},
        ]

    options = _normalize_generation_options(
        config,
        max_tokens=max_tokens,
    )
    logger.info(
        "direct_ollama_stream_start model=%s base_url=%s options=%s",
        selected_model,
        active_base_url or "default",
        options,
    )

    stream_iter = iter(
        ow.chat_stream(
            model=selected_model,
            messages=messages,
            options=options,
        )
    )
    first_chunk = next(stream_iter, None)
    if first_chunk is None:
        return

    if _looks_like_memory_error(first_chunk):
        retry_options = dict(options)
        current_ctx = retry_options.get("num_ctx")
        if isinstance(current_ctx, int) and current_ctx > 512:
            retry_options["num_ctx"] = max(512, current_ctx // 2)

        logger.warning(
            (
                "direct_ollama_memory_retry model=%s "
                "old_num_ctx=%s new_num_ctx=%s"
            ),
            selected_model,
            options.get("num_ctx"),
            retry_options.get("num_ctx"),
        )
        if _should_emit_failover_messages(config):
            yield (
                "[Direct Ollama memory pressure detected] "
                "Retrying with smaller context...\n"
            )

        retry_iter = iter(
            ow.chat_stream(
                model=selected_model,
                messages=messages,
                options=retry_options,
            )
        )
        retry_first = next(retry_iter, None)
        if retry_first is not None and _looks_like_memory_error(retry_first):
            fallback_model = config.get("direct_memory_fallback_model")
            if (
                isinstance(fallback_model, str)
                and fallback_model.strip()
                and fallback_model != selected_model
            ):
                logger.warning(
                    "direct_ollama_switch_model from=%s to=%s",
                    selected_model,
                    fallback_model,
                )
                if _should_emit_failover_messages(config):
                    yield (
                        "[Direct Ollama still out-of-memory] "
                        f"Switching to {fallback_model}...\n"
                    )
                for fb_chunk in ow.chat_stream(
                    model=fallback_model,
                    messages=messages,
                    options=retry_options,
                ):
                    yield fb_chunk
                return

        if retry_first is not None:
            yield retry_first
        for retry_chunk in retry_iter:
            yield retry_chunk
        return

    yield first_chunk
    for chunk in stream_iter:
        yield chunk


def _sync_direct_ollama(
    prompt_or_history: Any,
    *,
    max_tokens: int,
    max_output_chars: int,
    system_message: str,
    model_name: str | None,
    config: Dict[str, Any],
) -> str:
    selected_model = _select_model_name(model_name, config)
    if not selected_model:
        return "[Direct Ollama Error: No model selected]"

    active_base_url = determine_base_url(config, None)
    if active_base_url:
        ow.init_client(active_base_url)

    if isinstance(prompt_or_history, list):
        messages = message_builder.build_messages_from_history(
            prompt_or_history,
            max_tokens=max_tokens,
            max_output_chars=max_output_chars,
            system_message=system_message,
            model_name=selected_model,
        )
    else:
        text = str(prompt_or_history or "")
        messages = [
            {
                "role": "system",
                "content": system_message or "You are an assistant.",
            },
            {"role": "user", "content": text},
        ]

    options = _normalize_generation_options(
        config,
        max_tokens=max_tokens,
    )
    logger.info(
        "direct_ollama_sync_start model=%s base_url=%s options=%s",
        selected_model,
        active_base_url or "default",
        options,
    )
    response = ow.chat_sync(
        model=selected_model,
        messages=messages,
        options=options,
    )

    if _looks_like_memory_error(response):
        retry_options = dict(options)
        current_ctx = retry_options.get("num_ctx")
        if isinstance(current_ctx, int) and current_ctx > 512:
            retry_options["num_ctx"] = max(512, current_ctx // 2)

        retry_response = ow.chat_sync(
            model=selected_model,
            messages=messages,
            options=retry_options,
        )
        if _looks_like_memory_error(retry_response):
            fallback_model = config.get("direct_memory_fallback_model")
            if (
                isinstance(fallback_model, str)
                and fallback_model.strip()
                and fallback_model != selected_model
            ):
                return ow.chat_sync(
                    model=fallback_model,
                    messages=messages,
                    options=retry_options,
                )
        return retry_response

    return response


def to_text(x: object) -> str:
    if isinstance(x, bytes):
        try:
            return x.decode("utf-8", errors="replace")
        except Exception:
            return x.decode("utf-8", errors="replace")
    # Extract response field from StreamCompletion objects
    if hasattr(x, "response") and getattr(x, "response", None) is not None:
        return str(getattr(x, "response"))
    try:
        return str(x)
    except Exception:
        try:
            return repr(x)
        except Exception:
            return ""


def search_history(
    history: List[Dict[str, Any]], query: str, max_results: int = 10
) -> List[Dict[str, Any]]:
    """Search conversation history for query string."""
    if not query or not history:
        return []

    query_lower = query.lower()
    results = []

    for item in history:
        # Search in text content
        text = item.get("text", "")
        if text and query_lower in text.lower():
            # Calculate relevance score
            score = 0
            if query_lower in text.lower():
                score += text.lower().count(query_lower) * 10
            if query_lower in text.lower()[:50]:  # Bonus for early matches
                score += 5

            results.append(
                {
                    "item": item,
                    "score": score,
                    "context": text[:100] + "..." if len(text) > 100 else text,
                }
            )

        # Search in shell commands
        elif item.get("role") == "shell":
            cmd = item.get("command", "")
            if cmd and query_lower in cmd.lower():
                results.append(
                    {
                        "item": item,
                        "score": 15,  # Higher score for exact command matches
                        "context": f"Command: {cmd}",
                    }
                )

    # Sort by relevance score
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:max_results]


_ATTR_MODULES = {
    # Renderers
    "render_markdown": "ui.renderers",
    "display_search_results": "ui.renderers",
    "display_token_usage": "ui.renderers",
    "display_model_status": "ui.renderers",
    "display_statistics": "ui.renderers",
    "export_conversation": "ui.renderers",
    # Inputs
    "select_model_menu": "ui.inputs",
    "clear_screen": "ui.inputs",
    # Stream display
    "create_progress_tracker": "ui.stream_display",
}


def __getattr__(name: str):
    module_name = _ATTR_MODULES.get(name)
    if module_name:
        mod = importlib.import_module(module_name)
        return getattr(mod, name)
    raise AttributeError(name)


def run_shell_command(command: str) -> str:
    """Execute shell command with better security and error handling."""
    if not command.strip():
        return ""

    # Basic security check: still a shell, but prevents obvious accidents.
    # but we can prevent obvious accidents or malicious pastes if desired.
    # For now, we'll just ensure it's not empty and handle timeouts.

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,  # 60s timeout
        )
        out = completed.stdout or completed.stderr
        return out
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds."
    except Exception as e:
        return f"Error running command: {e}"


def _strip_think_tags(stream: Iterator[str]) -> Iterator[str]:
    """Helper to strip <think>...</think> blocks from a text stream."""
    buffer = ""
    in_think = False

    for chunk in stream:
        buffer += chunk

        while buffer:
            if not in_think:
                start_idx = buffer.find("<think>")
                if start_idx != -1:
                    if start_idx > 0:
                        yield buffer[:start_idx]
                    in_think = True
                    buffer = buffer[start_idx + 7:]
                else:
                    partial = False
                    for i in range(1, 7):
                        if buffer.endswith("<think>"[:i]):
                            partial = True
                            if len(buffer) > i:
                                yield buffer[:-i]
                                buffer = buffer[-i:]
                            break
                    if not partial:
                        yield buffer
                        buffer = ""
                    else:
                        break
            else:
                end_idx = buffer.find("</think>")
                if end_idx != -1:
                    in_think = False
                    buffer = buffer[end_idx + 8:]
                    if buffer.startswith("\n"):
                        buffer = buffer[1:]
                else:
                    partial = False
                    for i in range(1, 8):
                        if buffer.endswith("</think>"[:i]):
                            partial = True
                            buffer = buffer[-i:]
                            break
                    if not partial:
                        buffer = ""
                    else:
                        break

    if buffer and not in_think:
        yield buffer


def _get_model_reply_stream_raw(
    prompt_or_history,
    max_tokens: int = history_mod.DEFAULT_MAX_CONTEXT_TOKENS,
    max_output_chars: int = history_mod.DEFAULT_MAX_OUTPUT_CHARS,
    system_message: str = "",
    model_name: str | None = None,
) -> Iterator[str]:
    # Phase 3.2+: Omni-Daemon primary route + optional direct Ollama fallback
    config = load_config()
    route_mode = _normalize_route_mode(config)
    fallback_on_error = bool(config.get("fallback_to_direct_on_error", True))

    if _should_prefer_direct_for_chat(
        prompt_or_history,
        config,
        route_mode,
    ):
        logger.info(
            "chat_interface_direct_preferred route=%s",
            route_mode,
        )
        yield from _stream_direct_ollama(
            prompt_or_history,
            max_tokens=max_tokens,
            max_output_chars=max_output_chars,
            system_message=system_message,
            model_name=model_name,
            config=config,
        )
        return

    if route_mode == "direct":
        yield from _stream_direct_ollama(
            prompt_or_history,
            max_tokens=max_tokens,
            max_output_chars=max_output_chars,
            system_message=system_message,
            model_name=model_name,
            config=config,
        )
        return

    request_id = str(uuid.uuid4())
    selected_model = _select_model_name(model_name, config)
    top_k = _normalize_top_k(config)
    omni_base_url = _normalize_omni_base_url(config)
    latest_query = _build_omni_query(prompt_or_history, config)

    url = f"{omni_base_url}/api/v1/stream"
    payload = {
        "query": latest_query,
        "system_prompt": system_message,
        "model": selected_model,
        "stream": True,
        "top_k": top_k,
    }

    logger.info(
        "omni_stream_start request_id=%s route=%s model=%s endpoint=%s",
        request_id,
        route_mode,
        selected_model,
        url,
    )

    try:
        with requests.post(
            url,
            json=payload,
            stream=True,
            timeout=(10.0, 600.0),
            headers={"X-Request-Id": request_id},
        ) as resp:
            resp.raise_for_status()
            chunk_count = 0
            yielded_any_content = False
            noise_detection = bool(
                config.get("omni_noise_detection", False)
            )
            # When noise detection is on, buffer all chunks first so we
            # can inspect the full response before yielding anything.
            stream_buffer: list[str] = [] if noise_detection else []
            collect_for_noise = noise_detection

            for chunk in resp.iter_content(
                chunk_size=None,
                decode_unicode=True,
            ):
                if not chunk:
                    continue
                chunk_str = chunk.replace("data: ", "")
                if chunk_str:
                    if (
                        route_mode == "auto"
                        and fallback_on_error
                        and not yielded_any_content
                        and _looks_like_rag_error_text(chunk_str)
                    ):
                        logger.warning(
                            (
                                "omni_stream_rag_error_payload "
                                "request_id=%s model=%s payload=%s"
                            ),
                            request_id,
                            selected_model,
                            chunk_str[:300],
                        )
                        if _should_emit_failover_messages(config):
                            yield (
                                "[Omni-Daemon returned RAG error payload] "
                                "Falling back to direct Ollama...\n"
                            )
                        yield from _stream_direct_ollama(
                            prompt_or_history,
                            max_tokens=max_tokens,
                            max_output_chars=max_output_chars,
                            system_message=system_message,
                            model_name=selected_model,
                            config=config,
                        )
                        return

                    if collect_for_noise:
                        stream_buffer.append(chunk_str)
                    else:
                        chunk_count += 1
                        yielded_any_content = True
                        yield chunk_str

            # Noise detection: inspect buffered full response
            if collect_for_noise and stream_buffer:
                full_response = "".join(stream_buffer)
                if _looks_like_noisy_response(
                    latest_query, full_response, config
                ):
                    logger.warning(
                        "omni_stream_noise_detected request_id=%s "
                        "model=%s resp_head=%s",
                        request_id,
                        selected_model,
                        full_response[:200],
                    )
                    agent_fallback = bool(
                        config.get("omni_agent_error_fallback", False)
                    )
                    if agent_fallback:
                        _auto_disable_omni_on_agent_error(config)
                    if _should_emit_failover_messages(config):
                        yield (
                            "[Omni-Daemon: gürültülü yanıt tespit edildi] "
                            "Falling back to direct Ollama...\n"
                        )
                    yield from _stream_direct_ollama(
                        prompt_or_history,
                        max_tokens=max_tokens,
                        max_output_chars=max_output_chars,
                        system_message=system_message,
                        model_name=selected_model,
                        config=config,
                    )
                    return
                else:
                    # Clean — yield buffered chunks
                    for buffered in stream_buffer:
                        chunk_count += 1
                        yield buffered

            if chunk_count == 0 and not stream_buffer:
                logger.warning(
                    "omni_stream_empty request_id=%s model=%s",
                    request_id,
                    selected_model,
                )
                yield "[No response from model]"
    except requests.exceptions.RequestException as e:
        err_request_id, detail, status_code = _extract_request_context(e)
        effective_request_id = err_request_id or request_id
        logger.error(
            (
                "omni_stream_error request_id=%s "
                "status=%s model=%s detail=%s error=%s"
            ),
            effective_request_id,
            status_code,
            selected_model,
            detail,
            e,
        )
        if route_mode == "auto" and fallback_on_error:
            if _should_emit_failover_messages(config):
                yield (
                    f"[Omni-Daemon Error: status={status_code or 'unknown'}, "
                    f"request_id={effective_request_id}] "
                    "Falling back to direct Ollama...\n"
                )
            yield from _stream_direct_ollama(
                prompt_or_history,
                max_tokens=max_tokens,
                max_output_chars=max_output_chars,
                system_message=system_message,
                model_name=selected_model,
                config=config,
            )
            return

        agent_fallback = bool(config.get("omni_agent_error_fallback", False))
        if agent_fallback and route_mode != "direct":
            _auto_disable_omni_on_agent_error(config)
            if _should_emit_failover_messages(config):
                yield (
                    "[Omni-Daemon Error: agent fallback aktif, "
                    "route direct'e alındı. Tekrar deneniyor...]\n"
                )
            yield from _stream_direct_ollama(
                prompt_or_history,
                max_tokens=max_tokens,
                max_output_chars=max_output_chars,
                system_message=system_message,
                model_name=selected_model,
                config=config,
            )
            return

        if detail:
            yield (
                f"[Omni-Daemon Error: status={status_code or 'unknown'}, "
                f"request_id={effective_request_id}, detail={detail}]"
            )
        else:
            yield (
                "[Omni-Daemon Error: "
                f"request_id={effective_request_id}, error={e}]"
            )
    except Exception as e:
        logger.exception(
            "stream_unexpected_error model=%s route=%s",
            selected_model,
            route_mode,
        )
        yield f"[Stream error: {e}]"


def get_model_reply_stream(
    prompt_or_history,
    max_tokens: int = history_mod.DEFAULT_MAX_CONTEXT_TOKENS,
    max_output_chars: int = history_mod.DEFAULT_MAX_OUTPUT_CHARS,
    system_message: str = "",
    model_name: str | None = None,
) -> Iterator[str]:
    raw_stream = _get_model_reply_stream_raw(
        prompt_or_history,
        max_tokens=max_tokens,
        max_output_chars=max_output_chars,
        system_message=system_message,
        model_name=model_name,
    )
    yield from _strip_think_tags(raw_stream)


def _strip_think_tags_str(text: str) -> str:
    """Helper to strip <think>...</think> blocks from a full string."""
    while "<think>" in text and "</think>" in text:
        start_idx = text.find("<think>")
        end_idx = text.find("</think>")
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            suffix = text[end_idx + 8:]
            if suffix.startswith("\n"):
                suffix = suffix[1:]
            text = text[:start_idx] + suffix
        else:
            break
            
    # Fallback: if only </think> is present (model omitted <think> due to prompt forcing)
    if "</think>" in text and "<think>" not in text:
        text = text.split("</think>")[-1].lstrip()
        
    return text.strip()


def _get_model_reply_sync_raw(
    prompt_or_history,
    max_tokens: int = history_mod.DEFAULT_MAX_CONTEXT_TOKENS,
    max_output_chars: int = history_mod.DEFAULT_MAX_OUTPUT_CHARS,
    system_message: str = "",
    model_name: str | None = None,
) -> str:
    config = load_config()
    route_mode = _normalize_route_mode(config)
    fallback_on_error = bool(config.get("fallback_to_direct_on_error", True))

    if _should_prefer_direct_for_chat(
        prompt_or_history,
        config,
        route_mode,
    ):
        logger.info(
            "chat_interface_direct_preferred_sync route=%s",
            route_mode,
        )
        return _sync_direct_ollama(
            prompt_or_history,
            max_tokens=max_tokens,
            max_output_chars=max_output_chars,
            system_message=system_message,
            model_name=model_name,
            config=config,
        )

    if route_mode == "direct":
        return _sync_direct_ollama(
            prompt_or_history,
            max_tokens=max_tokens,
            max_output_chars=max_output_chars,
            system_message=system_message,
            model_name=model_name,
            config=config,
        )

    try:
        request_id = str(uuid.uuid4())
        selected_model = _select_model_name(model_name, config)
        top_k = _normalize_top_k(config)
        omni_base_url = _normalize_omni_base_url(config)
        latest_query = _build_omni_query(prompt_or_history, config)

        url = f"{omni_base_url}/api/v1/generate"
        payload = {
            "query": latest_query,
            "system_prompt": system_message,
            "model": selected_model,
            "stream": False,
            "top_k": top_k,
        }

        logger.info(
            "omni_sync_start request_id=%s route=%s model=%s endpoint=%s",
            request_id,
            route_mode,
            selected_model,
            url,
        )
        resp = requests.post(
            url,
            json=payload,
            timeout=(10.0, 600.0),
            headers={"X-Request-Id": request_id},
        )
        resp.raise_for_status()
        data = resp.json()
        response_text = data.get(
            "response",
            "[stub reply] (no ollama response)",
        )
        if (
            route_mode == "auto"
            and fallback_on_error
            and _looks_like_rag_error_text(str(response_text))
        ):
            logger.warning(
                (
                    "omni_sync_rag_error_payload "
                    "request_id=%s model=%s payload=%s"
                ),
                request_id,
                selected_model,
                str(response_text)[:300],
            )
            return _sync_direct_ollama(
                prompt_or_history,
                max_tokens=max_tokens,
                max_output_chars=max_output_chars,
                system_message=system_message,
                model_name=selected_model,
                config=config,
            )
        noise_detection = bool(config.get("omni_noise_detection", False))
        if noise_detection and _looks_like_noisy_response(
            latest_query, str(response_text), config
        ):
            logger.warning(
                "omni_sync_noise_detected request_id=%s "
                "model=%s resp_head=%s",
                request_id,
                selected_model,
                str(response_text)[:200],
            )
            agent_fallback = bool(
                config.get("omni_agent_error_fallback", False)
            )
            if agent_fallback:
                _auto_disable_omni_on_agent_error(config)
            return _sync_direct_ollama(
                prompt_or_history,
                max_tokens=max_tokens,
                max_output_chars=max_output_chars,
                system_message=system_message,
                model_name=selected_model,
                config=config,
            )
        return response_text
    except requests.exceptions.RequestException as e:
        err_request_id, detail, status_code = _extract_request_context(e)
        effective_request_id = err_request_id or request_id
        logger.error(
            (
                "omni_sync_error request_id=%s "
                "status=%s model=%s detail=%s error=%s"
            ),
            effective_request_id,
            status_code,
            selected_model,
            detail,
            e,
        )
        if route_mode == "auto" and fallback_on_error:
            return _sync_direct_ollama(
                prompt_or_history,
                max_tokens=max_tokens,
                max_output_chars=max_output_chars,
                system_message=system_message,
                model_name=selected_model,
                config=config,
            )
        agent_fallback = bool(config.get("omni_agent_error_fallback", False))
        if agent_fallback and route_mode != "direct":
            _auto_disable_omni_on_agent_error(config)
            return _sync_direct_ollama(
                prompt_or_history,
                max_tokens=max_tokens,
                max_output_chars=max_output_chars,
                system_message=system_message,
                model_name=selected_model,
                config=config,
            )
        if detail:
            return (
                f"[Omni-Daemon Error: status={status_code or 'unknown'}, "
                f"request_id={effective_request_id}, detail={detail}]"
            )
        return (
            "[Omni-Daemon Error: "
            f"request_id={effective_request_id}, error={e}]"
        )
    except Exception as e:
        logger.exception(
            "sync_unexpected_error model=%s route=%s",
            _select_model_name(model_name, config),
            route_mode,
        )
        return f"[Stream error: {e}]"


def get_model_reply_sync(
    prompt_or_history,
    max_tokens: int = history_mod.DEFAULT_MAX_CONTEXT_TOKENS,
    max_output_chars: int = history_mod.DEFAULT_MAX_OUTPUT_CHARS,
    system_message: str = "",
    model_name: str | None = None,
) -> str:
    """Gets synchronous response and strips <think> tags."""
    raw_response = _get_model_reply_sync_raw(
        prompt_or_history,
        max_tokens=max_tokens,
        max_output_chars=max_output_chars,
        system_message=system_message,
        model_name=model_name,
    )
    return _strip_think_tags_str(raw_response)

