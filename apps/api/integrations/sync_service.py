"""
Ticket sync wired to cases (Phase 13): apply a ticket's state to the cases
linked to it, push case changes to tickets, and poll tickets whose system
sends no webhooks.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from . import sync
from .store import IntegrationStore
from .tickets import TicketStore

logger = logging.getLogger(__name__)
POLL_SECONDS = int(os.getenv("LOGFORGE_TICKET_SYNC_SECONDS", "300"))
ACTOR = "ticket-sync"


async def reconcile(tickets: TicketStore, cases, integration: Dict[str, Any], link: Dict[str, Any],
                    ticket_state: Optional[str], http: httpx.AsyncClient) -> Optional[str]:
    """Bring one case/ticket pair in step. Returns what was done, if anything."""
    tenant, case_id, ticket = link["tenant_id"], link["case_id"], link["ticket"]
    case = await cases.get(tenant, case_id)
    if case is None:
        return None
    case_status = case.status if hasattr(case, "status") else case["status"]
    if ticket_state is None:  # couldn't read the ticket: assume it didn't move
        ticket_state = link["ticket_status"]
    action = sync.decide(link, ticket_state, case_status)
    system = link.get("system") or integration["kind"]
    if action == "close_case":
        case = await cases.act(tenant, case_id, "set_status", ACTOR, status="resolved",
                               reason=f"Closed in {system}: {ticket}")
    elif action == "reopen_case":
        case = await cases.act(tenant, case_id, "set_status", ACTOR, status="investigating",
                               reason=f"Reopened in {system}: {ticket}")
    elif action in ("close_ticket", "reopen_ticket"):
        state = "closed" if action == "close_ticket" else "open"
        if await sync.set_remote(integration, ticket, state, f"Case {case_id} is {case_status} in Logforge.",
                                 http=http):
            ticket_state = state
        else:
            logger.warning("Ticket sync couldn't %s %s for case %s", action, ticket, case_id)
            action = None
    new_status = case.status if hasattr(case, "status") else case["status"]
    if action or ticket_state != link["ticket_status"] or new_status != link["case_status"]:
        await asyncio.to_thread(tickets.link, tenant, case_id,
                                {"ticket": ticket, "url": link["url"], "system": link["system"],
                                 "integration": link["integration"]}, ticket_state, new_status)
    return action


async def on_webhook(client, cases, tenant_id: str, integration: Dict[str, Any], payload: Dict[str, Any],
                     http: httpx.AsyncClient) -> List[Dict[str, Any]]:
    parsed = sync.from_webhook(integration["kind"], payload)
    if not parsed:
        return []
    ticket, state = parsed
    tickets = TicketStore(client)
    done = []
    for link in await asyncio.to_thread(tickets.by_ticket, tenant_id, ticket):
        action = await reconcile(tickets, cases, integration, link, state, http)
        done.append({"case_id": link["case_id"], "ticket": ticket, "action": action})
    return done


async def poll(client, cases, http: httpx.AsyncClient, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Every link: read the ticket, reconcile. Also pushes case changes out."""
    tickets, integrations = TicketStore(client), IntegrationStore(client)
    report = {"checked": 0, "actions": []}
    cache: Dict[tuple, Optional[Dict[str, Any]]] = {}
    for link in await asyncio.to_thread(tickets._rows, "WHERE customer_id = {tenant:String}" if tenant_id else "",
                                        {"tenant": tenant_id} if tenant_id else {}):
        key = (link["tenant_id"], link["integration"])
        if key not in cache:
            cache[key] = await asyncio.to_thread(integrations.get, link["tenant_id"], link["integration"], True)
        integration = cache[key]
        if not integration:
            continue
        state = await sync.remote_state(integration, link["ticket"], http=http)
        action = await reconcile(tickets, cases, integration, link, state, http)
        report["checked"] += 1
        if action:
            report["actions"].append({"case_id": link["case_id"], "ticket": link["ticket"], "action": action})
    return report


async def loop() -> None:
    from dependencies import get_clickhouse_client
    from services.case_service import CaseService

    while True:
        await asyncio.sleep(POLL_SECONDS)
        try:
            async with httpx.AsyncClient(follow_redirects=False) as http:
                report = await poll(get_clickhouse_client(), CaseService(), http)
            if report["actions"]:
                logger.info("Ticket sync: %s", report)
        except Exception as e:
            logger.error("Ticket sync failed: %s", e)


def start() -> bool:
    if os.getenv("LOGFORGE_TICKET_SYNC", "on").lower() in ("off", "false", "0"):
        return False
    asyncio.create_task(loop())
    return True
