"""
Ingest pipeline processors (Phase 4). Each processor takes a document (the
log as a dict: ts, host, service, level, msg, src_ip, attrs, ...) and a
config, and changes the document in place. Field names are dotted paths.

Errors raise ProcessorError (with the processor and the reason), `drop`
raises DropEvent, and a bad config is rejected by build_processor before the
pipeline is saved.
"""

import hashlib
from datetime import datetime, timezone

import pytest

from pipeline_processors import (PROCESSORS, DropEvent, ProcessorContext, ProcessorError, build_processor,
                                 grok_to_regex)


def run(kind, config, doc, ctx=None):
    build_processor(kind, config)(doc, ctx or ProcessorContext())
    return doc


def doc(msg="", **fields):
    return {"msg": msg, "service": "app", "level": "info", "attrs": {}, **fields}


# -- parse --------------------------------------------------------------------

def test_json_parses_into_attrs_or_a_target():
    d = run("json", {"field": "msg"}, doc('{"user": "bob", "n": 2}'))
    assert d["attrs"] == {"user": "bob", "n": 2}
    d = run("json", {"field": "msg", "target": "attrs.payload"}, doc('{"a": 1}'))
    assert d["attrs"]["payload"] == {"a": 1}
    with pytest.raises(ProcessorError, match="json"):
        run("json", {"field": "msg"}, doc("not json"))


def test_kv_with_quotes_and_custom_separators():
    d = run("kv", {"field": "msg"}, doc('user=alice action="log in" result=ok'))
    assert d["attrs"] == {"user": "alice", "action": "log in", "result": "ok"}
    d = run("kv", {"field": "msg", "field_split": ";", "value_split": ":", "prefix": "kv_"}, doc("a:1;b:2"))
    assert d["attrs"] == {"kv_a": "1", "kv_b": "2"}


def test_csv_maps_columns():
    d = run("csv", {"field": "msg", "columns": ["when", "user", "note"]}, doc('2026-11-19,bob,"hello, world"'))
    assert d["attrs"] == {"when": "2026-11-19", "user": "bob", "note": "hello, world"}


def test_grok_with_the_bundled_patterns_and_type_casts():
    line = ('203.0.113.9 - frank [10/Oct/2026:13:55:36 +0000] "GET /a.gif?x=1 HTTP/1.1" 200 2326 '
            '"http://example.com/start" "Mozilla/5.0"')
    d = run("grok", {"field": "msg", "patterns": ["%{COMBINEDAPACHELOG}"]}, doc(line))
    a = d["attrs"]
    assert (a["clientip"], a["auth"], a["verb"], a["request"], a["response"], a["bytes"]) == \
        ("203.0.113.9", "frank", "GET", "/a.gif?x=1", 200, 2326)
    assert a["timestamp"] == "10/Oct/2026:13:55:36 +0000" and a["referrer"] == "http://example.com/start"


def test_grok_tries_patterns_in_order_and_supports_custom_definitions():
    config = {"field": "msg", "patterns": ["%{ORDER:order} shipped", "%{WORD:verb} %{ORDER:order}"],
              "pattern_definitions": {"ORDER": "ORD-%{INT}"}}
    assert run("grok", config, doc("cancel ORD-77"))["attrs"] == {"verb": "cancel", "order": "ORD-77"}
    with pytest.raises(ProcessorError, match="no grok pattern matched"):
        run("grok", config, doc("nothing here"))


def test_grok_rejects_unknown_patterns_at_build_time():
    with pytest.raises(ProcessorError, match="NOPE"):
        build_processor("grok", {"field": "msg", "patterns": ["%{NOPE:x}"]})
    assert "(?P<ip>" in grok_to_regex("%{IP:ip}")


def test_regex_named_groups():
    d = run("regex", {"field": "msg", "pattern": r"took (?P<ms>\d+)ms"}, doc("request took 35ms"))
    assert d["attrs"] == {"ms": "35"}


