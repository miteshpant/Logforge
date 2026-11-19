"""
Pack CI (Phase 7): run a pack's samples through its pipelines and rules.

The loader (source_packs.load_pack) already gates the rules and compiles
every query. This adds what only data can show: that the source's lines are
routed to the pack's pipeline, parse into the fields the pack promises, and
make the pack's rules fire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from pipeline_conditions import get_path
from pipeline_processors import ProcessorContext
from pipeline_store import PipelineRouter

SAMPLE_HOST = "pack-sample"


@dataclass
class Report:
    pack: str
    failures: List[str] = field(default_factory=list)
    events: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)  # sample file -> parsed events
    checked: Dict[str, int] = field(default_factory=lambda: {"samples": 0, "events": 0, "expectations": 0,
                                                             "rules": 0})

    @property
    def ok(self) -> bool:
        return not self.failures


def sample_event(line: str, service: str, now: datetime) -> Dict[str, Any]:
    """A raw line as a shipper delivers it."""
    return {"ts": now.isoformat(), "msg": line, "service": service, "host": SAMPLE_HOST, "level": "info",
            "attrs": {}}


def _matches(event: Dict[str, Any], expected: Dict[str, Any]) -> bool:
    for path, want in (expected.get("fields") or {}).items():
        got = get_path(event, path)
        if got != want and str(got) != str(want):
            return False
    text = expected.get("contains")
    return not text or text in str(event.get("msg", ""))


def _rule_matcher():
    from mitre_default_loader import MitreDefaultLoader

    loader = MitreDefaultLoader.__new__(MitreDefaultLoader)
    loader._condition_evaluator = None
    return loader._rule_matches


def check_pack(pack, now: datetime = None) -> Report:
    now = now or datetime.now(timezone.utc)
    report = Report(pack=pack.id)
    router = PipelineRouter(pack.pipelines)
    ctx = ProcessorContext(tenant_id="pack-check", now=now,
                           tables={name: t["rows"] for name, t in pack.lookups.items()})
    rules = {r["id"]: r for r in pack.rules}
    matches = _rule_matcher()

    for sample in pack.samples:
        report.checked["samples"] += 1
        parsed: List[Dict[str, Any]] = []
        for number, line in enumerate(sample.lines, start=1):
            doc = sample_event(line, sample.service, now)
            record = router.select(doc)
            where = f"{sample.file}:{number}"
            if record is None:
                report.failures.append(f"{where}: routed to no pipeline (service {sample.service})")
                continue
            if sample.pipeline and record.id != sample.pipeline:
                report.failures.append(f"{where}: routed to {record.id}, expected {sample.pipeline}")
            result = record.pipeline.run(doc, ctx)
            if result.status == "failed":
                report.failures.append(f"{where}: pipeline {record.id} failed: {result.error}")
                continue
            if result.status == "dropped":
                continue
            parsed.append(result.doc)
        report.events[sample.file] = parsed
        report.checked["events"] += len(parsed)

        for expected in sample.expect:
            report.checked["expectations"] += 1
            want = int(expected.get("min", 1))
            found = sum(1 for event in parsed if _matches(event, expected))
            if found < want:
                label = f"containing {expected['contains']!r}" if expected.get("contains") else ""
                report.failures.append(f"{sample.file}: {found} of {want} expected events {label} have "
                                       f"{expected.get('fields') or {}}".replace("  ", " "))

        for rule_id in sample.rules:
            report.checked["rules"] += 1
            rule = rules.get(rule_id)
            if rule is None:
                report.failures.append(f"{sample.file}: {rule_id} is not a rule of this pack")
                continue
            detection = rule.get("detection") or {}
            if rule.get("correlation") is not None or "count(" in str(detection.get("condition", "")):
                report.failures.append(f"{sample.file}: {rule_id} aggregates; list its base rule instead")
                continue
            if not any(matches(detection, event) for event in parsed):
                report.failures.append(f"{sample.file}: {rule_id} matched none of its {len(parsed)} events")
    return report
