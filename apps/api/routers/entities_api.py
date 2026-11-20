"""
Entity analytics API (Phase 11), under /v1/entities (security:read).

  GET /v1/entities                         entities, newest first; ?type=user|host|ip|service|cloud_account&q=
  GET /v1/entities/{type}/{value}          one entity: summary, related entities, the query for its events

Risk, alerts, cases, intel and baselines are added to the entity view by the
later Phase 11 deliverables.
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
    return {"entity": summary, "related": related, "query": query_for(entity_type, value)}
