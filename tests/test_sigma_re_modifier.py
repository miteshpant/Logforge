"""
`|re` is the Sigma specification's name for the regex modifier. The engine
only knew `|regex`, so a packaged rule written to the spec (`dst_ip|re: '.+'`)
silently never matched; vendored SigmaHQ rules only worked because the loader
renames `re` during translation.
"""

from sigma_engine import SigmaConditionEvaluator


def test_re_is_the_regex_modifier():
    evaluator = SigmaConditionEvaluator()
    event = {"dst_ip": "203.0.113.66"}
    assert evaluator.evaluate_selection(event, {"dst_ip|re": r"^203\.0\.113\."})[0]
    assert not evaluator.evaluate_selection(event, {"dst_ip|re": r"^10\."})[0]
