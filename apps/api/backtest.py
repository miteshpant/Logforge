"""
Backtest a detection rule over stored logs (Phase 1).

Reads the tenant's `logs_raw_mt` rows in a time range, oldest first and in
time chunks, narrowed by the rule's compiled prefilter (sigma_sql), and
replays them through the engine (detection_replay) with one correlation
store for the whole range, so windows span chunk boundaries. The SQL only
narrows the scan; every match is decided by the engine, so a backtest agrees
with what the live path would have alerted on.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from correlation import CorrelationStore
from detection_replay import replay
from detection_tuning import Throttler
from sigma_sql import compile_prefilter

MAX_RANGE = timedelta(days=31)
DEFAULT_CHUNK = timedelta(hours=6)
DEFAULT_MAX_EVENTS = 2_000_000
_COLUMNS = "ts, host, service, level, msg, trace_id, span_id, status, src_ip, user_id, attrs"


class BacktestError(ValueError):
    """The backtest request can't be run (bad range, ...)."""


class RuleNotFound(LookupError):
    pass


def row_to_event(row: Dict[str, Any]) -> Dict[str, Any]:
    """A stored row as the live detection path sees the event: model columns
    (with the normalizer's aliases) plus the caller's fields in `attrs`."""
    ts = row.get("ts")
    if isinstance(ts, datetime):
        ts = (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)).isoformat()
    attrs = row.get("attrs")
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs) if attrs else {}
        except ValueError:
            attrs = {}
    if not isinstance(attrs, dict):
        attrs = {}
    host = row.get("host", "")
    return {
        "ts": ts, "timestamp": ts,
        "host": host, "hostname": host,
        "service": row.get("service", ""),
        "level": row.get("level", ""), "log_level": row.get("level", ""),
        "msg": row.get("msg", ""), "message": row.get("msg", ""),
        "trace_id": row.get("trace_id", ""), "span_id": row.get("span_id", ""),
        "status": row.get("status", 0), "status_code": row.get("status", 0),
        "src_ip": row.get("src_ip", ""), "user_id": row.get("user_id", ""), "user": "",
        "attrs": attrs,
    }


def _labels(rule: Dict[str, Any]) -> List[str]:
    labels = [str(rule.get("id"))]
    if rule.get("name"):
        labels.append(str(rule["name"]))
    return labels


def resolve_rules(rules: List[Dict[str, Any]], rule_id: str) -> List[Dict[str, Any]]:
    """The rules a backtest of `rule_id` replays: its correlation
    dependencies (by name or id, transitively), then the rule itself."""
    by_label: Dict[str, Dict[str, Any]] = {}
    for rule in rules:
        for label in _labels(rule):
            by_label.setdefault(label, rule)
    target = by_label.get(rule_id) or by_label.get(f"logforge_{rule_id}")
    if target is None:
        raise RuleNotFound(rule_id)

    ordered: List[Dict[str, Any]] = []

    def visit(rule: Dict[str, Any], trail: tuple) -> None:
        if rule["id"] in trail or any(r["id"] == rule["id"] for r in ordered):
            return
        refs = (rule.get("correlation") or {}).get("rules") or []
        for ref in [refs] if isinstance(refs, str) else refs:
            dependency = by_label.get(str(ref))
            if dependency is not None:
                visit(dependency, trail + (rule["id"],))
        ordered.append(rule)

    visit(target, ())
    # The rule under test alerts even if it is a silent building block.
    ordered[-1] = dict(ordered[-1], generate=True)
    return ordered


def _prefilter(rules: List[Dict[str, Any]]) -> tuple:
    clauses, params = [], {}
    for rule in rules:
        if rule.get("correlation"):
            continue
        sql, rule_params = compile_prefilter(rule.get("detection") or {}, start=len(params))
        if sql is None:
            return None, {}  # one rule can't be narrowed: scan everything
        clauses.append(sql)
        params.update(rule_params)
    if not clauses:
        return None, {}
    return "(" + " OR ".join(clauses) + ")", params


async def run_backtest(db, rules: List[Dict[str, Any]], rule_id: str, tenant_id: str,
                       start: datetime, end: datetime, max_events: int = DEFAULT_MAX_EVENTS,
                       sample_limit: int = 50, chunk: timedelta = DEFAULT_CHUNK,
                       tuning=None) -> Dict[str, Any]:
    if end <= start:
        raise BacktestError("end must be after start")
    if end - start > MAX_RANGE:
        raise BacktestError(f"the range can be at most {MAX_RANGE.days} days")

    replayed = resolve_rules(rules, rule_id)
    target = replayed[-1]
    prefilter, params = _prefilter(replayed)
    sql = (f"SELECT {_COLUMNS} FROM logs_raw_mt WHERE customer_id = %(tenant_id)s "
           f"AND ts >= %(chunk_start)s AND ts < %(chunk_end)s"
           + (f" AND {prefilter}" if prefilter else "")
           + " ORDER BY ts LIMIT %(limit)s")

    began = time.monotonic()
    store = CorrelationStore()
    throttler = Throttler()
    suppressed = 0
    scanned = 0
    truncated = False
    alerts: List[Dict[str, Any]] = []
    total = 0
    by_day: Counter = Counter()
    cursor = start
    while cursor < end and not truncated:
        chunk_end = min(cursor + chunk, end)
        remaining = max_events - scanned
        rows = await db.fetch_all(sql, {**params, "tenant_id": tenant_id, "chunk_start": cursor,
                                        "chunk_end": chunk_end, "limit": remaining + 1})
        if len(rows) > remaining:
            rows, truncated = rows[:remaining], True
        scanned += len(rows)
        events = [row_to_event(r) for r in rows]
        for alert in replay(replayed, events, store=store, tenant_id=tenant_id):
            if alert.rule_id != target["id"]:
                continue
            # The tenant's exclusions and throttles, as the live path applies them.
            if tuning and (tuning.exclusion_for(alert.rule_id, alert.event, alert.ts)
                           or not throttler.allow(tenant_id, alert.rule_id, tuning.throttle_for(alert.rule_id),
                                                  alert.event, alert.group, alert.ts)):
                suppressed += 1
                continue
            total += 1
            by_day[alert.ts.date().isoformat()] += 1
            if len(alerts) < sample_limit:
                alerts.append({"ts": alert.ts.isoformat(), "group": alert.group, "value": alert.value,
                               "event": alert.event})
        cursor = chunk_end

    elapsed = time.monotonic() - began
    return {
        "rule_id": target["id"],
        "title": target.get("title"),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "events_scanned": scanned,
        "alerts_total": total,
        "alerts_suppressed": suppressed,
        "alerts": alerts,
        "by_day": dict(sorted(by_day.items())),
        "rules_replayed": [r["id"] for r in replayed],
        "prefilter": prefilter is not None,
        "truncated": truncated,
        "duration_ms": round(elapsed * 1000, 1),
    }
