"""
Platform admin (admin UI): bills across tenants, a month's billing run, bills
as PDF, and the tier feature matrix. Everything under /v1/admin needs the
platform admin role (authn_authz_middleware).
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

import platform_admin
import reports

router = APIRouter(prefix="/v1/admin", tags=["Platform admin"])
_PERIOD = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _client():
    from dependencies import get_clickhouse_client

    return get_clickhouse_client()


def _query(sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = _client().query(sql, parameters=params)
    return [dict(zip(result.column_names, r)) for r in result.result_rows]


def _tenants() -> Dict[str, Dict[str, Any]]:
    """Active tenants by id, latest version of each."""
    rows = _query("SELECT id, argMax(organization_name, updated_at) AS name, argMax(status, updated_at) AS status "
                  "FROM tenants_mt GROUP BY id", {})
    return {r["id"]: r for r in rows}


@router.get("/features/matrix")
async def feature_matrix() -> Dict[str, Any]:
    """Which features each subscription tier includes (wildcards resolved)."""
    from routers.subscription_api import list_all_available_features
    from subscription_service import get_subscription_service

    service = get_subscription_service()
    catalogue = (await list_all_available_features())["feature_categories"]
    return platform_admin.feature_matrix(service.feature_bundles, catalogue, service.has_feature_access)


@router.get("/billing/bills")
async def list_bills(period: Optional[str] = Query(None, description="YYYY-MM"),
                     limit: int = Query(200, ge=1, le=2000)) -> Dict[str, Any]:
    """Bills across tenants, newest first, with each tenant's name."""
    if period and not _PERIOD.match(period):
        raise HTTPException(422, "period is YYYY-MM")
    where = "WHERE billing_period = {p:String}" if period else ""
    bills = await asyncio.to_thread(_query, (
        "SELECT id, tenant_id, billing_period, subscription_tier, total_amount, currency, status, generated_at, "
        f"due_date, paid_at FROM tenant_bills_mt {where} ORDER BY generated_at DESC LIMIT {{n:UInt32}}"),
        {"p": period or "", "n": limit})
    names = await asyncio.to_thread(_tenants)
    for b in bills:
        b["tenant_name"] = names.get(b["tenant_id"], {}).get("name", "")
        for k in ("generated_at", "due_date", "paid_at"):
            if b.get(k) is not None:
                b[k] = b[k].isoformat()
    totals: Dict[str, float] = {}
    for b in bills:
        totals[b["currency"]] = round(totals.get(b["currency"], 0) + float(b["total_amount"] or 0), 2)
    return {"bills": bills, "totals": totals}


class RunBody(BaseModel):
    billing_period: str = Field(..., description="YYYY-MM")


@router.post("/billing/generate")
async def generate_all(body: RunBody) -> Dict[str, Any]:
    """Bill every active tenant for a month. Idempotent: tenants already billed
    for that month keep their bill, so a run can be repeated after a failure."""
    from routers.subscription_api import generate_bill

    if not _PERIOD.match(body.billing_period):
        raise HTTPException(422, "billing_period is YYYY-MM")
    tenants = [t for t in (await asyncio.to_thread(_tenants)).values() if t["status"] == "active"]
    gate = asyncio.Semaphore(4)
    outcome: Dict[str, Any] = {"billing_period": body.billing_period, "tenants": len(tenants),
                               "generated": 0, "already_billed": 0, "failed": []}

    async def one(t):
        async with gate:
            try:
                bill = await generate_bill(t["id"], {"billing_period": body.billing_period,
                                                     "include_usage_details": False}, "platform")
                outcome["already_billed" if bill.get("status") == "already_exists" else "generated"] += 1
            except Exception as e:
                detail = getattr(e, "detail", None) or str(e)
                outcome["failed"].append({"tenant_id": t["id"], "tenant_name": t["name"], "error": str(detail)[:300]})

    await asyncio.gather(*(one(t) for t in tenants))
    return outcome


@router.get("/billing/bills/{bill_id}/pdf")
async def bill_pdf(bill_id: str):
    rows = await asyncio.to_thread(_query, "SELECT * FROM tenant_bills_mt WHERE id = {id:String} LIMIT 1",
                                   {"id": bill_id})
    if not rows:
        raise HTTPException(404, "Bill not found")
    bill = rows[0]
    name = (await asyncio.to_thread(_tenants)).get(bill["tenant_id"], {}).get("name", "")
    pdf = reports.to_pdf(platform_admin.bill_report(bill, name))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="logforge-bill-{bill["billing_period"]}-{bill_id[:8]}.pdf"'})
