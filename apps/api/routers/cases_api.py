"""
Cases API (Phase 2): investigations built from alerts.

Mounted under /v1/security/cases, so it shares the security permissions
(security:read / security:write) and the security subscription feature.
The actor recorded on every change is the signed-in user.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from authn_authz_middleware import get_current_user
from cases import CaseError
from error_handling import internal_error
from models import User
import user_inbox

router = APIRouter(prefix="/v1/security/cases", tags=["cases"])


def _case_service():
    from services.case_service import CaseService

    return CaseService()


async def _notify(tenant_id: str, build) -> None:
    from dependencies import get_clickhouse_client

    await user_inbox.notify(get_clickhouse_client(), tenant_id, build)


def _actor(user: Any) -> str:
    return str(getattr(user, "email", None) or getattr(user, "id", "unknown"))


class Evidence(BaseModel):
    kind: str = Field(..., description="search | event | trace | log | link | file")
    ref: str = Field(..., max_length=4000, description="Query, event id, trace id or URL")
    title: Optional[str] = Field(None, max_length=300)
    data: Optional[Dict[str, Any]] = None


class CaseCreate(BaseModel):
    title: str = Field(..., max_length=300)
    severity: Optional[str] = Field(None, description="low | medium | high | critical (default: from the alerts)")
    description: str = Field("", max_length=20_000)
    tags: List[str] = Field(default_factory=list)
    alert_ids: List[str] = Field(default_factory=list, max_length=1000)
    evidence: List[Evidence] = Field(default_factory=list, max_length=100)
    assignee: Optional[str] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=20_000)
    severity: Optional[str] = None


class Assign(BaseModel):
    assignee: Optional[str] = Field(None, description="User to assign; null unassigns")


class Comment(BaseModel):
    text: str = Field(..., max_length=10_000, description="Markdown; @name mentions are recorded")


class StatusChange(BaseModel):
    status: str = Field(..., description="new | investigating | contained | resolved | false_positive")
    reason: str = Field("", max_length=2000, description="Required to close; becomes the alerts' verdict note")


class TagsChange(BaseModel):
    add: List[str] = Field(default_factory=list)
    remove: List[str] = Field(default_factory=list)


class AlertIds(BaseModel):
    alert_ids: List[str] = Field(..., min_length=1, max_length=1000)


class Merge(BaseModel):
    source_ids: List[str] = Field(..., min_length=1, max_length=100)


class Split(BaseModel):
    alert_ids: List[str] = Field(..., min_length=1, max_length=1000)
    title: Optional[str] = Field(None, max_length=300)


class Bulk(BaseModel):
    case_ids: List[str] = Field(..., min_length=1, max_length=500)
    action: str = Field(..., description="assign | set_status | tags")
    assignee: Optional[str] = None
    status: Optional[str] = None
    reason: str = ""
    add: List[str] = Field(default_factory=list)
    remove: List[str] = Field(default_factory=list)


async def _run(coro):
    from services.case_service import CaseNotFound

    try:
        return await coro
    except CaseNotFound:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error(e, "Case operation failed")


def _dict(case) -> Dict[str, Any]:
    from services.case_service import case_to_dict

    return case_to_dict(case)


@router.get("")
async def list_cases(
    status: Optional[List[str]] = Query(None),
    assignee: Optional[str] = None,
    severity: Optional[str] = None,
    q: Optional[str] = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Cases, most recently updated first."""
    cases, total = await _run(_case_service().list(customer_id, status=status, assignee=assignee,
                                                   severity=severity, q=q, limit=limit, offset=offset))
    return {"cases": [_dict(c) for c in cases], "total": total, "limit": limit, "offset": offset}


