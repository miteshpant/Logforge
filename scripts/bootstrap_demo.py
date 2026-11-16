#!/usr/bin/env python3
"""
Bootstrap a fresh Logforge stack for demos and end-to-end tests.

Runs the "first run" steps from the README against the API:

1. create the first platform admin with a setup token (or log in if setup
   was already done);
2. create a tenant, or reuse one with the same name;
3. put the tenant on the enterprise plan (all features, so the UI's pages
   and batch ingestion work);
4. create an active tenant_admin user, or reuse one with the same email.

Idempotent: safe to run against a stack that is already bootstrapped.
Standard library only. Prints the tenant id on success.

    python scripts/bootstrap_demo.py

Every value can be overridden with an environment variable (see DEFAULTS).
The defaults match the README and the Playwright specs; they are for local
development only.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

DEFAULTS = {
    "LOGFORGE_API_URL": "http://localhost:7080",
    "ADMIN_EMAIL": "admin@example.com",
    "ADMIN_PASSWORD": "Change-Me-Now-123!",
    "TENANT_NAME": "Acme",
    "DEMO_USER_NAME": "Dana Ops",
    "DEMO_USER_EMAIL": "dana@acme.example",
    "DEMO_USER_PASSWORD": "Acme-Demo-Pass-123!",
}
CFG = {key: os.getenv(key, default) for key, default in DEFAULTS.items()}
API = CFG["LOGFORGE_API_URL"].rstrip("/")


def call(method: str, path: str, body: Any = None, token: Optional[str] = None,
         tenant: Optional[str] = None) -> Tuple[int, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if tenant:
        headers["X-Customer-ID"] = tenant
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, raw.decode(errors="replace")


def require(ok: bool, what: str, status: int, body: Any) -> None:
    if not ok:
        sys.exit(f"bootstrap failed: {what}: HTTP {status}: {body}")


def admin_token() -> str:
    status, body = call("POST", "/v1/auth/setup/init")
    if status == 200:
        status, body = call("POST", "/v1/auth/setup", {
            "setup_token": body["setup_token"],
            "name": "Admin",
            "email": CFG["ADMIN_EMAIL"],
            "password": CFG["ADMIN_PASSWORD"],
        })
        require(status == 201, "create platform admin", status, body)
        print(f"created platform admin {CFG['ADMIN_EMAIL']}", file=sys.stderr)
    elif status != 400:  # 400 = setup already completed
        require(False, "start platform setup", status, body)

    status, body = call("POST", "/v1/auth/login",
                        {"email": CFG["ADMIN_EMAIL"], "password": CFG["ADMIN_PASSWORD"]})
    require(status == 200 and isinstance(body, dict) and body.get("access_token"),
            "log in as platform admin", status, body)
    return body["access_token"]


def tenant_id(token: str) -> str:
    # The list is paginated; walk every page so an existing tenant is reused.
    page, matches = 1, []
    while True:
        status, body = call("GET", f"/v1/tenants?page={page}&page_size=100", token=token, tenant="platform")
        require(status == 200, "list tenants", status, body)
        matches += [t for t in body.get("tenants", []) if t.get("name") == CFG["TENANT_NAME"]
                    and t.get("status") == "active"]
        if page >= int(body.get("total_pages") or 1):
            break
        page += 1
    if matches:
        return min(matches, key=lambda t: t.get("created_at", ""))["tenant_id"]

    status, body = call("POST", "/v1/tenants", {
        "name": CFG["TENANT_NAME"],
        "type": "startup",
        "primary_contact_name": "Ops",
        "primary_contact_email": "ops@example.com",
    }, token=token, tenant="platform")
    require(status == 201, "create tenant", status, body)
    print(f"created tenant {CFG['TENANT_NAME']}", file=sys.stderr)
    return body["tenant_id"]


def make_enterprise(token: str, tenant: str) -> None:
    status, body = call("PUT", f"/v1/admin/tenants/{tenant}/subscription", {
        "subscribed_features": ["*"],
        "subscription_tier": "enterprise",
        "reason": "bootstrap_demo.py",
    }, token=token, tenant="platform")
    require(status == 200, "set enterprise plan", status, body)


def demo_user(token: str, tenant: str) -> None:
    status, body = call("POST", "/v1/users", {
        "name": CFG["DEMO_USER_NAME"],
        "email": CFG["DEMO_USER_EMAIL"],
        "password": CFG["DEMO_USER_PASSWORD"],
    }, token=token, tenant="platform")
    if status == 201:
        user_id = body["id"]
        print(f"created user {CFG['DEMO_USER_EMAIL']}", file=sys.stderr)
    else:
        require(status in (400, 409), "create demo user", status, body)
        q = urllib.parse.quote(CFG["DEMO_USER_EMAIL"])
        status, body = call("GET", f"/v1/users/search?q={q}", token=token, tenant="platform")
        require(status == 200, "find existing demo user", status, body)
        matches = [u for u in body.get("users", []) if u.get("email") == CFG["DEMO_USER_EMAIL"]]
        require(bool(matches), "find existing demo user", status, body)
        user_id = matches[0]["id"]

    status, body = call("POST", f"/v1/users/{user_id}/roles",
                        {"tenant_id": tenant, "role": "tenant_admin"},
                        token=token, tenant="platform")
    # A repeated grant is reported as a conflict; either way the role is held.
    require(status in (200, 201, 400, 409), "grant tenant_admin", status, body)

    status, body = call("PUT", f"/v1/users/{user_id}", {"status": "active"},
                        token=token, tenant="platform")
    require(status == 200, "activate demo user", status, body)

    status, body = call("POST", "/v1/auth/login",
                        {"email": CFG["DEMO_USER_EMAIL"], "password": CFG["DEMO_USER_PASSWORD"]})
    require(status == 200, "log in as demo user", status, body)


def main() -> None:
    token = admin_token()
    tenant = tenant_id(token)
    make_enterprise(token, tenant)
    demo_user(token, tenant)
    print(tenant)


if __name__ == "__main__":
    main()
