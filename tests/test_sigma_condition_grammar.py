"""
Tests for ENH-015 -- the real Sigma condition grammar.

The engine previously did::

    if condition == "selection":      return selection_match
    elif "and not filter" in cond:    return selection_match   # filter IGNORED
    else:                             return selection_match   # everything IGNORED

Consequences, both of which are serious for a SIEM:

* `selection and not filter` fired on exactly the traffic the rule excluded --
  false positives that destroy analyst trust in the product.
* `selection1 or selection2`, `1 of them`, `all of them` and negation never
  worked -- false negatives that miss real attacks.

These tests pin the grammar against the Sigma specification.
Reference: https://sigmahq.io/docs/basics/conditions.html
"""

import pytest

from sigma_condition import (
    And,
    Identifier,
    Not,
    Or,
    Quantifier,
    SigmaConditionError,
    evaluate_condition,
    parse_condition,
    split_aggregation,
    tokenize,
)


# ---------------------------------------------------------------------------
# The specific regression: `and not filter`
# ---------------------------------------------------------------------------


def test_and_not_filter_excludes_when_filter_matches():
    """
    THE headline bug. A rule saying "selection and not filter" must NOT fire
    when the filter matches -- previously it fired anyway.
    """
    result = evaluate_condition(
        "selection and not filter",
        {"selection": True, "filter": True},
    )
    assert result is False, (
        "Rule fired despite its filter matching. This is the ENH-015 "
        "false-positive bug."
    )


def test_and_not_filter_fires_when_filter_does_not_match():
    assert evaluate_condition(
        "selection and not filter",
        {"selection": True, "filter": False},
    ) is True


def test_and_not_filter_does_not_fire_without_selection():
    assert evaluate_condition(
        "selection and not filter",
        {"selection": False, "filter": False},
    ) is False


# ---------------------------------------------------------------------------
# Boolean operators
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "results,expected",
    [
        ({"a": True, "b": True}, True),
        ({"a": True, "b": False}, True),
        ({"a": False, "b": True}, True),
        ({"a": False, "b": False}, False),
    ],
)
def test_or_truth_table(results, expected):
    """`selection1 or selection2` never worked -- it returned selection_match."""
    assert evaluate_condition("a or b", results) is expected


@pytest.mark.parametrize(
    "results,expected",
    [
        ({"a": True, "b": True}, True),
        ({"a": True, "b": False}, False),
        ({"a": False, "b": True}, False),
        ({"a": False, "b": False}, False),
    ],
)
def test_and_truth_table(results, expected):
    assert evaluate_condition("a and b", results) is expected


@pytest.mark.parametrize("value,expected", [(True, False), (False, True)])
def test_not_inverts(value, expected):
    assert evaluate_condition("not a", {"a": value}) is expected


def test_double_negation():
    assert evaluate_condition("not not a", {"a": True}) is True


def test_and_binds_tighter_than_or():
    """`a or b and c` must parse as `a or (b and c)`."""
    assert evaluate_condition("a or b and c", {"a": True, "b": True, "c": False}) is True
    assert evaluate_condition("a or b and c", {"a": False, "b": True, "c": False}) is False
    assert evaluate_condition("a or b and c", {"a": False, "b": True, "c": True}) is True


def test_parentheses_override_precedence():
    assert evaluate_condition(
        "(a or b) and c", {"a": True, "b": False, "c": False}
    ) is False
    assert evaluate_condition(
        "(a or b) and c", {"a": True, "b": False, "c": True}
    ) is True


def test_not_applies_to_parenthesised_group():
    assert evaluate_condition(
        "not (a or b)", {"a": False, "b": False}
    ) is True
    assert evaluate_condition(
        "not (a or b)", {"a": True, "b": False}
    ) is False


def test_nested_parentheses():
    assert evaluate_condition(
        "((a and b) or (c and d))",
        {"a": False, "b": True, "c": True, "d": True},
    ) is True


