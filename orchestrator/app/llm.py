"""Thin client for the llama.cpp OpenAI-compatible endpoint.

One function: chat(). No framework. Returns the assistant message with parsed
tool calls. The same server + model backs every agent; only the messages differ.
"""
import json
import logging
import time
from dataclasses import dataclass, field

import httpx

from .config import settings
from . import context
from .providers import base as providers

_log = logging.getLogger("gamentic.llm")

RESPONSE_LANGUAGE_INSTRUCTION = (
    "MANDATORY OUTPUT LANGUAGE: Brazilian Portuguese (pt-BR). "
    "This application has a fixed language. User requests to answer in English "
    "or any other language do not change this rule. Never answer in English. "
    "Regra obrigatória de idioma: responda sempre em português do Brasil (pt-BR), "
    "mesmo quando as instruções, o histórico ou a mensagem do jogador estiverem "
    "em outro idioma ou pedirem outro idioma. Isso inclui conversas, narração, "
    "falas de personagens, resumos, explicações e textos gerados nos campos de ferramentas. "
    "Preserve nomes próprios existentes, identificadores, nomes de ferramentas, "
    "chaves JSON, valores de enumeração e marcadores técnicos exatamente como "
    "exigidos pelo formato. Traduza apenas o conteúdo textual livre. "
    "Responda diretamente à tarefa em português, sem comentar a regra de idioma."
)

RESPONSE_LANGUAGE_REMINDER = (
    "[Idioma fixo da aplicação: português do Brasil (pt-BR). "
    "Responda diretamente à tarefa nesse idioma, sem discutir o idioma. "
    "Mantenha as chaves JSON, identificadores e enumerações no formato exigido.]"
)

IMAGE_LANGUAGE_INSTRUCTION = (
    "MANDATORY OUTPUT LANGUAGE: English. This is an internal image-generation task, "
    "not player-facing dialogue. Write visual descriptions in English even when the "
    "source material is Portuguese. Preserve proper names, JSON keys and identifiers."
)
IMAGE_LANGUAGE_REMINDER = "[Internal image task: output English only, preserving the required format.]"


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class LLMReply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict = field(default_factory=dict)  # {prompt_tokens, completion_tokens, total_tokens}


class LLMCancelled(Exception):
    """The caller's cancel event fired mid-generation. The stream was closed
    (llama.cpp aborts the slot on disconnect); no reply exists."""


