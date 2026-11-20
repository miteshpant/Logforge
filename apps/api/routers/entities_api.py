"""
Entity analytics API (Phase 11), under /v1/entities (security:read).

  GET /v1/entities                         entities, newest first; ?type=user|host|ip|service|cloud_account&q=
  GET /v1/entities/risk                    entities ranked by risk, with the factors behind each score
  GET /v1/entities/{type}/{value}          one entity: summary, risk and its factors, baseline anomalies,
                                           its alerts and cases, related entities, the query for its events
"""

from __future__ import annotations

from typing import Any

from entities import EntityError, EntityStore, query_for
from error_handling import internal_error
from fastapi import APIRouter, HTTPException, Query
from tenant_dependencies import MiddlewareTenant

router = APIRouter(prefix="/v1/entities", tags=["entities"])


def _store() -> EntityStore:
    return EntityStore()


@router.get("")
async def list_entities(customer_id: str = MiddlewareTenant, type: str | None = Query(None),
                        q: str = Query("", max_length=200), limit: int = Query(50, ge=1, le=500),
                        offset: int = Query(0, ge=0)) -> dict[str, Any]:
    try:
        return {"entities": await _store().search(customer_id, type, q=q, limit=limit, offset=offset)}
    except EntityError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Failed to list entities", customer_id=customer_id)


async def _ranking(tenant_id: str):
    from entity_risk_service import ranking

    return await ranking(tenant_id)


async def _baseline(tenant_id: str, entity_type: str, value: str) -> list[dict[str, Any]]:
    import asyncio

    from entity_baselines import EXPRESSIONS, BaselineStore

    if entity_type not in EXPRESSIONS:
        return []
    found = await asyncio.wait_for(BaselineStore().anomalies(tenant_id, entity_type, [value]), 15.0)
    return [a.to_public() for a in found.get(value, [])]


async def _cases(tenant_id: str, value: str) -> list[dict[str, Any]]:
    from services.case_service import CaseService, case_to_dict

    cases, _ = await CaseService().list(tenant_id, entity=value, limit=20)
    return [{k: v for k, v in case_to_dict(c).items() if k in ("id", "title", "status", "severity", "updated_at")}
            for c in cases]


@router.get("/risk")
async def entity_risk(customer_id: str = MiddlewareTenant, type: str | None = Query(None),
                      limit: int = Query(25, ge=1, le=500)) -> dict[str, Any]:
    """Entities ranked by risk over the last 14 days: alert severity with decay (repeats of one rule and rules
    common across the tenant count less), ATT&CK tactic progression (shared with linked entities), intel
    hits. Each comes with the factors behind its score."""
    try:
        ranked, _, flags = await _ranking(customer_id)
    except Exception as e:
        raise internal_error(e, "Failed to rank entities by risk", customer_id=customer_id)
    rows = [r for r in ranked if r.raw > 0 and (type is None or r.entity_type == type)]
    return {"entities": [r.to_public(top=5) for r in rows[:limit]], "window_days": 14, "flags": flags}


@router.get("/{entity_type}/{value:path}")
async def get_entity(entity_type: str, value: str, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    store = _store()
    try:
        summary = await store.get(customer_id, entity_type, value)
    except EntityError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Failed to read the entity", customer_id=customer_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"{entity_type} {value} has not been seen")
    try:
        related = await store.related(customer_id, entity_type, value)
    except Exception as e:
        raise internal_error(e, "Failed to read related entities", customer_id=customer_id)
    try:
        ranked, by_entity, flags = await _ranking(customer_id)
        cases = await _cases(customer_id, value)
    except Exception as e:
        raise internal_error(e, "Failed to read the entity's risk and cases", customer_id=customer_id)
    try:
        anomalies = await _baseline(customer_id, entity_type, value)
    except Exception:  # noqa: BLE001 - the rest of the page stands without it
        anomalies, flags = [], flags + ["baselines_unavailable"]
    risk = next((r for r in ranked if r.entity_type == entity_type and r.value == value), None)
    position = next((i + 1 for i, r in enumerate(ranked) if r is risk), None)
    alerts = sorted(by_entity.get((entity_type, value), []), key=lambda a: str(a.get("ts")), reverse=True)[:50]
    return {"entity": summary, "risk": risk.to_public(top=20) if risk else None, "rank": position,
            "anomalies": anomalies, "alerts": alerts, "cases": cases, "related": related,
            "query": query_for(entity_type, value), "flags": flags}
