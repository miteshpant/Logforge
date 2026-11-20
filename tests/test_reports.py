"""
Exports and reports (Phase 13): an ATT&CK Navigator layer of detection
coverage, and a security operations report as JSON, CSV or PDF.
"""

import csv
import io
import json
import os
import sys
import zlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import reports  # noqa: E402

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
COVERAGE = {"techniques": [
    {"technique_id": "T1110", "technique_name": "Brute Force", "tactics": ["credential-access"], "rule_count": 3,
     "enabled_rule_count": 3, "has_fixtures": True, "last_detection_at": "2026-11-19T10:00:00+00:00"},
    {"technique_id": "T1003.001", "technique_name": "LSASS Memory", "tactics": ["credential-access"],
     "rule_count": 1, "enabled_rule_count": 1, "has_fixtures": True, "last_detection_at": None},
    {"technique_id": "T1059", "technique_name": "Command and Scripting Interpreter", "tactics": ["execution"],
     "rule_count": 2, "enabled_rule_count": 0, "has_fixtures": True, "last_detection_at": None},
    {"technique_id": "T1566", "technique_name": "Phishing", "tactics": ["initial-access"], "rule_count": 1,
     "enabled_rule_count": 1, "has_fixtures": False, "last_detection_at": None}],
    "summary": {"total_techniques": 4, "covered_techniques": 2, "awaiting_content": 1, "total_rules": 7}}


def test_navigator_layer():
    layer = reports.navigator_layer(COVERAGE, "Acme", NOW)
    assert layer["domain"] == "enterprise-attack" and layer["versions"]["layer"] == "4.5"
    by_id = {t["techniqueID"]: t for t in layer["techniques"]}
    assert by_id["T1110"]["score"] == 3 and by_id["T1110"]["enabled"] is True
    assert "last detection 2026-11-19" in by_id["T1110"]["comment"]
    assert by_id["T1003.001"]["score"] == 1  # sub-techniques as they are
    assert by_id["T1059"]["score"] == 0 and "disabled" in by_id["T1059"]["comment"]
    assert by_id["T1566"]["score"] == 0 and "no tested fixtures" in by_id["T1566"]["comment"]
    assert layer["gradient"]["minValue"] == 0 and layer["gradient"]["maxValue"] == 3
    assert "Acme" in layer["name"] and "2 of 4" in layer["description"]
    json.dumps(layer)  # serialisable as is


INPUTS = {
    "tenant": "Acme", "start": datetime(2026, 10, 21, tzinfo=timezone.utc), "end": NOW,
    "alerts_by_severity": {"critical": 2, "high": 11, "medium": 40, "low": 103},
    "case_metrics": {"cases": 9, "open_total": 2, "by_severity": {
        "high": {"cases": 3, "open": 1, "mtta_minutes": {"median": 12.0}, "mttr_minutes": {"median": 300.5}},
        "low": {"cases": 6, "open": 1, "mtta_minutes": {"median": None}, "mttr_minutes": {"median": None}}},
        "sla_breaches": {"acknowledge": {"high": 1, "low": 0}, "resolve": {"high": 0, "low": 2}}},
    "coverage": COVERAGE,
    "retention": [{"data_type": "logs", "searchable_days": 30, "archive_days": 365}],
    "playbook_runs": [{"status": "succeeded"}, {"status": "succeeded"}, {"status": "rejected"},
                      {"status": "waiting_approval"}],
    "approvals": [{"by": "dana@acme.test", "approved": True}, {"by": "lee@acme.test", "approved": False}],
}


def test_the_report_has_its_sections_and_numbers():
    report = reports.build(INPUTS)
    titles = [s["title"] for s in report["sections"]]
    assert titles == ["Summary", "Alerts by severity", "Case response", "Detection coverage", "Retention",
                      "Response automation"]
    summary = dict(report["sections"][0]["rows"])
    assert summary["Alerts"] == 156 and summary["Cases"] == 9 and summary["Open cases"] == 2
    assert summary["ATT&CK techniques covered"] == "2 of 4"
    cases = report["sections"][2]
    assert cases["columns"][:3] == ["Severity", "Cases", "Open"]
    assert cases["rows"][0] == ["high", 3, 1, 12.0, 300.5, 1, 0]
    automation = dict(report["sections"][5]["rows"])
    assert automation["Runs succeeded"] == 2 and automation["Containment approvals given"] == 1
    assert report["period"] == {"start": "2026-10-21", "end": "2026-11-20", "days": 30}


def test_csv_has_every_section():
    text = reports.to_csv(reports.build(INPUTS))
    rows = list(csv.reader(io.StringIO(text)))
    assert ["# Alerts by severity"] in rows and ["Severity", "Alerts"] in rows and ["high", "11"] in rows


def test_pdf_is_a_valid_pdf_with_the_text():
    data = reports.to_pdf(reports.build(INPUTS))
    assert data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF")
    text = b""
    for chunk in data.split(b"stream\r\n")[1:]:
        text += zlib.decompress(chunk.split(b"\r\nendstream")[0])
    assert b"Security operations report" in text and b"Case response" in text
    # the xref table points at every object
    xref = data[data.index(b"\nxref\n") + 1:]
    count = int(xref.split(b"\n")[1].split()[1])
    assert count >= 5


def test_pdf_handles_long_reports_and_odd_characters():
    big = dict(INPUTS, retention=[{"data_type": f"type{i} (é ✓)", "searchable_days": i, "archive_days": 0}
                                  for i in range(200)])
    data = reports.to_pdf(reports.build(big))
    assert data.count(b"/Type /Page ") >= 3


def test_schedule_due_times():
    daily = {"every": "daily", "hour": 7}
    assert reports.due(daily, None, datetime(2026, 11, 20, 7, 5, tzinfo=timezone.utc))
    assert not reports.due(daily, None, datetime(2026, 11, 20, 6, 59, tzinfo=timezone.utc))
    assert not reports.due(daily, datetime(2026, 11, 20, 7, 1, tzinfo=timezone.utc),
                           datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc))
    weekly = {"every": "weekly", "hour": 7}  # Mondays
    assert reports.due(weekly, None, datetime(2026, 11, 23, 8, tzinfo=timezone.utc))
    assert not reports.due(weekly, None, datetime(2026, 11, 24, 8, tzinfo=timezone.utc))
    monthly = {"every": "monthly", "hour": 7}
    assert reports.due(monthly, datetime(2026, 11, 1, 7, tzinfo=timezone.utc),
                       datetime(2026, 12, 1, 7, 30, tzinfo=timezone.utc))
    assert reports.window(monthly, NOW)[0] == datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