@router.post("", status_code=201)
async def create_case(body: CaseCreate, customer_id: str = Header(..., alias="X-Customer-ID"),
                      current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Create a case, optionally from alerts (severity and entities come from
    them) and with pinned evidence (a saved search, an event, a trace...)."""
    case = await _run(_case_service().create(
        customer_id, _actor(current_user), body.title, severity=body.severity, description=body.description,
        tags=body.tags, alert_ids=body.alert_ids, evidence=[e.model_dump(exclude_none=True) for e in body.evidence],
        assignee=body.assignee))
    return _dict(case)


@router.post("/bulk")
async def bulk_cases(body: Bulk, customer_id: str = Header(..., alias="X-Customer-ID"),
                     current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Assign, change status or tag many cases; failures are reported per case."""
    kwargs: Dict[str, Any] = {}
    if body.action == "assign":
        kwargs = {"assignee": body.assignee}
    elif body.action == "set_status":
        kwargs = {"status": body.status, "reason": body.reason}
    elif body.action == "tags":
        kwargs = {"add": body.add, "remove": body.remove}
    return await _run(_case_service().bulk(customer_id, body.case_ids, body.action, _actor(current_user), **kwargs))


@router.get("/metrics")
async def case_metrics(days: int = Query(30, ge=1, le=365), customer_id: str = Header(..., alias="X-Customer-ID"),
                       current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """SOC overview: time to acknowledge and resolve per severity, SLA
    breaches, open cases by status and age, analyst load, alerts per case.
    Covers cases created in the last `days` plus every case still open."""
    return await _run(_case_service().metrics(customer_id, days))


class SlaBody(BaseModel):
    acknowledge: Dict[str, int] = Field(default_factory=dict)
    resolve: Dict[str, int] = Field(default_factory=dict)


def _sla_view(overrides: Dict[str, Any]) -> Dict[str, Any]:
    from case_metrics import SLA_TARGETS, sla_targets

    minutes = lambda t: {k: {s: int(v.total_seconds() // 60) for s, v in per.items()} for k, per in t.items()}  # noqa: E731
    return {"targets_minutes": minutes(sla_targets(overrides)), "defaults_minutes": minutes(SLA_TARGETS),
            "overrides": overrides}


@router.get("/sla")
async def get_sla_targets(customer_id: str = Header(..., alias="X-Customer-ID"),
                          current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """This tenant's SLA targets (minutes to acknowledge and resolve per severity)."""
    return _sla_view(await _run(_case_service().sla_overrides(customer_id)))


@router.put("/sla")
async def put_sla_targets(body: SlaBody, customer_id: str = Header(..., alias="X-Customer-ID"),
                          current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Override the default targets; severities left out keep the default. {} resets."""
    overrides = {k: v for k, v in body.model_dump().items() if v}
    return _sla_view(await _run(_case_service().set_sla_overrides(customer_id, overrides, _actor(current_user))))


@router.get("/audit/export")
async def export_case_audit(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(100_000, ge=1, le=1_000_000),
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user),
):
    """Every case change (who, what, when) in a time range, as JSON or CSV
    (default: the last 30 days)."""
    from fastapi.responses import Response

    from case_metrics import events_to_csv

    end = _utc(end) or datetime.now(timezone.utc)
    start = _utc(start) or end - timedelta(days=30)
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start")
    if end - start > timedelta(days=366):
        raise HTTPException(status_code=400, detail="the range can be at most 366 days")
    events = await _run(_case_service().audit(customer_id, start, end, limit))
    if format == "csv":
        return Response(content=events_to_csv(events), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="case-audit-{start:%Y%m%d}-{end:%Y%m%d}.csv"'})
    return {"start": start.isoformat(), "end": end.isoformat(), "count": len(events), "events": events}


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@router.get("/{case_id}")
async def get_case(case_id: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                   current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """The case, its alerts and its timeline (alerts, notes, status changes,
    evidence) in order."""
    return await _run(_case_service().details(customer_id, case_id))


@router.patch("/{case_id}")
async def update_case(case_id: str, body: CaseUpdate, customer_id: str = Header(..., alias="X-Customer-ID"),
                      current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return _dict(await _run(_case_service().act(customer_id, case_id, "update", _actor(current_user),
                                                **body.model_dump())))


@router.post("/{case_id}/assign")
async def assign_case(case_id: str, body: Assign, customer_id: str = Header(..., alias="X-Customer-ID"),
                      current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    actor = _actor(current_user)
    case = await _run(_case_service().act(customer_id, case_id, "assign", actor, assignee=body.assignee))
    await _notify(customer_id, lambda members: user_inbox.assignment_notice(case, actor, members))
    return _dict(case)


@router.post("/{case_id}/comments")
async def comment_case(case_id: str, body: Comment, customer_id: str = Header(..., alias="X-Customer-ID"),
                       current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    actor = _actor(current_user)
    case = await _run(_case_service().act(customer_id, case_id, "comment", actor, text=body.text))
    await _notify(customer_id, lambda members: user_inbox.mention_notices(case, body.text, actor, members))
    return _dict(case)


@router.post("/{case_id}/status")
async def set_case_status(case_id: str, body: StatusChange, customer_id: str = Header(..., alias="X-Customer-ID"),
                          current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Move the case through its workflow. Closing needs a reason, which is
    also set on the case's alerts (false_positive feeds tuning suggestions)."""
    return _dict(await _run(_case_service().act(customer_id, case_id, "set_status", _actor(current_user),
                                                status=body.status, reason=body.reason)))


@router.post("/{case_id}/tags")
async def tag_case(case_id: str, body: TagsChange, customer_id: str = Header(..., alias="X-Customer-ID"),
                   current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return _dict(await _run(_case_service().act(customer_id, case_id, "tags", _actor(current_user),
                                                add=body.add, remove=body.remove)))


@router.post("/{case_id}/evidence")
async def pin_evidence(case_id: str, body: Evidence, customer_id: str = Header(..., alias="X-Customer-ID"),
                       current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return _dict(await _run(_case_service().act(customer_id, case_id, "pin_evidence", _actor(current_user),
                                                evidence=body.model_dump(exclude_none=True))))


@router.delete("/{case_id}/evidence/{evidence_id}")
async def unpin_evidence(case_id: str, evidence_id: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                         current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Take back a pin (the pin stays in the timeline, marked as taken back)."""
    return _dict(await _run(_case_service().act(customer_id, case_id, "unpin_evidence", _actor(current_user),
                                                evidence_id=evidence_id)))


@router.post("/{case_id}/alerts")
async def attach_alerts(case_id: str, body: AlertIds, customer_id: str = Header(..., alias="X-Customer-ID"),
                        current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return _dict(await _run(_case_service().attach_alerts(customer_id, case_id, body.alert_ids,
                                                          _actor(current_user))))


@router.post("/{case_id}/merge")
async def merge_case(case_id: str, body: Merge, customer_id: str = Header(..., alias="X-Customer-ID"),
                     current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Merge other cases into this one; they are closed as merged."""
    return _dict(await _run(_case_service().merge(customer_id, case_id, body.source_ids, _actor(current_user))))


@router.post("/{case_id}/split")
async def split_case_route(case_id: str, body: Split, customer_id: str = Header(..., alias="X-Customer-ID"),
                           current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Move some alerts into a new case."""
    remaining, created = await _run(_case_service().split(customer_id, case_id, body.alert_ids,
                                                          _actor(current_user), title=body.title))
    return {"case": _dict(remaining), "new_case": _dict(created)}
