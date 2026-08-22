"""
Tests for ENH-008 -- feature/subscription checks must fail CLOSED.

The middleware previously returned `{"access_granted": True, "reason":
"Feature validation error - access granted"}` whenever the subscription lookup
raised. A degraded subscription service therefore handed every tenant every paid
feature: a revenue-integrity failure, an entitlement bypass, and a fabricated
success response of exactly the kind this project forbids.

The replacement raises 503 -- deliberately distinct from the 403 used for a real
entitlement denial, because the tenant may be entitled and we simply cannot
prove it right now.
"""

import pytest
from fastapi import HTTPException

from authn_authz_middleware import UnifiedAuthMiddleware


class _RaisingSubscriptionService:
    def __init__(self, exc):
        self.exc = exc

    async def validate_feature_access(self, tenant_id, endpoint):
        raise self.exc


class _GrantingSubscriptionService:
    async def validate_feature_access(self, tenant_id, endpoint):
        return {"access_granted": True, "feature": "queries.basic"}


class _DenyingSubscriptionService:
    async def validate_feature_access(self, tenant_id, endpoint):
        return {
            "access_granted": False,
            "error_code": "feature_not_in_plan",
            "reason": "Advanced queries require the Pro plan",
            "required_feature": "queries.advanced",
        }


def _middleware(subscription_service):
    mw = UnifiedAuthMiddleware.__new__(UnifiedAuthMiddleware)
    mw.subscription_service = subscription_service
    return mw


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("subscription DB unreachable"),
        ConnectionError("clickhouse down"),
        TimeoutError("lookup timed out"),
        ValueError("malformed subscription record"),
    ],
)
async def test_subscription_failure_denies_access(exc):
    """Any lookup failure must deny, never grant."""
    mw = _middleware(_RaisingSubscriptionService(exc))

    with pytest.raises(HTTPException) as err:
        await mw._validate_feature_access("tenant-a", "/v1/query/advanced")

    assert err.value.status_code == 503


@pytest.mark.asyncio
async def test_failure_never_returns_access_granted():
    """
    The specific regression: the old code returned a dict claiming access was
    granted. Nothing may return a truthy `access_granted` on failure.
    """
    mw = _middleware(_RaisingSubscriptionService(RuntimeError("boom")))

    try:
        result = await mw._validate_feature_access("tenant-a", "/v1/query/advanced")
    except HTTPException:
        return  # correct behaviour

    pytest.fail(
        f"Feature validation failed open and returned {result!r}. "
        "A degraded subscription service must never grant entitlements."
    )


@pytest.mark.asyncio
async def test_failure_uses_503_not_403():
    """
    503 (retry) is semantically different from 403 (upgrade your plan). Telling
    an entitled customer to upgrade because our database blipped is wrong.
    """
    mw = _middleware(_RaisingSubscriptionService(RuntimeError("boom")))

    with pytest.raises(HTTPException) as err:
        await mw._validate_feature_access("tenant-a", "/v1/query/advanced")

    assert err.value.status_code == 503
    assert err.value.status_code != 403


@pytest.mark.asyncio
async def test_error_detail_does_not_leak_internals():
    """The client must not receive the raw internal exception text."""
    mw = _middleware(
        _RaisingSubscriptionService(
            RuntimeError("clickhouse://user:password@10.0.0.5:8123 refused")
        )
    )

    with pytest.raises(HTTPException) as err:
        await mw._validate_feature_access("tenant-a", "/v1/query/advanced")

    assert "password" not in str(err.value.detail)
    assert "10.0.0.5" not in str(err.value.detail)


# ---------------------------------------------------------------------------
# Normal paths still work
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_granted_access_passes_through():
    mw = _middleware(_GrantingSubscriptionService())

    result = await mw._validate_feature_access("tenant-a", "/v1/logs")

    assert result["access_granted"] is True


@pytest.mark.asyncio
async def test_genuine_denial_is_preserved():
    """A real entitlement denial must still be reported as a denial, not a 503."""
    mw = _middleware(_DenyingSubscriptionService())

    result = await mw._validate_feature_access("tenant-a", "/v1/query/advanced")

    assert result["access_granted"] is False
    assert result["error_code"] == "feature_not_in_plan"


def test_denial_payload_is_read_defensively():
    """
    The 403 branch must tolerate a denial payload missing `error_code`/`reason`
    rather than raising KeyError and turning a correct 403 into a 500.
    """
    import inspect

    source = inspect.getsource(UnifiedAuthMiddleware.dispatch)
    assert 'feature_access["error_code"]' not in source, (
        "Denial payload should be read with .get() to avoid KeyError -> 500."
    )
    assert 'feature_access.get("error_code"' in source
