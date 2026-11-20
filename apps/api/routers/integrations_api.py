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