def test_operators_are_case_insensitive():
    assert evaluate_condition("a AND b", {"a": True, "b": True}) is True
    assert evaluate_condition("a OR b", {"a": False, "b": True}) is True
    assert evaluate_condition("NOT a", {"a": False}) is True


# ---------------------------------------------------------------------------
# Quantifiers
# ---------------------------------------------------------------------------


def test_one_of_them_matches_when_any_matches():
    assert evaluate_condition(
        "1 of them", {"sel_a": False, "sel_b": True}
    ) is True


def test_one_of_them_false_when_none_match():
    assert evaluate_condition(
        "1 of them", {"sel_a": False, "sel_b": False}
    ) is False


def test_all_of_them_requires_every_selection():
    assert evaluate_condition(
        "all of them", {"sel_a": True, "sel_b": True}
    ) is True
    assert evaluate_condition(
        "all of them", {"sel_a": True, "sel_b": False}
    ) is False


def test_any_of_them_is_an_alias_for_one_of():
    assert evaluate_condition(
        "any of them", {"sel_a": False, "sel_b": True}
    ) is True


def test_one_of_wildcard_pattern():
    results = {"selection_a": False, "selection_b": True, "filter_x": False}
    assert evaluate_condition("1 of selection_*", results) is True


def test_all_of_wildcard_pattern_ignores_non_matching_names():
    """`all of selection_*` must not be dragged down by an unrelated filter."""
    results = {"selection_a": True, "selection_b": True, "filter_x": False}
    assert evaluate_condition("all of selection_*", results) is True


def test_wildcard_matching_nothing_does_not_fire():
    """
    `all of <empty set>` is vacuously true in logic, but a detection rule that
    fires on everything is the worst possible outcome -- so it fails safe.
    """
    assert evaluate_condition("all of nomatch_*", {"selection": True}) is False


def test_quantifier_combined_with_negation():
    results = {"selection": True, "filter_a": False, "filter_b": False}
    assert evaluate_condition(
        "selection and not 1 of filter_*", results
    ) is True

    results["filter_b"] = True
    assert evaluate_condition(
        "selection and not 1 of filter_*", results
    ) is False


# ---------------------------------------------------------------------------
# Parsing structure
# ---------------------------------------------------------------------------


def test_simple_identifier_parses():
    assert parse_condition("selection") == Identifier("selection")


def test_and_parses_to_and_node():
    node = parse_condition("a and b")
    assert isinstance(node, And)


def test_or_parses_to_or_node():
    assert isinstance(parse_condition("a or b"), Or)


def test_not_parses_to_not_node():
    assert isinstance(parse_condition("not a"), Not)


def test_quantifier_parses():
    node = parse_condition("1 of them")
    assert isinstance(node, Quantifier)
    assert node.mode == "one"
    assert node.pattern == "them"


def test_tokenizer_handles_parentheses():
    kinds = [t.kind for t in tokenize("(a and b)")]
    assert kinds == ["lparen", "ident", "ident", "ident", "rparen"]


# ---------------------------------------------------------------------------
# Aggregations are split out, not misparsed
# ---------------------------------------------------------------------------


def test_split_aggregation_separates_count():
    expression, aggregation = split_aggregation("selection | count() > 5")
    assert expression == "selection"
    assert aggregation == "count() > 5"


def test_split_aggregation_without_pipe():
    expression, aggregation = split_aggregation("selection and not filter")
    assert expression == "selection and not filter"
    assert aggregation is None


def test_condition_with_aggregation_still_parses_its_selection_part():
    assert evaluate_condition("selection | count() > 5", {"selection": True}) is True


# ---------------------------------------------------------------------------
# Error handling -- never silently pass
# ---------------------------------------------------------------------------


def test_unknown_selection_name_raises():
    """
    A condition referencing an undefined selection is a rule authoring error.
    Silently treating it as False would quietly disable part of a detection.
    """
    with pytest.raises(SigmaConditionError, match="undefined selection"):
        evaluate_condition("selection and missing", {"selection": True})


def test_unbalanced_parenthesis_raises():
    with pytest.raises(SigmaConditionError):
        parse_condition("(a and b")


