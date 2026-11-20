"""
Triage summaries against datasets/triage.jsonl (Phase 9): no summary may
contain an uncited sentence, and fact coverage may not fall below the
recorded floor (baseline_triage.json). The template (AI off) runs on every
change; a model runs from recordings when they exist.
"""

import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent / "eval" / "ai"
sys.path.insert(0, str(EVAL))

import triage_eval as te  # noqa: E402

BASELINE = json.loads((EVAL / "baseline_triage.json").read_text())
RECORDING = EVAL / "recordings" / "triage.jsonl"


def test_the_dataset_covers_alerts_and_cases():
    items = te.load()
    assert len(items) >= 20
    assert {i["kind"] for i in items} == {"alert", "case"}
    assert all(i["required_facts"] for i in items)


def test_the_template_cites_every_sentence_and_states_the_facts():
    result = te.score(te.load(), te.template_writer)
    assert result["uncited"] == 0 and result["dropped"] == 0, result["per_item"]
    assert result["fact_coverage"] >= BASELINE["template"]["fact_coverage"], \
        [i for i in result["per_item"] if i["missing_facts"]]


@pytest.mark.skipif(not RECORDING.exists(), reason="no recorded model answers (see tests/eval/ai/README.md)")
def test_the_recorded_model_has_no_uncited_claims():
    from ai.providers.recorded import RecordedProvider

    result = te.score(te.load(), te.model_writer(RecordedProvider(RECORDING)))
    assert result["uncited"] == 0
    floor = BASELINE.get("model") or {}
    if floor:
        assert result["fact_coverage"] >= floor["fact_coverage"]
        assert result["raw_uncited_rate"] <= floor["raw_uncited_rate"]
