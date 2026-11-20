"""
Exports and reports API (Phase 13), under /v1/reports.

  GET  /v1/reports/attack-navigator         the tenant's coverage as an ATT&CK Navigator layer (security:read)
  GET  /v1/reports/soc?days=30&format=json|csv|pdf   the security operations report (security:read)
  GET  /v1/reports/schedules                scheduled reports
  POST /v1/reports/schedules                {name, every: daily|weekly|monthly, hour, format: pdf|csv,
                                             integration_id (email), recipients} (settings:write)
  PUT  /v1/reports/schedules/{id}, DELETE /v1/reports/schedules/{id}
  POST /v1/reports/schedules/{id}/send      send it now
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from error_handling import internal_error
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from tenant_dependencies import MiddlewareTenant

import reports

router = APIRouter(prefix="/v1/reports", tags=["reports"])
logger = logging.getLogger(__name__)
TICK_SECONDS = int(os.getenv("LOGFORGE_REPORT_TICK_SECONDS", "600"))
CONTENT = {"pdf": "application/pdf", "csv": "text/csv"}


class ScheduleBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    every: str = Field("weekly", pattern="^(daily|weekly|monthly)$")
    hour: int = Field(7, ge=0, le=23)
    format: str = Field("pdf", pattern="^(pdf|csv)$")
    integration_id: str
    recipients: List[str] = Field(default_factory=list, max_length=50)
    enabled: bool = True


def _client():
    from dependencies import get_clickhouse_client

    return get_clickhouse_client()


async def _coverage(tenant_id: str) -> Dict[str, Any]:
    from services.security_service import get_security_service

    return await get_security_service().get_mitre_coverage(tenant_id)


async def gather(tenant_id: str, start: datetime, end: datetime) -> Dict[str, Any]:
    """Everything the report needs, for one tenant and period."""
    from playbooks.store import PlaybookStore
    from services.case_service import CaseService
    from tier_manager import TierManager

    import storage_tiers as st

    client = _client()
    days = max(1, (end - start).days)
    alerts = await asyncio.to_thread(lambda: dict(client.query(
        "SELECT severity, count() FROM security_events_mt WHERE customer_id = {tenant:String} "
        "AND created_at >= {start:DateTime64(3)} AND created_at < {end:DateTime64(3)} GROUP BY severity",
        parameters={"tenant": tenant_id, "start": start, "end": end}).result_rows))
    case_metrics = await CaseService().metrics(tenant_id, days)
    try:
        coverage = await _coverage(tenant_id)
    except Exception as e:
        logger.warning("Report without coverage: %s", e)
        coverage = {}
    policies = await asyncio.to_thread(lambda: TierManager(client, None, st.load_config()).policies(tenant_id))
    runs = [r for r in await asyncio.to_thread(PlaybookStore(client).list_runs, tenant_id, None, 1000)
            if start.isoformat() <= r.created_at < end.isoformat()]
    approvals = [s["decision"] for r in runs for s in r.steps if s.get("decision")]
    return {"tenant": tenant_id, "start": start, "end": end, "alerts_by_severity": alerts,
            "case_metrics": case_metrics, "coverage": coverage,
            "retention": [p.__dict__ for p in policies.values()],
            "playbook_runs": [{"status": r.status} for r in runs], "approvals": approvals}


def render(report: Dict[str, Any], fmt: str):
    if fmt == "pdf":
        return reports.to_pdf(report)
    if fmt == "csv":
        return reports.to_csv(report).encode()
    raise ValueError(fmt)


@router.get("/attack-navigator")
async def attack_navigator(customer_id: str = MiddlewareTenant):
    try:
        layer = reports.navigator_layer(await _coverage(customer_id), customer_id, datetime.now(timezone.utc))
    except Exception as e:
        raise internal_error(e, "Failed to export coverage", customer_id=customer_id)
    return JSONResponse(layer, headers={"Content-Disposition": 'attachment; filename="logforge-coverage-layer.json"'})


@router.get("/soc")
async def soc_report(customer_id: str = MiddlewareTenant, days: int = Query(30, ge=1, le=366),
                     format: str = Query("json", pattern="^(json|csv|pdf)$")):
    end = datetime.now(timezone.utc)
    try:
        report = reports.build(await gather(customer_id, end - timedelta(days=days), end))
    except Exception as e:
        raise internal_error(e, "Failed to build the report", customer_id=customer_id)
    if format == "json":
        return report
    name = f"logforge-soc-report-{report['period']['end']}.{format}"
    return Response(render(report, format), media_type=CONTENT[format],
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# -- schedules ------------------------------------------------------------------------------

def _schedules(tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    where = "WHERE customer_id = {tenant:String}" if tenant_id else ""
    rows = _client().query(
        "SELECT customer_id, id, argMax(name, updated_at), argMax(every, updated_at), argMax(hour, updated_at), "
        "argMax(format, updated_at), argMax(integration_id, updated_at), argMax(recipients, updated_at), "
        "argMax(enabled, updated_at), argMax(last_sent, updated_at), argMax(last_error, updated_at) "
        f"FROM report_schedules_mt {where} GROUP BY customer_id, id HAVING argMax(deleted, updated_at) = 0",
        parameters={"tenant": tenant_id} if tenant_id else None).result_rows
    keys = ["tenant_id", "id", "name", "every", "hour", "format", "integration_id", "recipients", "enabled",
            "last_sent", "last_error"]
    return [dict(zip(keys, r)) for r in rows]


def _save(tenant_id: str, s: Dict[str, Any], user: str, deleted: bool = False) -> None:
    _client().command(
        "INSERT INTO report_schedules_mt (customer_id, id, name, every, hour, format, integration_id, recipients, "
        "enabled, deleted, last_sent, last_error, updated_by) SELECT {tenant:String}, {id:String}, {name:String}, "
        "{every:String}, {hour:UInt8}, {format:String}, {integration:String}, {recipients:Array(String)}, "
        "{enabled:UInt8}, {deleted:UInt8}, {last_sent:Nullable(DateTime64(3))}, {error:String}, {user:String}",
        parameters={"tenant": tenant_id, "id": s["id"], "name": s["name"], "every": s["every"], "hour": s["hour"],
                    "format": s["format"], "integration": s["integration_id"], "recipients": s["recipients"],
                    "enabled": int(s.get("enabled", True)), "deleted": int(deleted), "last_sent": s.get("last_sent"),
                    "error": s.get("last_error", ""), "user": user})


def _public(s: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in s.items() if k != "tenant_id"}
    out["last_sent"] = s["last_sent"].isoformat() if isinstance(s.get("last_sent"), datetime) else s.get("last_sent")
    out["enabled"] = bool(s.get("enabled"))
    return out


async def send(tenant_id: str, schedule: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    from integrations import actions
    from integrations.store import IntegrationStore

    now = now or datetime.now(timezone.utc)
    integration = await asyncio.to_thread(IntegrationStore(_client()).get, tenant_id, schedule["integration_id"], True)
    if not integration or integration["kind"] != "email":
        result = actions.ActionResult(False, error="the schedule's integration is missing or isn't email")
    else:
        start, end = reports.window(schedule, now)
        report = reports.build(await gather(tenant_id, start, end))
        data = render(report, schedule["format"])
        p = report["period"]
        inputs = {"to": schedule["recipients"], "subject": f"{schedule['name']}: {p['start']} to {p['end']}",
                  "body": f"The Logforge security operations report for {p['start']} to {p['end']} is attached.",
                  "attachments": [{"filename": f"logforge-soc-report-{p['end']}.{schedule['format']}",
                                   "content_type": CONTENT[schedule["format"]],
                                   "content_b64": base64.b64encode(data).decode()}]}
        result = await actions.run("email", integration["config"], integration["secrets"], inputs, {}, render=False)
    updated = {**schedule, "last_error": "" if result.ok else result.error}
    if result.ok:
        updated["last_sent"] = now
    await asyncio.to_thread(_save, tenant_id, updated, "report-scheduler")
    return result.to_dict()


@router.get("/schedules")
async def list_schedules(customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    return {"schedules": [_public(s) for s in await asyncio.to_thread(_schedules, customer_id)]}


@router.post("/schedules", status_code=201)
async def create_schedule(body: ScheduleBody, request: Request, customer_id: str = MiddlewareTenant):
    s = {"id": uuid.uuid4().hex, **body.model_dump()}
    await asyncio.to_thread(_save, customer_id, s, str(getattr(getattr(request.state, "user", None), "id", "")))
    return {"schedule": _public({**s, "last_sent": None, "last_error": ""})}


async def _one(tenant_id: str, sid: str) -> Dict[str, Any]:
    found = next((s for s in await asyncio.to_thread(_schedules, tenant_id) if s["id"] == sid), None)
    if not found:
        raise HTTPException(status_code=404, detail="No such schedule")
    return found


@router.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, body: ScheduleBody, request: Request,
                          customer_id: str = MiddlewareTenant):
    found = await _one(customer_id, schedule_id)
    s = {**found, **body.model_dump()}
    await asyncio.to_thread(_save, customer_id, s, str(getattr(getattr(request.state, "user", None), "id", "")))
    return {"schedule": _public(s)}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, request: Request, customer_id: str = MiddlewareTenant):
    found = await _one(customer_id, schedule_id)
    await asyncio.to_thread(_save, customer_id, found, "", True)
    return {"deleted": schedule_id}


@router.post("/schedules/{schedule_id}/send")
async def send_now(schedule_id: str, customer_id: str = MiddlewareTenant):
    return {"result": await send(customer_id, await _one(customer_id, schedule_id))}


async def loop() -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        try:
            now = datetime.now(timezone.utc)
            for s in await asyncio.to_thread(_schedules):
                last = s.get("last_sent")
                if last is not None and last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if s["enabled"] and reports.due(s, last, now):
                    await send(s["tenant_id"], s, now)
        except Exception as e:
            logger.error("Report scheduler failed: %s", e)


def start() -> bool:
    if os.getenv("LOGFORGE_REPORT_SCHEDULER", "on").lower() in ("off", "false", "0"):
        return False
    asyncio.create_task(loop())
    return True
