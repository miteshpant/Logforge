"""The signed-in user's notifications (user_inbox): GET /v1/inbox, POST /v1/inbox/read."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from authn_authz_middleware import get_current_user
from models import User

router = APIRouter(prefix="/v1/inbox", tags=["Notifications"])


def _inbox():
    from dependencies import get_clickhouse_client
    from user_inbox import Inbox

    return Inbox(get_clickhouse_client())


class ReadBody(BaseModel):
    ids: Optional[List[str]] = Field(None, description="Notifications to mark read; omit for all")


@router.get("")
async def list_inbox(limit: int = Query(50, ge=1, le=200), customer_id: str = Header(..., alias="X-Customer-ID"),
                     current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Your notifications, newest first, and how many are unread."""
    return await asyncio.to_thread(_inbox().list, customer_id, str(current_user.id), limit)


@router.post("/read")
async def mark_read(body: ReadBody, customer_id: str = Header(..., alias="X-Customer-ID"),
                    current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    marked = await asyncio.to_thread(_inbox().mark_read, customer_id, str(current_user.id), body.ids)
    return {"marked": marked}