def test_syslog_cef_and_leef():
    d = run("syslog", {"field": "msg"}, doc("<34>Oct 11 22:14:15 mymachine su[230]: 'su root' failed for lonvick"))
    assert d["host"] == "mymachine" and d["service"] == "su" and d["level"] == "fatal"
    assert d["attrs"]["syslog"]["pid"] == 230 and d["msg"].startswith("'su root' failed")

    cef = "CEF:0|Security|threatmanager|1.0|100|worm successfully stopped|10|src=10.0.0.1 dst=2.1.2.2 spt=1232"
    d = run("cef", {"field": "msg"}, doc(cef))
    assert d["attrs"]["cef"]["device_vendor"] == "Security" and d["attrs"]["cef"]["severity"] == 10
    assert d["attrs"]["src"] == "10.0.0.1" and d["attrs"]["spt"] == "1232" and d["level"] == "fatal"

    leef = "LEEF:2.0|Lancope|StealthWatch|1.0|41|^|src=10.0.1.8^dst=10.0.0.5^sev=5^usrName=joe"
    d = run("leef", {"field": "msg"}, doc(leef))
    assert d["attrs"]["leef"] == {"version": "2.0", "vendor": "Lancope", "product": "StealthWatch",
                                  "product_version": "1.0", "event_id": "41"}
    assert d["attrs"]["usrName"] == "joe" and d["attrs"]["dst"] == "10.0.0.5"
    leef1 = "LEEF:1.0|Microsoft|MSExchange|4.0 SP1|15345|src=10.50.1.1\tdst=2.10.20.20\tusrName=bob"
    assert run("leef", {"field": "msg"}, doc(leef1))["attrs"]["usrName"] == "bob"


def test_date_formats_set_ts():
    d = run("date", {"field": "attrs.when", "formats": ["HTTPDATE"]}, doc(attrs={"when": "10/Oct/2026:13:55:36 -0700"}))
    assert d["ts"] == datetime(2026, 10, 10, 20, 55, 36, tzinfo=timezone.utc)
    d = run("date", {"field": "attrs.t", "formats": ["UNIX_MS"]}, doc(attrs={"t": 1795000000123}))
    assert d["ts"].timestamp() == pytest.approx(1795000000.123)
    d = run("date", {"field": "attrs.t", "formats": ["%d.%m.%Y %H:%M"], "timezone": "Europe/Berlin"},
            doc(attrs={"t": "19.11.2026 10:00"}))
    assert d["ts"] == datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    d = run("date", {"field": "attrs.t", "formats": ["ISO8601"], "target": "attrs.parsed"},
            doc(attrs={"t": "2026-11-19T10:00:00Z"}))
    assert d["attrs"]["parsed"] == "2026-11-19T10:00:00+00:00"
    with pytest.raises(ProcessorError, match="date"):
        run("date", {"field": "attrs.t", "formats": ["ISO8601"]}, doc(attrs={"t": "yesterday"}))


def test_user_agent():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.71 Safari/537.36"
    d = run("user_agent", {"field": "attrs.agent"}, doc(attrs={"agent": ua}))
    assert d["attrs"]["user_agent"] == {"name": "Chrome", "version": "120.0.6099.71", "os": "Windows",
                                        "device": "desktop", "original": ua}
    bot = run("user_agent", {"field": "attrs.agent"}, doc(attrs={"agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"}))
    assert bot["attrs"]["user_agent"]["device"] == "bot"
    phone = run("user_agent", {"field": "attrs.agent"}, doc(attrs={
        "agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 Version/17.1 Mobile/15E148 Safari/604.1"}))
    assert phone["attrs"]["user_agent"]["os"] == "iOS" and phone["attrs"]["user_agent"]["device"] == "mobile"


# -- transform ----------------------------------------------------------------

