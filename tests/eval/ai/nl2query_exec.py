"""
Execution accuracy for natural language -> LogforgeQL (Phase 9).

A generated query is right when it returns the same rows as the expected
query on the seeded week of events: rows are compared as a multiset of value
tuples, so column names and row order don't matter, and numbers are compared
to 6 significant digits. A query that doesn't compile or fails scores 0.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

HERE = Path(__file__).resolve().parent
SCHEMAS = ["auth", "http", "dns"]
TENANT = "nl2query-eval"


def load(schema: str) -> List[Dict[str, Any]]:
    path = HERE / "datasets" / f"nl2query_{schema}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _value(v: Any) -> Any:
    if isinstance(v, float):
        return float(f"{v:.6g}")
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return tuple(sorted(_value(x) for x in v))
    return v


def result_key(rows: List[Dict[str, Any]]) -> List[tuple]:
    return sorted((tuple(sorted((_value(v) for v in row.values()), key=repr)) for row in rows), key=repr)


class Seeded:
    """The Phase 6 seed (tests/test_analyst_questions_live.make_events) in a scratch table."""

    def __init__(self, client, events, start, end):
        self.client, self.events, self.start, self.end = client, events, start, end
        self.table = f"test_nl2query_{uuid.uuid4().hex[:8]}"
        client.command(f"CREATE TABLE {self.table} AS logs_raw_mt")
        columns = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip",
                   "user_id", "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]
        client.insert(self.table, [[e["ts"], e["host"], e["service"], e["level"], e["msg"], "", "",
                                    json.dumps(e["attrs"]), e["status"], e["src_ip"], e["user_id"], e["ts"], 0, 16,
                                    "v1", TENANT] for e in events], column_names=columns)

    def catalogue(self) -> Dict[str, Any]:
        from field_catalogue import build_catalogue

        rows = [{**e, "attrs": json.dumps(e["attrs"])} for e in self.events[-2000:]]
        return build_catalogue(rows)

    def rows(self, query: str) -> List[Dict[str, Any]]:
        import logql_pipeline as lp

        compiled = lp.compile_pipeline(query, customer_id=TENANT, start=self.start, end=self.end, table=self.table)
        return lp.execute(self.client, compiled)["rows"]

    def drop(self):
        self.client.command(f"DROP TABLE IF EXISTS {self.table}")


def score(seeded: Seeded, items: List[Dict[str, Any]], system: Callable[[Dict[str, Any]], Optional[str]]):
    expected_cache: Dict[str, Any] = {}
    per_item, failures = {}, []
    for item in items:
        expected = expected_cache.get(item["expected_query"])
        if expected is None:
            expected = expected_cache[item["expected_query"]] = result_key(seeded.rows(item["expected_query"]))
        generated = system(item)
        ok = 0.0
        if generated:
            try:
                ok = 1.0 if result_key(seeded.rows(generated)) == expected else 0.0
            except Exception:  # noqa: BLE001 - a query that fails to run is wrong
                ok = 0.0
        per_item[item["id"]] = ok
        if not ok:
            failures.append({"id": item["id"], "question": item["question"], "expected": item["expected_query"],
                             "generated": generated})
    return {"items": len(items), "score": round(sum(per_item.values()) / len(items), 3) if items else 0.0,
            "per_item": per_item, "failures": failures}
