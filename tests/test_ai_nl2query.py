"""
Natural language -> LogforgeQL (Phase 9). The user asks; we draft a query,
show and explain it, and the user runs or edits it: the query, not the
model, produces the answer.

* With AI: the model gets the tenant's field catalogue (names, types,
  redacted example values) and must answer with JSON {query, explanation}.
  The query must compile; one repair round gets the compiler's error.
  Fields the catalogue doesn't know are reported.
* Without AI: a rule-based translator handles the common shapes (filters by
  level / service / IP / status / text, a time window, counts by a field,
  top values, trends, latest lines) and says when it can't.
"""

import asyncio
import json
from datetime import datetime, timezone

import pytest
from ai.nl2query import catalogue_prompt, rule_based, translate
from ai.providers import ChatResult, Usage
from ai.redaction import Redactor

CATALOGUE = {"fields": [
    {"name": "service", "type": "string", "examples": [{"value": "checkout", "count": 50}, {"value": "auth", "count": 40},
                                                      {"value": "api-gateway", "count": 30}]},
    {"name": "host", "type": "string", "examples": [{"value": "web-1", "count": 9}]},
    {"name": "level", "type": "string", "examples": [{"value": "error", "count": 9}]},
    {"name": "status", "type": "int", "examples": [{"value": 200, "count": 9}]},
    {"name": "src_ip", "type": "string", "examples": [{"value": "10.0.0.5", "count": 9}]},
    {"name": "user_id", "type": "string", "examples": [{"value": "bob", "count": 3}]},
    {"name": "attrs.path", "type": "string", "examples": [{"value": "/api/orders", "count": 3}]},
    {"name": "attrs.token", "type": "string", "examples": [{"value": "abc123secret", "count": 1}]},
]}
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("question, query", [
    ("How many errors did checkout log, per host?", '| where service = "checkout" and level = "error" | stats count() as count by host'),
    ("Which services logged the most errors?", '| where level = "error" | top limit=10 service'),
    ("Show warnings from payments in the last hour", '| last 1h | where level = "warn"'),
    ("Errors from auth in the last 15 minutes", '| last 15m | where service = "auth" and level = "error"'),
    ("Requests that returned a server error, by path", '| where status >= 500 | stats count() as count by attrs.path'),
    ("What did 10.0.0.5 do?", '| where src_ip = "10.0.0.5"'),
    ('Lines mentioning "connection reset" over time', '"connection reset" | timechart count()'),
    ("Latest 50 errors", '| where level = "error" | sort ts desc | head 50'),
    ("Show 5xx errors from api-gateway over time", '| where service = "api-gateway" and status >= 500 | timechart count()'),
    ("404 errors per path", '| where status >= 400 and status < 500 | stats count() as count by attrs.path'),
    ("Top 5 users by events in the last 7 days", '| last 7d | top limit=5 user_id'),
    # a value the catalogue has seen becomes a filter on its field
    ("Requests on web-1 per path", '| where host = "web-1" | stats count() as count by attrs.path'),
    ("What did bob do?", '| where user_id = "bob"'),
    # a dotted name is not the service it starts with
    ("Lookups of api-gateway.example.org", None),
    ("Requests by web-1", '| where host = "web-1"'),  # "by" followed by a value, not a field
    ("How many events did each service log in the last 24 hours?", '| last 24h | stats count() as count by service'),
])
def test_rule_based_translations(question, query):
    draft = rule_based(question, CATALOGUE)
    assert draft.query == query, draft
    assert draft.valid == (query is not None) and draft.explanation and draft.mode == "rule_based"


def test_rule_based_says_when_it_cannot():
    draft = rule_based("Why is the sky blue?", CATALOGUE)
    assert draft.query is None and not draft.valid and "couldn't" in draft.explanation


def test_the_catalogue_prompt_lists_fields_with_redacted_examples():
    text = catalogue_prompt(CATALOGUE, Redactor(["token"]))
    assert "service (string): checkout, auth, api-gateway" in text
    assert "attrs.path (string): /api/orders" in text
    assert "abc123secret" not in text and "attrs.token" in text


class Scripted:
    name, model, external = "s", "s-1", False

    def __init__(self, *texts):
        self.texts, self.sent = list(texts), []

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        self.sent.append(messages)
        return ChatResult(text=self.texts.pop(0), tool_calls=[], stop_reason="end", usage=Usage(10, 5), model="s-1")


def test_ai_translation_validates_and_repairs():
    good = json.dumps({"query": '| where level = "error" | stats count() as n by service',
                       "explanation": "Errors counted per service."})
    provider = Scripted('{"query": "| stats nonsense(((", "explanation": "x"}', good)
    draft = run(translate("errors per service?", provider, catalogue=CATALOGUE, redactor=Redactor([])))
    assert draft.valid and draft.query == '| where level = "error" | stats count() as n by service'
    assert draft.explanation == "Errors counted per service." and draft.mode == "ai"
    # the repair round told the model what was wrong
    assert len(provider.sent) == 2 and "did not compile" in provider.sent[1][-1].content
    # the system prompt carries the tenant's fields
    assert "attrs.path" in provider.sent[0][0].content


def test_ai_translation_reports_unknown_fields_and_gives_up_after_one_repair():
    provider = Scripted('```json\n{"query": "| where attrs.bogus = \\"x\\" | stats count() by host", '
                        '"explanation": "e"}\n```')
    draft = run(translate("q", provider, catalogue=CATALOGUE, redactor=Redactor([])))
    assert draft.valid and draft.unknown_fields == ["attrs.bogus"]
    bad = Scripted("not json at all", "still | stats ((( nothing")
    draft = run(translate("q", bad, catalogue=CATALOGUE, redactor=Redactor([])))
    assert not draft.valid and draft.query is None and draft.error
