"""
OpenAI-compatible chat completions (POST {base_url}/chat/completions with
`tools`), which many hosted gateways and local servers (vLLM, LM Studio,
llama.cpp server, LiteLLM) implement.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .base import (
    ChatResult,
    Message,
    ProviderError,
    ToolCall,
    ToolSpec,
    Usage,
    retryable_status,
)

_FINISH = {"stop": "end", "tool_calls": "tool_use", "function_call": "tool_use", "length": "max_tokens",
           "content_filter": "refusal"}


class OpenAICompatibleProvider:
    kind = "openai_compatible"

    def __init__(self, *, name: str, base_url: str, model: str, api_key: str | None = None,
                 external: bool = True, timeout: float = 120.0, transport: httpx.AsyncBaseTransport | None = None):
        self.name, self.model, self.external = name, model, external
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._timeout, self._transport = timeout, transport

    @staticmethod
    def _message(m: Message) -> dict[str, Any]:
        if m.role == "tool":
            return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
        out: dict[str, Any] = {"role": m.role, "content": m.content or None}
        if m.role == "assistant" and m.tool_calls:
            out["tool_calls"] = [{"id": c.id, "type": "function",
                                  "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                                 for c in m.tool_calls]
        if out["content"] is None and m.role != "assistant":
            out["content"] = ""
        return out

    async def chat(self, messages: list[Message], tools: list[ToolSpec], *, max_tokens: int = 4096,
                   model: str | None = None) -> ChatResult:
        body: dict[str, Any] = {"model": model or self.model, "max_tokens": max_tokens,
                                "messages": [self._message(m) for m in messages]}
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                               "parameters": t.input_schema}} for t in tools]
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(self._url, json=body, headers=self._headers)
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name}: could not reach the provider ({type(e).__name__})",
                                retryable=True) from None
        if response.status_code >= 400:
            raise ProviderError(f"{self.name}: the provider returned HTTP {response.status_code}",
                                status=response.status_code, retryable=retryable_status(response.status_code))
        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice.get("message") or {}
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError(f"{self.name}: unexpected response shape") from None
        calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except ValueError:
                raise ProviderError(f"{self.name}: tool call arguments are not valid JSON") from None
            if not isinstance(arguments, dict):
                raise ProviderError(f"{self.name}: tool call arguments must be an object")
            calls.append(ToolCall(id=call.get("id") or f"call_{len(calls) + 1}", name=function.get("name", ""),
                                  arguments=arguments))
        usage = data.get("usage") or {}
        stop = _FINISH.get(choice.get("finish_reason") or "stop", "end")
        if calls:
            stop = "tool_use"
        return ChatResult(text=message.get("content") or "", tool_calls=calls, stop_reason=stop,
                          usage=Usage(int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)),
                          model=data.get("model") or body["model"], raw_assistant=None)
