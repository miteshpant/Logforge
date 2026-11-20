"""
The dependency audit gate (Phase 14): high and critical advisories fail CI
unless allowlisted with a reason and an expiry date.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import audit_gate  # noqa: E402


def report(*advisories):
    vulns = {}
    for pkg, ghsa, sev in advisories:
        vulns.setdefault(pkg, {"name": pkg, "severity": sev, "via": []})["via"].append(
            {"url": f"https://github.com/advisories/{ghsa}", "severity": sev, "title": f"{pkg} issue", "name": pkg})
    vulns["wrapper"] = {"name": "wrapper", "severity": "high", "via": ["axios"]}  # a dependent, not an advisory
    return {"vulnerabilities": vulns}


ALLOW = [{"package": "next", "advisory": "GHSA-next-1", "reason": "needs Next 15", "expires": "2027-01-31"}]


def test_findings_are_advisories_at_or_above_high():
    found = audit_gate.findings(report(("axios", "GHSA-ax-1", "high"), ("lodash", "GHSA-lo-1", "moderate"),
                                       ("next", "GHSA-next-1", "critical")))
    assert sorted((f["package"], f["advisory"]) for f in found) == [("axios", "GHSA-ax-1"), ("next", "GHSA-next-1")]


def test_allowlisted_advisories_pass_until_they_expire():
    found = audit_gate.findings(report(("next", "GHSA-next-1", "critical")))
    assert audit_gate.check(found, ALLOW, today=date(2026, 11, 20)) == []
    problems = audit_gate.check(found, ALLOW, today=date(2027, 2, 1))
    assert len(problems) == 1 and "expired" in problems[0]


def test_new_advisories_fail():
    found = audit_gate.findings(report(("next", "GHSA-next-1", "critical"), ("axios", "GHSA-ax-1", "high")))
    problems = audit_gate.check(found, ALLOW, today=date(2026, 11, 20))
    assert len(problems) == 1 and "GHSA-ax-1" in problems[0]


def test_allowlist_entries_need_a_reason_and_an_expiry():
    bad = [{"package": "next", "advisory": "GHSA-next-1", "reason": "", "expires": "2027-01-31"},
           {"package": "x", "advisory": "GHSA-x", "reason": "r"}]
    assert len(audit_gate.check([], bad, today=date(2026, 11, 20))) == 2
