"""
Single sign-on (Phase 14).

Public, for signing in:
  GET /v1/auth/sso/discover?email=        the providers for an address's domain
  GET /v1/auth/sso/{provider}/start?next=  to the IdP
  GET /v1/auth/sso/callback               back from the IdP; to the UI with a session

Settings (settings:read / settings:write):
  GET, POST /v1/sso/providers; PUT, DELETE /v1/sso/providers/{id}
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from tenant_dependencies import MiddlewareTenant

from sso import oidc
from sso.service import complete_sign_in
from sso.store import ProviderStore, public

logger = logging.getLogger(__name__)
login_router = APIRouter(prefix="/v1/auth/sso", tags=["sso"])
router = APIRouter(prefix="/v1/sso/providers", tags=["sso"])
COOKIE = "lf_oidc"


class ProviderBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    issuer: str = Field(..., pattern=r"^https://")
    client_id: str = Field(..., min_length=1)
    client_secret: Optional[str] = None  # write-only; omitted keeps the stored one
    scopes: str = "openid email profile"
    groups_claim: str = "groups"
    role_mapping: Dict[str, str] = Field(default_factory=dict)
    default_role: Optional[str] = None
    allowed_domains: List[str] = Field(..., min_length=1)
    enabled: bool = True


# dependency hooks (replaced in tests)
def _store() -> ProviderStore:
    from dependencies import get_clickhouse_client

    return ProviderStore(get_clickhouse_client())


def _http() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)


def _users():
    from routers.auth_api import get_user_service

    return get_user_service()


def _roles():
    from routers.role_api import get_role_service

    return get_role_service()


async def _session(user, tenant_id: str, role: str, request: Request) -> Dict[str, Any]:
    from routers.auth_api import _refresh_tokens_enabled, get_refresh_token_service, get_user_service

    ip = request.client.host if request.client else "unknown"
    agent = request.headers.get("user-agent", "unknown")
    session = await get_user_service().create_session(user, ip, agent, tenant_id, role)
    out = {"access_token": session["access_token"], "expires_at": str(session["expires_at"])}
    if _refresh_tokens_enabled():
        refresh = await get_refresh_token_service().issue(user.id, tenant_id, ip, agent)
        out.update(refresh_token=refresh["refresh_token"], refresh_expires_at=str(refresh["expires_at"]))
    return out


def _ui() -> str:
    import account_emails

    return account_emails.public_url()


def _callback_url(request: Request) -> str:
    base = os.getenv("LOGFORGE_API_PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/v1/auth/sso/callback"


def _fail(message: str) -> RedirectResponse:
    response = RedirectResponse(f"{_ui()}/login?{urlencode({'sso_error': message})}", status_code=303)
    response.delete_cookie(COOKIE, path="/v1/auth/sso")
    return response


def _validate_roles(body: ProviderBody) -> None:
    for role in [*body.role_mapping.values(), *([body.default_role] if body.default_role else [])]:
        if role not in oidc.TENANT_ROLES:
            raise HTTPException(422, f"{role!r} isn't a tenant role ({', '.join(oidc.TENANT_ROLES)})")


# -- signing in ---------------------------------------------------------------------------

@login_router.get("/discover")
async def discover_providers(email: str = Query(..., max_length=320)) -> Dict[str, Any]:
    domain = email.rsplit("@", 1)[-1].strip().lower() if "@" in email else ""
    providers = await asyncio.to_thread(_store().for_domain, domain) if domain else []
    return {"providers": [{"id": p.id, "name": p.name} for p in providers]}


@login_router.get("/{provider_id}/start")
async def start(provider_id: str, request: Request, next: Optional[str] = None):
    provider = await asyncio.to_thread(_store().get, provider_id)
    if not provider or not provider.enabled:
        return _fail("This sign-in isn't available.")
    try:
        async with _http() as http:
            discovery = await oidc.discover(provider.issuer, http)
    except oidc.OIDCError as e:
        logger.warning("SSO start failed for %s: %s", provider_id, e)
        return _fail("The identity provider can't be reached.")
    state, nonce = oidc.new_state()
    verifier, challenge = oidc.pkce_pair()
    response = RedirectResponse(oidc.authorization_url(discovery, provider, _callback_url(request), state, nonce,
                                                       challenge), status_code=303)
    response.set_cookie(COOKIE, oidc.seal_state({"p": provider.id, "s": state, "n": nonce, "v": verifier,
                                                 "next": oidc.safe_next(next)}),
                        max_age=600, httponly=True, samesite="lax", path="/v1/auth/sso",
                        secure=request.url.scheme == "https")
    return response


@login_router.get("/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return _fail(f"The identity provider said: {error}")
    try:
        saved = oidc.open_state(request.cookies.get(COOKIE, ""))
        if not state or state != saved.get("s"):
            raise oidc.OIDCError("the sign-in doesn't match this browser")
        provider = await asyncio.to_thread(_store().get, saved["p"])
        if not provider or not provider.enabled:
            raise oidc.OIDCError("this sign-in isn't available")
        async with _http() as http:
            discovery = await oidc.discover(provider.issuer, http)
            tokens = await oidc.exchange(discovery, provider, code, saved["v"], _callback_url(request), http)
            jwks = await oidc.fetch_jwks(discovery, http)
        claims = oidc.validate_id_token(tokens["id_token"], jwks, provider.issuer, provider.client_id, saved["n"])
        user, role = await complete_sign_in(provider, claims, _users(), _roles())
        session = await _session(user, provider.tenant_id, role, request)
    except oidc.OIDCError as e:
        logger.warning("SSO sign-in refused: %s", e)
        return _fail(str(e)[:300])
    logger.info("SSO sign-in", extra={"user_id": user.id, "tenant_id": provider.tenant_id, "role": role})
    # in the fragment: never sent to a server, so not in any access log
    response = RedirectResponse(f"{_ui()}/login/sso#{urlencode({**session, 'next': saved.get('next', '/centrum')})}",
                                status_code=303)
    response.delete_cookie(COOKIE, path="/v1/auth/sso")
    return response


# -- settings ------------------------------------------------------------------------------

def _user(request: Request) -> str:
    return str(getattr(getattr(request.state, "user", None), "id", "") or "")


@router.get("")
async def list_providers(customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    providers = await asyncio.to_thread(_store().list, customer_id)
    return {"providers": [public(p) for p in providers],
            "callback_url_path": "/v1/auth/sso/callback", "roles": oidc.TENANT_ROLES}


@router.post("", status_code=201)
async def create_provider(body: ProviderBody, request: Request, customer_id: str = MiddlewareTenant):
    _validate_roles(body)
    provider = oidc.Provider(id="", tenant_id=customer_id, **body.model_dump(exclude={"client_secret"}),
                             client_secret=body.client_secret or "")
    saved = await asyncio.to_thread(_store().save, provider, _user(request))
    return {"provider": public(saved)}


@router.put("/{provider_id}")
async def update_provider(provider_id: str, body: ProviderBody, request: Request,
                          customer_id: str = MiddlewareTenant):
    _validate_roles(body)
    store = _store()
    found = await asyncio.to_thread(store.get, provider_id, customer_id)
    if not found:
        raise HTTPException(404, "No such provider")
    secret = found.client_secret if body.client_secret is None else body.client_secret
    provider = oidc.Provider(id=provider_id, tenant_id=customer_id, **body.model_dump(exclude={"client_secret"}),
                             client_secret=secret)
    return {"provider": public(await asyncio.to_thread(store.save, provider, _user(request)))}


@router.delete("/{provider_id}")
async def delete_provider(provider_id: str, request: Request, customer_id: str = MiddlewareTenant):
    store = _store()
    found = await asyncio.to_thread(store.get, provider_id, customer_id)
    if not found:
        raise HTTPException(404, "No such provider")
    await asyncio.to_thread(store.save, found, _user(request), True)
    return {"deleted": provider_id}
