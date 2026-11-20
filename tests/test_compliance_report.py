"""Compliance report (the Phase 13 deliverable): evidence for SOC 2 and ISO 27001
controls from the tenant's own records: who has access (and MFA), API keys,
the audit trail, retention and legal holds, and incident response."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import reports  # noqa: E402

END = datetime(2026, 11, 20, tzinfo=timezone.utc)
START = END - timedelta(days=90)

INPUTS = {
    "tenant": "Acme", "start": START, "end": END, "generated_at": END,
    "users": [
        {"email": "dana@acme.example", "status": "active", "roles": ["tenant_admin"], "last_login_at": END - timedelta(days=1),
         "mfa": True, "custom_roles": []},
        {"email": "sam@acme.example", "status": "active", "roles": ["viewer"], "last_login_at": END - timedelta(days=120),
         "mfa": False, "custom_roles": ["Auth only"]},
        {"email": "old@acme.example", "status": "inactive", "roles": ["viewer"], "last_login_at": None,
         "mfa": False, "custom_roles": []},
    ],
    "api_keys": [
        {"name": "shipper", "created_by": "dana", "permissions": ["logs:write"], "last_used": END - timedelta(days=2),
         "expires_at": None, "is_active": True},
        {"name": "old ci", "created_by": "dana", "permissions": [], "last_used": END - timedelta(days=200),
         "expires_at": None, "is_active": True},
    ],
    "audit": [{"action_type": "update", "resource_type": "user", "user_id": "dana", "count": 5},
              {"action_type": "delete", "resource_type": "api_key", "user_id": "dana", "count": 1}],
    "retention": [{"data_type": "logs", "searchable_days": 30, "archive_days": 365}],
    "legal_holds": [{"reason": "Litigation 42", "status": "active", "start_date": START, "end_date": None}],
    "case_metrics": {"cases": 12, "open_total": 2, "sla_breaches": {"acknowledge": {"high": 1}, "resolve": {}}},
}


def section(report, title):
    return next(s for s in report["sections"] if s["title"].startswith(title))


def test_the_report_cites_the_controls_it_evidences():
    report = reports.build_compliance(INPUTS)
    assert report["title"] == "Compliance evidence report"
    titles = " ".join(s["title"] for s in report["sections"])
    for control in ("CC6.2", "CC6.3", "A.5.18", "CC7.2", "A.8.15", "A.5.33", "CC7.4", "A.5.26"):
        assert control in titles


def test_access_review_lists_users_and_flags_what_to_look_at():
    report = reports.build_compliance(INPUTS)
    summary = dict(section(report, "Summary")["rows"])
    assert summary["Active users"] == 2
    assert summary["Active users without MFA"] == 1
    assert summary["Active users not seen in 90 days"] == 1
    assert summary["Administrators"] == 1
    assert summary["API keys unused in 90 days"] == 1
    rows = section(report, "Access review")["rows"]
    sam = next(r for r in rows if r[0] == "sam@acme.example")
    assert "viewer" in sam[1] and "Auth only" in sam[1] and sam[4] == "no"


def test_audit_trail_and_holds():
    report = reports.build_compliance(INPUTS)
    assert ["update", "user", 5] in section(report, "Audit trail")["rows"]
    assert section(report, "Retention")["rows"][0][0] == "logs"
    assert section(report, "Legal holds")["rows"][0][0] == "Litigation 42"


def test_it_renders_as_csv_and_pdf():
    report = reports.build_compliance(INPUTS)
    assert "Access review" in reports.to_csv(report)
    assert reports.to_pdf(report).startswith(b"%PDF")
