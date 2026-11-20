"""
Detection drafting on the evaluation behaviours (Phase 10): at least the
recorded share of drafts must pass the gate within two attempts (the
roadmap's target is >= 70%), and held-out recall and quiet may not fall.
The heuristic drafter (AI off) runs on every change; a model runs from
recordings when they exist.
"""

import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent / "eval" / "ai"
sys.path.insert(0, str(EVAL))

import rule_draft_eval as rde  # noqa: E402

BASELINE = json.loads((EVAL / "baseline_rule_draft.json").read_text())
RECORDING = EVAL / "recordings" / "rule_draft.jsonl"


def test_the_behaviours():
    items = rde.load()
    assert len(items) >= 20 and len({i["technique"] for i in items}) >= 15
    assert all(i["held_out_attack"] and i["held_out_benign"] for i in items)


def test_the_heuristic_drafter():
    result = rde.score(rde.load(), rde.heuristic_drafter)
    floor = BASELINE["heuristic"]
    assert result["passed"] >= max(0.7, floor["passed"]), result["per_behaviour"]
    for key in ("first", "held_out_recall", "held_out_quiet"):
        assert result[key] >= floor[key], (key, result[key])


@pytest.mark.skipif(not RECORDING.exists(), reason="no recorded model answers (see tests/eval/ai/README.md)")
def test_the_recorded_model():
    from ai.providers.recorded import RecordedProvider

    result = rde.score(rde.load(), rde.model_drafter(RecordedProvider(RECORDING)))
    floor = BASELINE.get("model") or {}
    if floor:
        assert result["passed"] >= floor["passed"]
