"""
Tests for ENH-038 -- stop shipping auto-generated non-detections.

The platform advertised "286 MITRE ATT&CK techniques" as seeded default rules.
Measuring what those rules actually did:

    194 rules  selection = {"process_name|contains": "suspicious"}
     92 rules  selection = {"event_id": [4688, 4624, 4625, 1]}

The first group matches essentially nothing -- dead content. The second fires on
**every ordinary logon**, and fires identically on real malicious PowerShell, so
it carries zero information. Measured directly: a single benign 4624 logon
triggered **92 rules**, and a genuine attack triggered the same 92.

That is worse than having no rules. It inflates a coverage number while
generating the alert fatigue that teaches analysts to ignore the product.

The generator now returns None when it cannot synthesise a discriminating
selection, and the loader reports those techniques as `awaiting_content`.
Real detections live in `packages/rules/`, hand-written and fixture-tested.
"""

import pytest

from mitre_default_loader import MitreDefaultLoader
from mitre_metadata_generator import mitre_metadata_generator
from sigma_engine import SigmaConditionEvaluator


@pytest.fixture(scope="module")
def metadata():
    return mitre_metadata_generator.generate_all_metadata()


@pytest.fixture(scope="module")
def loader():
    # __init__ opens a database connection; only the pure logic is needed here.
    return MitreDefaultLoader.__new__(MitreDefaultLoader)


BENIGN_LOGON = {
    "event_id": 4624,
    "process_name": "explorer.exe",
    "command_line": "C:\\Windows\\explorer.exe",
    "user": "alice",
    "result": "success",
}


# ---------------------------------------------------------------------------
# The generator must not manufacture non-detections
# ---------------------------------------------------------------------------


def test_no_generated_rule_fires_on_a_benign_logon(metadata, loader):
    """
    The headline regression. 92 auto-generated rules used to fire on this exact
    event -- 92 alerts from one benign logon.
    """
    evaluator = SigmaConditionEvaluator()
    firing = []

    for technique_id, meta in metadata.items():
        logic = loader._generate_detection_logic(meta)
        if logic is None:
            continue
        if evaluator.evaluate_selection(BENIGN_LOGON, logic["selection"])[0]:
            firing.append(technique_id)

    assert not firing, (
        f"{len(firing)} generated rules fire on a benign logon: "
        f"{firing[:10]}... Each is pure alert fatigue."
    )


def test_generator_does_not_emit_the_suspicious_placeholder(metadata, loader):
    """`process_name contains "suspicious"` matches nothing -- dead content."""
    offenders = []

    for technique_id, meta in metadata.items():
        logic = loader._generate_detection_logic(meta)
        if logic is None:
            continue
        if logic["selection"].get("process_name|contains") == "suspicious":
            offenders.append(technique_id)

    assert not offenders, f"Placeholder selections emitted for: {offenders[:10]}"


def test_generator_does_not_emit_bare_event_id_rules(metadata, loader):
    """
    A selection of only `event_id in [4688,4624,4625,1]` cannot distinguish an
    attack from routine activity, whatever technique it claims to detect.
    """
    offenders = []

    for technique_id, meta in metadata.items():
        logic = loader._generate_detection_logic(meta)
        if logic is None:
            continue
        if set(logic["selection"]) == {"event_id"}:
            offenders.append(technique_id)

    assert not offenders, f"Bare event_id rules emitted for: {offenders[:10]}"


def test_generator_returns_none_when_it_cannot_discriminate(metadata, loader):
    """
    Returning None is the honest outcome. The alternative -- emitting a rule
    anyway -- is what produced the noise.
    """
    skipped = [
        tid for tid, meta in metadata.items()
        if loader._generate_detection_logic(meta) is None
    ]

    assert skipped, (
        "Every technique produced a rule. Given the metadata available, that "
        "means placeholders are being emitted again."
    )


def test_every_emitted_rule_has_a_real_selection(metadata, loader):
    """Any rule that IS emitted must have a non-empty, non-placeholder selection."""
    for technique_id, meta in metadata.items():
        logic = loader._generate_detection_logic(meta)
        if logic is None:
            continue

        selection = logic["selection"]
        assert selection, f"{technique_id} emitted an empty selection"
        assert selection.get("process_name|contains") != "suspicious"
        assert selection.get("msg|contains") != "security"


# ---------------------------------------------------------------------------
# Skipped techniques must be reported, not hidden
# ---------------------------------------------------------------------------


def test_rule_creation_returns_none_for_unsynthesisable_techniques(metadata, loader):
    technique_id, meta = next(
        (t, m) for t, m in metadata.items()
        if loader._generate_detection_logic(m) is None
    )

    rule = loader._create_default_sigma_rule(
        f"mitre_default_{technique_id.lower()}", technique_id, meta
    )

    assert rule is None


def test_loader_reports_awaiting_content():
    """
    Coverage reporting must stay honest: techniques with no detection are
    counted separately rather than disguised as loaded rules.
    """
    import inspect

    source = inspect.getsource(MitreDefaultLoader.load_default_mitre_rules)

    assert "awaiting_content" in source
    assert '"rules_loaded": loaded_count' in source, (
        "rules_loaded must count only real rules."
    )


def test_coverage_claim_is_not_inflated_by_placeholders(metadata, loader):
    """
    The product claimed 286 techniques of coverage. Real coverage is the number
    of techniques with a genuine detection -- which is what a buyer evaluating
    this SIEM actually cares about.
    """
    emitted = sum(
        1 for meta in metadata.values()
        if loader._generate_detection_logic(meta) is not None
    )

    assert emitted < len(metadata), (
        "Every technique claims a rule again -- the coverage number is inflated."
    )


# ---------------------------------------------------------------------------
# Curated content is where real detection lives
# ---------------------------------------------------------------------------


def test_curated_rules_exist_and_outnumber_generated_detections(loader, metadata):
    """
    The intended architecture after this change: `packages/rules/` is the
    detection content; the generator supplies coverage metadata only.
    """
    import glob
    from pathlib import Path

    rules = glob.glob(
        str(Path(__file__).resolve().parent.parent / "packages" / "rules" / "*.yml")
    )

    generated = sum(
        1 for meta in metadata.values()
        if loader._generate_detection_logic(meta) is not None
    )

    assert len(rules) > generated, (
        "Hand-written, fixture-tested rules should be the source of detection "
        f"content. Curated: {len(rules)}, generated: {generated}."
    )
