"""
Single-call AI features (Phase 8), scored by tests/eval/ai on every change:

* nl2query(question)  -> one LogforgeQL query, or None if the model's
  answer doesn't compile (it is never passed on unchecked);
* summarise(task, evidence) -> a short summary citing the evidence as [E#].

They take any provider (ai/providers), so the evaluation can run them on a
recorded model in CI and on a live one when recording.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .providers import Message

NL2QUERY_PROMPT = """You turn questions about logs into one LogforgeQL query. Reply with the query only: \
no explanation, no code fence.

Each event has: ts, service, host, level (debug, info, warn, error), msg, status (HTTP status), src_ip, \
user_id, trace_id, and attrs.* for anything else.

A query is optional free text to search for, then pipeline stages separated by |:
  | where <condition>       service = "auth", level = "error", status >= 500, msg contains "panic",
                            src_ip = "10.0.0.1"; combine with and / or / not
  | stats count() by f1, f2  also sum(f), avg(f), dc(f), p95(f), values(f); "as name" renames
  | timechart span=5m count() by service
  | top limit=10 field      most common values
  | sort ts desc            or -field / field
  | limit 100               (also | head 100)
  | last 15m                time window: 15m, 1h, 24h, 7d

Examples:
  Errors from the api service per host -> | where service = "api" and level = "error" | stats count() by host
  Lines mentioning "connection reset" in the last hour -> "connection reset" | last 1h | limit 100
  Slowest endpoints -> | stats p95(attrs.duration_ms) as p95 by attrs.path | sort -p95 | head 10"""

SUMMARY_PROMPT = """You summarise security alerts and incidents for an analyst, using only the evidence \
given. After every sentence, cite the evidence it relies on as [E1], [E2]. Do not state anything the \
evidence does not support. Two to four sentences."""


def _compiles(query: str) -> bool:
    import logql
    import logql_pipeline as lp

    try:
        logql.compile_to_request_payload(query)
        return True
    except Exception:  # noqa: BLE001 - any failure means "not a query"
        pass
    end = datetime.now(timezone.utc)
    try:
        lp.compile_pipeline(query, customer_id="nl2query-check", start=end - timedelta(hours=1), end=end)
        return True
    except Exception:  # noqa: BLE001
        return False


def extract_query(text: str) -> str | None:
    fenced = re.findall(r"```(?:\w+)?\n(.*?)```", text or "", re.DOTALL)
    candidates = []
    for block in fenced or [text or ""]:
        for line in block.splitlines():
            line = line.strip().strip("`").strip()
            if not line:
                continue
            if "|" in line and not line.startswith("|"):
                prefix, rest = line[:line.index("|")].strip(), line[line.index("|"):].strip()
                prose = prefix.endswith(":") or any(ch in prefix for ch in "!?") or len(prefix.split()) > 6
                candidates.extend([rest, line] if prose else [line, rest])
            else:
                candidates.append(line)
    for candidate in candidates:
        if _looks_like_query(candidate) and _compiles(candidate):
            return candidate
    return None


def _looks_like_query(text: str) -> bool:
    """Any text is a valid free-text search, so prose must be told apart:
    a query has a pipeline stage, or is a quoted phrase or a word or two."""
    if "|" in text or text.startswith('"'):
        return True
    return len(text.split()) <= 2 and not re.search(r"[.!?,;]$", text)


async def nl2query(question: str, provider, max_tokens: int = 1024, catalogue=None) -> str | None:
    """The product's natural-language-to-query feature (ai.nl2query.translate):
    the drafted query if it compiled, else None."""
    from .nl2query import translate

    draft = await translate(question, provider, catalogue=catalogue, max_tokens=max_tokens)
    return draft.query if draft.valid else None


async def summarise(task: str, evidence: dict[str, str], provider, max_tokens: int = 1024) -> str:
    lines = "\n".join(f"[{eid}] {text}" for eid, text in evidence.items())
    result = await provider.chat([Message(role="system", content=SUMMARY_PROMPT),
                                  Message(role="user", content=f"{task}\n\nEvidence:\n{lines}")], [],
                                 max_tokens=max_tokens)
    return result.text.strip()
