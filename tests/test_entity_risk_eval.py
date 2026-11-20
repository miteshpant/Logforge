"""
Entity risk on the evaluation scenarios (Phase 11): in every scenario, the
compromised entities rank in the top 5 by risk at the scenario's end
(tests/eval/ueba). 9,000+ alerts per run of noise: daily churn, recurring
admin activity, an internal scanner, failed-login bursts, weak intel hits.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "eval" / "ueba"))

import risk_eval  # noqa: E402


def test_compromised_entities_rank_in_the_top_5():
    result = risk_eval.score(risk_eval.load())
    assert result["scenarios"] == 10
    assert result["all_in_top"] == 1.0, [p for p in result["per_scenario"] if not p["passed"]]
