"""
Threat intelligence API (Phase 3): the tenant's feeds and indicators.

Mounted under /v1/security/intel (security permissions and feature). Feed
API keys are never accepted or returned: a feed names the environment
variable holding its key, and responses say only whether it is set.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from authn_authz_middleware import get_current_user
from error_handling import internal_error
from models import User
from threat_feeds import clean
from threat_intel import Indicator
from threat_intel_store import BUILTIN_FEEDS, FeedConfig, get_indicator_index, run_feed

router = APIRouter(prefix="/v1/security/intel", tags=["threat-intel"])


def _dao():
    from threat_intel_store import ThreatIntelDAO

    return ThreatIntelDAO()


def _fetch():
    return None  # run_feed's default HTTP fetch


async def _retro_hunt(tenant_id: str, keys: List[Any]) -> None:
    from retro_hunt import retro_hunt_new_indicators

    await retro_hunt_new_indicators(tenant_id, [tuple(k) for k in keys])


class FeedCreate(BaseModel):
    template: Optional[str] = Field(None, description="Name of a built-in feed to start from")
    name: Optional[str] = None
    kind: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    body: Optional[Dict[str, Any]] = None
    auth_header: Optional[str] = None
    secret_env: Optional[str] = Field(None, description="Environment variable holding the feed's API key")
    options: Optional[Dict[str, Any]] = None
    interval_minutes: Optional[int] = Field(None, ge=5, le=10080)
    confidence: Optional[int] = Field(None, ge=0, le=100)
    ttl_days: Optional[int] = Field(None, ge=1, le=3650)
    enabled: Optional[bool] = None


class FeedUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = Field(None, ge=5, le=10080)
    confidence: Optional[int] = Field(None, ge=0, le=100)
    ttl_days: Optional[int] = Field(None, ge=1, le=3650)
    options: Optional[Dict[str, Any]] = None


class IndicatorCreate(BaseModel):
    value: str = Field(..., max_length=2048)
    indicator_type: Optional[str] = Field(None, description="ip | domain | url | hash | email (default: inferred)")
    threat_type: str = Field("malicious", max_length=100)
    confidence: int = Field(70, ge=0, le=100)
    ttl_days: Optional[int] = Field(90, ge=1, le=3650)
    tags: List[str] = Field(default_factory=list)
    description: str = Field("", max_length=2000)


async def _find_feed(dao, tenant_id: str, feed_id: str) -> FeedConfig:
    for _, feed in await dao.list_feeds(tenant_id):
        if feed.id == feed_id:
            return feed
    raise HTTPException(status_code=404, detail="Feed not found")


@router.get("/feeds")
async def list_feeds(customer_id: str = Header(..., alias="X-Customer-ID"),
                     current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        feeds = [f.to_public() for _, f in await _dao().list_feeds(customer_id)]
    except Exception as e:
        raise internal_error(e, "Failed to list feeds")
    templates = [FeedConfig.from_dict(t).to_public() | {"id": None} for t in BUILTIN_FEEDS]
    return {"feeds": feeds, "templates": templates}


@router.post("/feeds", status_code=201)
async def create_feed(body: FeedCreate, customer_id: str = Header(..., alias="X-Customer-ID"),
                      current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if body.template:
        template = next((t for t in BUILTIN_FEEDS if t["name"] == body.template), None)
        if template is None:
            raise HTTPException(status_code=400, detail=f"Unknown template {body.template!r}")
        data.update(template)
    data.update({k: v for k, v in body.model_dump(exclude={"template"}).items() if v is not None})
    try:
        feed = FeedConfig.from_dict({**data, "created_at": datetime.now(timezone.utc)})
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await _dao().save_feed(customer_id, feed)
    except Exception as e:
        raise internal_error(e, "Failed to save the feed")
    return feed.to_public()


@router.patch("/feeds/{feed_id}")
async def update_feed(feed_id: str, body: FeedUpdate, customer_id: str = Header(..., alias="X-Customer-ID"),
                      current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    dao = _dao()
    feed = await _find_feed(dao, customer_id, feed_id)
    try:
        updated = FeedConfig.from_dict({**feed.to_row(), **{k: v for k, v in body.model_dump().items()
                                                            if v is not None}})
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    await dao.save_feed(customer_id, updated)
    return updated.to_public()


@router.delete("/feeds/{feed_id}", status_code=204)
async def delete_feed(feed_id: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                      current_user: User = Depends(get_current_user)):
    dao = _dao()
    feed = await _find_feed(dao, customer_id, feed_id)
    await dao.save_feed(customer_id, feed, deleted=True)


@router.post("/feeds/{feed_id}/run")
async def run_feed_now(feed_id: str, background: BackgroundTasks,
                       customer_id: str = Header(..., alias="X-Customer-ID"),
                       current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Fetch the feed now. New indicators are retro-hunted in the background."""
    dao = _dao()
    feed = await _find_feed(dao, customer_id, feed_id)
    result = await run_feed(customer_id, feed, dao, fetch=_fetch())
    if result["status"] == "ok":
        get_indicator_index().invalidate(customer_id)
        if result["new"]:
            background.add_task(_retro_hunt, customer_id, result["new"])
    return result


