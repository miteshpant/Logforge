"""
Storage tiers API (Phase 12), under /v1/storage/tiers (storage:read; changes
need storage:write, which tenant admins have).

  GET  /v1/storage/tiers                       the tiers, the tenant's retention per data type, its archives
  PUT  /v1/storage/tiers/policies/{data_type}  {searchable_days, archive_days}: the tenant's retention
  POST /v1/storage/tiers/run                   run retention now for the tenant (what the hourly job does)

At startup the API creates the buckets, puts the tiered tables on the
`tiered` storage policy with their TTL, and (LOGFORGE_RETENTION_JOB, on by
default) runs retention for every tenant hourly. With more than one API
replica, turn the job off and run `python -m tier_manager run` once per hour
(the Helm chart's CronJob).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from error_handling import internal_error
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from tenant_dependencies import MiddlewareTenant

import storage_tiers as st

router = APIRouter(prefix="/v1/storage/tiers", tags=["storage tiers"])
logger = logging.getLogger(__name__)
JOB_INTERVAL = int(os.getenv("LOGFORGE_RETENTION_INTERVAL", "3600"))
_status: Dict[str, Any] = {}


class PolicyBody(BaseModel):
    searchable_days: int = Field(..., ge=1)
    archive_days: int = Field(0, ge=0)


def _manager():
    from dependencies import get_clickhouse_client
    from tier_manager import S3Objects, TierManager

    cfg = st.load_config()
    return TierManager(get_clickhouse_client(), S3Objects(cfg.archive_bucket), cfg)


def _user(request: Request) -> str:
    return str(getattr(getattr(request.state, "user", None), "id", "") or "")


def _summary(mgr, tenant_id: str) -> Dict[str, Any]:
    cfg = mgr.cfg
    policies = mgr.policies(tenant_id)
    custom = {p.data_type for p in mgr._stored(tenant_id).get(tenant_id, [])}
    types = []
    for name, dtype in cfg.data_types.items():
        archived = mgr.archived(name, tenant_id).get(tenant_id, {})
        policy = policies[name]
        types.append({"data_type": name, "table": dtype.table, "searchable_days": policy.searchable_days,
                      "archive_days": policy.archive_days, "custom": name in custom,
                      "default": {"searchable_days": cfg.defaults[name].searchable_days,
                                  "archive_days": cfg.defaults[name].archive_days},
                      "archived_days": len(archived), "archived_rows": sum(n for n, _ in archived.values()),
                      "oldest_archive": min(archived).isoformat() if archived else None})
    return {"tiers": {"hot": {"where": "ClickHouse, local disk", "days": cfg.hot_days},
                      "warm": {"where": "ClickHouse, object storage", "enabled": _status.get("warm"),
                               "until_days": "searchable_days"},
                      "cold": {"where": "Parquet in object storage", "bucket": cfg.archive_bucket}},
            "limits": {"max_searchable_days": cfg.max_searchable_days, "max_archive_days": cfg.max_archive_days},
            "data_types": types, "last_run": _status.get("last_run")}


@router.get("")
async def get_tiers(customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    try:
        return await asyncio.to_thread(_summary, _manager(), customer_id)
    except Exception as e:
        raise internal_error(e, "Failed to read storage tiers", customer_id=customer_id)


@router.put("/policies/{data_type}")
async def set_policy(data_type: str, body: PolicyBody, request: Request,
                     customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    mgr = _manager()
    policy = st.Policy(data_type, body.searchable_days, body.archive_days)
    try:
        st.validate(policy, mgr.cfg)
    except st.PolicyError as e:
        raise HTTPException(status_code=422, detail=str(e))
    try:
        await asyncio.to_thread(mgr.set_policy, customer_id, policy, _user(request))
        return {"policy": policy.__dict__}
    except Exception as e:
        raise internal_error(e, "Failed to save the retention policy", customer_id=customer_id)


@router.post("/run")
async def run_now(customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    try:
        return await asyncio.to_thread(_manager().run, None, [customer_id])
    except Exception as e:
        raise internal_error(e, "Retention run failed", customer_id=customer_id)


def ensure() -> Optional[Dict[str, Any]]:
    """Buckets and tables (blocking). Failures are logged: the API runs without tiers."""
    if os.getenv("LOGFORGE_STORAGE_TIERS", "on").lower() in ("off", "false", "0"):
        return None
    try:
        mgr = _manager()
        mgr.objects.ensure_buckets(mgr.cfg.archive_bucket, mgr.cfg.warm_bucket)
        _status.update(mgr.ensure_tables())
        logger.info("Storage tiers ready: warm=%s", _status.get("warm"))
        return _status
    except Exception as e:
        logger.error("Storage tiers not set up: %s", e)
        _status["error"] = str(e)
        return None


async def job_loop() -> None:
    from datetime import datetime, timezone

    while True:
        await asyncio.sleep(JOB_INTERVAL)
        try:
            report = await asyncio.to_thread(_manager().run)
            _status["last_run"] = {**report, "at": datetime.now(timezone.utc).isoformat()}
            if report["errors"]:
                logger.warning("Retention run had errors: %s", report["errors"][:5])
        except Exception as e:
            logger.error("Retention run failed: %s", e)


def start() -> bool:
    """At startup: set up the tiers, then the hourly job unless LOGFORGE_RETENTION_JOB is off."""
    async def setup():
        await asyncio.to_thread(ensure)

    asyncio.create_task(setup())
    if os.getenv("LOGFORGE_RETENTION_JOB", "on").lower() in ("off", "false", "0"):
        return False
    asyncio.create_task(job_loop())
    return True
