"""
Field catalogue API (Phase 5), under /v1/fields (logs:read).

GET /v1/fields          fields seen in a sample of the window's latest events
GET /v1/fields/values   exact top values of one field over the window
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from authn_authz_middleware import get_current_user
from error_handling import internal_error
from field_catalogue import build_catalogue, top_values_sql, totals_sql
from models import User
from query_engine import QueryFieldError

router = APIRouter(prefix="/v1/fields", tags=["fields"])
MAX_WINDOW = timedelta(days=31)
CACHE_SECONDS = 60
_cache: Dict[Tuple[str, str, Optional[str], int], Tuple[float, Dict[str, Any]]] = {}


def _db():
    from database_layer import DatabaseLayer

    return DatabaseLayer("FieldCatalogue", os.getenv("FIELD_CATALOGUE_SERVICE_KEY", "field-catalogue-service-key"))


def _window(window: str) -> Tuple[datetime, datetime]:
    units = {"m": 60, "h": 3600, "d": 86400}
    try:
        seconds = int(window[:-1]) * units[window[-1]]
    except (KeyError, ValueError, IndexError):
        raise HTTPException(status_code=400, detail="window must look like 15m, 24h or 7d") from None
    if seconds <= 0 or timedelta(seconds=seconds) > MAX_WINDOW:
        raise HTTPException(status_code=400, detail="window must be between 1m and 31d")
    end = datetime.now(timezone.utc)
    return end - timedelta(seconds=seconds), end


@router.get("")
async def field_catalogue(window: str = Query("24h"), service: Optional[str] = Query(None, max_length=200),
                          sample: int = Query(2000, ge=100, le=10000),
                          customer_id: str = Header(..., alias="X-Customer-ID"),
                          user: User = Depends(get_current_user)):
    start, end = _window(window)
    key = (customer_id, window, service, sample)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    params: Dict[str, Any] = {"tenant_id": customer_id, "start": start, "end": end, "limit": sample}
    where = "customer_id = %(tenant_id)s AND ts >= %(start)s AND ts <= %(end)s"
    if service:
        where += " AND service = %(service)s"
        params["service"] = service
    try:
        rows = await _db().fetch_all(
            "SELECT ts, host, service, level, msg, status, src_ip, user_id, trace_id, attrs FROM logs_raw_mt "
            f"WHERE {where} ORDER BY ts DESC LIMIT %(limit)s", params)
    except Exception as e:
        raise internal_error(e, "Failed to read fields", customer_id=customer_id)
    body = {**build_catalogue(rows or []), "window": window, "service": service,
            "note": "computed from the most recent events in the window"}
    _cache[key] = (time.monotonic(), body)
    return body


@router.get("/values")
async def field_values(field: str = Query(..., max_length=300), window: str = Query("24h"),
                       service: Optional[str] = Query(None, max_length=200), limit: int = Query(10, ge=1, le=100),
                       customer_id: str = Header(..., alias="X-Customer-ID"),
                       user: User = Depends(get_current_user)):
    start, end = _window(window)
    try:
        sql, params = top_values_sql(customer_id, field, start, end, service=service, limit=limit)
        totals, totals_params = totals_sql(customer_id, field, start, end, service=service)
    except QueryFieldError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    try:
        db = _db()
        rows = await db.fetch_all(sql, params)
        summary = (await db.fetch_all(totals, totals_params) or [{}])[0]
    except Exception as e:
        raise internal_error(e, "Failed to read field values", customer_id=customer_id)
    return {"field": field, "total": int(summary.get("total") or 0), "distinct": int(summary.get("distinct") or 0),
            "values": [{"value": r["value"], "count": int(r["count"])} for r in rows or []]}
