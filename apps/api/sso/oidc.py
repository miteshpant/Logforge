"""
OpenID Connect sign-in (Phase 14): the authorization code flow with PKCE.

1. /v1/auth/sso/{provider}/start sends the browser to the IdP with a state,
   a nonce and a PKCE challenge, kept in a signed, short-lived cookie.
2. The IdP sends it back to /v1/auth/sso/callback with a code. The code is
   exchanged (with the PKCE verifier and the client secret) for an ID
   token, which must be signed by one of the IdP's published keys (RS/ES/PS
   algorithms only), name the IdP as issuer and Logforge as audience, be
   unexpired and carry the nonce.
3. The email must be verified by the IdP and in one of the provider's
   domains. Roles come from a groups claim through the provider's mapping
   (the highest tenant role matched wins), else its default role; platform
   roles can't be granted this way.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx
import jwt

ASYMMETRIC = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"]
# tenant roles, most privileged first
TENANT_ROLES = ["tenant_admin", "security_analyst", "devops_engineer", "compliance_officer", "viewer"]
STATE_AUDIENCE = "logforge-oidc-state"
DEFAULT_NEXT = "/centrum"


class OIDCError(Exception):
    pass


@dataclass
class Provider:
    id: str
    tenant_id: str
    name: str
    issuer: str
    client_id: str
    client_secret: str = ""
    scopes: str = "openid email profile"
    groups_claim: str = "groups"
    role_mapping: Dict[str, str] = field(default_factory=dict)
    default_role: Optional[str] = "viewer"
    allowed_domains: List[str] = field(default_factory=list)
    enabled: bool = True


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def pkce_pair() -> Tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    return verifier, _b64(hashlib.sha256(verifier.encode()).digest())


async def discover(issuer: str, http: httpx.AsyncClient) -> Dict[str, Any]:
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        response = await http.get(url, timeout=10)
        response.raise_for_status()
        config = response.json()
    except (httpx.HTTPError, ValueError) as e:
        raise OIDCError(f"couldn't read the IdP's configuration: {e}")
    if config.get("issuer", "").rstrip("/") != issuer.rstrip("/"):
        raise OIDCError("the IdP's configuration names another issuer")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not config.get(key):
            raise OIDCError(f"the IdP's configuration has no {key}")
    return config


def authorization_url(discovery: Dict[str, Any], provider: Provider, redirect_uri: str, state: str, nonce: str,
                      challenge: str) -> str:
    scopes = provider.scopes.split()
    for needed in ("openid", "email"):
        if needed not in scopes:
            scopes.insert(0, needed)
    query = {"response_type": "code", "client_id": provider.client_id, "redirect_uri": redirect_uri,
             "scope": " ".join(scopes), "state": state, "nonce": nonce, "code_challenge": challenge,
             "code_challenge_method": "S256"}
    return f"{discovery['authorization_endpoint']}?{urlencode(query)}"


async def exchange(discovery: Dict[str, Any], provider: Provider, code: str, verifier: str, redirect_uri: str,
                   http: httpx.AsyncClient) -> Dict[str, Any]:
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
            "client_id": provider.client_id, "code_verifier": verifier}
    if provider.client_secret:
        data["client_secret"] = provider.client_secret
    try:
        response = await http.post(discovery["token_endpoint"], data=data, timeout=10,
                                   headers={"Accept": "application/json"})
    except httpx.HTTPError as e:
        raise OIDCError(f"the IdP's token endpoint failed: {e}")
    if response.status_code != 200:
        raise OIDCError(f"the IdP refused the code ({response.status_code})")
    tokens = response.json()
    if not tokens.get("id_token"):
        raise OIDCError("the IdP returned no ID token")
    return tokens


async def fetch_jwks(discovery: Dict[str, Any], http: httpx.AsyncClient) -> Dict[str, Any]:
    try:
        response = await http.get(discovery["jwks_uri"], timeout=10)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as e:
        raise OIDCError(f"couldn't read the IdP's keys: {e}")


def validate_id_token(token: str, jwks: Dict[str, Any], issuer: str, client_id: str, nonce: str,
                      leeway: int = 60) -> Dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise OIDCError(f"not a token: {e}")
    if header.get("alg") not in ASYMMETRIC:
        raise OIDCError(f"ID tokens must be signed with a public key, not {header.get('alg')!r}")
    keys = [k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")] if header.get("kid") else \
        list(jwks.get("keys", []))
    if not keys:
        raise OIDCError("the token was signed with a key the IdP doesn't publish")
    last: Exception = OIDCError("no key verified the token")
    for key in keys:
        try:
            public = jwt.PyJWK(key, algorithm=header["alg"]).key
            claims = jwt.decode(token, public, algorithms=[header["alg"]], audience=client_id, issuer=issuer,
                                leeway=leeway, options={"require": ["exp", "iss", "aud"]})
            break
        except jwt.PyJWTError as e:
            last = e
    else:
        raise OIDCError(f"the ID token is invalid: {last}")
    if not nonce or claims.get("nonce") != nonce:
        raise OIDCError("the ID token's nonce doesn't match this sign-in")
    return claims


def email_of(claims: Dict[str, Any], provider: Provider) -> str:
    email = str(claims.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise OIDCError("the IdP sent no email address")
    if claims.get("email_verified") is not True:
        raise OIDCError("the IdP hasn't verified this email address")
    domain = email.rsplit("@", 1)[1]
    if provider.allowed_domains and domain not in {d.lower().lstrip("@") for d in provider.allowed_domains}:
        raise OIDCError(f"{domain} isn't one of this sign-in's domains")
    return email


def resolve_role(claims: Dict[str, Any], provider: Provider) -> Optional[str]:
    groups = claims.get(provider.groups_claim) or []
    if isinstance(groups, str):
        groups = [groups]
    matched = {provider.role_mapping[g] for g in groups if g in provider.role_mapping}
    for role in TENANT_ROLES:
        if role in matched:
            return role
    return provider.default_role if provider.default_role in TENANT_ROLES else None


def _state_key() -> str:
    from authn_authz_middleware import JWT_SECRET

    return "oidc-state:" + JWT_SECRET


def seal_state(data: Dict[str, Any], ttl: int = 600) -> str:
    return jwt.encode({**data, "aud": STATE_AUDIENCE, "exp": int(time.time()) + ttl}, _state_key(), algorithm="HS256")


def open_state(cookie: str) -> Dict[str, Any]:
    try:
        return jwt.decode(cookie or "", _state_key(), algorithms=["HS256"], audience=STATE_AUDIENCE)
    except jwt.PyJWTError as e:
        raise OIDCError(f"the sign-in expired or was tampered with ({e})")


def safe_next(value: Optional[str]) -> str:
    if not value or not value.startswith("/") or value.startswith("//") or value.startswith("/login"):
        return DEFAULT_NEXT
    return value


def new_state() -> Tuple[str, str]:
    return secrets.token_urlsafe(24), secrets.token_urlsafe(24)
