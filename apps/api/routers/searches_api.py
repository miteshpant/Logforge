"""
Saved and scheduled searches API (Phase 6), under /v1/query/searches.

Reading needs queries:read, changing queries:write (the /v1/query/ prefix in
authn_authz_middleware). A query is compiled before it is stored, so a
saved search that saves is one that can run.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Response

from authn_authz_middleware import get_current_user
from error_handling import internal_error
from models import User
from saved_searches import Run, Runner, SavedSearch, SearchStore, SearchValidationError

router = APIRouter(prefix="/v1/query/searches", tags=["saved searches"])
MAX_SEARCHES = 200


def _store():
    return SearchStore()


async def _validate_query(tenant_id: str, query: str) -> None:
    from routers.query import validate_pipeline_text

    try:
        await validate_pipeline_text(query, tenant_id)
    except ValueError as e:
        raise SearchValidationError(str(e)) from None


async def _execute(query: str, tenant_id: str, start: datetime, end: datetime) -> Dict[str, Any]:
    from routers.query import execute_pipeline_text

    return await execute_pipeline_text(query, tenant_id, start, end)


async def _write_alert(tenant_id: str, search: SavedSearch, run: Run, result: Dict[str, Any]) -> str:
    from dao.alert_dao import AlertDAO

    alert_id = str(uuid.uuid4())
    condition = search.alert.condition
    await AlertDAO().save_alert_instance({
        "id": alert_id, "alert_id": alert_id, "rule_id": f"search:{search.id}", "customer_id": tenant_id,
        "status": "triggered", "triggered_at": run.run_at,
        "trigger_data": json.dumps({
            "source": "saved_search", "title": f"Search alert: {search.name}", "severity": search.alert.severity,
            "search_id": search.id, "search_name": search.name, "query": search.query,
            "condition": {"kind": condition.kind, "field": condition.field, "op": condition.op,
                          "value": condition.value},
            "value": run.value, "rows": run.rows,
            "window_start": run.window_start.isoformat(), "window_end": run.window_end.isoformat(),
            "sample": (result.get("rows") or [])[:20]}, default=str),
    })
    return alert_id


async def _send(tenant_id: str, channel_id: str, payload: Dict[str, Any], event_type: str) -> None:
    from dao.alert_dao import AlertDAO
    from services.notification_service import get_notification_service

    channels = {c.get("id"): c for c in await AlertDAO().list_notification_channels(tenant_id)}
    channel = channels.get(channel_id)
    if channel is None:
        raise LookupError(f"notification channel {channel_id} not found")
    if not channel.get("is_enabled", 1):
        return
    service = get_notification_service()
    result = await service.send_to_channel(channel, json.loads(json.dumps(payload, default=str)),
                                           event_type=event_type)
    event_id = payload.get("alert_id") or f"search:{payload['search']['id']}:{payload['window']['end']}"
    await service.record_delivery(tenant_id, event_id, channel_id, str(channel.get("channel_type", "webhook")),
                                  result)


def _runner() -> Runner:
    return Runner(store=_store(), execute=_execute, alert=_write_alert, send=_send)


def _actor(user) -> str:
    return getattr(user, "email", None) or getattr(user, "id", "") or ""


async def _parse(tenant_id: str, body: Dict[str, Any], search_id: Optional[str] = None) -> SavedSearch:
    try:
        search = SavedSearch.from_dict({**body, **({"id": search_id} if search_id else {})})
        await _validate_query(tenant_id, search.query)
    except SearchValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return search


async def _with_last_run(store, tenant_id: str, search: SavedSearch) -> Dict[str, Any]:
    last = await store.last_runs(tenant_id, search.id, limit=1)
    return {**search.to_public(), "last_run": last[0].to_public() if last else None}


@router.get("")
async def list_searches(customer_id: str = Header(..., alias="X-Customer-ID")):
    store = _store()
    try:
        searches = await store.list(customer_id)
        return {"searches": [await _with_last_run(store, customer_id, s) for s in searches]}
    except Exception as e:
        raise internal_error(e, "Failed to list saved searches", customer_id=customer_id)


@router.post("", status_code=201)
async def create_search(body: Dict[str, Any] = Body(...), customer_id: str = Header(..., alias="X-Customer-ID"),
                        user: User = Depends(get_current_user)):
    search = await _parse(customer_id, body)
    store = _store()
    if await store.get(customer_id, search.id) is not None:
        raise HTTPException(status_code=409, detail=f"A saved search {search.id} already exists")
    if len(await store.list(customer_id)) >= MAX_SEARCHES:
        raise HTTPException(status_code=400, detail=f"A tenant can have at most {MAX_SEARCHES} saved searches")
    return (await store.save(customer_id, search, _actor(user))).to_public()


@router.get("/{search_id}")
async def get_search(search_id: str, customer_id: str = Header(..., alias="X-Customer-ID")):
    store = _store()
    search = await store.get(customer_id, search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return await _with_last_run(store, customer_id, search)


@router.put("/{search_id}")
async def update_search(search_id: str, body: Dict[str, Any] = Body(...),
                        customer_id: str = Header(..., alias="X-Customer-ID"),
                        user: User = Depends(get_current_user)):
    store = _store()
    if await store.get(customer_id, search_id) is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    search = await _parse(customer_id, body, search_id)
    return (await store.save(customer_id, search, _actor(user))).to_public()


@router.delete("/{search_id}", status_code=204)
async def delete_search(search_id: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                        user: User = Depends(get_current_user)):
    store = _store()
    if await store.get(customer_id, search_id) is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    await store.delete(customer_id, search_id, _actor(user))
    return Response(status_code=204)


@router.post("/{search_id}/run")
async def run_search(search_id: str, dry_run: bool = Query(True, description="Preview: no alert, report or record"),
                     customer_id: str = Header(..., alias="X-Customer-ID")):
    runner = _runner()
    search = await runner.store.get(customer_id, search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    run, result = await runner.run(customer_id, search, datetime.now(timezone.utc), trigger="manual",
                                   dry_run=dry_run)
    return {"run": run.to_public(), "result": result}


@router.get("/{search_id}/runs")
async def list_runs(search_id: str, limit: int = Query(50, ge=1, le=500),
                    customer_id: str = Header(..., alias="X-Customer-ID")):
    store = _store()
    if await store.get(customer_id, search_id) is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return {"runs": [r.to_public() for r in await store.last_runs(customer_id, search_id, limit=limit)]}


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

TICK_SECONDS = int(os.getenv("LOGFORGE_SEARCH_SCHEDULER_SECONDS", "30"))


async def scheduler_loop() -> None:
    import asyncio
    import logging

    logger = logging.getLogger(__name__)
    while True:
        try:
            import scheduler_lease

            due = await _runner().run_due() if await scheduler_lease.acquire("saved-searches", TICK_SECONDS) else []
            for run in due:
                logger.info(f"Saved search run {run.search_id}: {run.status}, {run.rows} rows, "
                            f"fired={run.fired} alerted={run.alerted} throttled={run.throttled}")
        except Exception as e:
            logger.error(f"Saved search scheduler tick failed: {e}")
        await asyncio.sleep(TICK_SECONDS)


def start_scheduler() -> bool:
    import asyncio

    if os.getenv("LOGFORGE_SEARCH_SCHEDULER", "on").lower() in ("off", "false", "0"):
        return False
    asyncio.create_task(scheduler_loop())
    return True
