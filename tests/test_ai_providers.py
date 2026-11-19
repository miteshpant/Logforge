"""
AI providers (Phase 8): one interface for chat with tool calling, and
adapters for an OpenAI-compatible endpoint, Anthropic and Ollama.

A provider takes a conversation in one neutral form (system / user /
assistant / tool messages, with tool calls) and returns a ChatResult: the
text, the tool calls the model asked for, why it stopped, and token usage.
Adapters translate both ways; these tests pin the wire format each adapter
sends and how it reads the reply, with the HTTP mocked.

Providers are configured per deployment (config/ai.yml) and none is
enabled by default.
"""

import asyncio
import json

import httpx
import httpx2
import pytest
from ai.providers import (
    ChatResult,
    Message,
    ProviderConfigError,
    ProviderError,
    ToolCall,
    ToolSpec,
    build_provider,
    load_ai_config,
)
from ai.providers.anthropic_provider import AnthropicProvider
from ai.providers.ollama import OllamaProvider
from ai.providers.openai_compatible import OpenAICompatibleProvider

TOOLS = [ToolSpec(name="run_query", description="Run a LogforgeQL query",
                  input_schema={"type": "object", "properties": {"query": {"type": "string"}},
                                "required": ["query"]})]

CONVERSATION = [
    Message(role="system", content="Answer from tool results."),
    Message(role="user", content="How many failed logins?"),
    Message(role="assistant", content="", tool_calls=[ToolCall(id="call_1", name="run_query",
                                                               arguments={"query": "| stats count()"})]),
    Message(role="tool", content='{"rows": [{"n": 3}]}', tool_call_id="call_1", name="run_query"),
]


def run(coro):
    return asyncio.run(coro)


# -- configuration -------------------------------------------------------------

def test_the_shipped_config_enables_nothing():
    config = load_ai_config()
    assert config.enabled is False
    assert config.providers == {}


def test_config_lists_providers_and_reads_keys_from_the_environment(tmp_path, monkeypatch):
    path = tmp_path / "ai.yml"
    path.write_text("""
enabled: true
providers:
  claude: {kind: anthropic, model: claude-opus-5-5, api_key_env: TEST_ANTHROPIC_KEY}
  local: {kind: ollama, base_url: "http://ollama:11434", model: llama3.1}
""")
    config = load_ai_config(path)
    assert config.enabled and set(config.providers) == {"claude", "local"}
    assert config.providers["claude"].external is True       # hosted by default
    assert config.providers["local"].external is False       # ollama runs locally
    with pytest.raises(ProviderConfigError, match="TEST_ANTHROPIC_KEY"):
        build_provider(config.providers["claude"])           # the key isn't set
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", "sk-test")
    assert isinstance(build_provider(config.providers["claude"]), AnthropicProvider)


def test_the_environment_can_switch_ai_off_but_not_on(tmp_path, monkeypatch):
    path = tmp_path / "ai.yml"
    path.write_text("enabled: true\nproviders: {}\n")
    monkeypatch.setenv("LOGFORGE_AI_ENABLED", "false")
    assert load_ai_config(path).enabled is False
    path.write_text("enabled: false\nproviders: {}\n")
    monkeypatch.setenv("LOGFORGE_AI_ENABLED", "true")
    assert load_ai_config(path).enabled is False


def test_bad_provider_entries_are_rejected(tmp_path):
    path = tmp_path / "ai.yml"
    path.write_text("enabled: true\nproviders:\n  x: {kind: magic, model: m}\n")
    with pytest.raises(ProviderConfigError, match="kind"):
        load_ai_config(path)
    path.write_text("enabled: true\nproviders:\n  x: {kind: openai_compatible}\n")
    with pytest.raises(ProviderConfigError, match="model"):
        load_ai_config(path)


# -- OpenAI-compatible -------------------------------------------------------------

def openai_provider(handler):
    return OpenAICompatibleProvider(name="gw", base_url="https://gw.example/v1", api_key="k-123",
                                    model="m-1", transport=httpx.MockTransport(handler))


