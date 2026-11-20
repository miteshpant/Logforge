"""
AI evaluation gate (Phase 8): each AI feature runs against its dataset in CI
from recorded model responses (tests/eval/ai/recordings), and must keep the
score in tests/eval/ai/baseline.json. A feature with no baseline yet is
reported as skipped, so a missing recording is visible, never green.

Record with: python tests/eval/ai/run_ai_eval.py --record --provider <name>
             python tests/eval/ai/run_ai_eval.py --update-baseline
"""

import json

import ai_eval
import pytest
import run_ai_eval
from ai.providers import ChatResult, ProviderError, Usage
from ai.providers.recorded import RecordedProvider

BASELINE = run_ai_eval.load_baseline()


@pytest.mark.parametrize("feature", sorted(run_ai_eval.FEATURES))
def test_recorded_features_keep_their_baseline(feature):
    if feature not in BASELINE:
        pytest.skip(f"{feature}: not gated yet; no recorded baseline (see tests/eval/ai/README.md)")
    path = run_ai_eval.RECORDINGS / f"{feature}.jsonl"
    assert path.exists(), f"{feature} has a baseline but no recording at {path}"
    result = run_ai_eval.score(feature, RecordedProvider(path))
    assert result["score"] >= BASELINE[feature]["min_score"], (
        f"{feature} scored {result['score']} < baseline {BASELINE[feature]['min_score']}: {result['per_item']}")


class Scripted:
    """Answers each question with the dataset's reference answer: a stand-in
    for a model, to check the wiring (it is not a model and proves nothing
    about one)."""

    name, kind, model, external = "scripted", "scripted", "scripted-1", False

    def __init__(self, answers, as_json=False):
        self.answers, self.as_json = answers, as_json

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        question = messages[-1].content
        text = next(answer for key, answer in self.answers.items() if key in question)
        if self.as_json:  # nl2query answers {query, explanation}
            text = json.dumps({"query": text, "explanation": "reference"})
        return ChatResult(text=text, tool_calls=[], stop_reason="end", usage=Usage(1, 1), model=self.model)


@pytest.mark.parametrize("feature, field, key", [("nl2query", "expected_query", "question"),
                                                  ("summaries", "reference_summary", "task")])
def test_recording_and_replay_wiring(tmp_path, feature, field, key):
    items = ai_eval.load_dataset(run_ai_eval.FEATURES[feature][0])
    if feature == "summaries":  # the task text repeats; key on the evidence instead
        answers = {next(iter(item["evidence"].values())): item[field] for item in items}
    else:
        answers = {item[key]: item[field] for item in items}
    path = tmp_path / f"{feature}.jsonl"
    recorded = run_ai_eval.score(feature, RecordedProvider(path, inner=Scripted(answers, as_json=feature == "nl2query"), record=True))
    replayed = run_ai_eval.score(feature, RecordedProvider(path))
    assert recorded["score"] == replayed["score"] == 1.0
    assert len(path.read_text().splitlines()) == len(items)

    # a dataset item with no recording fails instead of scoring zero quietly
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[1:]) + "\n")
    with pytest.raises(ProviderError, match="no recording"):
        run_ai_eval.score(feature, RecordedProvider(path))


def test_baseline_file_is_well_formed():
    for feature, entry in BASELINE.items():
        assert feature in run_ai_eval.FEATURES
        assert 0 <= entry["min_score"] <= 1 and entry["model"]
    json.dumps(BASELINE)
