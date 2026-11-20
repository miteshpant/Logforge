"""
AI features scored by the evaluation harness (Phase 8), and the recorded
provider that lets CI run them without calling a model.

* nl2query: a question becomes one LogforgeQL query; anything that doesn't
  compile is no answer (None), never passed on.
* summarise: evidence {E1: ...} becomes a short summary citing [E#].
* RecordedProvider: replays responses recorded from a real model, keyed by a
  hash of the request; a request with no recording fails loudly, so a
  changed prompt can't silently pass on an old answer.
"""

import asyncio
import json

import pytest
from ai.features import nl2query, summarise
from ai.providers import ChatResult, Message, ProviderError, Usage
from ai.providers.recorded import RecordedProvider, request_key


class Canned:
    name, kind, model, external = "canned", "canned", "canned-1", False

    def __init__(self, text):
        self.text, self.calls = text, 0

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        self.calls += 1
        self.last = messages
        return ChatResult(text=self.text, tool_calls=[], stop_reason="end", usage=Usage(10, 5), model=self.model)


def run(coro):
    return asyncio.run(coro)


def test_nl2query_returns_a_compiling_query():
    """The evaluated feature is the product's (ai.nl2query.translate)."""
    q = '| where service = "auth" | stats count() by level'
    provider = Canned(json.dumps({"query": q, "explanation": "Auth logs by level."}))
    assert run(nl2query("Break down auth logs by level", provider)) == q
    assert provider.last[0].role == "system" and "LogforgeQL" in provider.last[0].content
    assert run(nl2query("q", Canned("I am not sure what you mean."))) is None


def test_summarise_passes_the_evidence_and_returns_the_text():
    provider = Canned("bastion-01 saw 15 failed root logins [E1]. Then one succeeded [E2].")
    out = run(summarise("Summarise this alert.", {"E1": "15x failed", "E2": "accepted"}, provider))
    assert out.startswith("bastion-01")
    user = next(m for m in provider.last if m.role == "user")
    assert "[E1] 15x failed" in user.content and "[E2] accepted" in user.content


def test_recordings_replay_and_misses_fail(tmp_path):
    path = tmp_path / "rec.jsonl"
    live = Canned("| where level = \"error\"")
    recorder = RecordedProvider(path, inner=live, record=True)
    messages = [Message(role="system", content="s"), Message(role="user", content="errors?")]
    first = run(recorder.chat(messages, []))
    assert live.calls == 1 and path.exists()
    entry = json.loads(path.read_text().splitlines()[0])
    assert entry["key"] == request_key(messages, [], "canned-1") and entry["result"]["text"] == first.text
    assert entry["model"] == "canned-1"

    replay = RecordedProvider(path)
    again = run(replay.chat(messages, []))
    assert again.text == first.text and again.usage == Usage(10, 5) and replay.model == "canned-1"
    with pytest.raises(ProviderError, match="no recording"):
        run(replay.chat([Message(role="user", content="something else")], []))


def test_the_request_key_ignores_nothing_that_matters():
    a = [Message(role="user", content="x")]
    assert request_key(a, [], "m") == request_key([Message(role="user", content="x")], [], "m")
    assert request_key(a, [], "m") != request_key([Message(role="user", content="y")], [], "m")
    assert request_key(a, [], "m") != request_key(a, [], "other-model")
