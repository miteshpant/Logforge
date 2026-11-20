"""
Exports and reports (Phase 13).

- navigator_layer: the tenant's detection coverage as an ATT&CK Navigator
  layer (load it at https://mitre-attack.github.io/attack-navigator/).
- build: a security operations report for a period (alerts, case response
  and SLA breaches, detection coverage, retention, response automation),
  rendered by to_csv or to_pdf; the sections are evidence auditors ask for
  (SOC 2 CC7, ISO 27001 A.5.24–A.5.28: incidents detected, responded to,
  within targets).
- due / window: when a scheduled report is sent, and what period it covers.

to_pdf writes PDF 1.4 itself (Helvetica, A4, compressed text streams):
no PDF library is a dependency of the API.
"""

from __future__ import annotations

import csv
import io
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

SEVERITIES = ("critical", "high", "medium", "low")


# -- ATT&CK Navigator ----------------------------------------------------------------------

def navigator_layer(coverage: Dict[str, Any], tenant_name: str, now: datetime) -> Dict[str, Any]:
    techniques = []
    for t in coverage.get("techniques", []):
        covered = t.get("has_fixtures") and t.get("enabled_rule_count", 0) > 0
        if covered:
            comment = f"{t['enabled_rule_count']} enabled rule(s)"
            if t.get("last_detection_at"):
                comment += f", last detection {str(t['last_detection_at'])[:10]}"
        elif t.get("rule_count", 0) and not t.get("has_fixtures"):
            comment = f"{t['rule_count']} rule(s) with no tested fixtures: not counted as covered"
        else:
            comment = f"{t.get('rule_count', 0)} rule(s), all disabled"
        techniques.append({"techniqueID": t["technique_id"], "score": t.get("enabled_rule_count", 0) if covered else 0,
                           "comment": comment, "enabled": True,
                           "metadata": [{"name": "tactics", "value": ", ".join(t.get("tactics", []))}]})
    top = max([t["score"] for t in techniques] + [1])
    summary = coverage.get("summary", {})
    return {
        "name": f"Logforge coverage: {tenant_name}",
        "versions": {"attack": "16", "navigator": "5.1.0", "layer": "4.5"},
        "domain": "enterprise-attack",
        "description": (f"Detection coverage exported {now:%Y-%m-%d %H:%M} UTC: "
                        f"{summary.get('covered_techniques', 0)} of {summary.get('total_techniques', 0)} techniques "
                        "covered by enabled, fixture-tested rules. Score = enabled rules."),
        "sorting": 3, "hideDisabled": False,
        "gradient": {"colors": ["#fde2e2", "#ffd166", "#06d6a0"], "minValue": 0, "maxValue": top},
        "legendItems": [{"label": "not covered", "color": "#fde2e2"}, {"label": "covered", "color": "#06d6a0"}],
        "techniques": techniques,
    }


# -- the report ---------------------------------------------------------------------------

def _median(stats: Optional[Dict[str, Any]]) -> Any:
    return (stats or {}).get("median")


