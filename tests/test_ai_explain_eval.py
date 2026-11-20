"""
"Explain this event" on the content packs' sample events (Phase 9): no
uncited sentence; events identified and expected rules named may not fall
below the recorded floors (baseline_explain.json). The template (AI off)
runs on every change; a model runs from recordings when they exist.
"""

import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent / "eval" / "ai"
sys.path.insert(0, str(EVAL))

import explain_eval as ee  # noqa: E402

BASELINE = json.loads((EVAL / "baseline_explain.json").read_text())
RECORDING = EVAL / "recordings" / "explain.jsonl"


@pytest.fixture(scope="module")
def items():
    return ee.load()


def test_the_set(items):
    assert sum(len(i["events"]) for i in items) >= 80 and sum(len(i["rules"]) for i in items) >= 25


def test_the_template_explanations(items):
    result = ee.score(items, ee.template_explainer)
    assert result["uncited"] == 0
    assert result["identified"] >= BASELINE["template"]["identified"]
    assert result["rule_recall"] >= BASELINE["template"]["rule_recall"], result["per_item"]


@pytest.mark.skipif(not RECORDING.exists(), reason="no recorded model answers (see tests/eval/ai/README.md)")
def test_the_recorded_model_explanations(items):
    from ai.providers.recorded import RecordedProvider

    result = ee.score(items, ee.model_explainer(RecordedProvider(RECORDING)))
    assert result["uncited"] == 0
