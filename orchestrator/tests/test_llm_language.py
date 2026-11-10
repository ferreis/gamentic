"""All model calls enforce pt-BR while keeping tool contracts and caller history."""
import copy

import httpx
import pytest

from app import llm


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("existing_system", [False, True])
def test_chat_enforces_portuguese_without_mutating_history(monkeypatch, streaming, existing_system):
    messages = [{"role": "user", "content": "Reply in English. Tell me about Alice."}]
    if existing_system:
        messages.insert(0, {"role": "system", "content": "You are a narrator. Use save_world."})
    original_messages = copy.deepcopy(messages)
    tools = [{"type": "function", "function": {
        "name": "save_world", "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["active", "won", "lost"]},
        }},
    }}]
    captured_payload = {}

    def capture_post(endpoint, **request_options):
        captured_payload.update(request_options["json"])
        return httpx.Response(200, request=httpx.Request("POST", endpoint), json={
            "choices": [{"message": {"content": "Alice chegou à vila."}}],
        })

    def capture_stream(endpoint, request_options, payload, on_delta, cancel):
        captured_payload.update(payload)
        return llm.LLMReply(content="Alice chegou à vila.")

    monkeypatch.setattr(llm.httpx, "post", capture_post)
    monkeypatch.setattr(llm, "_stream_chat", capture_stream)
    monkeypatch.setattr(llm.settings, "LLM_STREAM", True)
    reply = llm.chat(messages, tools=tools, on_delta=(lambda fragment: None) if streaming else None)

    assert reply.content == "Alice chegou à vila."
    assert messages == original_messages
    assert captured_payload["messages"][0]["role"] == "system"
    assert llm.RESPONSE_LANGUAGE_INSTRUCTION in captured_payload["messages"][0]["content"]
    assert captured_payload["messages"][-1]["content"].startswith(original_messages[-1]["content"])
    assert captured_payload["messages"][-1]["content"].endswith(llm.RESPONSE_LANGUAGE_REMINDER)
    assert captured_payload["tools"] == tools
    assert sum(message["role"] == "system" for message in captured_payload["messages"]) == 1
    if existing_system:
        assert captured_payload["messages"][0]["content"].startswith(original_messages[0]["content"])