@router.get("/indicators")
async def search_indicators(q: str = Query("", max_length=200), indicator_type: Optional[str] = Query(None, alias="type"),
                            limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                            customer_id: str = Header(..., alias="X-Customer-ID"),
                            current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Indicators, newest first, with how often each appears in your logs
    over the last 7 days."""
    dao = _dao()
    try:
        rows, total = await dao.search_indicators(customer_id, q=q, indicator_type=indicator_type,
                                                  limit=limit, offset=offset)
        seen = await dao.seen_counts(customer_id, [(r["indicator_type"], r["value"]) for r in rows])
    except Exception as e:
        raise internal_error(e, "Failed to search indicators")
    indicators = []
    for r in rows:
        item = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items() if k != "tenant_id"}
        item["seen_7d"] = seen.get((r["indicator_type"], r["value"]), 0)
        indicators.append(item)
    return {"indicators": indicators, "total": total, "limit": limit, "offset": offset}


@router.post("/indicators", status_code=201)
async def add_indicator(body: IndicatorCreate, background: BackgroundTasks,
                        customer_id: str = Header(..., alias="X-Customer-ID"),
                        current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Add an indicator by hand (defanged forms accepted). Your recent logs
    are searched for it in the background."""
    cleaned = clean(body.value, body.indicator_type)
    if cleaned is None:
        raise HTTPException(status_code=400, detail=f"{body.value!r} is not a usable indicator (internal addresses "
                                                    "and malformed values are rejected)")
    kind, value = cleaned
    now = datetime.now(timezone.utc)
    indicator = Indicator(value=value, indicator_type=kind, threat_type=body.threat_type, confidence=body.confidence,
                          source=f"manual:{getattr(current_user, 'email', None) or current_user.id}",
                          tags=sorted(set(body.tags)), first_seen=now, last_seen=now,
                          expires_at=now + timedelta(days=body.ttl_days) if body.ttl_days else None,
                          description=body.description)
    dao = _dao()
    try:
        await dao.upsert_indicators(customer_id, [indicator], "manual", now)
    except Exception as e:
        raise internal_error(e, "Failed to add the indicator")
    get_indicator_index().invalidate(customer_id)
    background.add_task(_retro_hunt, customer_id, [(kind, value)])
    return {"indicator_type": kind, "value": value, "threat_type": indicator.threat_type,
            "confidence": indicator.confidence, "source": indicator.source, "tags": indicator.tags,
            "expires_at": indicator.expires_at.isoformat() if indicator.expires_at else None}


@router.delete("/indicators/{indicator_type}/{value:path}", status_code=204)
async def delete_indicator(indicator_type: str, value: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                           current_user: User = Depends(get_current_user)):
    await _dao().delete_indicator(customer_id, indicator_type, value, datetime.now(timezone.utc))
    get_indicator_index().invalidate(customer_id)
