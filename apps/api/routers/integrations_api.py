"""
Integrations API (Phase 13), under /v1/integrations (settings:read; changes
need settings:write: tenant admins).

  GET    /v1/integrations/kinds        what each kind needs (config, secrets, step inputs)
  GET    /v1/integrations              the tenant's integrations; secrets only as the names that are set
  POST   /v1/integrations              {name, kind, config, secrets}
  GET    /v1/integrations/{id}
  PUT    /v1/integrations/{id}         secrets left out are kept, "" removes one
  DELETE /v1/integrations/{id}
  POST   /v1/integrations/{id}/test    {inputs}: run the action once with a sample alert and case
  GET    /v1/integrations/tickets?case_id=   tickets linked to a case
  POST   /v1/integrations/tickets/sync       sync this tenant's linked tickets now

  POST   /v1/hooks/{tenant}/{integration}    Jira or GitHub issue webhooks (no login: authenticated
                                             by the integration's webhook_secret, as an
                                             X-Hub-Signature-256 HMAC or ?token=)
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx
from error_handling import internal_error
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from tenant_dependencies import MiddlewareTenant

from integrations import actions, templates

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])
hooks_router = APIRouter(prefix="/v1/hooks", tags=["integrations"])

SAMPLE_INPUTS = {
    "webhook": {"body": {"alert": "{{ alert.id }}", "title": "{{ alert.title }}"}},
    "slack": {"text": ":white_check_mark: Logforge test: {{ alert.title }}"},
    "teams": {"text": "Logforge test: {{ alert.title }}"},
    "pagerduty": {"summary": "Logforge test: {{ alert.title }}", "severity": "info", "event_action": "trigger"},
    "opsgenie": {"message": "Logforge test: {{ alert.title }}", "priority": "P5"},
    "email": {"subject": "Logforge test", "body": "{{ alert.title }}"},
    "jira_issue": {"summary": "Logforge test: {{ alert.title }}", "description": "Created by a test from Logforge."},
    "github_issue": {"title": "Logforge test: {{ alert.title }}", "body": "Created by a test from Logforge."},
    "containment_webhook": {"action": "block_ip", "target": "203.0.113.250", "reason": "Logforge test (dry run)"},
}


class IntegrationBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: str
    config: Dict[str, Any] = Field(default_factory=dict)
    secrets: Optional[Dict[str, str]] = None
    enabled: bool = True


class TestBody(BaseModel):
    inputs: Optional[Dict[str, Any]] = None


def _store():
    from dependencies import get_clickhouse_client

    from integrations.store import IntegrationStore

    return IntegrationStore(get_clickhouse_client())


def _http() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)


def _user(request: Request) -> str:
    return str(getattr(getattr(request.state, "user", None), "id", "") or "")


def sample_context(tenant_id: str) -> Dict[str, Any]:
    return {"tenant": {"id": tenant_id},
            "alert": {"id": "test-alert", "title": "Test alert from Logforge", "severity": "low",
                      "rule_id": "test", "entities": {"src_ip": ["203.0.113.250"]}},
            "case": {"id": "test-case", "title": "Test case", "status": "new"}}


def _validate(store, tenant_id: str, body: IntegrationBody, integration_id: Optional[str] = None):
    secrets = store.merged_secrets(tenant_id, integration_id, body.secrets)
    try:
        actions.validate(body.kind, body.config, secrets)
        templates.check(body.config)
    except (actions.ActionError, templates.TemplateError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/kinds")
async def kinds() -> Dict[str, Any]:
    return {"kinds": actions.describe()}


@router.get("")
async def list_integrations(customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    try:
        return {"integrations": await asyncio.to_thread(_store().list, customer_id)}
    except Exception as e:
        raise internal_error(e, "Failed to list integrations", customer_id=customer_id)


@router.post("", status_code=201)
async def create(body: IntegrationBody, request: Request, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    store = _store()
    _validate(store, customer_id, body)
    row = {"name": body.name, "kind": body.kind, "config": body.config, "enabled": body.enabled}
    return {"integration": await asyncio.to_thread(store.save, customer_id, row, body.secrets, _user(request))}


def _cases():
    from services.case_service import CaseService

    return CaseService()


@router.get("/tickets")
async def case_tickets(case_id: str, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    from dependencies import get_clickhouse_client

    from integrations.tickets import TicketStore

    return {"tickets": await asyncio.to_thread(TicketStore(get_clickhouse_client()).for_case, customer_id, case_id)}


@router.post("/tickets/sync")
async def sync_now(customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    from dependencies import get_clickhouse_client

    from integrations.sync_service import poll

    async with _http() as http:
        return await poll(get_clickhouse_client(), _cases(), http, tenant_id=customer_id)


@router.get("/{integration_id}")
async def get_one(integration_id: str, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    found = await asyncio.to_thread(_store().get, customer_id, integration_id)
    if not found:
        raise HTTPException(status_code=404, detail="No such integration")
    return {"integration": found}


@router.put("/{integration_id}")
async def update(integration_id: str, body: IntegrationBody, request: Request,
                 customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    store = _store()
    if not await asyncio.to_thread(store.get, customer_id, integration_id):
        raise HTTPException(status_code=404, detail="No such integration")
    _validate(store, customer_id, body, integration_id)
    row = {"id": integration_id, "name": body.name, "kind": body.kind, "config": body.config,
           "enabled": body.enabled}
    return {"integration": await asyncio.to_thread(store.save, customer_id, row, body.secrets, _user(request))}


@router.delete("/{integration_id}")
async def delete(integration_id: str, request: Request, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    if not await asyncio.to_thread(_store().delete, customer_id, integration_id, _user(request)):
        raise HTTPException(status_code=404, detail="No such integration")
    return {"deleted": integration_id}


@router.post("/{integration_id}/test")
async def test(integration_id: str, body: TestBody, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    found = await asyncio.to_thread(_store().get, customer_id, integration_id, True)
    if not found:
        raise HTTPException(status_code=404, detail="No such integration")
    inputs = body.inputs or SAMPLE_INPUTS.get(found["kind"], {})
    async with _http() as http:
        result = await actions.run(found["kind"], found["config"], found["secrets"], inputs,
                                   sample_context(customer_id), http=http)
    return {"result": result.to_dict()}


@hooks_router.post("/{tenant_id}/{integration_id}", status_code=202)
async def webhook(tenant_id: str, integration_id: str, request: Request) -> Dict[str, Any]:
    """A ticket changed in Jira or GitHub: bring the linked cases in step."""
    import json as _json

    from integrations import sync
    from integrations.sync_service import on_webhook

    body = await request.body()
    store = _store()
    found = await asyncio.to_thread(store.get, tenant_id, integration_id, True)
    # the same answer for an unknown integration and a bad signature: don't reveal which exist
    if not found or not sync.verify(dict(request.headers), dict(request.query_params), body,
                                     (found.get("secrets") or {}).get("webhook_secret", "")):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = _json.loads(body or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Body is not JSON")
    async with _http() as http:
        done = await on_webhook(store.client, _cases(), tenant_id, found, payload, http)
    return {"synced": done}
