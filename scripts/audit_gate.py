#!/usr/bin/env python3
"""
Dependency audit gate (Phase 14, docs/security.md).

    npm audit --omit=dev --json | python scripts/audit_gate.py security/audit-allowlist.json

Fails (exit 1) on any high or critical advisory that isn't allowlisted. An
allowlist entry names the package and advisory (GHSA id), says why it's
accepted, and expires; an expired or incomplete entry fails too, so
exceptions get looked at again.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from typing import Any, Dict, List, Optional

SEVERE = ("high", "critical")


def findings(report: Dict[str, Any]) -> List[Dict[str, str]]:
    out = {}
    for pkg, vuln in (report.get("vulnerabilities") or {}).items():
        for via in vuln.get("via") or []:
            if not isinstance(via, dict) or via.get("severity") not in SEVERE:
                continue  # a string names a dependency that carries the advisory, not the advisory
            advisory = str(via.get("url", "")).rstrip("/").rsplit("/", 1)[-1] or str(via.get("source"))
            out[(pkg, advisory)] = {"package": pkg, "advisory": advisory, "severity": via["severity"],
                                    "title": via.get("title", "")}
    return sorted(out.values(), key=lambda f: (f["package"], f["advisory"]))


def check(found: List[Dict[str, str]], allowlist: List[Dict[str, str]], today: Optional[date] = None) -> List[str]:
    today = today or date.today()
    problems, allowed = [], {}
    for entry in allowlist:
        key = (entry.get("package"), entry.get("advisory"))
        if not entry.get("reason") or not entry.get("expires"):
            problems.append(f"allowlist entry {key} needs a reason and an expiry date")
            continue
        allowed[key] = entry
    for f in found:
        entry = allowed.get((f["package"], f["advisory"]))
        if entry is None:
            problems.append(f"{f['severity']}: {f['package']} {f['advisory']} {f['title']}")
        elif date.fromisoformat(entry["expires"]) < today:
            problems.append(f"allowlist entry for {f['package']} {f['advisory']} expired on {entry['expires']}: "
                            f"fix it or review the exception")
    return problems


def main(argv: List[str]) -> int:
    allowlist = json.load(open(argv[1])) if len(argv) > 1 else []
    found = findings(json.load(sys.stdin))
    problems = check(found, allowlist)
    accepted = len(found) - sum(1 for p in problems if p.startswith(("high", "critical")))
    print(f"{len(found)} high/critical advisories, {accepted} allowlisted")
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
