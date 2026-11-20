"""
Scoring detection drafting (Phase 10) on datasets/rule_behaviours.jsonl.

For each behaviour the drafter gets the description, the technique, the
attack samples and one known-good sample. Scored:

* passed: the draft passes (fixture gate, fires on the samples, quiet on the
  known-good one) on the first or second attempt. Target >= 70%.
* first: it passes on the first attempt.
* held-out recall: of the drafts that passed, held-out attack events fired on.
* held-out quiet: of the drafts that passed, held-out benign events not fired on.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
DATASET = HERE / "datasets" / "rule_behaviours.jsonl"


def load() -> list[dict[str, Any]]:
    return [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]


def score(items: list[dict[str, Any]], drafter: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    from ai.rule_draft import check

    per, fires, of, quiet, of_benign = [], 0, 0, 0, 0
    for item in items:
        out = drafter(item)
        # a heuristic fallback after two failed model attempts is a third attempt: not counted
        within_two = out.passed and "model_draft_failed" not in out.flags and len(out.attempts) <= 2
        held = check(out.rule, item["held_out_attack"], item["held_out_benign"]) if out.passed else None
        if held:
            fires, of = fires + held["fires"], of + held["of"]
            quiet, of_benign = quiet + held["quiet"], of_benign + held["of_benign"]
        per.append({"id": item["id"], "passed": bool(within_two), "first": bool(out.passed and out.attempts[0]["passed"]),
                    "attempts": out.attempts, "held_out": held, "mode": out.mode})
    n = len(per)
    return {"behaviours": n, "passed": round(sum(p["passed"] for p in per) / n, 4),
            "first": round(sum(p["first"] for p in per) / n, 4),
            "held_out_recall": round(fires / of, 4) if of else 0.0,
            "held_out_quiet": round(quiet / of_benign, 4) if of_benign else 0.0, "per_behaviour": per}


def heuristic_drafter(item):
    from ai.rule_draft import heuristic

    return heuristic(item["description"], item["attack"], technique=item["technique"], known_good=item["known_good"])


def model_drafter(provider):
    from ai.redaction import Redactor
    from ai.rule_draft import draft

    return lambda item: asyncio.run(draft(item["description"], item["attack"], provider, redactor=Redactor([]),
                                          technique=item["technique"], known_good=item["known_good"]))
