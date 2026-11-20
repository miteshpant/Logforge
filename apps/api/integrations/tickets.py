"""Tickets linked to cases (Phase 13): case_tickets_mt."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TicketStore:
    def __init__(self, client):
        self.client = client

    def link(self, tenant_id: str, case_id: str, ticket: Dict[str, Any], ticket_status: str = "open",
             case_status: str = "") -> None:
        self.client.insert("case_tickets_mt", [[
            tenant_id, case_id, ticket.get("integration", ""), ticket.get("system", ""), ticket["ticket"],
            ticket.get("url", ""), ticket_status, case_status, datetime.now(timezone.utc)]],
            column_names=["customer_id", "case_id", "integration_id", "system", "ticket", "url", "ticket_status",
                          "case_status", "synced_at"])

    def _rows(self, where: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = self.client.query(
            "SELECT customer_id, case_id, ticket, argMax(integration_id, updated_at), argMax(system, updated_at), "
            "argMax(url, updated_at), argMax(ticket_status, updated_at), argMax(case_status, updated_at), "
            "max(synced_at) FROM case_tickets_mt " + where + " GROUP BY customer_id, case_id, ticket",
            parameters=params).result_rows
        return [{"tenant_id": r[0], "case_id": r[1], "ticket": r[2], "integration": r[3], "system": r[4],
                 "url": r[5], "ticket_status": r[6], "case_status": r[7], "synced_at": str(r[8])} for r in rows]

    def for_case(self, tenant_id: str, case_id: str) -> List[Dict[str, Any]]:
        return self._rows("WHERE customer_id = {tenant:String} AND case_id = {case:String}",
                          {"tenant": tenant_id, "case": case_id})

    def by_ticket(self, tenant_id: str, ticket: str) -> List[Dict[str, Any]]:
        return self._rows("WHERE customer_id = {tenant:String} AND ticket = {ticket:String}",
                          {"tenant": tenant_id, "ticket": ticket})

    def open_tickets(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        where = "WHERE customer_id = {tenant:String}" if tenant_id else ""
        rows = self._rows(where, {"tenant": tenant_id} if tenant_id else {})
        return [r for r in rows if r["ticket_status"] != "closed"]
