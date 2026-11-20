"""
Playbooks wired to the platform (Phase 13): the real actions, enrichment,
searches and ticket links for engine.Runner, starting runs from new alerts
and cases (dispatch), and expiring approvals.

dispatch() looks back LOOKBACK over alerts and cases, so a run is started
even if the API was down a while; (playbook, trigger_ref) makes it start
once. With several API replicas only the one holding the Redis lock
dispatches in a given tick.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from integrations import actions
from integrations.store import IntegrationStore
from integrations.tickets import TicketStore

from . import model
from .engine import FINAL, Run, Runner
from .store import PlaybookStore

logger = logging.getLogger(__name__)
LOOKBACK = timedelta(minutes=int(os.getenv("LOGFORGE_PLAYBOOK_LOOKBACK_MINUTES", "15")))
TICK_SECONDS = int(os.getenv("LOGFORGE_PLAYBOOK_TICK_SECONDS", "15"))
MAX_RUNS_PER_TICK = 200


def _client():
    from dependencies import get_clickhouse_client

    return get_clickhouse_client()


def integrations_by_name(client, tenant_id: str) -> Dict[str, Dict[str, Any]]:
    store = IntegrationStore(client)
    out = {}
    for item in store.list(tenant_id):
        full = store.get(tenant_id, item["id"], with_secrets=True)
        if full and full.get("enabled", True):
            out[full["name"]] = full
    return out


def build_runner(client=None, http=None) -> Runner:
    client = client or _client()

    async def action(integration, inputs, ctx):
        return await actions.run(integration["kind"], integration["config"], integration.get("secrets") or {},
                                 inputs, ctx, http=http, render=False)

    async def enrich(tenant_id, spec, ctx):
        from ai.tools import _indicators

        value = str(spec.get("indicator") or spec.get("entity") or "")
        matches = [m if isinstance(m, dict) else getattr(m, "__dict__", {}) for m in await _indicators(value, tenant_id)]
        best = max((int(m.get("confidence") or 0) for m in matches), default=0)
        verdict = "malicious" if best >= 70 else "suspicious" if matches else "unknown"
        return {"value": value, "verdict": verdict, "matches": [
            {k: str(v) for k, v in m.items() if k in ("indicator_type", "value", "threat_type", "confidence",
                                                       "source")} for m in matches[:10]]}

    async def search(tenant_id, spec, ctx):
        from routers.query import execute_pipeline_text, _parse_since

        end = datetime.now(timezone.utc)
        start = end - _parse_since(spec.get("since") or "24h")
        result = await execute_pipeline_text(spec["query"], tenant_id, start, end)
        rows = result["rows"][:50]
        return {"rows": json.loads(json.dumps(rows, default=str)), "count": len(result["rows"])}

    def link(tenant_id, case_id, ticket):
        TicketStore(client).link(tenant_id, case_id, ticket)

    return Runner(action=action, enrich=enrich, search=search, link_ticket=link,
                  integrations=lambda tenant: integrations_by_name(client, tenant))


def run_id(playbook_id: str, trigger_ref: str) -> str:
    return hashlib.sha256(f"{playbook_id}:{trigger_ref}".encode()).hexdigest()[:32]


# -- trigger events ------------------------------------------------------------------

def _alert_context(row: Dict[str, Any]) -> Dict[str, Any]:
    from services.case_service import alert_summary

    alert = alert_summary(dict(row))
    alert["title"] = row.get("title") or alert.get("title", "")
    return {"id": alert.get("id"), "title": alert.get("title"), "severity": alert.get("severity"),
            "rule_id": alert.get("rule_id"), "status": row.get("status"), "ts": str(alert.get("ts")),
            "mitre_techniques": list(row.get("mitre_techniques") or []), "entities": alert.get("entities") or {}}


def _case_context(row: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": row["id"], "title": row["title"], "severity": row["severity"], "status": row["status"],
            "assignee": row.get("assignee"), "tags": list(row.get("tags") or []),
            "alert_ids": list(row.get("alert_ids") or []), "created_at": str(row.get("created_at"))}


def events(client, tenant_id: str, since: datetime) -> List[Tuple[str, str, Dict[str, Any]]]:
    """(trigger, trigger_ref, context) for alerts and cases since `since`."""
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    cols = ["id", "rule_id", "title", "severity", "status", "raw_log_data", "mitre_techniques", "created_at"]
    alerts = client.query(
        f"SELECT {', '.join(cols)} FROM security_events_mt WHERE customer_id = {{tenant:String}} "
        "AND created_at >= {since:DateTime64(3)} ORDER BY created_at LIMIT 1000",
        parameters={"tenant": tenant_id, "since": since}).result_rows
    case_cols = ["id", "title", "severity", "status", "assignee", "tags", "alert_ids", "created_at", "updated_at"]
    cases = [dict(zip(case_cols, r)) for r in client.query(
        f"SELECT {', '.join(case_cols)} FROM cases_mt FINAL WHERE tenant_id = {{tenant:String}} "
        "AND updated_at >= {since:DateTime64(3)} AND merged_into = '' ORDER BY updated_at LIMIT 1000",
        parameters={"tenant": tenant_id, "since": since}).result_rows]
    case_of_alert = {a: c for c in cases for a in c["alert_ids"]}
    for r in alerts:
        row = dict(zip(cols, r))
        ctx = {"alert": _alert_context(row), "tenant": {"id": tenant_id}}
        if row["id"] in case_of_alert:
            ctx["case"] = _case_context(case_of_alert[row["id"]])
        out.append(("alert", f"alert:{row['id']}", ctx))
    for c in cases:
        created = c["created_at"] >= since if isinstance(c["created_at"], datetime) else False
        ctx = {"case": _case_context(c), "tenant": {"id": tenant_id}}
        if created:
            out.append(("case_created", f"case:{c['id']}", ctx))
        out.append(("case_updated", f"case:{c['id']}:{c['updated_at']}", ctx))
    return out


async def dispatch(client=None, now: Optional[datetime] = None, runner: Optional[Runner] = None,
                   tenants: Optional[List[str]] = None) -> Dict[str, Any]:
    """Start the runs new alerts and cases call for; expire overdue approvals."""
    client = client or _client()
    now = now or datetime.now(timezone.utc)
    store = PlaybookStore(client)
    runner = runner or build_runner(client)
    report = {"started": 0, "expired": 0, "errors": []}
    for tenant in tenants if tenants is not None else await asyncio.to_thread(store.tenants):
        playbooks = []
        for p in await asyncio.to_thread(store.list, tenant, True):
            try:
                playbooks.append((p, model.parse(p["definition"])))
            except model.PlaybookError as e:
                report["errors"].append(f"{tenant} {p['name']}: {e}")
        if not playbooks:
            continue
        evts = await asyncio.to_thread(events, client, tenant, now - LOOKBACK)
        for p, pb in playbooks:
            matching = [(t, ref, ctx) for t, ref, ctx in evts if pb.matches(t, ctx)]
            done = await asyncio.to_thread(store.started, tenant, p["id"], [ref for _, ref, _ in matching])
            for trigger, ref, ctx in matching:
                if ref in done or report["started"] >= MAX_RUNS_PER_TICK:
                    continue
                try:
                    run = await runner.start(tenant, pb, trigger, ctx, playbook_id=p["id"], trigger_ref=ref)
                    run.id = run_id(p["id"], ref)
                    await asyncio.to_thread(store.save_run, run)
                    report["started"] += 1
                except Exception as e:
                    report["errors"].append(f"{tenant} {p['name']} {ref}: {e}")
        for run in await asyncio.to_thread(store.list_runs, tenant, "waiting_approval", 500):
            if runner.expire(run):
                await asyncio.to_thread(store.save_run, run)
                report["expired"] += 1
    return report


async def _locked(seconds: int) -> bool:
    """One dispatcher per tick across API replicas (Redis SET NX); without Redis, run."""
    try:
        import redis.asyncio as redis

        r = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", "6379")),
                        socket_timeout=2)
        return bool(await r.set("logforge:playbooks:dispatch", "1", nx=True, ex=max(1, seconds - 1)))
    except Exception:
        return True


async def loop() -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        try:
            if await _locked(TICK_SECONDS):
                report = await dispatch()
                if report["started"] or report["errors"]:
                    logger.info("Playbooks: %s", report)
        except Exception as e:
            logger.error("Playbook dispatch failed: %s", e)


def start() -> bool:
    if os.getenv("LOGFORGE_PLAYBOOKS", "on").lower() in ("off", "false", "0"):
        return False
    asyncio.create_task(loop())
    return True


__all__ = ["build_runner", "dispatch", "events", "run_id", "start", "FINAL", "Run"]