def test_openai_compatible_request_and_tool_call_reply():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "m-1",
            "choices": [{"finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "call_2", "type": "function",
                                "function": {"name": "run_query", "arguments": '{"query": "| head 5"}'}}]}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 17}})

    result = run(openai_provider(handler).chat(CONVERSATION, TOOLS, max_tokens=500))
    body = seen["body"]
    assert seen["url"] == "https://gw.example/v1/chat/completions" and seen["auth"] == "Bearer k-123"
    assert body["model"] == "m-1" and body["max_tokens"] == 500
    assert body["tools"] == [{"type": "function", "function": {
        "name": "run_query", "description": "Run a LogforgeQL query", "parameters": TOOLS[0].input_schema}}]
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "tool"]
    assert body["messages"][2]["tool_calls"][0]["function"] == {"name": "run_query",
                                                               "arguments": '{"query": "| stats count()"}'}
    assert body["messages"][3] == {"role": "tool", "tool_call_id": "call_1", "content": '{"rows": [{"n": 3}]}'}
    assert "tool_choice" not in body
    assert result.stop_reason == "tool_use"
    assert result.tool_calls == [ToolCall(id="call_2", name="run_query", arguments={"query": "| head 5"})]
    assert (result.usage.input_tokens, result.usage.output_tokens) == (120, 17)


def test_openai_compatible_text_reply_and_errors():
    def text(request):
        return httpx.Response(200, json={"model": "m-1", "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": "Three [C1]."}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3}})

    result = run(openai_provider(text).chat(CONVERSATION[:2], TOOLS))
    assert result == ChatResult(text="Three [C1].", tool_calls=[], stop_reason="end",
                                usage=result.usage, model="m-1", raw_assistant=None)

    with pytest.raises(ProviderError) as limited:
        run(openai_provider(lambda r: httpx.Response(429, json={"error": "slow down"})).chat(CONVERSATION, TOOLS))
    assert limited.value.retryable and limited.value.status == 429
    with pytest.raises(ProviderError) as bad:
        run(openai_provider(lambda r: httpx.Response(400, json={"error": "bad"})).chat(CONVERSATION, TOOLS))
    assert not bad.value.retryable

    def broken_args(request):
        return httpx.Response(200, json={"model": "m-1", "choices": [{"finish_reason": "tool_calls", "message": {
            "role": "assistant", "tool_calls": [{"id": "c", "type": "function",
                                                 "function": {"name": "run_query", "arguments": "{not json"}}]}}]})

    with pytest.raises(ProviderError, match="arguments"):
        run(openai_provider(broken_args).chat(CONVERSATION, TOOLS))


def test_provider_errors_never_echo_the_api_key():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(ProviderError) as e:
        run(openai_provider(handler).chat(CONVERSATION, TOOLS))
    assert e.value.retryable and "k-123" not in str(e.value)


# -- Anthropic -------------------------------------------------------------------

def anthropic_reply(content, stop_reason="end_turn", model="claude-opus-5-5"):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": model, "content": content,
            "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": 200, "output_tokens": 40}}


def anthropic_provider(handler, **kw):
    return AnthropicProvider(name="claude", api_key="sk-test", model="claude-opus-5-5",
                             transport=httpx2.MockTransport(handler), **kw)


def test_anthropic_request_shape():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["beta"] = request.headers.get("anthropic-beta")
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=anthropic_reply([
            {"type": "thinking", "thinking": "", "signature": "sig-1"},
            {"type": "text", "text": "Let me check."},
            {"type": "tool_use", "id": "tu_2", "name": "run_query", "input": {"query": "| head 5"}}],
            stop_reason="tool_use"))

    result = run(anthropic_provider(handler, effort="medium").chat(CONVERSATION, TOOLS, max_tokens=4000))
    body = seen["body"]
    assert seen["path"] == "/v1/messages"
    assert body["model"] == "claude-opus-5-5" and body["max_tokens"] == 4000
    assert body["system"] == "Answer from tool results."
    assert body["output_config"] == {"effort": "medium"}
    assert "tool_choice" not in body and "thinking" not in body and "temperature" not in body
    assert body["tools"] == [{"name": "run_query", "description": "Run a LogforgeQL query",
                              "input_schema": TOOLS[0].input_schema}]
    # refusal fallbacks are on by default (server-side, routed by category)
    assert seen["beta"] == "server-side-fallback-2026-07-01" and body["fallbacks"] == "default"
    # the tool call goes out as a tool_use block, its result as a tool_result in the next user turn
    assert body["messages"][1]["content"] == [{"type": "tool_use", "id": "call_1", "name": "run_query",
                                               "input": {"query": "| stats count()"}}]
    assert body["messages"][2] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "call_1", "content": '{"rows": [{"n": 3}]}'}]}
    assert result.stop_reason == "tool_use" and result.text == "Let me check."
    assert result.tool_calls == [ToolCall(id="tu_2", name="run_query", arguments={"query": "| head 5"})]
    assert (result.usage.input_tokens, result.usage.output_tokens) == (200, 40)
    # the whole assistant turn, thinking block included, is kept to send back unchanged
    assert [b["type"] for b in result.raw_assistant] == ["thinking", "text", "tool_use"]


