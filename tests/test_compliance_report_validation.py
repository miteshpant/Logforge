"""
Regression test: bad input to the compliance-report endpoint is a 400, not 500.

The Settings > Compliance page asked for framework "SOC2", which is not
implemented; the endpoint raised ValueError and wrapped it as a 500. Invalid
dates did the same. The supported list must also match what the service
actually implements.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

ARGS = dict(period_start="2026-10-16T00:00:00Z", period_end="2026-11-16T00:00:00Z",
            sections=["access_controls"], customer_id="tenant-1")


@pytest.mark.asyncio
@pytest.mark.parametrize("framework", ["SOC2", "iso27001", ""])
async def test_unsupported_framework_is_400(framework):
    from routers.enterprise_api import generate_compliance_report

    with pytest.raises(HTTPException) as exc:
        await generate_compliance_report(compliance_framework=framework, **ARGS)
    assert exc.value.status_code == 400
    assert "sox" in exc.value.detail  # tells the caller what IS supported


@pytest.mark.asyncio
@pytest.mark.parametrize("start,end", [("not-a-date", "2026-11-16T00:00:00Z"),
                                       ("2026-11-16T00:00:00Z", "2026-10-16T00:00:00Z")])
async def test_bad_period_is_400(start, end):
    from routers.enterprise_api import generate_compliance_report

    with pytest.raises(HTTPException) as exc:
        await generate_compliance_report(compliance_framework="sox", **{**ARGS, "period_start": start, "period_end": end})
    assert exc.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("framework", ["sox", "GDPR", "pci_dss", "hipaa"])
async def test_supported_framework_reaches_the_service(framework):
    from routers import enterprise_api

    with patch.object(enterprise_api, "EnterpriseService") as svc:
        svc.return_value.generate_compliance_report = AsyncMock(return_value={"status": "generated"})
        result = await enterprise_api.generate_compliance_report(compliance_framework=framework, **ARGS)
    assert result == {"status": "generated"}


def test_supported_list_matches_service_implementation():
    import inspect

    from routers.enterprise_api import SUPPORTED_COMPLIANCE_FRAMEWORKS
    from services.enterprise_service import EnterpriseService

    src = inspect.getsource(EnterpriseService.generate_compliance_report)
    for fw in SUPPORTED_COMPLIANCE_FRAMEWORKS:
        assert f"'{fw}'" in src
