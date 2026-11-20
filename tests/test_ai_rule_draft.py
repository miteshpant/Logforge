"""
Detection drafting gated by tests (Phase 10): "AI drafts, the gate verifies".

A draft is a Sigma rule with its fixtures. It passes only when:
* the Phase 1 fixture gate accepts it (its true positive fires, its true
  negative and the benign corpus don't, it has an ATT&CK technique);
* it fires on every attack sample the analyst gave;
* it stays quiet on the known-good sample.
Two attempts at most: the second is told why the first failed.

* heuristic(): without AI, from the attack samples: fields whose values the
  samples share, and for text fields (command line, URL, message, query) the
  tokens every sample has and the known-good one doesn't.
* draft(): the model writes the YAML; the same checks apply.
* Enabling (the API) runs the gate and a backtest again; a draft that
  hasn't passed can't be enabled.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest
import yaml
from ai.providers import ChatResult, Usage
from ai.redaction import Redactor
from ai.rule_draft import check, draft, heuristic

sys.path.insert(0, str(Path(__file__).resolve().parent / "eval" / "ai"))

ITEMS = {json.loads(line)["id"]: json.loads(line) for line in
         (Path(__file__).resolve().parent / "eval" / "ai" / "datasets" / "rule_behaviours.jsonl").read_text().splitlines()}


def run(coro):
    return asyncio.run(coro)


def drafted(bid):
    item = ITEMS[bid]
    return item, heuristic(item["description"], item["attack"], technique=item["technique"],
                           known_good=item["known_good"])


def test_a_heuristic_draft_passes_the_gate_and_reads_like_a_rule():
    item, out = drafted("shadow-delete")
    assert out.passed and out.mode == "heuristic" and out.attempts[0]["passed"]
    rule = yaml.safe_load(out.yaml)
    assert rule["id"].startswith("ai_") and rule["status"] == "experimental"
    assert "attack.t1490" in rule["tags"] and "attack.impact" in rule["tags"]
    selection = rule["detection"]["selection"]
    assert selection["command_line|contains|all"] and "vssadmin" not in [t.lower() for t in
                                                                        selection["command_line|contains|all"]]
    assert rule["fixtures"]["true_positive"] == item["attack"][0]
    # it generalises to the held-out attack and stays quiet on the held-out benign events
    assert check(rule, item["held_out_attack"], item["held_out_benign"]) == {"fires": 1, "of": 1, "quiet": 2,
                                                                             "of_benign": 2}


@pytest.mark.parametrize("bid", ["kerberoast", "dyndns-query", "webshell-request", "sqli-union"])
def test_fields_suffixes_and_url_tokens(bid):
    item, out = drafted(bid)
    assert out.passed, out.attempts
    rule = yaml.safe_load(out.yaml)
    result = check(rule, item["held_out_attack"], item["held_out_benign"])
    assert result["quiet"] == result["of_benign"], (bid, rule["detection"])


def test_without_a_technique_the_draft_cannot_pass():
    item = ITEMS["shadow-delete"]
    out = heuristic("Something odd", item["attack"], known_good=item["known_good"])
    assert not out.passed and "technique" in out.attempts[-1]["reason"]


def test_a_draft_that_matches_the_known_good_event_fails():
    item = ITEMS["whoami-priv"]
    out = heuristic(item["description"], item["attack"], technique=item["technique"], known_good=item["attack"][0])
    assert not out.passed and len(out.attempts) == 2


def test_raw_lines_are_drafted_against_the_message():
    out = heuristic("SSH login as root", ["Accepted password for root from 203.0.113.9 port 4022 ssh2",
                                          "Accepted publickey for root from 198.51.100.4 port 51515 ssh2"],
                    technique="T1078", known_good="Accepted password for deploy from 10.0.1.2 port 2 ssh2")
    rule = yaml.safe_load(out.yaml)
    assert out.passed, out.attempts
    assert "for root" in " ".join(rule["detection"]["selection"]["message|contains|all"]).lower() or \
        "root" in [t.lower() for t in rule["detection"]["selection"]["message|contains|all"]]


class Scripted:
    name, model, external = "s", "s-1", False

    def __init__(self, *texts):
        self.texts, self.sent = list(texts), []

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        self.sent.append(messages)
        return ChatResult(text=self.texts.pop(0), tool_calls=[], stop_reason="end", usage=Usage(10, 5), model="s-1")


def _rule(selection, positive, negative):
    return yaml.safe_dump({"title": "Shadow copies deleted", "id": "shadows", "level": "high",
                           "tags": ["attack.impact", "attack.t1490"],
                           "detection": {"selection": selection, "condition": "selection"},
                           "fixtures": {"true_positive": positive, "true_negative": negative}})


def test_the_model_gets_a_second_attempt_with_the_reason():
    item = ITEMS["shadow-delete"]
    # first answer: a rule that fires on its own made-up fixture but not on the analyst's samples
    wrong = _rule({"Image|endswith": "\\vssadmin.exe"}, {"Image": "C:\\Windows\\vssadmin.exe"}, {"Image": "x.exe"})
    right = _rule({"command_line|contains|all": ["delete", "shadows"]}, item["attack"][0], item["known_good"])
    provider = Scripted(f"```yaml\n{wrong}```", f"```yaml\n{right}```")
    out = run(draft(item["description"], item["attack"], provider, redactor=Redactor([]),
                    technique=item["technique"], known_good=item["known_good"]))
    assert out.passed and out.mode == "ai" and [a["passed"] for a in out.attempts] == [False, True]
    assert "attack sample" in out.attempts[0]["reason"]
    assert "attack sample" in provider.sent[1][-1].content
    assert yaml.safe_load(out.yaml)["id"].startswith("ai_")


def test_two_failed_model_attempts_fall_back_to_the_heuristic_draft():
    item = ITEMS["shadow-delete"]
    provider = Scripted("not yaml: [", "still not a rule")
    out = run(draft(item["description"], item["attack"], provider, redactor=Redactor([]),
                    technique=item["technique"], known_good=item["known_good"]))
    assert out.mode == "heuristic" and out.passed and "model_draft_failed" in out.flags
    assert [a["by"] for a in out.attempts] == ["model", "model", "heuristic"]


def test_samples_are_redacted_before_they_are_sent():
    item = ITEMS["shadow-delete"]
    provider = Scripted("x", "y")
    secret = dict(item["attack"][0], command_line=item["attack"][0]["command_line"] + " password=hunter2")
    run(draft(item["description"], [secret], provider, redactor=Redactor([]), technique=item["technique"]))
    assert "hunter2" not in provider.sent[0][-1].content
