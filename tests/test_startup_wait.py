"""
The API waits for ClickHouse at startup. It used to start while ClickHouse
was still coming up; the startup hook raised, uvicorn (lifespan "auto")
carried on without it, and every signed-in request failed until a restart.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))


def test_it_retries_until_clickhouse_answers():
    from dependencies import wait_for

    calls = []

    def check():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionRefusedError("not yet")

    asyncio.run(wait_for(check, "ClickHouse", attempts=5, delay=0))
    assert len(calls) == 3


def test_it_gives_up_with_the_last_error():
    from dependencies import wait_for

    def check():
        raise ConnectionRefusedError("still down")

    with pytest.raises(RuntimeError, match="ClickHouse.*still down"):
        asyncio.run(wait_for(check, "ClickHouse", attempts=3, delay=0))


def test_the_server_fails_instead_of_serving_without_startup():
    dockerfile = open(os.path.join(os.path.dirname(__file__), "..", "apps", "api", "Dockerfile")).read()
    assert '"--lifespan", "on"' in dockerfile
    chart = open(os.path.join(os.path.dirname(__file__), "..", "deploy", "helm", "logforge", "templates", "api.yaml")).read()
    assert '"--lifespan", "on"' in chart


def test_building_the_auth_middleware_needs_no_database(monkeypatch):
    import authn_authz_middleware as m

    def boom():
        raise ConnectionRefusedError("ClickHouse is still starting")

    monkeypatch.setattr(m, "get_user_service", boom)
    monkeypatch.setattr(m, "get_subscription_service", boom)
    mw = m.UnifiedAuthMiddleware(lambda scope, receive, send: None)  # must not touch the database
    with pytest.raises(ConnectionRefusedError):
        mw.user_service  # only when first used
