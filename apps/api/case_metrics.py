"""
SLA metrics and the SOC overview for cases (Phase 2).

Per severity: mean and median time to acknowledge (created -> first move out
of `new` or first assignment) and time to resolve (created -> closed), with
cases merged into others left out. Overview: open cases by status, their
age, open cases per analyst, alerts per case, and SLA breaches against
per-severity targets.
"""

from __future__ import annotations

import csv
import io
import json
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from cases import CLOSED, SEVERITIES, Case

SLA_TARGETS = {
    "acknowledge": {"critical": timedelta(minutes=15), "high": timedelta(hours=1),
                    "medium": timedelta(hours=4), "low": timedelta(hours=24)},
    "resolve": {"critical": timedelta(hours=4), "high": timedelta(hours=24),
                "medium": timedelta(days=3), "low": timedelta(days=7)},
}
AGE_BUCKETS = (("<1h", timedelta(hours=1)), ("1-4h", timedelta(hours=4)), ("4-24h", timedelta(hours=24)),
               ("1-7d", timedelta(days=7)), (">7d", None))


def _stats(minutes: List[float]) -> Dict[str, Any]:
    if not minutes:
        return {"mean": None, "median": None, "count": 0}
    return {"mean": round(statistics.fmean(minutes), 1), "median": round(statistics.median(minutes), 1),
            "count": len(minutes)}


def _minutes(delta: timedelta) -> float:
    return delta.total_seconds() / 60


def _breached(case: Case, kind: str, now: datetime) -> bool:
    target = SLA_TARGETS[kind].get(case.severity)
    if target is None or case.created_at is None:
        return False
    done = case.acknowledged_at if kind == "acknowledge" else (case.resolved_at if case.status in CLOSED else None)
    return ((done or now) - case.created_at) > target


def case_metrics(cases: Sequence[Case], now: datetime) -> Dict[str, Any]:
    cases = [c for c in cases if not c.merged_into]
    by_severity: Dict[str, Any] = {}
    for severity in SEVERITIES:
        group = [c for c in cases if c.severity == severity]
        ack = [_minutes(c.acknowledged_at - c.created_at) for c in group if c.acknowledged_at and c.created_at]
        res = [_minutes(c.resolved_at - c.created_at) for c in group
               if c.status in CLOSED and c.resolved_at and c.created_at]
        by_severity[severity] = {"cases": len(group), "open": sum(1 for c in group if c.is_open),
                                 "mtta_minutes": _stats(ack), "mttr_minutes": _stats(res)}

    open_cases = [c for c in cases if c.is_open]
    ageing = {label: 0 for label, _ in AGE_BUCKETS}
    for c in open_cases:
        age = now - (c.created_at or now)
        for label, limit in AGE_BUCKETS:
            if limit is None or age < limit:
                ageing[label] += 1
                break
    load: Dict[str, int] = {}
    for c in open_cases:
        name = c.assignee or "unassigned"
        load[name] = load.get(name, 0) + 1
    alerts = sum(len(c.alert_ids) for c in cases)
    return {
        "generated_at": now.isoformat(),
        "cases": len(cases),
        "by_severity": by_severity,
        "open_total": len(open_cases),
        "open_by_status": {s: sum(1 for c in open_cases if c.status == s) for s in ("new", "investigating", "contained")},
        "ageing": ageing,
        "analyst_load": dict(sorted(load.items(), key=lambda kv: (-kv[1], kv[0]))),
        "alerts": alerts,
        "alerts_per_case": round(alerts / len(cases), 2) if cases else 0.0,
        "sla_targets_minutes": {k: {s: _minutes(v) for s, v in t.items()} for k, t in SLA_TARGETS.items()},
        "sla_breaches": {kind: {s: sum(1 for c in cases if c.severity == s and _breached(c, kind, now))
                                for s in SEVERITIES} for kind in SLA_TARGETS},
    }


def events_to_csv(events: Sequence[Dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["ts", "case_id", "event_id", "actor", "kind", "data"])
    for e in events:
        ts = e.get("ts")
        writer.writerow([ts.isoformat() if isinstance(ts, datetime) else ts, e.get("case_id"), e.get("id"),
                         e.get("actor"), e.get("kind"), json.dumps(e.get("data") or {}, default=str)])
    return out.getvalue()