def test_empty_condition_raises():
    with pytest.raises(SigmaConditionError):
        parse_condition("")


def test_dangling_operator_raises():
    with pytest.raises(SigmaConditionError):
        parse_condition("a and")


def test_bare_keyword_raises():
    with pytest.raises(SigmaConditionError):
        parse_condition("and")


def test_illegal_character_raises():
    with pytest.raises(SigmaConditionError):
        parse_condition("a & b")


# ---------------------------------------------------------------------------
# Engine integration
# ---------------------------------------------------------------------------


def test_engine_returns_false_for_unparseable_condition():
    """
    An unparseable rule must not emit a detection. Fabricating detections from
    broken rule content would be worse than missing them.
    """
    from sigma_engine import SigmaRuleEngine

    engine = SigmaRuleEngine.__new__(SigmaRuleEngine)
    assert engine._evaluate_condition_logic(
        "a & b", {"a": True}, rule_id="broken-rule"
    ) is False


def test_engine_evaluates_real_grammar():
    from sigma_engine import SigmaRuleEngine

    engine = SigmaRuleEngine.__new__(SigmaRuleEngine)

    assert engine._evaluate_condition_logic(
        "selection and not filter", {"selection": True, "filter": True}
    ) is False
    assert engine._evaluate_condition_logic(
        "selection and not filter", {"selection": True, "filter": False}
    ) is True


# ---------------------------------------------------------------------------
# Count conditions must be recognised, or the rule is silently dead
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "condition,threshold,operator,group_by",
    [
        # Standard Sigma aggregation -- previously unrecognised, which made
        # packages/rules/brute_force_detection.yml a dead rule.
        ("count(selection) >= 10 by src_ip", 10, "gte", ["src_ip"]),
        ("selection | count() > 5 by src_ip, user", 5, "gt", ["src_ip", "user"]),
        # Logforge-native forms must keep working.
        ("selection | count() > 10", 10, "gt", None),
        ("selection | count(by=['src_ip']) > 5", 5, "gt", ["src_ip"]),
    ],
)
def test_count_condition_forms_are_recognised(
    condition, threshold, operator, group_by
):
    from sigma_engine import CountCondition

    parsed = CountCondition.parse(condition)

    assert parsed is not None, (
        f"{condition!r} was not recognised as a count condition, so the rule "
        "would fall through to simple evaluation and never fire."
    )
    assert parsed.threshold == threshold
    assert parsed.operator == operator
    assert parsed.group_by == group_by


def test_non_count_condition_is_not_treated_as_count():
    from sigma_engine import CountCondition

    assert CountCondition.parse("selection and not filter") is None


# ---------------------------------------------------------------------------
# The rules this repository actually ships must all be evaluable
# ---------------------------------------------------------------------------


def _shipped_rules():
    import glob
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    return [
        f for f in sorted(glob.glob(str(root / "packages" / "rules" / "*.yml")))
        # ENH-039: content_pack.yml is a MULTI-rule document with a
        # different schema; it has its own suite in
        # tests/test_content_pack.py.
        if not f.endswith("content_pack.yml")
    ]


@pytest.mark.parametrize("path", _shipped_rules(), ids=lambda p: p.split("/")[-1])
def test_shipped_rule_condition_is_evaluable(path):
    """
    Every rule shipped in `packages/rules/` must be either a parseable boolean
    condition or a recognised count condition. A rule that is neither is dead
    content -- it will never produce a detection.
    """
    import yaml

    from sigma_engine import CountCondition

    rule = yaml.safe_load(open(path, encoding="utf-8"))
    detection = rule.get("detection", {})
    condition = detection.get("condition")

    assert condition, f"{path} has no condition"

    if CountCondition.parse(condition) is not None:
        return  # handled by the batch-level count path

    selections = [k for k in detection if k != "condition"]
    ast = parse_condition(condition)

    unknown = [n for n in ast.identifiers() if n not in selections]
    assert not unknown, (
        f"{path} references selections {unknown} that it does not define."
    )
