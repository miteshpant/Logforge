"""
`| patterns` (Phase 11): log pattern clustering as the last stage of a
LogforgeQL query.

    | where service = "checkout" | patterns   templates of the window's lines
    | where level = "error" | patterns new      only templates the last 7 days never had
    "timeout" | patterns rare                  lines mentioning timeout: new or seen at most twice

The query before the stage selects the lines (up to MAX_LINES in the
window); the same query over the BASELINE_DAYS before the window (up to
BASELINE_LINES) is the baseline that decides what is new. The result is a
table (pattern_id, pattern, count, first_seen, last_seen, new, rare,
baseline_count, example, services), so a saved search on `| patterns new`
alerts on a sudden new pattern.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

MAX_LINES = 1_000_000
BASELINE_LINES = 200_000
BASELINE_DAYS = 7
MAX_PATTERNS = 1000
MODES = ("all", "new", "rare")
COLUMNS = ["pattern_id", "pattern", "count", "first_seen", "last_seen", "new", "rare", "baseline_count", "example",
           "services"]


class PatternQueryError(ValueError):
    pass


def split(query: str) -> Optional[Tuple[str, str]]:
    """(the query before `| patterns`, the mode), or None if it has no patterns stage."""
    from logql import _split_top_level

    stages = _split_top_level(query or "", "|")
    if len(stages) < 2 and not (stages and (query or "").lstrip().startswith("|")):
        return None
    words = stages[-1].split()
    if not words or words[0].lower() != "patterns":
        if any(s.split()[:1] == ["patterns"] for s in stages[:-1]):
            raise PatternQueryError("patterns must be the last stage")
        return None
    if len(words) > 2 or (len(words) == 2 and words[1].lower() not in MODES):
        raise PatternQueryError("use | patterns, | patterns new or | patterns rare")
    if any(s.split()[:1] == ["patterns"] for s in stages[:-1]):
        raise PatternQueryError("patterns must be the last stage")
    base = "|".join(stages[:-1]).strip()
    if base and (query or "").lstrip().startswith("|") and not base.startswith("|"):
        base = "| " + base
    return (base or "*"), (words[1].lower() if len(words) == 2 else "all")


def lines_query(base: str, limit: int) -> str:
    return f"{base} | fields ts, service, msg | head {limit}"


def run(client, base: str, mode: str, tenant_id: str, start: datetime, end: datetime,
        settings: Optional[Dict[str, Any]] = None, lookups=None) -> Dict[str, Any]:
    """Cluster the window's lines against the baseline (blocking: run it in a thread)."""
    import time

    from log_patterns import Clusterer
    from logql_pipeline import compile_pipeline

    began = time.perf_counter()
    clusterer = Clusterer()

    def stream(begin: datetime, finish: datetime, limit: int):
        compiled = compile_pipeline(lines_query(base, limit), customer_id=tenant_id, start=begin, end=finish,
                                    max_rows=limit, lookups=lookups, rollup=False)
        names = compiled.columns
        index = {name: i for i, name in enumerate(names)}
        with client.query_row_block_stream(compiled.sql, parameters=compiled.params, settings=settings or {}) as blocks:
            for block in blocks:
                for row in block:
                    yield row[index["ts"]], row[index["service"]], row[index["msg"]]

    baseline = 0

    def baseline_lines():
        nonlocal baseline
        for _, _, msg in stream(start - timedelta(days=BASELINE_DAYS), start - timedelta(milliseconds=1), BASELINE_LINES):
            baseline += 1
            yield msg

    clusterer.baseline(baseline_lines())
    lines = 0
    for ts, service, msg in stream(start, end, MAX_LINES):
        lines += 1
        clusterer.add(msg, ts, service)
    rows = clusterer.results(mode, with_baseline=baseline > 0)
    return {"rows": rows[:MAX_PATTERNS], "columns": COLUMNS, "result_type": "table",
            "truncated": lines >= MAX_LINES or len(rows) > MAX_PATTERNS,
            "patterns": {"lines": lines, "baseline_lines": baseline, "templates": len(rows), "mode": mode,
                         "seconds": round(time.perf_counter() - began, 2)}}
