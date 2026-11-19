"""
Recorded provider (Phase 8): replays a real model's responses so the AI
evaluation can run in CI without network access or cost.

A recording is a JSONL file: one {key, model, result} per request, where key
is a hash of everything that shapes the answer (model, messages, tools).
Recording wraps a live provider (record=True) and appends every response;
replay finds the response by key and fails if there is none, so a changed
prompt or tool list needs a new recording instead of reusing an old answer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .base import ChatResult, Message, ProviderError, ToolCall, ToolSpec, Usage


def request_key(messages: list[Message], tools: list[ToolSpec], model: str) -> str:
    canonical = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content, "tool_call_id": m.tool_call_id,
                      "tool_calls": [[c.name, c.arguments] for c in m.tool_calls], "is_error": m.is_error}
                     for m in messages],
        "tools": [[t.name, t.description, t.input_schema] for t in tools],
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def _result_to_json(result: ChatResult) -> dict[str, Any]:
    return {"text": result.text, "stop_reason": result.stop_reason, "model": result.model,
            "tool_calls": [{"id": c.id, "name": c.name, "arguments": c.arguments} for c in result.tool_calls],
            "usage": {"input_tokens": result.usage.input_tokens, "output_tokens": result.usage.output_tokens}}


def _result_from_json(data: dict[str, Any]) -> ChatResult:
    return ChatResult(text=data["text"], stop_reason=data["stop_reason"], model=data["model"],
                      tool_calls=[ToolCall(**c) for c in data.get("tool_calls", [])],
                      usage=Usage(**data.get("usage", {})))


class RecordedProvider:
    kind = "recorded"

    def __init__(self, path, inner=None, record: bool = False):
        self.path = Path(path)
        self.inner, self.record = inner, record
        if record and inner is None:
            raise ValueError("recording needs a live provider")
        self._entries: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self._entries[entry["key"]] = entry
        first = next(iter(self._entries.values()), None)
        self.model = inner.model if inner is not None else (first["model"] if first else "unrecorded")
        self.name = f"recorded:{inner.name}" if inner is not None else f"recorded:{self.path.stem}"
        self.external = False

    async def chat(self, messages: list[Message], tools: list[ToolSpec], *, max_tokens: int = 4096,
                   model: str | None = None) -> ChatResult:
        key = request_key(messages, tools, model or self.model)
        if self.record:
            result = await self.inner.chat(messages, tools, max_tokens=max_tokens, model=model)
            entry = {"key": key, "model": model or self.model, "result": _result_to_json(result)}
            self._entries[key] = entry
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")
            return result
        entry = self._entries.get(key)
        if entry is None:
            raise ProviderError(f"no recording for this request in {self.path.name}; re-record the evaluation")
        return _result_from_json(entry["result"])