def test_rename_set_remove():
    d = run("rename", {"field": "attrs.usr", "target_field": "attrs.user"}, doc(attrs={"usr": "bob"}))
    assert d["attrs"] == {"user": "bob"}
    d = run("set", {"field": "attrs.summary", "value": "{{attrs.user}} from {{src_ip}}"},
            doc(src_ip="203.0.113.9", attrs={"user": "bob"}))
    assert d["attrs"]["summary"] == "bob from 203.0.113.9"
    d = run("set", {"field": "attrs.user", "value": "x", "override": False}, doc(attrs={"user": "bob"}))
    assert d["attrs"]["user"] == "bob"
    d = run("set", {"field": "attrs.copy", "copy_from": "attrs.user"}, doc(attrs={"user": "bob"}))
    assert d["attrs"]["copy"] == "bob"
    d = run("remove", {"field": ["attrs.a", "attrs.b"]}, doc(attrs={"a": 1, "b": 2, "c": 3}))
    assert d["attrs"] == {"c": 3}
    with pytest.raises(ProcessorError, match="attrs.nope"):
        run("rename", {"field": "attrs.nope", "target_field": "attrs.x"}, doc())
    assert run("remove", {"field": "attrs.nope", "ignore_missing": True}, doc())["attrs"] == {}


def test_convert_lowercase_split():
    d = run("convert", {"field": "attrs.n", "type": "integer"}, doc(attrs={"n": "42"}))
    assert d["attrs"]["n"] == 42
    assert run("convert", {"field": "attrs.f", "type": "float"}, doc(attrs={"f": "1.5"}))["attrs"]["f"] == 1.5
    assert run("convert", {"field": "attrs.b", "type": "boolean"}, doc(attrs={"b": "TRUE"}))["attrs"]["b"] is True
    assert run("convert", {"field": "status", "type": "string"}, doc(status=200))["status"] == "200"
    with pytest.raises(ProcessorError, match="integer"):
        run("convert", {"field": "attrs.n", "type": "integer"}, doc(attrs={"n": "abc"}))
    assert run("lowercase", {"field": "attrs.u"}, doc(attrs={"u": "BoB"}))["attrs"]["u"] == "bob"
    assert run("uppercase", {"field": "attrs.u"}, doc(attrs={"u": "bob"}))["attrs"]["u"] == "BOB"
    assert run("split", {"field": "attrs.t", "separator": ","}, doc(attrs={"t": "a, b,c"}))["attrs"]["t"] == ["a", "b", "c"]


def test_script():
    d = run("script", {"source": "attrs.kb = attrs.bytes / 1024; level = 'error' if status >= 500 else level"},
            doc(status=503, attrs={"bytes": 2048}))
    assert d["attrs"]["kb"] == 2.0 and d["level"] == "error"
    with pytest.raises(ProcessorError, match="script"):
        build_processor("script", {"source": "import os"})


# -- enrich -------------------------------------------------------------------

def test_geoip_lookup_and_threat_intel_use_the_context():
    from enrichment_processors import GeoIP, _Ranges
    from threat_intel import Indicator

    city = _Ranges()
    city.add_all([("203.0.113.0", "203.0.113.255", ("EU", "DE", "Berlin", "Berlin"))])
    ctx = ProcessorContext(geo=GeoIP(city=city), tables={"owners": {"web-01": {"owner": "payments"}}},
                           intel={"ip": {"203.0.113.9": Indicator(value="203.0.113.9", indicator_type="ip",
                                                                 threat_type="botnet_cc", confidence=90,
                                                                 source="Feodo")}})
    d = run("geoip", {"field": "src_ip"}, doc(src_ip="203.0.113.9"), ctx)
    assert d["attrs"]["geo"]["src_ip"]["country"] == "DE"
    d = run("lookup", {"field": "host", "table": "owners", "target": "attrs.asset"}, doc(host="WEB-01"), ctx)
    assert d["attrs"]["asset"] == {"owner": "payments"}
    d = run("lookup", {"field": "attrs.code", "values": {"E1": "disk full"}, "target": "attrs.reason"},
            doc(attrs={"code": "E1"}), ctx)
    assert d["attrs"]["reason"] == "disk full"
    d = run("threat_intel", {}, doc(src_ip="203.0.113.9"), ctx)
    assert d["attrs"]["threat"]["matched"] is True and d["attrs"]["threat"]["indicators"][0]["source"] == "Feodo"


# -- privacy ------------------------------------------------------------------

