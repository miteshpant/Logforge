"""
Scoring the investigation copilot (Phase 10) on datasets/copilot_scenarios.jsonl.

Each scenario is seeded into a scratch ClickHouse table as its own tenant.
The copilot runs as it does for an analyst who approves everything it
proposes once: plan, run, then run again with its proposed next steps
added. Its searches go through the real tool and the real query compiler;
only the table is the scratch one.

* found: the scenario's root-cause event is among the copilot's root-cause
  candidates (at most 3);
* first: it is the first candidate;
* fabricated: timeline events that aren't in the seeded data, and root
  causes or citations that aren't events or searches the copilot fetched
  (target: 0).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
DATASET = HERE / "datasets" / "copilot_scenarios.jsonl"
PREFIX = "copilot-eval-"


def load() -> list[dict[str, Any]]:
    return [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]


def _second(value: Any) -> str:
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _key(event: dict[str, Any]) -> tuple:
    return (_second(event["ts"]), event.get("service"), event.get("host"), event.get("msg"))


class Seeded:
    def __init__(self, client, scenarios: list[dict[str, Any]]):
        self.client = client
        self.table = f"test_copilot_{uuid.uuid4().hex[:8]}"
        client.command(f"CREATE TABLE {self.table} AS logs_raw_mt")
        columns = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip",
                   "user_id", "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]
        rows = []
        for scenario in scenarios:
            for e in scenario["events"]:
                ts = datetime.fromisoformat(e["ts"])
                rows.append([ts, e["host"], e["service"], e["level"], e["msg"], "", "", json.dumps(e["attrs"]),
                             e["status"], e["src_ip"], e["user_id"], ts, 0, 16, "v1", PREFIX + scenario["id"]])
        client.insert(self.table, rows, column_names=columns)

    async def logql(self, body: dict[str, Any], tenant: str) -> dict[str, Any]:
        import logql_pipeline as lp

        start = datetime.fromisoformat(body["start_time"])
        end = datetime.fromisoformat(body["end_time"])
        compiled = lp.compile_pipeline(body["query"], customer_id=tenant, start=start, end=end, table=self.table)
        result = await asyncio.to_thread(lp.execute, self.client, compiled)
        return {"logs": result["rows"], "total_count": len(result["rows"]), "truncated": result["truncated"]}

    def drop(self):
        self.client.command(f"DROP TABLE IF EXISTS {self.table}")


async def investigate(scenario: dict[str, Any], seeded: Seeded, write=None) -> dict[str, Any]:
    """The copilot on one scenario: plan, run, approve its next steps once.
    `write(result, context)` optionally rewrites the result (the model)."""
    from ai import copilot
    from ai import tools as tool_module
    from ai.tools import ToolContext

    tenant = PREFIX + scenario["id"]
    ctx = ToolContext(tenant_id=tenant, user_id="eval", roles=[{"role": "tenant_admin", "tenant_id": tenant}])
    original = tool_module._logql
    tool_module._logql = seeded.logql
    try:
        context = await copilot.gather_context(scenario["subject"], ctx)
        steps = copilot.plan(context)
        first = await copilot.run(context, steps, ctx)
        approved = [s.to_public() for s in steps] + first["next_steps"]
        final = await copilot.run(context, copilot.validate_steps(approved[:copilot.MAX_STEPS]), ctx)
        if write is not None:
            final = await write(final, context)
    finally:
        tool_module._logql = original
    return final


def score_one(scenario: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    from ai.citations import CITE

    seeded = {_key(e): e["attrs"]["eid"] for e in scenario["events"]}
    by_cid = {e["cid"]: e for e in result["timeline"]}
    fabricated = [e["cid"] for e in result["timeline"] if _key(e) not in seeded]
    issued = {c["id"] for c in result["citations"]}
    fabricated += [c for c in result["root_cause"] if c not in by_cid]
    fabricated += [c for c in CITE.findall("\n".join(result["hypotheses"])) if c not in issued]
    roots = [seeded.get(_key(by_cid[c])) for c in result["root_cause"] if c in by_cid]
    return {"id": scenario["id"], "kind": scenario["kind"], "found": scenario["root"] in roots,
            "first": bool(roots) and roots[0] == scenario["root"], "fabricated": fabricated,
            "timeline": len(result["timeline"]), "candidates": roots, "mode": result["mode"]}


def score(scenarios: list[dict[str, Any]], seeded: Seeded,
          write_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    per = []
    for scenario in scenarios:
        result = asyncio.run(investigate(scenario, seeded, write_factory() if write_factory else None))
        per.append(score_one(scenario, result))
    n = len(per)
    return {"scenarios": n, "found": round(sum(p["found"] for p in per) / n, 4),
            "first": round(sum(p["first"] for p in per) / n, 4),
            "fabricated": sum(len(p["fabricated"]) for p in per), "per_scenario": per}


def model_writer(provider):
    from ai import copilot
    from ai.redaction import Redactor

    def factory():
        async def write(result, context):
            return await copilot.write(result, context, provider, redactor=Redactor([]))
        return write
    return factory
