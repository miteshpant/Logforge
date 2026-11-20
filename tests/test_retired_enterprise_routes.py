"""The legacy Enterprise RBAC, OIDC-config, MFA-setup and integrations routes are
retired: each answers 410 Gone naming its successor, and none is in the API spec."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from routers import enterprise_api  # noqa: E402

RETIRED = [
    ("POST", "/v1/enterprise/auth/oidc/configure", "/v1/sso/providers"),
    ("GET", "/v1/enterprise/auth/providers", "/v1/sso/providers"),
    ("POST", "/v1/enterprise/auth/mfa/setup", "/v1/auth/mfa"),
    ("GET", "/v1/enterprise/rbac/roles", "/v1/roles/custom"),
    ("POST", "/v1/enterprise/rbac/roles", "/v1/roles/custom"),
    ("PUT", "/v1/enterprise/rbac/roles/r1", "/v1/roles/custom"),
    ("DELETE", "/v1/enterprise/rbac/roles/r1", "/v1/roles/custom"),
    ("PUT", "/v1/enterprise/rbac/users/u1/roles", "/v1/users/{user_id}/roles"),
    ("GET", "/v1/enterprise/rbac/permissions", "/v1/auth/access"),
    ("GET", "/v1/enterprise/integrations", "/v1/integrations"),
    ("POST", "/v1/enterprise/integrations/slack/configure", "/v1/integrations"),
    ("GET", "/v1/enterprise/integrations/slack/status", "/v1/integrations"),
    ("POST", "/v1/enterprise/integrations/i1/test", "/v1/integrations"),
    ("DELETE", "/v1/enterprise/integrations/i1", "/v1/integrations"),
]


def client():
    app = FastAPI()
    app.include_router(enterprise_api.router)
    return app, TestClient(app)


def test_retired_routes_answer_gone_with_their_successor():
    _, c = client()
    for method, path, successor in RETIRED:
        r = c.request(method, path, json={}, headers={"X-Customer-ID": "acme"})
        assert r.status_code == 410, (method, path, r.status_code)
        assert successor in r.json()["detail"], path


def test_retired_routes_are_not_in_the_api_spec():
    app, _ = client()
    paths = app.openapi()["paths"]
    for _, path, _ in RETIRED:
        prefix = path.rsplit("/", 1)[0] if path.endswith(("r1", "i1", "u1/roles")) else path
        assert not any(p.startswith("/v1/enterprise/rbac") or p.startswith("/v1/enterprise/integrations")
                       or p in ("/v1/enterprise/auth/oidc/configure", "/v1/enterprise/auth/providers",
                                "/v1/enterprise/auth/mfa/setup") for p in paths), prefix