def build(inputs: Dict[str, Any]) -> Dict[str, Any]:
    start, end = inputs["start"], inputs["end"]
    alerts = inputs.get("alerts_by_severity", {})
    cm = inputs.get("case_metrics", {})
    coverage = inputs.get("coverage", {}).get("summary", {})
    runs = inputs.get("playbook_runs", [])
    approvals = inputs.get("approvals", [])
    by_status: Dict[str, int] = {}
    for r in runs:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    breaches = cm.get("sla_breaches", {})
    case_rows = []
    for sev in SEVERITIES:
        s = (cm.get("by_severity") or {}).get(sev)
        if not s:
            continue
        case_rows.append([sev, s.get("cases", 0), s.get("open", 0), _median(s.get("mtta_minutes")),
                          _median(s.get("mttr_minutes")), (breaches.get("acknowledge") or {}).get(sev, 0),
                          (breaches.get("resolve") or {}).get(sev, 0)])
    sections = [
        {"title": "Summary", "kind": "kv", "rows": [
            ["Alerts", sum(alerts.values())],
            ["Cases", cm.get("cases", 0)],
            ["Open cases", cm.get("open_total", 0)],
            ["ATT&CK techniques covered", f"{coverage.get('covered_techniques', 0)} of "
                                          f"{coverage.get('total_techniques', 0)}"],
            ["Playbook runs", len(runs)],
        ]},
        {"title": "Alerts by severity", "kind": "table", "columns": ["Severity", "Alerts"],
         "rows": [[s, alerts.get(s, 0)] for s in SEVERITIES]},
        {"title": "Case response", "kind": "table",
         "columns": ["Severity", "Cases", "Open", "MTTA min", "MTTR min", "Ack SLA missed", "Resolve SLA missed"],
         "note": "MTTA, MTTR: median minutes to acknowledge and to resolve.", "rows": case_rows},
        {"title": "Detection coverage", "kind": "kv", "rows": [
            ["Techniques covered (enabled, fixture-tested rules)", coverage.get("covered_techniques", 0)],
            ["Techniques with rules", coverage.get("total_techniques", 0)],
            ["Rules awaiting tested fixtures", coverage.get("awaiting_content", 0)],
            ["Rules", coverage.get("total_rules", 0)],
        ]},
        {"title": "Retention", "kind": "table", "columns": ["Data", "Searchable days", "Archive days"],
         "rows": [[r["data_type"], r["searchable_days"], r["archive_days"] or "none"]
                  for r in inputs.get("retention", [])]},
        {"title": "Response automation", "kind": "kv", "rows": [
            *[[f"Runs {status.replace('_', ' ')}", n] for status, n in sorted(by_status.items())],
            ["Containment approvals given", sum(1 for a in approvals if a.get("approved"))],
            ["Containment approvals refused", sum(1 for a in approvals if not a.get("approved"))],
        ]},
    ]
    return {"title": "Security operations report", "tenant": inputs.get("tenant", ""),
            "period": {"start": f"{start:%Y-%m-%d}", "end": f"{end:%Y-%m-%d}", "days": (end - start).days},
            "generated_at": inputs.get("generated_at", end).isoformat(), "sections": sections}


