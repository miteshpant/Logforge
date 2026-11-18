"""
Detection evaluation harness.

Measures what Logforge's shipped detection rules catch and how noisy they
are, using the same rule set and matching logic as the running platform:

* rules are built by the startup loader (`MitreDefaultLoader`): vendored
  SigmaHQ content plus `packages/rules/`, each already through the fixture
  gate;
* every scenario, and the benign corpus, is replayed as a timeline through
  `detection_replay.replay`, the runtime's own logic: single-event rules per
  event, `count()` rules as windowed counts, correlation rules on base-rule
  matches. Building blocks (`generate: false`) don't alert, so they aren't
  scored.

Corpus (this directory):

* `benign.py`: a deterministic generator of ordinary activity (logins,
  web requests, process starts, cron, DNS, ...). Any alert on it is a false
  positive.
* `scenarios/*.yml`: labelled attack scenarios, each listing the ATT&CK
  techniques it should be detected as, and its events in Logforge field
  names. Events are 1s apart unless timed with `at`/`every`/`repeat`
  (see detection_replay.expand_timeline).

Usage:

    python tests/eval/detection/eval_harness.py                 # print report
    python tests/eval/detection/eval_harness.py --update-baseline

CI runs tests/test_detection_eval_baseline.py, which fails on any regression
against `baseline.json` (see `compare`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASELINE = HERE / "baseline.json"
SCENARIO_DIR = HERE / "scenarios"


# ---------------------------------------------------------------------------
# Matching (delegates to the platform's own logic)
# ---------------------------------------------------------------------------

_loader = None


def _matcher():
    global _loader
    if _loader is None:
        if str(REPO / "apps" / "api") not in sys.path:
            sys.path.insert(0, str(REPO / "apps" / "api"))
        from mitre_default_loader import MitreDefaultLoader

        _loader = MitreDefaultLoader.__new__(MitreDefaultLoader)  # no database
        _loader._condition_evaluator = None
    return _loader


def _replay(rules: List[Dict[str, Any]], entries: List[Any]) -> List[Any]:
    _matcher()  # puts apps/api on sys.path
    from detection_replay import expand_timeline, replay

    return replay(rules, expand_timeline(entries))


def _alerting(rule: Dict[str, Any]) -> bool:
    return rule.get("generate") is not False


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(rules: List[Dict[str, Any]], scenarios: List[Dict[str, Any]],
             benign: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate `rules` ({id, techniques, detection, [correlation, name,
    generate]}) on the corpus.

    True positives: scenarios a rule alerts on (once per scenario).
    False positives: alerts a rule raises on the benign timeline.
    """
    scored = [r for r in rules if _alerting(r)]
    by_id = {r["id"]: r for r in scored}
    rule_stats = {r["id"]: {"true_positives": 0, "false_positives": 0} for r in scored}

    scenario_results: Dict[str, Any] = {}
    for scenario in scenarios:
        fired_ids = sorted({a.rule_id for a in _replay(rules, scenario["events"]) if a.rule_id in by_id})
        for rule_id in fired_ids:
            rule_stats[rule_id]["true_positives"] += 1
        expected = sorted(scenario["techniques"])
        detected_techniques = {t for rid in fired_ids for t in by_id[rid].get("techniques", [])}
        detected = [t for t in expected if _technique_covered(t, detected_techniques)]
        scenario_results[scenario["id"]] = {
            "expected": expected,
            "detected": detected,
            "missing": [t for t in expected if t not in detected],
            "rules": fired_ids,
        }

    false_positive_alerts = 0
    for alert in _replay(rules, benign):
        if alert.rule_id in rule_stats:
            rule_stats[alert.rule_id]["false_positives"] += 1
            false_positive_alerts += 1

    detected_count = sum(1 for s in scenario_results.values() if s["detected"])
    return {
        "summary": {
            "rules": len(scored),
            "benign_events": len(benign),
            "false_positive_alerts": false_positive_alerts,
            "false_positives_per_1000": round(1000 * false_positive_alerts / len(benign), 3) if benign else 0.0,
            "scenarios_total": len(scenarios),
            "scenarios_detected": detected_count,
        },
        "scenarios": scenario_results,
        "rules": rule_stats,
    }


