"""
Detection tuning (Phase 1): exclusions, throttling, and exclusion
suggestions from analysts' false-positive verdicts.

* An exclusion is a set of field conditions in the same syntax as a Sigma
  selection (modifiers included), scoped to one rule or to all ('*'),
  optionally expiring. An alert whose event matches it is not raised.
* A throttle raises at most one alert per rule and group (`group_by` fields)
  per window; state is bounded.
* `suggest_exclusion` proposes the field values shared by a rule's false
  positives and reports how many of its other detections the exclusion would
  also hide, so an analyst can judge it before saving.
"""

from datetime import datetime, timedelta, timezone

import pytest

from detection_tuning import Throttler, TuningError, TuningSet, suggest_exclusion, validate_record

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
SCANNER = {"src_ip": "10.0.5.5", "user": "svc_scan", "hostname": "scan-01"}


def record(rid="x1", rule_id="r1", kind="exclusion", **spec):
    return {"id": rid, "rule_id": rule_id, "kind": kind, "spec": spec, "reason": "authorised scanner"}


# --- exclusions -------------------------------------------------------------------

def test_an_exclusion_suppresses_matching_events_for_its_rule_only():
    tuning = TuningSet.from_records([record(conditions={"src_ip": "10.0.5.5"})])
    assert tuning.exclusion_for("r1", SCANNER, T0) == "x1"
    assert tuning.exclusion_for("r2", SCANNER, T0) is None
    assert tuning.exclusion_for("r1", dict(SCANNER, src_ip="10.0.5.6"), T0) is None


def test_exclusions_use_sigma_field_syntax_and_attrs():
    tuning = TuningSet.from_records([record(rule_id="*", conditions={"user|startswith": "svc_",
                                                                     "hostname": ["scan-01", "scan-02"]})])
    assert tuning.exclusion_for("any-rule", {"attrs": {"user": "svc_scan", "hostname": "scan-02"}}, T0) == "x1"
    assert tuning.exclusion_for("any-rule", {"user": "alice", "hostname": "scan-01"}, T0) is None


def test_expired_exclusions_no_longer_apply():
    tuning = TuningSet.from_records([record(conditions={"src_ip": "10.0.5.5"},
                                            expires_at=(T0 - timedelta(hours=1)).isoformat())])
    assert tuning.exclusion_for("r1", SCANNER, T0) is None


# --- throttling -------------------------------------------------------------------

def test_throttle_allows_one_alert_per_group_per_window():
    tuning = TuningSet.from_records([record("t1", kind="throttle", window="10m", group_by=["src_ip"])])
    throttler = Throttler()
    allow = lambda ts, event: throttler.allow("tenant", "r1", tuning.throttle_for("r1"), event, {}, ts)  # noqa: E731
    assert allow(T0, SCANNER)
    assert not allow(T0 + timedelta(minutes=5), SCANNER)
    assert allow(T0 + timedelta(minutes=5), dict(SCANNER, src_ip="10.0.5.6"))  # another group
    assert allow(T0 + timedelta(minutes=11), SCANNER)  # window passed


def test_correlation_groups_are_used_when_present():
    tuning = TuningSet.from_records([record("t1", kind="throttle", window="1h", group_by=["src_ip"])])
    throttler = Throttler()
    rule_throttle = tuning.throttle_for("r1")
    assert throttler.allow("t", "r1", rule_throttle, {}, {"src_ip": "1.2.3.4"}, T0)
    assert not throttler.allow("t", "r1", rule_throttle, {}, {"src_ip": "1.2.3.4"}, T0 + timedelta(minutes=1))


def test_no_throttle_means_every_alert_passes():
    throttler = Throttler()
    assert all(throttler.allow("t", "r1", None, SCANNER, {}, T0) for _ in range(5))


def test_throttle_state_is_bounded():
    throttle = TuningSet.from_records([record("t1", kind="throttle", window="1h", group_by=["src_ip"])]).throttle_for("r1")
    throttler = Throttler(max_keys=100)
    for i in range(1000):
        throttler.allow("t", "r1", throttle, {"src_ip": f"10.0.{i // 250}.{i % 250}"}, {}, T0)
    assert throttler.size() == 100


# --- validation -------------------------------------------------------------------

@pytest.mark.parametrize("kind, spec, message", [
    ("exclusion", {}, "conditions"),
    ("exclusion", {"conditions": {"x'); DROP": "1"}}, "field name"),
    ("throttle", {"window": "soon"}, "invalid timespan"),
    ("throttle", {"window": "10m", "group_by": "src_ip; x"}, "group_by"),
    ("mute", {}, "kind"),
])
def test_invalid_records_are_rejected(kind, spec, message):
    with pytest.raises(TuningError, match=message):
        validate_record({"rule_id": "r1", "kind": kind, "spec": spec})


def test_valid_records_pass():
    validate_record({"rule_id": "r1", "kind": "exclusion", "spec": {"conditions": {"src_ip": "10.0.5.5"}}})
    validate_record({"rule_id": "*", "kind": "throttle", "spec": {"window": "10m", "group_by": ["src_ip"]}})


# --- suggestions ------------------------------------------------------------------

def test_suggests_the_values_false_positives_share():
    fps = [dict(SCANNER, url=f"/p{i}") for i in range(4)]
    tps = [{"src_ip": "45.155.205.20", "user": "root", "hostname": "web-01"},
           {"src_ip": "10.0.5.5", "user": "root", "hostname": "web-01"}]
    suggestion = suggest_exclusion(fps, tps)
    assert suggestion["conditions"] == {"hostname": "scan-01", "src_ip": "10.0.5.5", "user": "svc_scan"}
    assert suggestion["false_positives"] == 4
    assert suggestion["would_also_suppress"] == 0  # no true positive has all three values


def test_reports_when_a_suggestion_would_hide_real_detections():
    fps = [{"src_ip": "10.0.5.5"}] * 3
    tps = [{"src_ip": "10.0.5.5"}, {"src_ip": "1.1.1.1"}]
    assert suggest_exclusion(fps, tps)["would_also_suppress"] == 1


def test_needs_enough_consistent_false_positives():
    assert suggest_exclusion([SCANNER, SCANNER], [])["conditions"] is None  # fewer than 3
    varied = [{"src_ip": f"10.0.0.{i}", "user": f"u{i}"} for i in range(5)]
    assert suggest_exclusion(varied, [])["conditions"] is None  # nothing shared


def test_pipeline_metadata_is_not_proposed():
    """Found live: the suggestion listed facility, parser_version, severity_num,
    log level, status 0... which every event carries; only fields that
    describe the false positive belong in an exclusion."""
    event = {"hostname": "pentest-01", "host": "pentest-01", "service": "auditd", "level": "info",
             "log_level": "info", "facility": 16, "parser_version": "v1", "severity_num": 0, "status": 0,
             "status_code": 0, "attrs": {"user": "kali", "processing_version": "smart_v1", "source_format": "json"}}
    suggestion = suggest_exclusion([event] * 3, [])
    assert suggestion["conditions"] == {"hostname": "pentest-01", "service": "auditd", "user": "kali"}
