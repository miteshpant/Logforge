"""
Phase 3: the security events list carries a threat-intel summary for each
event that matched an indicator, so the events page can badge it.
"""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient


def stored(event_id, attrs):
    return {"id": event_id, "rule_id": "logforge_lf-ti-known-c2", "rule_title": "Known C2", "severity": "high",
            "status": "triggered", "timestamp": "2026-11-18T09:00:00Z", "event_data": {}, "matched_fields": {},
            "attack_techniques": ["T1071"], "investigation_notes": [], "artifacts": [],
            "raw_log_data": json.dumps({"normalized_log": {"src_ip": "10.0.1.15", "attrs": attrs}})}


def test_events_list_includes_threat_summary(monkeypatch):
    import routers.security_api as security_api

    class Service:
        async def get_security_events(self, **kwargs):
            return [stored("e1", {"dst_ip": "50.16.16.211",
                                  "threat": {"matched": True, "max_confidence": 90, "threat_types": ["botnet_cc"],
                                             "indicators": [{"source": "abuse.ch Feodo Tracker"}]}}),
                    stored("e2", {"dst_ip": "198.51.100.1"})]

    monkeypatch.setattr(security_api, "get_security_service", lambda: Service())
    app = FastAPI()
    app.include_router(security_api.router)
    events = TestClient(app).get("/v1/security/events", headers={"X-Customer-ID": "acme"}).json()
    assert events[0]["threat"] == {"max_confidence": 90, "threat_types": ["botnet_cc"],
                                   "sources": ["abuse.ch Feodo Tracker"]}
    assert events[1]["threat"] is None