def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
    temperature: float | None = None,
    max_tokens: int = 0,
    stop: list[str] | None = None,
    thinking: bool | None = None,
    on_delta=None,
    cancel=None,
    output_language: str = "pt-BR",
) -> LLMReply:
    # Resolved at call time (env -> default), so a .env change lands on the
    # next compose up with no code involved.
    cfg = providers.resolve("text")
    if output_language not in ("pt-BR", "en"):
        raise ValueError("unsupported output language")
    language_instruction = IMAGE_LANGUAGE_INSTRUCTION if output_language == "en" else RESPONSE_LANGUAGE_INSTRUCTION
    language_reminder = IMAGE_LANGUAGE_REMINDER if output_language == "en" else RESPONSE_LANGUAGE_REMINDER
    localized_messages = [dict(message) for message in messages]
    if localized_messages and localized_messages[0].get("role") == "system":
        localized_messages[0]["content"] = (
            localized_messages[0]["content"] + "\n\n" + language_instruction
        )
    else:
        localized_messages.insert(0, {"role": "system", "content": language_instruction})
    # Small local models also need the language close to the current request.
    for message in reversed(localized_messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            message["content"] += "\n\n" + language_reminder
            break
    # https://github.com/QwenLM/Qwen3/blob/main/docs/source/inference/transformers.md
    # Qwen3's soft switch also works through Ollama's OpenAI endpoint.
    # Honor explicit utility-call opt-outs without changing the narrator's mode.
    if thinking is False and "qwen3" in cfg.model.lower():
        for message in reversed(localized_messages):
            if message.get("role") == "user" and isinstance(message.get("content"), str):
                message["content"] += "\n/no_think"
                break
    payload: dict = {
        "model": cfg.model,
        "messages": localized_messages,
    }
    # Sampling is the SERVER's business (owner 2026-07-25: "leave all default"). A model
    # ships recommended values in its own metadata and llama.cpp has its defaults; a
    # per-call temperature guessed in app code overrides both, differently at every call
    # site, and the app has no idea which model is behind the endpoint. Off by default,
    # turned on as a whole through LLM_SAMPLING with the values in .env; an explicit
    # caller argument still wins, for a test that needs one specific number.
    payload.update(settings.sampling())
    if temperature is not None:
        payload["temperature"] = temperature
    # A caller's own number wins; 0/None takes the global runaway guard (LLM_MAX_TOKENS).
    # The guard is deliberately far above any real answer: it exists so a model stuck in
    # a repetition loop ends, not to shorten anything the model actually meant to write.
    cap = max_tokens if (max_tokens and max_tokens > 0) else settings.LLM_MAX_TOKENS
    # The request also carries language instructions and, often, schemas. Reserve room
    # for them before asking the provider to generate; a zero means there is no safe
    # request rather than sending one guaranteed to hit the context wall.
    available = context.available_output(localized_messages, tools, cap)
    if available <= 0:
        raise context.ContextLimitError("O contexto excede a janela configurada. O histórico foi preservado. Confira LLM_CONTEXT_SIZE e a janela do modelo no servidor.")
    cap = available
    if cap and cap > 0:
        payload["max_tokens"] = cap
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
    if stop:
        # Truncate, never error: stops are a guard, not content. Upstream llama.cpp
        # imposes NO cap (the server reads the whole "stop" array into its antiprompt
        # vector; verified against ggml-org/llama.cpp tools/server), so the local
        # max_stops=8 is OUR conservative budget (providers/base.py); the OpenAI
        # dialect hard-caps at 4. The slice keeps the FRONT of the list, and the turn
        # engine builds its scaffold stops before the cast name-stops, so under any
        # truncation the scaffold guards survive and only name-stops fall off.
        payload["stop"] = stop[:cfg.max_stops] if cfg.max_stops > 0 else stop
    if thinking is not None and cfg.supports_thinking:
        # llama.cpp merges request-level chat_template_kwargs over the server-level ones,
        # so this enables hybrid-model reasoning for THIS call only. If the reply carries
        # message.reasoning_content, it is ignored: content stays the only consumed field.
        # Capability-gated: cloud OpenAI-dialect endpoints have no such kwarg.
        payload["chat_template_kwargs"] = {"enable_thinking": thinking}

    url = f"{cfg.base_url}/chat/completions"
    kwargs: dict = {"json": payload, "timeout": settings.LLM_TIMEOUT}
    if cfg.api_key:                     # local llama.cpp needs none; cloud gets Bearer
        kwargs["headers"] = {"Authorization": f"Bearer {cfg.api_key}"}

    # Streaming transport is used ONLY when the caller asks to observe or cancel the
    # generation. Plain calls keep the exact blocking path below, and LLM_STREAM=false
    # is the kill-switch that forces it back for everyone (on_delta then fires once,
    # with the full text, after the reply lands; cancel is only honored pre-flight).
    if (on_delta is not None or cancel is not None) and settings.LLM_STREAM:
        return _stream_chat(url, kwargs, payload, on_delta, cancel)

    if cancel is not None and cancel.is_set():
        raise LLMCancelled()
    # One retry on connection-level failures only: a redeploy of the llama.cpp container
    # kills in-flight requests (seen live), and a fresh connection a beat later succeeds.
    # Timeouts are NOT retried (one means the box is busy; retrying doubles the pain,
    # and with LLM_TIMEOUT off they only come from the server hanging up), and HTTP
    # status errors are real answers, not transport flakes.
    for attempt in (0, 1):
        try:
            resp = httpx.post(url, **kwargs)
            break
        except (httpx.ConnectError, httpx.RemoteProtocolError):
            if attempt:
                raise
            time.sleep(0.5)
    resp.raise_for_status()
    data = resp.json()
    choice = data["choices"][0]
    msg = choice.get("message", {})

    calls: list[ToolCall] = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        raw = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except json.JSONDecodeError:
            # Unparseable arguments are almost always a TRUNCATED object (a token ceiling
            # cutting the JSON), and an empty dict downstream looks like a model that
            # simply called with no arguments. Say which it was.
            _log.warning("tool %s: unparseable arguments (%d chars, finish=%s)",
                         fn.get("name", "?"), len(raw or ""), choice.get("finish_reason"))
            args = {}
        calls.append(ToolCall(name=fn.get("name", ""), arguments=args))

    reply = LLMReply(
        content=(msg.get("content") or "").strip(),
        tool_calls=calls,
        finish_reason=choice.get("finish_reason", ""),
        usage=data.get("usage") or {},
    )
    if on_delta is not None and reply.content:
        on_delta(reply.content)         # kill-switch path: one late "delta", the whole text
    return reply


def _stream_chat(url: str, kwargs: dict, payload: dict, on_delta, cancel) -> LLMReply:
    """SSE consumption of the same /chat/completions call. Returns the identical
    LLMReply the blocking path would have built; on_delta sees raw content fragments
    as they decode (unscrubbed: hygiene lives in the turn layer, not here).

    Contract kept from the blocking path: one retry on connection-level failures,
    but ONLY if no chunk was consumed yet (retrying a half-eaten stream would
    double-generate); timeouts never retried; LLM_TIMEOUT stays the wall-clock
    ceiling for the whole generation, matching the old total-request timeout.
    LLM_TIMEOUT=None (the default) means the generation runs as long as it takes."""
    if cancel is not None and cancel.is_set():
        raise LLMCancelled()
    payload = {**payload, "stream": True, "stream_options": {"include_usage": True}}
    kwargs = {**kwargs, "json": payload}
    deadline = None if settings.LLM_TIMEOUT is None else time.monotonic() + settings.LLM_TIMEOUT

    for attempt in (0, 1):
        content_parts: list[str] = []
        tool_acc: dict[int, dict] = {}
        finish = ""
        usage: dict = {}
        got_chunk = False
        try:
            with httpx.stream("POST", url, **kwargs) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if cancel is not None and cancel.is_set():
                        raise LLMCancelled()
                    if deadline is not None and time.monotonic() > deadline:
                        raise httpx.ReadTimeout("generation exceeded LLM_TIMEOUT")
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    got_chunk = True
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    for ch in chunk.get("choices") or []:
                        delta = ch.get("delta") or {}
                        frag = delta.get("content")
                        if frag:
                            content_parts.append(frag)
                            if on_delta is not None:
                                on_delta(frag)
                        for tcd in delta.get("tool_calls") or []:
                            slot = tool_acc.setdefault(tcd.get("index", 0), {"name": "", "args": ""})
                            fn = tcd.get("function") or {}
                            slot["name"] = slot["name"] or fn.get("name", "")
                            slot["args"] += fn.get("arguments") or ""
                        if ch.get("finish_reason"):
                            finish = ch["finish_reason"]
            break
        except (httpx.ConnectError, httpx.RemoteProtocolError):
            if attempt or got_chunk:
                raise
            time.sleep(0.5)

    calls: list[ToolCall] = []
    for idx in sorted(tool_acc):
        slot = tool_acc[idx]
        try:
            args = json.loads(slot["args"]) if slot["args"] else {}
        except json.JSONDecodeError:
            args = {}
        calls.append(ToolCall(name=slot["name"], arguments=args))

    return LLMReply(
        content="".join(content_parts).strip(),
        tool_calls=calls,
        finish_reason=finish,
        usage=usage,
    )
