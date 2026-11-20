"""
OIDC sign-in (Phase 14): authorization code with PKCE, ID tokens checked
against the IdP's keys, users created on first sign-in, roles from groups.
"""

import asyncio
import base64
import hashlib
import json
import os
import sys
import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from sso import oidc  # noqa: E402

ISSUER = "https://idp.acme.test"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks_of(key, kid="k1"):
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    return {"keys": [{**jwk, "kid": kid, "use": "sig", "alg": "RS256"}]}


JWKS = jwks_of(KEY)
DISCOVERY = {"issuer": ISSUER, "authorization_endpoint": f"{ISSUER}/authorize", "token_endpoint": f"{ISSUER}/token",
             "jwks_uri": f"{ISSUER}/jwks"}
PROVIDER = oidc.Provider(id="p1", tenant_id="acme", name="Acme SSO", issuer=ISSUER, client_id="logforge",
                         client_secret="s3cret", groups_claim="groups",
                         role_mapping={"secops": "security_analyst", "it-admins": "tenant_admin"},
                         default_role="viewer", allowed_domains=["acme.test"])


def id_token(key=KEY, kid="k1", alg="RS256", **claims):
    now = int(time.time())
    body = {"iss": ISSUER, "aud": "logforge", "sub": "u-123", "email": "dana@acme.test", "email_verified": True,
            "nonce": "n0nce", "iat": now, "exp": now + 300, "groups": ["secops"], **claims}
    return jwt.encode(body, key, algorithm=alg, headers={"kid": kid})


# -- tokens ---------------------------------------------------------------------------

def test_a_good_id_token_is_accepted():
    claims = oidc.validate_id_token(id_token(), JWKS, ISSUER, "logforge", "n0nce")
    assert claims["email"] == "dana@acme.test"


@pytest.mark.parametrize("token", [
    lambda: id_token(aud="someone-else"),
    lambda: id_token(iss="https://evil.test"),
    lambda: id_token(exp=int(time.time()) - 600),
    lambda: id_token(nonce="other"),
    lambda: id_token(key=OTHER_KEY),                 # not signed by the IdP
    lambda: id_token(kid="unknown"),
    lambda: jwt.encode({"iss": ISSUER, "aud": "logforge", "nonce": "n0nce", "exp": int(time.time()) + 60},
                       "s3cret", algorithm="HS256", headers={"kid": "k1"}),  # symmetric, with the client secret
    lambda: "not.a.token",
])
def test_bad_id_tokens_are_refused(token):
    with pytest.raises(oidc.OIDCError):
        oidc.validate_id_token(token(), JWKS, ISSUER, "logforge", "n0nce")


def test_unsigned_tokens_are_refused():
    header = base64.urlsafe_b64encode(b'{"alg":"none","kid":"k1"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps({"iss": ISSUER, "aud": "logforge", "nonce": "n0nce",
                                                "exp": int(time.time()) + 60}).encode()).rstrip(b"=").decode()
    with pytest.raises(oidc.OIDCError):
        oidc.validate_id_token(f"{header}.{body}.", JWKS, ISSUER, "logforge", "n0nce")


# -- the request ----------------------------------------------------------------------

def test_pkce_and_the_authorization_url():
    verifier, challenge = oidc.pkce_pair()
    assert len(verifier) >= 43
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    url = oidc.authorization_url(DISCOVERY, PROVIDER, "https://lf.test/v1/auth/sso/callback", "st", "n0nce", challenge)
    q = parse_qs(urlparse(url).query)
    assert url.startswith(f"{ISSUER}/authorize?")
    assert q["response_type"] == ["code"] and q["client_id"] == ["logforge"] and q["state"] == ["st"]
    assert q["nonce"] == ["n0nce"] and q["code_challenge_method"] == ["S256"] and q["code_challenge"] == [challenge]
    assert "openid" in q["scope"][0].split() and "email" in q["scope"][0].split()


def test_discovery_must_name_the_configured_issuer():
    def idp(request):
        return httpx.Response(200, json={**DISCOVERY, "issuer": "https://evil.test"})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(idp)) as http:
            return await oidc.discover(ISSUER, http)

    with pytest.raises(oidc.OIDCError):
        asyncio.run(go())


# -- who may sign in, and as what ------------------------------------------------------

def test_roles_come_from_groups_highest_first_then_the_default():
    assert oidc.resolve_role({"groups": ["secops", "it-admins"]}, PROVIDER) == "tenant_admin"
    assert oidc.resolve_role({"groups": ["secops"]}, PROVIDER) == "security_analyst"
    assert oidc.resolve_role({"groups": "secops"}, PROVIDER) == "security_analyst"  # a single string
    assert oidc.resolve_role({"groups": ["sales"]}, PROVIDER) == "viewer"
    assert oidc.resolve_role({}, oidc.Provider(**{**PROVIDER.__dict__, "default_role": None})) is None
    # platform roles can't be granted from an IdP
    evil = oidc.Provider(**{**PROVIDER.__dict__, "role_mapping": {"x": "super_admin"}, "default_role": None})
    assert oidc.resolve_role({"groups": ["x"]}, evil) is None


def test_the_email_must_be_verified_and_in_an_allowed_domain():
    assert oidc.email_of({"email": "Dana@Acme.test", "email_verified": True}, PROVIDER) == "dana@acme.test"
    for claims in ({"email": "dana@acme.test", "email_verified": False}, {"email": "dana@evil.test", "email_verified": True},
                   {"email_verified": True}, {"email": "dana@sub.acme.test.evil", "email_verified": True}):
        with pytest.raises(oidc.OIDCError):
            oidc.email_of(claims, PROVIDER)


def test_the_state_cookie_is_signed_and_expires():
    cookie = oidc.seal_state({"p": "p1", "s": "st"}, ttl=600)
    assert oidc.open_state(cookie)["s"] == "st"
    with pytest.raises(oidc.OIDCError):
        oidc.open_state(cookie[:-2] + "xx")
    with pytest.raises(oidc.OIDCError):
        oidc.open_state(oidc.seal_state({"p": "p1"}, ttl=-1))


def test_next_must_be_a_local_path():
    assert oidc.safe_next("/security/cases?x=1") == "/security/cases?x=1"
    for bad in ("https://evil.test", "//evil.test", "/login", "javascript:alert(1)", "", None):
        assert oidc.safe_next(bad) == "/centrum"
