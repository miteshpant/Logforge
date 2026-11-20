"""
Pipeline drafts on held-out formats (Phase 9): the content packs' sample
files, drafted without their pipelines (tests/eval/ai/pipeline_draft_eval.py).
Parse rate and value recall may not fall below the recorded floors
(baseline_pipeline_draft.json). The heuristic drafter (AI off) runs on every
change; a model runs from recordings when they exist.
"""

import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent / "eval" / "ai"
sys.path.insert(0, str(EVAL))

import pipeline_draft_eval as pe  # noqa: E402

BASELINE = json.loads((EVAL / "baseline_pipeline_draft.json").read_text())
RECORDING = EVAL / "recordings" / "pipeline_draft.jsonl"


def test_the_held_out_formats():
    items = pe.load()
    assert len(items) >= 12 and sum(len(i["lines"]) for i in items) >= 80
    assert sum(len(pe.recoverable(i)) for i in items) >= 50


def test_the_heuristic_drafter_meets_its_floor():
    result = pe.score(pe.load(), pe.heuristic_drafter)
    floor = BASELINE["heuristic"]
    assert result["parse_rate"] >= floor["parse_rate"], result["per_item"]
    assert result["value_recall"] >= floor["value_recall"], result["per_item"]


@pytest.mark.skipif(not RECORDING.exists(), reason="no recorded model answers (see tests/eval/ai/README.md)")
def test_the_recorded_model_meets_its_floor():
    from ai.providers.recorded import RecordedProvider

    result = pe.score(pe.load(), pe.model_drafter(RecordedProvider(RECORDING)))
    floor = BASELINE.get("model") or {}
    if floor:
        assert result["parse_rate"] >= floor["parse_rate"] and result["value_recall"] >= floor["value_recall"]
