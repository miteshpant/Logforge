"""
Ingest pipelines API (Phase 4), under /v1/pipelines.

Reading needs logs:read, changing logs:write (authn_authz_middleware). A
definition is validated in full before it is stored, so a pipeline that
saves is one that can run; every change invalidates the tenant's routing
cache so ingest picks it up at once.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field

from authn_authz_middleware import get_current_user
from error_handling import internal_error
from models import User
from pipeline_store import PipelineRecord, get_pipeline_registry
from pipelines import PipelineError, simulate

router = APIRouter(prefix="/v1/pipelines", tags=["pipelines"])
MAX_SIMULATE_DOCS = 100


def _registry():
    return get_pipeline_registry()


class PipelineBody(BaseModel):
    name: str = Field(..., max_length=200)
    id: Optional[str] = Field(None, description="Defaults to a slug of the name")
    description: str = Field("", max_length=2000)
    enabled: bool = True
    routing: Dict[str, Any] = Field(default_factory=dict,
                                    description='{"services": [...], "if": "...", "priority": 100, "default": false}')
    processors: List[Dict[str, Any]] = Field(default_factory=list)
    on_failure: List[Dict[str, Any]] = Field(default_factory=list)


class SimulateBody(BaseModel):
    pipeline: Optional[Dict[str, Any]] = Field(None, description="An inline definition")
    pipeline_id: Optional[str] = Field(None, description="Or a saved / built-in pipeline")
    docs: List[Union[str, Dict[str, Any]]] = Field(..., min_length=1, max_length=MAX_SIMULATE_DOCS,
                                                   description="Sample events: objects, or raw lines (become msg)")


def _actor(user: User) -> str:
    return getattr(user, "email", None) or str(getattr(user, "id", "unknown"))


def _parse(body: Dict[str, Any]) -> PipelineRecord:
    try:
        return PipelineRecord.from_dict(body)
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


async def _find(tenant_id: str, pipeline_id: str) -> PipelineRecord:
    registry = _registry()
    record = await registry.dao.get(tenant_id, pipeline_id)
    if record is None:
        record = registry.builtins().get(pipeline_id)
    if record is None:
        raise HTTPException(status_code=404, detail="pipeline not found")
    return record


@router.get("")
async def list_pipelines(customer_id: str = Header(..., alias="X-Customer-ID"),
                         user: User = Depends(get_current_user)):
    registry = _registry()
    try:
        tenant = await registry.dao.list(customer_id)
    except Exception as e:
        raise internal_error(e, "Failed to list pipelines", customer_id=customer_id)
    return {"pipelines": [r.to_public() for r in tenant],
            "builtins": [r.to_public() for r in sorted(registry.builtins().values(), key=lambda r: r.id)]}


@router.post("", status_code=201)
async def create_pipeline(body: PipelineBody, customer_id: str = Header(..., alias="X-Customer-ID"),
                          user: User = Depends(get_current_user)):
    record = _parse(body.model_dump())
    registry = _registry()
    if await registry.dao.get(customer_id, record.id) is not None:
        raise HTTPException(status_code=409, detail=f"a pipeline with id {record.id!r} already exists")
    saved = await registry.dao.save(customer_id, record, actor=_actor(user))
    registry.invalidate(customer_id)
    return saved.to_public()


@router.post("/simulate")
async def simulate_pipeline(body: SimulateBody, customer_id: str = Header(..., alias="X-Customer-ID"),
                            user: User = Depends(get_current_user)):
    if body.pipeline is not None:
        record = _parse({"name": "simulation", **body.pipeline})
    elif body.pipeline_id:
        record = await _find(customer_id, body.pipeline_id)
    else:
        raise HTTPException(status_code=400, detail="give pipeline (a definition) or pipeline_id")
    docs = []
    for item in body.docs:
        doc = {"msg": item} if isinstance(item, str) else dict(item)
        doc.setdefault("service", "sample")
        doc.setdefault("level", "info")
        doc.setdefault("msg", "")
        if not isinstance(doc.get("attrs"), dict):
            doc["attrs"] = {}
        docs.append(doc)
    from ingest_pipeline_runner import context_for

    ctx = await context_for(customer_id)
    return {"pipeline": record.id, "results": simulate(record.pipeline, docs, ctx)}


@router.get("/{pipeline_id}")
async def get_pipeline(pipeline_id: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                       user: User = Depends(get_current_user)):
    return (await _find(customer_id, pipeline_id)).to_public()


@router.get("/{pipeline_id}/versions")
async def pipeline_versions(pipeline_id: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                            user: User = Depends(get_current_user)):
    versions = await _registry().dao.versions(customer_id, pipeline_id)
    if not versions:
        raise HTTPException(status_code=404, detail="pipeline not found")
    return {"versions": [v.to_public() for v in versions]}


@router.put("/{pipeline_id}")
async def update_pipeline(pipeline_id: str, body: PipelineBody, customer_id: str = Header(..., alias="X-Customer-ID"),
                          user: User = Depends(get_current_user)):
    registry = _registry()
    if await registry.dao.get(customer_id, pipeline_id) is None:
        raise HTTPException(status_code=404, detail="pipeline not found (create it with POST /v1/pipelines)")
    data = body.model_dump()
    if data.get("id") and data["id"] != pipeline_id:
        raise HTTPException(status_code=400, detail="the id cannot be changed")
    record = _parse({**data, "id": pipeline_id})
    saved = await registry.dao.save(customer_id, record, actor=_actor(user))
    registry.invalidate(customer_id)
    return saved.to_public()


@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(pipeline_id: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                          user: User = Depends(get_current_user)):
    registry = _registry()
    if await registry.dao.get(customer_id, pipeline_id) is None:
        raise HTTPException(status_code=404, detail="pipeline not found")
    await registry.dao.delete(customer_id, pipeline_id, actor=_actor(user))
    registry.invalidate(customer_id)
    return Response(status_code=204)
