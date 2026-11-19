"""
Phase 5 acceptance: the same detection works unchanged across Linux auth,
Windows Security, Okta and an application log once each is mapped to the
common schema.

Each source's sample events go through its mapping pipeline (built-in for
Linux, Windows and Okta; a tenant pipeline for the application), then
through the shipped rule set with the runtime's own replay. Two rules are
written only against schema fields:

* lf-schema-failed-logon: OCSF Authentication (3002), Logon, Failure;
* lf-schema-logon-brute-force: 5+ of those from one source address within
  5 minutes, counted across sources.
"""

import json

import pytest

import eval_harness
from builtin_pipelines import builtin_records
from pipeline_processors import ProcessorContext
from pipeline_store import PipelineRecord

FAILED = "logforge_lf-schema-failed-logon"
BRUTE = "logforge_lf-schema-logon-brute-force"

APP_PIPELINE = {
    "name": "shop-auth",
    "processors": [
        {"json": {"field": "msg", "target": "attrs"}, "if": "startswith(msg, '{')"},
        {"set": {"field": "attrs.ocsf.class_uid", "value": 3002}, "if": "attrs.event == 'login'"},
        {"set": {"field": "attrs.ocsf.activity_id", "value": 1}, "if": "attrs.event == 'login'"},
        {"script": {"source": "attrs.ocsf.status_id = 1 if attrs.outcome == 'ok' else 2"}, "if": "attrs.event == 'login'"},
        {"set": {"field": "attrs.ocsf.actor.user.name", "copy_from": "attrs.username"}, "if": "attrs.event == 'login'"},
        {"set": {"field": "attrs.ocsf.src_endpoint.ip", "copy_from": "attrs.client_ip"}, "if": "attrs.event == 'login'"},
    ],
}


def windows(event_id, user, ip, sub_status="0x0"):
    return json.dumps({"EventID": event_id, "Channel": "Security", "Computer": "DC01.corp.example",
                       "TargetUserName": user, "TargetDomainName": "CORP", "IpAddress": ip, "LogonType": 3,
                       "Status": "0xC000006D" if event_id == 4625 else "0x0", "SubStatus": sub_status})


def okta(result, user, ip, reason=None):
    return json.dumps({"eventType": "user.session.start", "published": "2026-11-19T09:00:00.000Z",
                       "outcome": {"result": result, "reason": reason}, "displayMessage": "User login to Okta",
                       "actor": {"alternateId": user, "displayName": user.split("@")[0]},
                       "client": {"ipAddress": ip, "userAgent": {"rawUserAgent": "Mozilla/5.0"}}})


def app(outcome, user, ip):
    return json.dumps({"event": "login", "outcome": outcome, "username": user, "client_ip": ip})


SOURCES = {
    "linux": ("linux-auth", "sshd", {
        "failed": [("Failed password for root from 203.0.113.9 port 51022 ssh2", "root", "203.0.113.9"),
                   ("Failed password for invalid user oracle from 203.0.113.9 port 51023 ssh2", "oracle", "203.0.113.9"),
                   ("Invalid user admin from 203.0.113.9 port 4222", "admin", "203.0.113.9")],
        "success": [("Accepted publickey for deploy from 10.0.0.5 port 55022 ssh2", "deploy", "10.0.0.5")],
        "other": ["pam_unix(sshd:session): session opened for user deploy(uid=1000) by (uid=0)"]}),
    "windows": ("windows-security", "windows-security", {
        "failed": [(windows(4625, "jsmith", "198.51.100.20", "0xC000006A"), "jsmith", "198.51.100.20")],
        "success": [(windows(4624, "jsmith", "198.51.100.20"), "jsmith", "198.51.100.20")],
        "other": [json.dumps({"EventID": 4688, "NewProcessName": "C:\\\\Windows\\\\System32\\\\cmd.exe"})]}),
    "okta": ("okta", "okta", {
        "failed": [(okta("FAILURE", "bob@acme.example", "192.0.2.44", "INVALID_CREDENTIALS"), "bob@acme.example",
                    "192.0.2.44")],
        "success": [(okta("SUCCESS", "bob@acme.example", "192.0.2.44"), "bob@acme.example", "192.0.2.44")],
        "other": [json.dumps({"eventType": "user.account.update_profile", "outcome": {"result": "SUCCESS"}})]}),
    "app": (None, "shop", {
        "failed": [(app("denied", "carol", "203.0.113.77"), "carol", "203.0.113.77")],
        "success": [(app("ok", "carol", "203.0.113.77"), "carol", "203.0.113.77")],
        "other": [json.dumps({"event": "checkout", "amount": 12})]}),
}

_rules = None


def rules():
    global _rules
    if _rules is None:
        _rules = eval_harness.shipped_rules()
    return _rules


def pipeline_for(source):
    pipeline_id = SOURCES[source][0]
    if pipeline_id is None:
        return PipelineRecord.from_dict(APP_PIPELINE).pipeline
    return builtin_records()[pipeline_id].pipeline


def mapped(source, msg):
    result = pipeline_for(source).run({"msg": msg, "service": SOURCES[source][1], "level": "info", "src_ip": "",
                                       "user_id": "", "attrs": {}}, ProcessorContext())
    assert result.status == "ok", (source, result.error)
    return result.doc


def fired(events):
    from detection_replay import expand_timeline, replay

    return {a.rule_id for a in replay(rules(), expand_timeline(events))}


@pytest.mark.parametrize("source", list(SOURCES))
def test_each_source_maps_to_the_authentication_class(source):
    for kind in ("failed", "success"):
        for msg, user, ip in SOURCES[source][2][kind]:
            ocsf = mapped(source, msg)["attrs"]["ocsf"]
            assert (ocsf["class_uid"], ocsf["activity_id"]) == (3002, 1), (source, ocsf)
            assert ocsf["status_id"] == (2 if kind == "failed" else 1), (source, kind, ocsf)
            assert ocsf["actor"]["user"]["name"] == user and ocsf["src_endpoint"]["ip"] == ip


@pytest.mark.parametrize("source", list(SOURCES))
def test_the_same_rule_fires_for_every_source(source):
    for msg, _, _ in SOURCES[source][2]["failed"]:
        assert FAILED in fired([mapped(source, msg)]), (source, msg)
    for msg, _, _ in SOURCES[source][2]["success"]:
        assert FAILED not in fired([mapped(source, msg)]), (source, msg)
    for msg in SOURCES[source][2]["other"]:
        doc = mapped(source, msg)
        assert "class_uid" not in (doc["attrs"].get("ocsf") or {}), (source, msg)
        assert FAILED not in fired([doc])


def test_brute_force_counts_failures_across_sources():
    ip = "203.0.113.200"
    burst = [mapped("linux", f"Failed password for root from {ip} port 5{i} ssh2") for i in range(2)]
    burst += [mapped("windows", windows(4625, "administrator", ip, "0xC000006A")) for _ in range(2)]
    burst.append(mapped("okta", okta("FAILURE", "admin@acme.example", ip, "INVALID_CREDENTIALS")))
    for event in burst:
        event.pop("ts", None)  # the replay timeline sets the times (the Okta sample carries its own)
    timeline = [burst[0]] + [{"at": f"{i * 20}s", "event": e} for i, e in enumerate(burst) if i]
    assert BRUTE in fired(timeline)
    assert BRUTE not in fired(timeline[:4])


def test_the_schema_rules_raise_no_benign_false_positives():
    report = eval_harness.run()
    assert report["rules"][FAILED]["false_positives"] == 0
    assert report["rules"][BRUTE]["false_positives"] == 0
