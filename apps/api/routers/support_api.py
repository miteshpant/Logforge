"""
Support tickets (support_tickets): tenant members at /v1/support/tickets,
platform admins at /v1/admin/support/tickets.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

import support_tickets as st
from authn_authz_middleware import get_current_user
from models import User

router = APIRouter(prefix="/v1/support", tags=["Support"])
admin_router = APIRouter(prefix="/v1/admin/support", tags=["Support"])


def _store() -> st.TicketStore:
    from dependencies import get_clickhouse_client

    return st.TicketStore(get_clickhouse_client())


async def _run(fn, *args):
    try:
        return await asyncio.to_thread(fn, *args)
    except st.TicketError as e:
        raise HTTPException(422, str(e))


def _apply(fn, *args):
    try:
        return fn(*args)
    except st.TicketError as e:
        raise HTTPException(422, str(e))


class NewTicket(BaseModel):
    subject: str = Field(..., max_length=200)
    text: str = Field(..., max_length=10_000)
    priority: str = Field("normal", description="low | normal | high | urgent")


class Message(BaseModel):
    text: str = Field(..., max_length=10_000)


class TicketUpdate(BaseModel):
    status: Optional[str] = Field(None, description="open | answered | closed")
    priority: Optional[str] = None


# -- tenant members ---------------------------------------------------------------------------

@router.get("/tickets")
async def my_tickets(customer_id: str = Header(..., alias="X-Customer-ID")) -> Dict[str, Any]:
    """This tenant's tickets, most recently updated first."""
    return {"tickets": [t.public() for t in await _run(_store().list, customer_id)]}


@router.post("/tickets", status_code=201)
async def open_ticket(body: NewTicket, customer_id: str = Header(..., alias="X-Customer-ID"),
                      user: User = Depends(get_current_user)) -> Dict[str, Any]:
    ticket = _apply(st.open_ticket, customer_id, body.subject, body.text, body.priority, str(user.email), str(user.id))
    await _run(_store().save, ticket)
    return ticket.public()


async def _mine(ticket_id: str, tenant_id: str) -> st.Ticket:
    ticket = await _run(_store().get, ticket_id, tenant_id)
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    return ticket


@router.post("/tickets/{ticket_id}/messages")
async def customer_reply(ticket_id: str, body: Message, customer_id: str = Header(..., alias="X-Customer-ID"),
                         user: User = Depends(get_current_user)) -> Dict[str, Any]:
    ticket = _apply(st.reply, await _mine(ticket_id, customer_id), body.text, str(user.email), False)
    await _run(_store().save, ticket)
    return ticket.public()


@router.post("/tickets/{ticket_id}/close")
async def customer_close(ticket_id: str, customer_id: str = Header(..., alias="X-Customer-ID")) -> Dict[str, Any]:
    ticket = st.update(await _mine(ticket_id, customer_id), status="closed")
    await _run(_store().save, ticket)
    return ticket.public()


# -- platform admins ----------------------------------------------------------------------------

@admin_router.get("/tickets")
async def all_tickets(status: Optional[str] = Query(None, description="open | answered | closed")) -> Dict[str, Any]:
    """Every tenant's tickets, most recently updated first, with the tenant's name."""
    tickets = await _run(_store().list, None, status)
    from routers.platform_admin_api import _tenants

    names = await asyncio.to_thread(_tenants)
    counts: Dict[str, int] = {}
    for t in await _run(_store().list, None, None):
        counts[t.status] = counts.get(t.status, 0) + 1
    return {"tickets": [{**t.public(), "tenant_name": names.get(t.tenant_id, {}).get("name", "")} for t in tickets],
            "counts": counts}


async def _any(ticket_id: str) -> st.Ticket:
    ticket = await _run(_store().get, ticket_id)
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    return ticket


@admin_router.post("/tickets/{ticket_id}/messages")
async def support_reply(ticket_id: str, body: Message, request: Request) -> Dict[str, Any]:
    """Answer a ticket; the requester is notified (bell, and email with SMTP)."""
    user = getattr(request.state, "user", None)
    author = f"Logforge support ({getattr(user, 'email', 'admin')})"
    ticket = _apply(st.reply, await _any(ticket_id), body.text, author, True)
    await _run(_store().save, ticket)
    import user_inbox
    from dependencies import get_clickhouse_client

    await user_inbox.notify(get_clickhouse_client(), ticket.tenant_id, lambda members: [
        {"user_id": m["id"], "email": m["email"], "kind": "support",
         "title": f"Support answered: {ticket.subject}", "body": body.text[:500], "link": "/support",
         "actor": "Logforge support"} for m in members if m["id"] == ticket.created_by_id])
    return ticket.public()


@admin_router.put("/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, body: TicketUpdate) -> Dict[str, Any]:
    ticket = _apply(st.update, await _any(ticket_id), body.status, body.priority)
    await _run(_store().save, ticket)
    return ticket.public()
