"""
Lookup tables API (Phase 6), under /v1/query/lookups.

Reading needs queries:read, changing queries:write (authn_authz_middleware,
the /v1/query/ prefix). Uploads are validated in full before anything is
stored; a replacement is a new version, and queries read the current one.
"""

from __future__ import annotations

from typing import List, Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

from authn_authz_middleware import get_current_user
from error_handling import internal_error
from lookup_tables import MAX_LOOKUPS, LookupDAO, LookupValidationError, check_name, parse_csv, parse_list
from models import User

router = APIRouter(prefix="/v1/query/lookups", tags=["lookups"])


def _dao():
    return LookupDAO()


def _actor(user) -> str:
    return getattr(user, "email", None) or getattr(user, "id", "") or ""


class LookupBody(BaseModel):
    csv: Optional[str] = Field(None, description="CSV text; the first row is the header")
    values: Optional[List[Union[str, int, float]]] = Field(None, description="A managed list of values")
    key: Optional[str] = Field(None, description="Key column of a CSV (default: the first column)")
    description: str = Field("", max_length=500)


class ValuesBody(BaseModel):
    add: List[Union[str, int, float]] = Field(default_factory=list)
    remove: List[Union[str, int, float]] = Field(default_factory=list)


def _name(name: str) -> str:
    try:
        return check_name(name)
    except LookupValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_lookups(customer_id: str = Header(..., alias="X-Customer-ID")):
    try:
        tables = await _dao().list(customer_id)
    except Exception as e:
        raise internal_error(e, "Failed to list lookups", customer_id=customer_id)
    return {"lookups": [t.to_public() for t in tables]}


@router.get("/{name}")
async def get_lookup(name: str, limit: int = Query(100, ge=1, le=1000),
                     customer_id: str = Header(..., alias="X-Customer-ID")):
    dao = _dao()
    table = await dao.get(customer_id, _name(name))
    if table is None:
        raise HTTPException(status_code=404, detail=f"Lookup {name} not found")
    return {**table.to_public(), "rows": await dao.rows(customer_id, table, limit)}


@router.put("/{name}")
async def put_lookup(name: str, body: LookupBody, customer_id: str = Header(..., alias="X-Customer-ID"),
                     user: User = Depends(get_current_user)):
    name = _name(name)
    if (body.csv is None) == (body.values is None):
        raise HTTPException(status_code=400, detail="Send either csv or values")
    try:
        if body.csv is not None:
            kind = "csv"
            columns, key, rows = parse_csv(body.csv, key=body.key)
        else:
            kind = "list"
            columns, key, rows = parse_list(body.values)
    except LookupValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    dao = _dao()
    try:
        if await dao.get(customer_id, name) is None and len(await dao.list(customer_id)) >= MAX_LOOKUPS:
            raise HTTPException(status_code=400, detail=f"A tenant can have at most {MAX_LOOKUPS} lookups")
        table = await dao.save(customer_id, name, kind, columns, key, rows, body.description, _actor(user))
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error(e, "Failed to save lookup", customer_id=customer_id)
    return table.to_public()


@router.post("/{name}/values")
async def change_list_values(name: str, body: ValuesBody, customer_id: str = Header(..., alias="X-Customer-ID"),
                             user: User = Depends(get_current_user)):
    dao = _dao()
    table = await dao.get(customer_id, _name(name))
    if table is None:
        raise HTTPException(status_code=404, detail=f"Lookup {name} not found")
    if table.kind != "list":
        raise HTTPException(status_code=400, detail=f"{name} is a CSV lookup; upload a new CSV to change it")
    current = await dao.all_rows(customer_id, table)
    removed = {str(v).strip() for v in body.remove}
    try:
        _, key, rows = parse_list([v for v in current if v not in removed] + list(body.add))
    except LookupValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    rows = {k: v for k, v in rows.items() if k not in removed or k in {str(a).strip() for a in body.add}}
    saved = await dao.save(customer_id, table.name, "list", table.columns, key, rows, table.description,
                           _actor(user))
    return saved.to_public()


@router.delete("/{name}", status_code=204)
async def delete_lookup(name: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                        user: User = Depends(get_current_user)):
    dao = _dao()
    if await dao.get(customer_id, _name(name)) is None:
        raise HTTPException(status_code=404, detail=f"Lookup {name} not found")
    await dao.delete(customer_id, name, _actor(user))
    return Response(status_code=204)