FAKE_TOKEN = "sk" + "_live_" + "abcdefghijklmnopqrstuvwx"  # a test value, assembled so it isn't a key literal


def test_mask_and_hash():
    d = run("mask", {"field": "msg", "kinds": ["email", "card", "token"]},
            doc(f"mail bob@example.com card 4111 1111 1111 1111 key={FAKE_TOKEN}"))
    assert "bob@example.com" not in d["msg"] and "4111" not in d["msg"] and "abcdefghijklmnop" not in d["msg"]
    assert "[email]" in d["msg"] and "[card]" in d["msg"]
    # a 16-digit number that fails the Luhn check is not a card
    assert "1234 5678 9012 3456" in run("mask", {"field": "msg", "kinds": ["card"]}, doc("id 1234 5678 9012 3456"))["msg"]
    d = run("mask", {"field": "msg", "pattern": r"ssn=\d{3}-\d{2}-\d{4}", "replacement": "ssn=***"}, doc("ssn=123-45-6789"))
    assert d["msg"] == "ssn=***"
    d = run("hash", {"field": "attrs.email", "salt": "s1"}, doc(attrs={"email": "Bob@Example.com"}))
    assert d["attrs"]["email"] == hashlib.sha256(b"s1Bob@Example.com").hexdigest()


# -- flow ---------------------------------------------------------------------

def test_drop_route_fail():
    with pytest.raises(DropEvent):
        run("drop", {}, doc())
    d = run("route", {"retention": "short", "stream": "debug-logs"}, doc())
    assert d["_route"] == {"retention": "short", "stream": "debug-logs"}
    with pytest.raises(ProcessorError, match="unsupported version 9 from app"):
        run("fail", {"message": "unsupported version {{attrs.v}} from {{service}}"}, doc(attrs={"v": 9}))


def test_every_processor_named_in_the_roadmap_exists():
    roadmap = {"json", "kv", "csv", "grok", "regex", "syslog", "cef", "leef", "date", "user_agent", "rename", "set",
               "remove", "convert", "lowercase", "split", "script", "geoip", "lookup", "threat_intel", "mask", "hash",
               "drop", "route", "fail"}
    assert roadmap <= set(PROCESSORS)


def test_unknown_processor_and_missing_options_are_rejected():
    with pytest.raises(ProcessorError, match="unknown processor"):
        build_processor("teleport", {})
    with pytest.raises(ProcessorError, match="field"):
        build_processor("json", {})
    with pytest.raises(ProcessorError, match="type"):
        build_processor("convert", {"field": "x", "type": "complex"})


def test_cef_values_keep_spaces_and_escapes():
    """parsers.CEFParser splits extension values at spaces; the CEF spec lets
    a value run until the next ` key=`, with \\= and \\| escaped."""
    cef = r"CEF:0|Acme|IDS|1|7|pipe \| in name|5|msg=disk is full now suser=bob cs1=a\=b"
    d = run("cef", {"field": "msg"}, doc(cef))
    assert d["msg"] == "pipe | in name" and d["attrs"]["msg"] == "disk is full now"
    assert d["attrs"]["cs1"] == "a=b" and d["user_id"] == "bob"


def test_regex_with_ordered_patterns_and_flags():
    config = {"field": "msg", "patterns": [r"username[=:\s]+(?P<user>[^\s,]+)", r"user[=:\s]+(?P<user>[^\s,]+)"],
              "flags": "i", "target": ""}
    assert run("regex", config, doc("login USERNAME=root ok"))["user"] == "root"
    assert run("regex", config, doc("User: alice"))["user"] == "alice"


def test_urldecode_and_compact():
    assert run("urldecode", {"field": "attrs.uri"}, doc(attrs={"uri": "/a%20b?q=%2Fx"}))["attrs"]["uri"] == "/a b?q=/x"
    d = run("compact", {"field": "attrs", "values": ["", "-"]}, doc(attrs={"a": "", "b": "-", "c": None, "d": 0, "e": "x"}))
    assert d["attrs"] == {"d": 0, "e": "x"}
