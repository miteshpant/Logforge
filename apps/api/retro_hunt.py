"""
Retro-hunting (Phase 3): when new indicators arrive, search the tenant's
recent stored logs for them and raise an alert for each past match.

New indicators come from feed runs (threat_feed_scheduler) and manual adds.
For each indicator type one parameterised query runs over logs_raw_mt:
src_ip plus the caller's fields in attrs (ingest_enrichment.FIELDS);
domains also match subdomains. Each hit is stamped like ingest-time
matching would have done and raised as an alert (rule
logforge_lf-ti-retro-match), which then goes through case grouping like any
other alert.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

import structlog

from ingest_enrichment import FIELDS, _matches
from threat_intel import Indicator, normalize_indicator

logger = structlog.get_logger(__name__)

RETRO_RULE_ID = "logforge_lf-ti-retro-match"
RETRO_TITLE = "Past activity matched a new threat indicator"
Key = Tuple[str, str]
Sink = Callable[[str, Dict[str, Any]], Awaitable[Any]]
_BATCH = {"domain": 200}


def _ms(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _attr(name: str) -> str:
    return f"JSONExtractString(attrs, '{name}')"


def _query(kind: str, values: List[str]) -> Tuple[str, Dict[str, Any]]:
    params: Dict[str, Any] = {"values": values, "kind": kind}
    if kind == "ip":
        clauses = ["src_ip IN %(values)s"] + [f"{_attr(f)} IN %(values)s" for f in FIELDS["ip"]]
    elif kind == "domain":
        clauses = []
        for name in FIELDS["domain"]:
            clauses.append(f"lower({_attr(name)}) IN %(values)s")
            for i in range(len(values)):
                clauses.append(f"endsWith(lower({_attr(name)}), %(suffix_{i})s)")
        # ...and the host of URL fields, as ingest-time matching does.
        for name in FIELDS["url"]:
            host = f"lower(domain({_attr(name)}))"
            clauses.append(f"{host} IN %(values)s")
            clauses += [f"endsWith({host}, %(suffix_{i})s)" for i in range(len(values))]
        params.update({f"suffix_{i}": f".{v}" for i, v in enumerate(values)})
    else:
        clauses = [f"lower({_attr(f)}) IN %(values)s" for f in FIELDS.get(kind, ())]
    sql = ("SELECT ts, host, service, level, msg, trace_id, span_id, status, src_ip, user_id, attrs "
           "FROM logs_raw_mt WHERE customer_id = %(tenant_id)s AND ts >= %(since)s AND (" + " OR ".join(clauses) +
           ") ORDER BY ts DESC LIMIT %(limit)s")
    return sql, params


def _value_condition(kind: str, param: str) -> str:
    """SQL that is true when a stored log mentions the value %(param)s."""
    if kind == "ip":
        return " OR ".join([f"src_ip = %({param})s"] + [f"{_attr(f)} = %({param})s" for f in FIELDS["ip"]])
    if kind == "domain":
        parts = []
        for expr in [f"lower({_attr(f)})" for f in FIELDS["domain"]] + \
                [f"lower(domain({_attr(f)}))" for f in FIELDS["url"]]:
            parts.append(f"({expr} = %({param})s OR endsWith({expr}, concat('.', %({param})s)))")
        return " OR ".join(parts)
    return " OR ".join(f"lower({_attr(f)}) = %({param})s" for f in FIELDS.get(kind, ())) or "0"


async def seen_counts(db, tenant_id: str, keys: Iterable[Key], days: int = 7,
                      now: Optional[datetime] = None) -> Dict[Key, int]:
    """How many of the tenant's logs in the last `days` mention each indicator."""
    keys = [k for k in dict.fromkeys(keys) if k[0] in FIELDS][:200]
    if not keys:
        return {}
    now = now or datetime.now(timezone.utc)
    params: Dict[str, Any] = {"tenant_id": tenant_id, "since": _ms(now - timedelta(days=days))}
    columns = []
    for i, (kind, value) in enumerate(keys):
        params[f"v{i}"] = value
        columns.append(f"countIf({_value_condition(kind, f'v{i}')}) AS c{i}")
    rows = await db.fetch_all(f"SELECT {', '.join(columns)} FROM logs_raw_mt WHERE customer_id = %(tenant_id)s "
                              "AND ts >= %(since)s", params)
    row = (rows or [{}])[0]
    return {key: int(row.get(f"c{i}") or 0) for i, key in enumerate(keys)}


