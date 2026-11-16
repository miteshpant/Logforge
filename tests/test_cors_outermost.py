"""
CORS must wrap every other middleware.

Found in a live browser QA run: the UI's call to /v1/tenants/{id} came back as
a browser "CORS error" although the API had answered 401. CORSMiddleware was
registered first, which in Starlette makes it the INNERMOST layer, so responses
produced by the auth or rate-limit middleware never passed through it and had
no Access-Control-Allow-Origin header. The browser then hides the real status
from the page.
"""

import importlib

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

ORIGIN = "http://localhost:3001"


def _app():
    return importlib.import_module("main").app


def test_cors_is_the_outermost_middleware():
    # Starlette inserts each add_middleware() at index 0: [0] runs first.
    assert _app().user_middleware[0].cls is CORSMiddleware


def test_auth_rejection_still_carries_cors_headers():
    """
    Rebuild main.py's real middleware stack, in the same order, with only the
    auth layer swapped for a stub that always rejects (the real one needs
    ClickHouse). A 401 produced inside the stack must still get CORS headers.
    """
    from fastapi import FastAPI
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    from authn_authz_middleware import UnifiedAuthMiddleware

    class RejectingAuth(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            return JSONResponse({"error": "Invalid or expired session"}, status_code=401)

    probe = FastAPI()

    @probe.get("/v1/tenants/{tenant_id}")
    async def _tenant(tenant_id: str):  # pragma: no cover - auth rejects first
        return {"tenant_id": tenant_id}

    # user_middleware[0] is outermost; re-adding in reverse rebuilds the stack.
    for mw in reversed(_app().user_middleware):
        cls = RejectingAuth if mw.cls is UnifiedAuthMiddleware else mw.cls
        kwargs = {} if cls is RejectingAuth else dict(mw.kwargs)
        if cls is CORSMiddleware:
            kwargs["allow_origins"] = [ORIGIN]
        probe.add_middleware(cls, *(() if cls is RejectingAuth else mw.args), **kwargs)

    resp = TestClient(probe).get("/v1/tenants/acme", headers={"Origin": ORIGIN})
    assert resp.status_code == 401
    assert resp.headers.get("access-control-allow-origin") == ORIGIN