def to_csv(report: Dict[str, Any]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([f"# {report['title']}: {report['tenant']}, {report['period']['start']} to {report['period']['end']}"])
    for section in report["sections"]:
        w.writerow([])
        w.writerow([f"# {section['title']}"])
        if section["kind"] == "table":
            w.writerow(section["columns"])
        for row in section["rows"]:
            w.writerow(["" if v is None else v for v in row])
    return out.getvalue()


# -- PDF -------------------------------------------------------------------------------------

def _lines(report: Dict[str, Any]) -> List[Tuple[str, str]]:
    """(style, text) lines: title, h (section heading), t (text), m (monospaced table row)."""
    p = report["period"]
    lines = [("title", report["title"]), ("t", f"{report['tenant']}  |  {p['start']} to {p['end']} ({p['days']} days)"),
             ("t", f"Generated {report['generated_at'][:16].replace('T', ' ')} UTC by Logforge"), ("t", "")]
    for section in report["sections"]:
        lines.append(("h", section["title"]))
        if section["kind"] == "kv":
            width = max(len(str(k)) for k, _ in section["rows"]) if section["rows"] else 0
            lines += [("m", f"{str(k).ljust(width)}  {'' if v is None else v}") for k, v in section["rows"]]
        else:
            cols = section["columns"]
            cells = [[("-" if v is None else str(v)) for v in row] for row in section["rows"]]
            widths = [min(28, max([len(c)] + [len(r[i]) for r in cells])) for i, c in enumerate(cols)]
            fmt = lambda row: "  ".join(str(v)[:widths[i]].ljust(widths[i]) for i, v in enumerate(row))  # noqa: E731
            lines += [("m", fmt(cols))] + [("m", fmt(r)) for r in cells]
            if not cells:
                lines.append(("t", "None in this period."))
            if section.get("note"):
                lines.append(("t", section["note"]))
        lines.append(("t", ""))
    return lines


def _escape(text: str) -> str:
    text = text.encode("latin-1", "replace").decode("latin-1")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def to_pdf(report: Dict[str, Any]) -> bytes:
    width, height, margin = 595, 842, 50  # A4 in points
    fonts = {"title": ("F2", 16, 22), "h": ("F2", 12, 18), "t": ("F1", 9, 13), "m": ("F3", 8, 11)}
    pages: List[List[str]] = [[]]
    y = height - margin
    for style, text in _lines(report):
        font, size, lead = fonts[style]
        chunks = [text[i:i + 110] for i in range(0, len(text), 110)] or [""]
        for chunk in chunks:
            if y - lead < margin:
                pages.append([])
                y = height - margin
            y -= lead
            pages[-1].append(f"BT /{font} {size} Tf {margin} {y} Td ({_escape(chunk)}) Tj ET")
    objects: List[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")  # filled in below
    pages_obj = add(b"")
    f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    f3 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    kids = []
    for n, page in enumerate(pages, start=1):
        footer = f"BT /F1 8 Tf {margin} 25 Td (Page {n} of {len(pages)}) Tj ET"
        stream = zlib.compress("\n".join(page + [footer]).encode("latin-1"))
        content = add(b"<< /Length %d /Filter /FlateDecode >>\r\nstream\r\n" % len(stream) + stream + b"\r\nendstream")
        kids.append(add(("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R "
                         "/Resources << /Font << /F1 %d 0 R /F2 %d 0 R /F3 %d 0 R >> >> >>"
                         % (pages_obj, width, height, content, f1, f2, f3)).encode()))
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj
    objects[pages_obj - 1] = ("<< /Type /Pages /Kids [%s] /Count %d >>"
                              % (" ".join(f"{k} 0 R" for k in kids), len(kids))).encode()
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, catalog, xref)
    return bytes(out)


# -- schedules -------------------------------------------------------------------------------

PERIODS = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "monthly": timedelta(days=31)}


def _slot(schedule: Dict[str, Any], now: datetime) -> Optional[datetime]:
    """The most recent send time at or before now."""
    hour = int(schedule.get("hour", 7))
    today = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    every = schedule.get("every", "weekly")
    if every == "daily":
        return today if today <= now else today - timedelta(days=1)
    if every == "weekly":
        slot = today - timedelta(days=today.weekday())  # Monday
        return slot if slot <= now else slot - timedelta(days=7)
    if every == "monthly":
        slot = today.replace(day=1)
        if slot > now:
            prev = (slot - timedelta(days=1)).replace(day=1)
            slot = prev
        return slot
    return None


FIRST_SEND_GRACE = timedelta(hours=6)


def due(schedule: Dict[str, Any], last_sent: Optional[datetime], now: datetime) -> bool:
    """Sent once per slot. A schedule never sent waits for its first slot (or
    sends within FIRST_SEND_GRACE of one), rather than at once for a period
    that ended before it existed."""
    slot = _slot(schedule, now)
    if slot is None:
        return False
    if last_sent is None:
        return now - slot <= FIRST_SEND_GRACE
    return last_sent < slot


def window(schedule: Dict[str, Any], now: datetime) -> Tuple[datetime, datetime]:
    every = schedule.get("every", "weekly")
    days = {"daily": 1, "weekly": 7, "monthly": 31}[every]
    return now - timedelta(days=days if every != "monthly" else 31), now


def period_of(start: datetime, end: datetime) -> Dict[str, Any]:
    return {"start": start.astimezone(timezone.utc), "end": end.astimezone(timezone.utc)}


__all__ = ["navigator_layer", "build", "to_csv", "to_pdf", "due", "window", "SEVERITIES", "Sequence"]