async def retro_hunt(tenant_id: str, keys: Iterable[Key], get_indicator: Callable[[Key], Optional[Indicator]],
                     db, sink: Sink, now: Optional[datetime] = None, days: int = 7,
                     max_alerts: int = 1000) -> Dict[str, Any]:
    from backtest import row_to_event

    now = now or datetime.now(timezone.utc)
    indicators = [i for i in (get_indicator(k) for k in dict.fromkeys(keys)) if i is not None]
    result = {"indicators": len(indicators), "matches": 0, "alerts": 0, "truncated": False}
    if not indicators:
        return result
    sets: Dict[str, Dict[str, Indicator]] = {}
    for indicator in indicators:
        sets.setdefault(indicator.indicator_type, {})[indicator.normalized()] = indicator

    for kind, values_by_value in sets.items():
        if kind not in FIELDS:
            continue
        values = sorted(values_by_value)
        size = _BATCH.get(kind, 1000)
        for start in range(0, len(values), size):
            if result["alerts"] >= max_alerts:
                result["truncated"] = True
                return result
            sql, params = _query(kind, values[start:start + size])
            rows = await db.fetch_all(sql, {**params, "tenant_id": tenant_id, "since": _ms(now - timedelta(days=days)),
                                            "limit": max_alerts - result["alerts"] + 1})
            for row in rows or []:
                event = row_to_event(row)
                hits = _matches({kind: values_by_value}, event, now)
                if not hits:
                    continue
                result["matches"] += 1
                if result["alerts"] >= max_alerts:
                    result["truncated"] = True
                    return result
                hit = hits[0]
                event["attrs"]["threat"] = {"matched": True, "max_confidence": hit["confidence"],
                                            "threat_types": [hit["threat_type"]], "indicators": hits, "retro": True}
                await sink(tenant_id, {
                    "id": str(uuid.uuid4()), "rule_id": RETRO_RULE_ID, "rule_title": RETRO_TITLE,
                    "severity": "high" if hit["confidence"] >= 80 else "medium", "event": event,
                    "matched_fields": {"retro_hunt": {"type": hit["type"], "value": hit["value"],
                                                      "field": hit["field"], "source": hit["source"],
                                                      "confidence": hit["confidence"], "log_ts": event.get("ts")}},
                    "attack_techniques": ["T1071"] if hit["threat_type"] == "botnet_cc" else [],
                })
                result["alerts"] += 1
    return result


async def store_alert(tenant_id: str, alert: Dict[str, Any]) -> None:
    """Save a retro-hunt alert as a security detection and route it into a case."""
    from services.case_service import CaseService
    from services.security_service import SecurityService

    raw = json.dumps({"normalized_log": alert["event"], "source_format": "retro_hunt"}, default=str)
    detection = {"id": alert["id"], "customer_id": tenant_id, "rule_id": alert["rule_id"],
                 "rule_title": alert["rule_title"], "severity": alert["severity"], "status": "triggered",
                 "raw_log_data": raw, "enrichment_data": json.dumps(alert["matched_fields"], default=str),
                 "attack_techniques": alert["attack_techniques"], "mitre_techniques": alert["attack_techniques"],
                 "matched_fields": alert["matched_fields"]}
    event_id = await SecurityService().create_security_event(detection)
    try:
        await CaseService().route_alert(tenant_id, {
            "id": event_id, "rule_id": alert["rule_id"], "title": alert["rule_title"], "severity": alert["severity"],
            "raw_log_data": raw, "mitre_techniques": alert["attack_techniques"], "created_at": datetime.now(timezone.utc)})
    except Exception as e:
        logger.warning(f"Retro-hunt alert {event_id} not routed into a case: {e}")


async def retro_hunt_new_indicators(tenant_id: str, keys: List[Key], days: int = 7) -> Dict[str, Any]:
    """Scheduler / API hook: hunt for indicators just added for a tenant."""
    from threat_intel_store import ThreatIntelDAO

    dao = ThreatIntelDAO()
    now = datetime.now(timezone.utc)
    wanted = {(k, normalize_indicator(v)) for k, v in keys}
    known = {(i.indicator_type, i.normalized()): i for i in await dao.active_indicators(tenant_id, now)
             if (i.indicator_type, i.normalized()) in wanted}
    result = await retro_hunt(tenant_id, wanted, known.get, db=dao.db, sink=store_alert, now=now, days=days)
    logger.info("Retro-hunt", tenant_id=tenant_id, **result)
    return result
