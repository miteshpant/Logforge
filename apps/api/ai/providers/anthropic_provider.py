"""
Anthropic (Claude) through the official SDK's Messages API.

* The assistant turn's content blocks (thinking blocks included) are kept
  as `raw` and sent back unchanged on the next request.
* Tool results for one assistant turn go back together in a single user
  message.
* Tool choice is left to the model (`auto`): current models reject forced
  tool choice, and the system prompt says when to use tools.
* Server-side refusal fallbacks are on by default (`fallbacks: "default"`),
  so a request declined by a safety classifier is retried on a fallback
  model in the same call; set `fallbacks: false` to turn that off.
* `effort` maps to `output_config.effort`. Thinking is left at the model's
  default (adaptive on current models).
"""

from __future__ import annotations

from typing import Any

import anthropic

from .base import ChatResult, Message, ProviderError, ToolCall, ToolSpec, Usage

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
_STOP = {"end_turn": "end", "stop_sequence": "end", "tool_use": "tool_use", "max_tokens": "max_tokens",
         "refusal": "refusal", "pause_turn": "end"}


class AnthropicProvider:
    kind = "anthropic"

    def __init__(self, *, name: str, api_key: str, model: str = DEFAULT_MODEL, base_url: str | None = None,
                 external: bool = True, effort: str | None = None, fallbacks: bool = True,
                 timeout: float = 300.0, max_retries: int = 2, transport: Any = None):
        self.name, self.model, self.external = name, model, external
        self.effort, self.fallbacks = effort, fallbacks
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout, "max_retries": max_retries}
        if base_url:
            kwargs["base_url"] = base_url
        if transport is not None:
            kwargs["http_client"] = anthropic.DefaultAsyncHttpxClient(transport=transport)
        self._client = anthropic.AsyncAnthropic(**kwargs)

    @staticmethod
    def _messages(messages: list[Message]):
        system = "\n\n".join(m.content for m in messages if m.role == "system" and m.content)
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool":
                block: dict[str, Any] = {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
                if m.is_error:
                    block["is_error"] = True
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) and all(
                        b.get("type") == "tool_result" for b in out[-1]["content"]):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            elif m.role == "assistant":
                if m.raw is not None:
                    content = m.raw
                else:
                    content = ([{"type": "text", "text": m.content}] if m.content else []) + [
                        {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in m.tool_calls]
                out.append({"role": "assistant", "content": content})
            else:
                out.append({"role": "user", "content": m.content})
        return system, out

    async def chat(self, messages: list[Message], tools: list[ToolSpec], *, max_tokens: int = 16000,
                   model: str | None = None) -> ChatResult:
        system, wire = self._messages(messages)
        params: dict[str, Any] = {"model": model or self.model, "max_tokens": max_tokens, "messages": wire}
        if system:
            params["system"] = system
        if tools:
            params["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.input_schema}
                               for t in tools]
        if self.effort:
            params["output_config"] = {"effort": self.effort}
        try:
            if self.fallbacks:
                response = await self._client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default",
                                                                   **params)
            else:
                response = await self._client.messages.create(**params)
        except anthropic.APIStatusError as e:
            status = e.status_code
            retryable = status in (408, 409, 429) or status >= 500
            raise ProviderError(f"{self.name}: Anthropic returned HTTP {status} ({type(e).__name__})",
                                status=status, retryable=retryable) from None
        except anthropic.APIConnectionError as e:
            raise ProviderError(f"{self.name}: could not reach Anthropic ({type(e).__name__})",
                                retryable=True) from None
        text, calls = [], []
        for block in response.content:
            if block.type == "text":
                text.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input or {})))
        stop = _STOP.get(response.stop_reason or "end_turn", "end")
        if calls and stop != "refusal":
            stop = "tool_use"
        return ChatResult(text="".join(text), tool_calls=calls, stop_reason=stop,
                          usage=Usage(int(response.usage.input_tokens or 0), int(response.usage.output_tokens or 0)),
                          model=response.model, raw_assistant=[b.to_dict() for b in response.content])
