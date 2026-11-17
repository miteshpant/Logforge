"""
AI evaluation harness.

Every AI feature must reach its target on these evaluations before it ships
(docs/PLATFORM_ROADMAP.md, Phases 8-10). The harness is provider-agnostic: a
"system" is any callable `item -> output`, so a model-backed feature, the
existing rule-based fallback, or a reference answer can all be scored the
same way.

Tasks and scoring:

* `nl2query`: natural-language question -> LogforgeQL. An item scores 1 if
  the generated query compiles to the same request as the reference (filters,
  aggregations and grouping compared order-insensitively), else 0. Execution
  accuracy against live data is the next step (it needs a seeded stack).
* `summaries`: alert/incident evidence -> summary that cites evidence ids as
  `[E1]`. An item scores its required-fact coverage (0-1), but **0 if any
  sentence is uncited or cites evidence that doesn't exist**: an unsupported
  claim is the failure that matters most in a security product.
* `rule_drafting`: behaviour description -> Sigma rule YAML with fixtures.
  An item scores 1 if the draft passes the platform's fixture gate, detects
  the item's attack events, and raises nothing on the benign corpus.

Datasets live in `datasets/<task>.jsonl`, one item per line.

    python tests/eval/ai/ai_eval.py            # score the reference answers
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATASETS = HERE / "datasets"
TASKS = ["nl2query", "summaries", "rule_drafting"]

for extra in (REPO / "apps" / "api", REPO / "tests" / "eval" / "detection"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


# ---------------------------------------------------------------------------
# nl2query
# ---------------------------------------------------------------------------

def _normalised_request(query: str) -> Optional[Dict[str, Any]]:
    import logql

    try:
        payload = logql.compile_to_request_payload(query)
    except Exception:  # noqa: BLE001 - any compile failure means "not a valid query"
        return None
    payload = dict(payload)
    # `last 15m` compiles to absolute start/end times taken from "now"; compare
    # the window's length, not the instant it was compiled at.
    if "start_time" in payload and "end_time" in payload:
        from datetime import datetime

        start = datetime.fromisoformat(payload.pop("start_time"))
        end = datetime.fromisoformat(payload.pop("end_time"))
        payload["window_seconds"] = round((end - start).total_seconds())
    payload["filters"] = sorted(json.dumps(f, sort_keys=True) for f in payload.get("filters", []))
    if "aggregations" in payload:
        payload["aggregations"] = sorted(json.dumps(a, sort_keys=True) for a in payload["aggregations"])
    if "group_by" in payload:
        payload["group_by"] = sorted(payload["group_by"])
    return payload


def score_nl2query(item: Dict[str, Any], generated: Optional[str]) -> float:
    if not generated:
        return 0.0
    expected = _normalised_request(item["expected_query"])
    actual = _normalised_request(generated)
    return 1.0 if actual is not None and actual == expected else 0.0


# ---------------------------------------------------------------------------
# summaries
# ---------------------------------------------------------------------------

_CITATION = re.compile(r"\[(E\d+)\]")


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def score_summary(item: Dict[str, Any], summary: Optional[str]) -> Dict[str, Any]:
    text = summary or ""
    sentences = _sentences(text)
    evidence = set(item["evidence"])
    uncited = sum(1 for s in sentences if not _CITATION.search(s))
    invalid = sum(1 for ref in _CITATION.findall(text) if ref not in evidence)
    facts = item.get("required_facts", [])
    covered = sum(1 for f in facts if f.lower() in text.lower())
    return {
        "facts_covered": round(covered / len(facts), 3) if facts else 1.0,
        "sentences": len(sentences),
        "uncited_sentences": uncited,
        "invalid_citations": invalid,
    }


def _summary_item_score(item: Dict[str, Any], summary: Optional[str]) -> float:
    if not summary:
        return 0.0
    s = score_summary(item, summary)
    if s["uncited_sentences"] or s["invalid_citations"]:
        return 0.0
    return s["facts_covered"]


# ---------------------------------------------------------------------------
# rule drafting
# ---------------------------------------------------------------------------

def score_rule_draft(item: Dict[str, Any], draft: Optional[str]) -> Dict[str, Any]:
    import yaml

    result = {"passes_gate": False, "gate_reason": None, "detects_attack": False, "benign_hits": None}
    try:
        rule = yaml.safe_load(draft) if draft else None
    except yaml.YAMLError:
        rule = None
    if not isinstance(rule, dict):
        result["gate_reason"] = "not a YAML mapping"
        return result

    import eval_harness
    from benign import benign_events

    loader = eval_harness._matcher()
    row, reason = loader._packaged_rule_to_row(rule, f"draft:{item['id']}")
    result["gate_reason"] = reason
    if row is None:
        return result
    result["passes_gate"] = True

    candidate = {"id": row["id"], "techniques": row["mitre_techniques"],
                 "detection": json.loads(row["rule_content"])["detection"]}
    if eval_harness._is_count_rule(candidate):
        result["detects_attack"] = eval_harness._count_fires(candidate, item["attack_events"])
        result["benign_hits"] = 1 if eval_harness._count_fires(candidate, benign_events()) else 0
    else:
        result["detects_attack"] = any(eval_harness._single_matches(candidate, e) for e in item["attack_events"])
        result["benign_hits"] = sum(1 for e in benign_events() if eval_harness._single_matches(candidate, e))
    return result


def _rule_item_score(item: Dict[str, Any], draft: Optional[str]) -> float:
    s = score_rule_draft(item, draft)
    return 1.0 if s["passes_gate"] and s["detects_attack"] and s["benign_hits"] == 0 else 0.0


# ---------------------------------------------------------------------------
# Datasets, systems, runner
# ---------------------------------------------------------------------------

_ITEM_SCORERS: Dict[str, Callable[[Dict[str, Any], Any], float]] = {
    "nl2query": score_nl2query,
    "summaries": _summary_item_score,
    "rule_drafting": _rule_item_score,
}
_REFERENCE_FIELD = {"nl2query": "expected_query", "summaries": "reference_summary",
                    "rule_drafting": "reference_rule"}


def load_dataset(task: str) -> List[Dict[str, Any]]:
    path = DATASETS / f"{task}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def reference_system(task: str) -> Callable[[Dict[str, Any]], Any]:
    """The dataset's own reference answers, used to check the scorers."""
    field = _REFERENCE_FIELD[task]
    return lambda item: item[field]


def evaluate(task: str, system: Callable[[Dict[str, Any]], Any],
             items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    items = items if items is not None else load_dataset(task)
    scorer = _ITEM_SCORERS[task]
    per_item = {item["id"]: scorer(item, system(item)) for item in items}
    return {
        "task": task,
        "items": len(items),
        "score": round(sum(per_item.values()) / len(items), 3) if items else 0.0,
        "per_item": per_item,
    }


def main() -> int:
    for task in TASKS:
        result = evaluate(task, reference_system(task))
        print(f"{task:15s} reference score {result['score']:.3f} over {result['items']} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
