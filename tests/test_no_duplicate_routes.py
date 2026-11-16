"""
No two handlers may register the same method + path.

GET /v1/tenants/{tenant_id}/usage was defined in both tenant_api and
subscription_api. Starlette dispatches to the first match, so the second
handler was dead code -- and the OpenAPI spec documented whichever was
registered last, so the published contract did not describe what was served.
"""

import importlib
from collections import Counter

from fastapi.routing import APIRoute


def _routes(router):
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):  # included router (FastAPI >= 0.15x)
            yield from _routes(route.original_router)
        elif hasattr(route, "routes"):
            yield from _routes(route)


def test_walks_the_included_routers():
    app = importlib.import_module("main").app
    assert sum(1 for _ in _routes(app.router)) > 300


def test_every_method_and_path_is_registered_once():
    app = importlib.import_module("main").app
    seen = Counter(
        (method, route.path) for route in _routes(app.router) for method in route.methods
    )
    duplicates = sorted(k for k, n in seen.items() if n > 1)
    assert duplicates == []
