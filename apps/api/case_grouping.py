"""
Automatic case grouping (Phase 2): a new alert joins the open case for the
same entity seen within the window, instead of becoming one more item to
triage.

The entity key is the most specific actor: source IP (network-origin
activity), then host (endpoint activity), then user, taken from the Phase 1
correlation group when the alert has one, otherwise from its event. A
correlation group with none of those fields keys on all its fields. Alerts below the
minimum severity join an existing case but don't open one. An alert with no
entity at all gets a case of its own.

Configuration: CASE_GROUPING=off disables it; CASE_GROUPING_WINDOW_HOURS
(default 24); CASE_AUTO_MIN_SEVERITY (default medium).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from cases import SEVERITIES, Case

ENTITY_PRIORITY = ("src_ip", "hostname", "user")


@dataclass
class GroupingPolicy:
    window: timedelta = timedelta(hours=24)
    min_severity: str = "medium"
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "GroupingPolicy":
        try:
            hours = float(os.getenv("CASE_GROUPING_WINDOW_HOURS", "24"))
        except ValueError:
            hours = 24.0
        severity = os.getenv("CASE_AUTO_MIN_SEVERITY", "medium")
        return cls(window=timedelta(hours=max(hours, 0.01)),
                   min_severity=severity if severity in SEVERITIES else "medium",
                   enabled=os.getenv("CASE_GROUPING", "on").lower() not in ("off", "false", "0"))


def group_key(alert: Dict[str, Any], correlation_group: Optional[Dict[str, Any]] = None) -> str:
    group = {k: v for k, v in (correlation_group or {}).items() if v not in (None, "", "None")}
    if group:
        # Same priority as single-event alerts, so a correlation grouped by
        # (hostname, user) joins that host's other alerts.
        for name in ENTITY_PRIORITY:
            if name in group:
                return f"{name}={group[name]}"
        return "|".join(f"{k}={group[k]}" for k in sorted(group))
    entities = alert.get("entities") or {}
    for name in ENTITY_PRIORITY:
        values = entities.get(name) or []
        if values:
            return f"{name}={values[0]}"
    return ""


def plan(alert: Dict[str, Any], open_case: Optional[Case], now: datetime, policy: GroupingPolicy) -> str:
    """'attach' to the open case, 'create' a new one, or 'skip'."""
    if open_case is not None and open_case.is_open and open_case.last_alert_at is not None \
            and now - open_case.last_alert_at <= policy.window:
        return "attach"
    severity = alert.get("severity")
    if severity in SEVERITIES and SEVERITIES.index(severity) < SEVERITIES.index(policy.min_severity):
        return "skip"
    return "create"
