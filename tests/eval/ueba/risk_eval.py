"""
Scoring entity risk (Phase 11) on risk_scenarios.jsonl: at each scenario's
end, rank every entity by risk; the scenario passes when all its compromised
entities (attacker address, taken-over user, host) are in the top 5.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def load() -> list[dict[str, Any]]:
    return [json.loads(line) for line in (HERE / "risk_scenarios.jsonl").read_text().splitlines() if line.strip()]


def score(scenarios: list[dict[str, Any]], top: int = 5) -> dict[str, Any]:
    from entity_risk import rank

    per, passed, hits, total = [], 0, 0, 0
    for s in scenarios:
        ranked = rank(s["alerts"], datetime.fromisoformat(s["end"]), limit=10_000)
        position = {(r.entity_type, r.value): i + 1 for i, r in enumerate(ranked)}
        ranks = [position.get(tuple(c)) for c in s["compromised"]]
        inside = [r is not None and r <= top for r in ranks]
        passed += all(inside)
        hits += sum(inside)
        total += len(inside)
        per.append({"id": s["id"], "ranks": ranks, "chain": s["chain"], "passed": all(inside),
                    "top": [(r.entity_type, r.value, r.score) for r in ranked[:top]]})
    return {"scenarios": len(per), "all_in_top": round(passed / len(per), 4), "recall_at_top": round(hits / total, 4),
            "per_scenario": per}
