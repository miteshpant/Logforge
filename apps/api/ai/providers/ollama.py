"""
Ollama (and other local runners with its API): POST {base_url}/api/chat,
non-streaming, with `tools`. Local by default, so `external` is false.
"""

from __future__ import annotations

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


class OllamaProvider:
    kind = "ollama"

    def __init__(self, *, name: str, base_url: str, model: str, external: bool = False, timeout: float = 300.0,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.name, self.model, self.external = name, model, external
        self._url = base_url.rstrip("/") + "/api/chat"
        self._timeout, self._transport = timeout, transport

    @staticmethod
    def _message(m: Message) -> dict[str, Any]:
        if m.role == "tool":
            return {"role": "tool", "content": m.content, "tool_name": m.name}
        out: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.role == "assistant" and m.tool_calls:
            out["tool_calls"] = [{"function": {"name": c.name, "arguments": c.arguments}} for c in m.tool_calls]
        return out

    async def chat(self, messages: list[Message], tools: list[ToolSpec], *, max_tokens: int = 4096,
                   model: str | None = None) -> ChatResult:
        body: dict[str, Any] = {"model": model or self.model, "stream": False,
                                "messages": [self._message(m) for m in messages],
                                "options": {"num_predict": max_tokens}}
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                               "parameters": t.input_schema}} for t in tools]
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(self._url, json=body)
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name}: could not reach the model server ({type(e).__name__})",
                                retryable=True) from None
        if response.status_code >= 400:
            raise ProviderError(f"{self.name}: the model server returned HTTP {response.status_code}",
                                status=response.status_code, retryable=retryable_status(response.status_code))
        try:
            data = response.json()
            message = data.get("message") or {}
        except ValueError:
            raise ProviderError(f"{self.name}: unexpected response shape") from None
        calls = []
        for i, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function") or {}
            arguments = function.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise ProviderError(f"{self.name}: tool call arguments must be an object")
            calls.append(ToolCall(id=call.get("id") or f"ollama_{i + 1}", name=function.get("name", ""),
                                  arguments=arguments))
        reason = data.get("done_reason") or "stop"
        stop = "tool_use" if calls else ("max_tokens" if reason == "length" else "end")
        return ChatResult(text=message.get("content") or "", tool_calls=calls, stop_reason=stop,
                          usage=Usage(int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0)),
                          model=data.get("model") or body["model"], raw_assistant=None)
