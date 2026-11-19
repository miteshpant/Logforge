"""
Detections are routed into cases as they are saved (Phase 2).

After the security handler stores a detection it hands it to
CaseService.route_alert, with the correlation group when the detection came
from a correlation rule. Grouping is best-effort: a failure there must never
lose the detection.
"""

import asyncio
import json
import sys
import types

import pytest

from events.handlers.security_handler import SecurityEventHandler

EVENT = {"detection_id": "d1", "rule_id": "logforge_lf-c-password-spray", "rule_name": "Password spray",
         "customer_id": "acme", "severity": "high", "triggered_at": "2026-11-18T09:00:00Z",
         "attack_techniques": ["T1110.003"],
         "matched_fields": {"_correlation": {"type": "value_count", "group": {"src_ip": "45.155.205.10"}}},
         "enrichment_data": {"src_ip": "45.155.205.10", "user": "erin", "service": "sshd"}}


@pytest.fixture
def handler(monkeypatch):
    saved, routed = [], []

    class FakeSecurityService:
        async def create_security_event(self, data):
            saved.append(data)
            return "d1"

    class FakeCaseService:
        async def route_alert(self, tenant_id, row, correlation_group=None, policy=None):
            routed.append((tenant_id, row, correlation_group))
            if getattr(FakeCaseService, "fail", False):
                raise RuntimeError("clickhouse down")

    monkeypatch.setitem(sys.modules, "services.security_service",
                        types.SimpleNamespace(SecurityService=FakeSecurityService))
    monkeypatch.setitem(sys.modules, "services.case_service", types.SimpleNamespace(CaseService=FakeCaseService))
    instance = SecurityEventHandler.__new__(SecurityEventHandler)

    async def no_intel(*args, **kwargs):
        return {}

    instance._correlate_with_threat_intel = no_intel
    instance.saved, instance.routed, instance.case_service = saved, routed, FakeCaseService
    return instance


def test_saved_detections_are_routed_into_cases(handler):
    assert asyncio.run(handler._save_security_detection_to_database(dict(EVENT))) is True
    tenant, row, group = handler.routed[0]
    assert tenant == "acme" and group == {"src_ip": "45.155.205.10"}
    assert row["id"] == "d1" and row["severity"] == "high" and row["title"] == "Password spray"
    assert json.loads(row["raw_log_data"])["normalized_log"]["user"] == "erin"


def test_a_grouping_failure_does_not_lose_the_detection(handler):
    handler.case_service.fail = True
    assert asyncio.run(handler._save_security_detection_to_database(dict(EVENT))) is True
    assert len(handler.saved) == 1
