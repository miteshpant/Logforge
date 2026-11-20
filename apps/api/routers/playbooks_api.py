"""
Playbooks API (Phase 13), under /v1/playbooks.

  GET    /v1/playbooks                    definitions (security:read)
  POST   /v1/playbooks                    {definition (YAML), enabled} (settings:write: tenant admins)
  POST   /v1/playbooks/validate           {definition}: errors, or the parsed trigger and steps
  GET    /v1/playbooks/{id}
  PUT    /v1/playbooks/{id}
  DELETE /v1/playbooks/{id}
  POST   /v1/playbooks/{id}/run           {alert_id | case_id}: run it now on that alert or case (security:write)
  GET    /v1/playbooks/runs               ?status=waiting_approval
  GET    /v1/playbooks/runs/{run_id}
  POST   /v1/playbooks/runs/{run_id}/decision   {step, decision: approve|reject, note} (security:write,
                                          and one of the step's approver roles)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from error_handling import internal_error
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from tenant_dependencies import MiddlewareTenant

from playbooks import model
from playbooks.engine import RunError

router = APIRouter(prefix="/v1/playbooks", tags=["playbooks"])


class PlaybookBody(BaseModel):
    definition: str = Field(..., min_length=1, max_length=50_000)
    enabled: bool = True


class RunBody(BaseModel):
    alert_id: Optional[str] = None
    case_id: Optional[str] = None


class DecisionBody(BaseModel):
    step: str
    decision: str
    note: str = Field("", max_length=2000)


def _client():
    from dependencies import get_clickhouse_client

    return get_clickhouse_client()


def _store():
    from playbooks.store import PlaybookStore

    return PlaybookStore(_client())


def _runner():
    from playbooks.service import build_runner

    return build_runner(_client())


def _integrations(tenant_id: str) -> Dict[str, Dict[str, Any]]:
    from playbooks.service import integrations_by_name

    return integrations_by_name(_client(), tenant_id)


def _user(request: Request) -> str:
    user = getattr(request.state, "user", None)
    return str(getattr(user, "email", None) or getattr(user, "id", "") or "")


async def _roles(request: Request, tenant_id: str) -> List[str]:
    user = getattr(request.state, "user", None)
    if user is None:
        return []
    from authn_authz_middleware import get_user_service

    roles = await get_user_service().get_user_tenant_roles(str(user.id), tenant_id)
    return [str(r.get("role")) for r in roles if r.get("tenant_id") in (tenant_id, "platform")]


def _summary(p: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(p)
    try:
        pb = model.parse(p["definition"])
        out.update(trigger=pb.trigger_on, when=pb.when, steps=[{"id": s.id, "type": s.type} for s in pb.steps],
                   error=None)
    except model.PlaybookError as e:
        out.update(trigger=None, when=None, steps=[], error=str(e))
    return out


async def _parse(definition: str, tenant_id: str) -> model.Playbook:
    try:
        return model.parse(definition, integrations=await asyncio.to_thread(_integrations, tenant_id))
    except model.PlaybookError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("")
async def list_playbooks(customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    try:
        return {"playbooks": [_summary(p) for p in await asyncio.to_thread(_store().list, customer_id)]}
    except Exception as e:
        raise internal_error(e, "Failed to list playbooks", customer_id=customer_id)


@router.post("/validate")
async def validate(body: PlaybookBody, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    try:
        pb = model.parse(body.definition, integrations=await asyncio.to_thread(_integrations, customer_id))
    except model.PlaybookError as e:
        return {"valid": False, "error": str(e)}
    return {"valid": True, "name": pb.name, "trigger": pb.trigger_on, "when": pb.when,
            "steps": [{"id": s.id, "type": s.type, "containment": s.containment} for s in pb.steps]}


@router.post("", status_code=201)
async def create(body: PlaybookBody, request: Request, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    pb = await _parse(body.definition, customer_id)
    saved = await asyncio.to_thread(_store().save, customer_id, pb.name, body.definition, body.enabled,
                                    _user(request))
    return {"playbook": _summary(saved)}


@router.get("/runs")
async def list_runs(customer_id: str = MiddlewareTenant, status: Optional[str] = Query(None),
                    limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    runs = await asyncio.to_thread(_store().list_runs, customer_id, status, limit)
    return {"runs": [r.to_dict() for r in runs]}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    run = await asyncio.to_thread(_store().get_run, customer_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="No such run")
    return {"run": run.to_dict()}


@router.post("/runs/{run_id}/decision")
async def decide(run_id: str, body: DecisionBody, request: Request,
                 customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    store = _store()
    run = await asyncio.to_thread(store.get_run, customer_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="No such run")
    playbook = await asyncio.to_thread(store.get, customer_id, run.playbook_id)
    if not playbook:
        raise HTTPException(status_code=409, detail="The run's playbook was deleted")
    waiting = run.waiting_step()
    if waiting and waiting["id"] == body.step:
        allowed = set(waiting.get("approvers") or model.DEFAULT_APPROVERS)
        if not allowed & set(await _roles(request, customer_id)):
            raise HTTPException(status_code=403, detail=f"Approving this step needs one of: {', '.join(sorted(allowed))}")
    try:
        run = await _runner().decide(run, model.parse(playbook["definition"]), body.step, body.decision,
                                     user=_user(request), note=body.note)
    except RunError as e:
        await asyncio.to_thread(store.save_run, run)  # an expiry found here is saved
        raise HTTPException(status_code=409, detail=str(e))
    await asyncio.to_thread(store.save_run, run)
    return {"run": run.to_dict()}


@router.get("/{playbook_id}")
async def get_one(playbook_id: str, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    found = await asyncio.to_thread(_store().get, customer_id, playbook_id)
    if not found:
        raise HTTPException(status_code=404, detail="No such playbook")
    return {"playbook": _summary(found)}


@router.put("/{playbook_id}")
async def update(playbook_id: str, body: PlaybookBody, request: Request,
                 customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    store = _store()
    if not await asyncio.to_thread(store.get, customer_id, playbook_id):
        raise HTTPException(status_code=404, detail="No such playbook")
    pb = await _parse(body.definition, customer_id)
    saved = await asyncio.to_thread(store.save, customer_id, pb.name, body.definition, body.enabled, _user(request),
                                    playbook_id)
    return {"playbook": _summary(saved)}


@router.delete("/{playbook_id}")
async def delete(playbook_id: str, request: Request, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    store = _store()
    found = await asyncio.to_thread(store.get, customer_id, playbook_id)
    if not found:
        raise HTTPException(status_code=404, detail="No such playbook")
    await asyncio.to_thread(store.save, customer_id, found["name"], found["definition"], False, _user(request),
                            playbook_id, True)
    return {"deleted": playbook_id}


@router.post("/{playbook_id}/run")
async def run_now(playbook_id: str, body: RunBody, request: Request,
                  customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    from playbooks.service import _alert_context, _case_context

    store = _store()
    found = await asyncio.to_thread(store.get, customer_id, playbook_id)
    if not found:
        raise HTTPException(status_code=404, detail="No such playbook")
    pb = await _parse(found["definition"], customer_id)
    client = _client()
    ctx: Dict[str, Any] = {"tenant": {"id": customer_id}, "requested_by": _user(request)}
    if body.alert_id:
        cols = ["id", "rule_id", "title", "severity", "status", "raw_log_data", "mitre_techniques", "created_at"]
        rows = await asyncio.to_thread(lambda: client.query(
            f"SELECT {', '.join(cols)} FROM security_events_mt WHERE customer_id = {{tenant:String}} "
            "AND id = {id:String} LIMIT 1", parameters={"tenant": customer_id, "id": body.alert_id}).result_rows)
        if not rows:
            raise HTTPException(status_code=404, detail="No such alert")
        ctx["alert"] = _alert_context(dict(zip(cols, rows[0])))
    if body.case_id:
        cols = ["id", "title", "severity", "status", "assignee", "tags", "alert_ids", "created_at", "updated_at"]
        rows = await asyncio.to_thread(lambda: client.query(
            f"SELECT {', '.join(cols)} FROM cases_mt FINAL WHERE tenant_id = {{tenant:String}} AND id = {{id:String}}",
            parameters={"tenant": customer_id, "id": body.case_id}).result_rows)
        if not rows:
            raise HTTPException(status_code=404, detail="No such case")
        ctx["case"] = _case_context(dict(zip(cols, rows[0])))
    if "alert" not in ctx and "case" not in ctx:
        raise HTTPException(status_code=422, detail="Give an alert_id or a case_id")
    try:
        run = await _runner().start(customer_id, pb, "manual", ctx, playbook_id=playbook_id,
                                    trigger_ref=f"manual:{uuid.uuid4().hex}")
    except Exception as e:
        raise internal_error(e, "Playbook run failed", customer_id=customer_id)
    await asyncio.to_thread(store.save_run, run)
    return {"run": run.to_dict()}
