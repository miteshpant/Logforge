"""
The ATT&CK coverage matrix (SecurityService.get_mitre_coverage) had no route,
so the SIEM page computed coverage in the browser from a hard-coded
technique->tactic table. GET /v1/security/mitre-coverage exposes the server
matrix; GET /v1/security/mitre-attack/techniques lists the catalogue.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _paths():
    from routers import security_api

    return {route.path for route in security_api.router.routes}


def test_routes_are_registered():
    paths = _paths()
    assert "/v1/security/mitre-coverage" in paths
    assert "/v1/security/mitre-attack/techniques" in paths


@pytest.mark.asyncio
async def test_coverage_route_returns_service_matrix_for_tenant():
    from routers import security_api

    matrix = {"techniques": [], "awaiting_content": [], "summary": {"total_techniques": 0}}
    service = MagicMock()
    service.get_mitre_coverage = AsyncMock(return_value=matrix)
    with patch.object(security_api, "get_security_service", return_value=service):
        out = await security_api.get_mitre_coverage(customer_id="tenant-1")

    assert out is matrix
    service.get_mitre_coverage.assert_awaited_once_with("tenant-1")


@pytest.mark.asyncio
async def test_techniques_lists_catalogue_and_filters_by_tactic():
    from routers import security_api

    everything = await security_api.list_mitre_techniques(tactic=None)
    assert everything["total_count"] == len(everything["techniques"]) > 0
    first = everything["techniques"][0]
    assert first["id"].startswith("T") and first["name"] and first["description"]
    assert everything["framework_version"].startswith("logforge-catalogue-")

    cred = await security_api.list_mitre_techniques(tactic="credential-access")
    assert 0 < cred["total_count"] < everything["total_count"]
    assert all("credential-access" in t["tactics"] for t in cred["techniques"])
    assert any(t["id"] == "T1003" for t in cred["techniques"])