def test_anthropic_sends_earlier_assistant_turns_back_unchanged_and_merges_tool_results():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=anthropic_reply([{"type": "text", "text": "Done [C1][C2]."}]))

    raw = [{"type": "thinking", "thinking": "", "signature": "sig-1"},
           {"type": "tool_use", "id": "tu_a", "name": "run_query", "input": {"query": "a"}},
           {"type": "tool_use", "id": "tu_b", "name": "run_query", "input": {"query": "b"}}]
    conversation = [
        Message(role="user", content="Compare a and b"),
        Message(role="assistant", content="", raw=raw, tool_calls=[
            ToolCall(id="tu_a", name="run_query", arguments={"query": "a"}),
            ToolCall(id="tu_b", name="run_query", arguments={"query": "b"})]),
        Message(role="tool", content="A", tool_call_id="tu_a", name="run_query"),
        Message(role="tool", content="B", tool_call_id="tu_b", name="run_query", is_error=True),
    ]
    result = run(anthropic_provider(handler, fallbacks=False).chat(conversation, TOOLS))
    body = seen["body"]
    assert "system" not in body and "fallbacks" not in body
    assert body["messages"][1] == {"role": "assistant", "content": raw}
    assert body["messages"][2] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "tu_a", "content": "A"},
        {"type": "tool_result", "tool_use_id": "tu_b", "content": "B", "is_error": True}]}
    assert result.stop_reason == "end" and result.text == "Done [C1][C2]."


def test_anthropic_refusals_and_errors():
    refused = run(anthropic_provider(lambda r: httpx2.Response(200, json=anthropic_reply(
        [], stop_reason="refusal"))).chat(CONVERSATION[:2], TOOLS))
    assert refused.stop_reason == "refusal" and refused.text == ""

    with pytest.raises(ProviderError) as limited:
        run(anthropic_provider(lambda r: httpx2.Response(429, json={
            "type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}), max_retries=0)
            .chat(CONVERSATION[:2], TOOLS))
    assert limited.value.retryable and limited.value.status == 429
    with pytest.raises(ProviderError) as bad:
        run(anthropic_provider(lambda r: httpx2.Response(400, json={
            "type": "error", "error": {"type": "invalid_request_error", "message": "bad"}}))
            .chat(CONVERSATION[:2], TOOLS))
    assert not bad.value.retryable and "sk-test" not in str(bad.value)


# -- Ollama ----------------------------------------------------------------------

def test_ollama_chat_with_tools():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "llama3.1", "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": "",
                        "tool_calls": [{"function": {"name": "run_query", "arguments": {"query": "| head 1"}}}]},
            "prompt_eval_count": 90, "eval_count": 12})

    provider = OllamaProvider(name="local", base_url="http://ollama:11434", model="llama3.1",
                              transport=httpx.MockTransport(handler))
    result = run(provider.chat(CONVERSATION, TOOLS, max_tokens=300))
    body = seen["body"]
    assert seen["url"] == "http://ollama:11434/api/chat"
    assert body["stream"] is False and body["model"] == "llama3.1" and body["options"]["num_predict"] == 300
    assert body["tools"][0]["function"]["name"] == "run_query"
    assert body["messages"][2]["tool_calls"] == [{"function": {"name": "run_query",
                                                              "arguments": {"query": "| stats count()"}}}]
    assert body["messages"][3] == {"role": "tool", "content": '{"rows": [{"n": 3}]}', "tool_name": "run_query"}
    assert result.stop_reason == "tool_use"
    assert result.tool_calls[0].name == "run_query" and result.tool_calls[0].arguments == {"query": "| head 1"}
    assert result.tool_calls[0].id  # Ollama sends none; the adapter makes one up
    assert (result.usage.input_tokens, result.usage.output_tokens) == (90, 12)