def _technique_covered(expected: str, detected: Iterable[str]) -> bool:
    """A sub-technique rule (T1003.001) covers its parent (T1003) and vice versa
    for the purpose of "was this scenario detected as this technique"."""
    expected = expected.upper()
    for technique in detected:
        technique = technique.upper()
        if technique == expected or technique.split(".")[0] == expected or expected.split(".")[0] == technique:
            return True
    return False


# ---------------------------------------------------------------------------
# Regression gate
# ---------------------------------------------------------------------------

def compare(current: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    """Regressions of `current` against `baseline` (empty list = none).

    A regression is: a technique a scenario used to be detected as is no
    longer detected; a rule detects fewer scenarios than before (even if
    another rule still covers them) or has disappeared; or a rule fires on
    more benign events than before.
    New detections and fewer false positives are improvements, not failures.
    """
    problems: List[str] = []
    for scenario_id, before in baseline.get("scenarios", {}).items():
        now = current.get("scenarios", {}).get(scenario_id)
        for technique in before.get("detected", []):
            if not now or technique not in now.get("detected", []):
                problems.append(f"scenario {scenario_id} no longer detects {technique}")
    for rule_id, before in baseline.get("rules", {}).items():
        now = current.get("rules", {}).get(rule_id)
        if now is None:
            problems.append(f"rule {rule_id} is no longer in the rule set")
            continue
        # Redundant coverage must not hide a rule that silently broke.
        if now["true_positives"] < before["true_positives"]:
            problems.append(
                f"rule {rule_id} true positives fell from {before['true_positives']} to {now['true_positives']}")
        if now["false_positives"] > before["false_positives"]:
            problems.append(
                f"rule {rule_id} false positives rose from {before['false_positives']} to {now['false_positives']}")
    for rule_id, now in current.get("rules", {}).items():
        if rule_id not in baseline.get("rules", {}) and now["false_positives"] > 0:
            problems.append(f"new rule {rule_id} has {now['false_positives']} false positives")
    return problems


# ---------------------------------------------------------------------------
# Real corpus and rules
# ---------------------------------------------------------------------------

def shipped_rules() -> List[Dict[str, Any]]:
    """The default rule set, built exactly as the startup loader builds it."""
    loader = _matcher()
    rows, _ = loader._load_content_rules()
    packaged, _ = loader._load_packaged_rules()
    rules = []
    for row in rows + packaged:
        content = json.loads(row["rule_content"])
        rules.append({
            "id": row["id"],
            "techniques": list(row.get("mitre_techniques") or []),
            "detection": content.get("detection") or {},
            "correlation": content.get("correlation"),
            "name": content.get("name"),
            "generate": content.get("generate", True),
            "tags": content.get("tags", []),
            "severity": row.get("severity"),
            "title": row.get("name"),
        })
    return rules


def grouping_report(rules: Optional[List[Dict[str, Any]]] = None,
                    scenarios: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Route the alerts of all scenarios, replayed in one shared timeline
    (each scenario starts 2 minutes after the previous), through the
    production case grouping, and count items needing triage."""
    _matcher()
    from datetime import timedelta

    from case_grouping import GroupingPolicy, group_key, plan
    from cases import apply_action, new_case
    from detection_replay import TIMELINE_START, expand_timeline, replay
    from services.case_service import alert_summary

    rules = rules if rules is not None else shipped_rules()
    scenarios = scenarios if scenarios is not None else load_scenarios()
    events = []
    for i, scenario in enumerate(scenarios):
        for event in expand_timeline(scenario["events"], start=TIMELINE_START + timedelta(minutes=2 * i)):
            event["_scenario"] = scenario["id"]
            events.append(event)
    by_id = {r["id"]: r for r in rules}
    policy = GroupingPolicy()
    cases: List[Any] = []
    members: Dict[str, set] = {}
    uncased = 0
    alerts = replay(rules, events)
    for n, alert in enumerate(alerts):
        rule = by_id.get(alert.rule_id, {})
        summary = alert_summary({"id": f"alert-{n}", "rule_id": alert.rule_id, "title": rule.get("title"),
                                 "severity": rule.get("severity"), "raw_log_data": {"normalized_log": alert.event}})
        key = group_key(summary, alert.group or None)
        candidates = [c for c in cases if key and c.group_key == key and c.is_open]
        existing = max(candidates, key=lambda c: c.last_alert_at) if candidates else None
        decision = plan(summary, existing, alert.ts, policy)
        if decision == "skip":
            uncased += 1
            continue
        if decision == "attach":
            index = cases.index(existing)
            cases[index], _ = apply_action(existing, "attach_alert", "system", alert.ts, alert=summary)
            case = cases[index]
        else:
            case, _ = new_case("eval", summary.get("title") or "alert", "system", alert.ts, alerts=[summary],
                               group_key=key)
            cases.append(case)
        members.setdefault(case.id, set()).add(alert.event.get("_scenario"))

    per_scenario: Dict[str, int] = {}
    for case_id, owners in members.items():
        for owner in owners:
            per_scenario[owner] = per_scenario.get(owner, 0) + 1
    total = len(alerts)
    items = len(cases) + uncased
    return {
        "alerts": total,
        "cases": len(cases),
        "uncased_low_alerts": uncased,
        "items_needing_triage": items,
        "reduction": round(1 - len(cases) / total, 3) if total else 0.0,
        "alerts_per_case": round((total - uncased) / len(cases), 2) if cases else 0.0,
        "cases_per_scenario": dict(sorted(per_scenario.items())),
        "mixed_cases": sum(1 for owners in members.values() if len(owners) > 1),
    }


def load_scenarios(directory: Path = SCENARIO_DIR) -> List[Dict[str, Any]]:
    import yaml

    scenarios = []
    for path in sorted(directory.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data.setdefault("id", path.stem)
        scenarios.append(data)
    return scenarios


def run(update_baseline: bool = False) -> Dict[str, Any]:
    from benign import benign_events

    report = evaluate(shipped_rules(), load_scenarios(), benign_events())
    if update_baseline:
        BASELINE.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def load_baseline() -> Optional[Dict[str, Any]]:
    return json.loads(BASELINE.read_text()) if BASELINE.exists() else None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--update-baseline", action="store_true",
                        help="write the current results to baseline.json")
    args = parser.parse_args(argv)

    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    report = run(update_baseline=args.update_baseline)
    s = report["summary"]
    print(f"rules: {s['rules']}  benign events: {s['benign_events']}  "
          f"false-positive alerts: {s['false_positive_alerts']} ({s['false_positives_per_1000']}/1000)")
    print(f"scenarios detected: {s['scenarios_detected']}/{s['scenarios_total']}")
    for sid, res in report["scenarios"].items():
        mark = "OK " if not res["missing"] else ("PART" if res["detected"] else "MISS")
        print(f"  [{mark}] {sid}: detected {res['detected'] or '-'} missing {res['missing'] or '-'}")
    noisy = sorted(((r, v["false_positives"]) for r, v in report["rules"].items() if v["false_positives"]),
                   key=lambda x: -x[1])
    if noisy:
        print("noisy rules:")
        for rule_id, fp in noisy[:20]:
            print(f"  {fp:5d}  {rule_id}")
    baseline = load_baseline()
    if baseline and not args.update_baseline:
        problems = compare(report, baseline)
        print("regressions:" if problems else "no regressions against baseline.json")
        for p in problems:
            print("  " + p)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
