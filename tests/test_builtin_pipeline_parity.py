"""
Built-in pipelines replace the hard-coded parsers (Phase 4, "one mechanism").

For every sample line both the legacy parser class and the built-in
pipeline run, and the stored fields must be identical: ts, service, level,
msg, status, src_ip, user_id, severity, facility and attrs. Where the legacy
parser was wrong the expected result is stated instead (FIXED below).

ParserFactory now returns the pipeline-backed parser for these formats, so
the format endpoints (/v1/ingest/nginx, /syslog, /cef, /text) use them.
"""

from datetime import datetime, timezone

import pytest

import parsers
from builtin_pipelines import FORMAT_PIPELINES, builtin_records, parse_line

LEGACY = {"nginx": parsers.NginxAccessLogParser, "syslog": parsers.SyslogParser, "cef": parsers.CEFParser,
          "text": parsers.TextParser}
FIELDS = ("service", "level", "msg", "status", "src_ip", "user_id", "severity_num", "facility", "attrs")

SAME = {
    "nginx": [
        '203.0.113.9 - frank [19/Nov/2026:10:00:00 +0000] "GET /a%20b?x=1 HTTP/1.1" 200 2326 "http://example.com/" '
        '"Mozilla/5.0"',
        '203.0.113.9 - - [19/Nov/2026:10:00:02 +0000] "GET /slow HTTP/1.1" 503 15 "-" "curl/8.4.0" 0.512 0.500',
        '{"remote_addr":"198.51.100.7","remote_user":"-","time_iso8601":"2026-11-19T10:00:03Z","request":'
        '"GET /j HTTP/2.0","status":"404","body_bytes_sent":"12","http_referer":"","http_user_agent":"curl/8",'
        '"request_time":"0.01","ssl_protocol":"TLSv1.3"}',
        '203.0.113.9 - - [19/Nov/2026:10:00:04 +0000] "-" 400 0 "-" "-"',
    ],
    "syslog": [
        "<34>Oct 11 22:14:15 mymachine su[230]: 'su root' failed for user admin from 10.0.0.5",
        "Nov 19 10:00:00 web-01 sshd[99]: Accepted password for deploy from 203.0.113.4 port 22",
        "<13>1 2026-11-19T10:00:00.003Z host1 app - - - plain message for user=bob",
        "this is not syslog at all",
    ],
    "cef": [
        "CEF:0|Security|threatmanager|1.0|100|worm successfully stopped|10|src=10.0.0.1 dst=2.1.2.2 spt=1232 "
        "suser=alice dhost=web-01",
    ],
    "text": [
        "2026-11-19 10:00:02 ERROR database connection lost",
        "ERROR 2026-11-19 10:00:03 worker crashed",
        "something went wrong for user=carol from 192.0.2.10",
        "plain line with nothing in it",
    ],
}

FIXED = [
    # (format, line, field -> expected value from the built-in)
    ("nginx", '203.0.113.9 - - [19/Nov/2026:10:00:01 +0000] "POST /api HTTP/1.1" 502 0',
     {"status": 502, "level": "error", "msg": "POST /api 502 0"}),  # legacy: no matching pattern
    ("syslog", '<165>1 2026-11-19T10:00:00.003Z host1 evntslog 1234 ID47 [exampleSDID@32473 iut="3"] login ok',
     {"msg": "login ok", "attrs.structured_data": '[exampleSDID@32473 iut="3"]'}),  # legacy split the SD element
    ("cef", "CEF:0|Acme|IDS|2.1|7|Port scan|5|src=198.51.100.3 msg=scan detected on edge rt=1795000000000",
     {"attrs.msg": "scan detected on edge", "ts": datetime.fromtimestamp(1795000000, tz=timezone.utc)}),
    ("text", "2026-11-19 10:00:00 INFO login successful for user alice from 10.0.0.8",
     {"msg": "2026-11-19 10:00:00 INFO login successful for user alice from 10.0.0.8", "user_id": "alice",
      "src_ip": "10.0.0.8", "attrs.pattern": "auth_login_success"}),  # legacy stored msg ""
    ("text", "2026-11-19 10:00:04,123 ERROR [main] com.acme.App - NullPointerException at line 4",
     {"attrs.pattern": "java_exception", "attrs.thread": "main", "service": "com.acme.App",
      "msg": "NullPointerException at line 4"}),  # legacy never reached java_exception
]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _cases():
    return [(fmt, line) for fmt, lines in SAME.items() for line in lines]


@pytest.mark.parametrize("fmt, line", _cases())
def test_builtin_matches_the_legacy_parser(fmt, line):
    legacy = LEGACY[fmt]().parse(line)
    built = parse_line(FORMAT_PIPELINES[fmt], line)
    for name in FIELDS:
        assert getattr(built, name) == getattr(legacy, name), (name, getattr(built, name), getattr(legacy, name))
    if abs((_utc(legacy.ts) - datetime.now(timezone.utc)).total_seconds()) > 5:  # the line had a time
        assert _utc(built.ts) == _utc(legacy.ts)


@pytest.mark.parametrize("fmt, line, expected", FIXED)
def test_builtin_fixes_legacy_parser_bugs(fmt, line, expected):
    built = parse_line(FORMAT_PIPELINES[fmt], line)
    for path, value in expected.items():
        actual = built.attrs.get(path.split(".", 1)[1]) if path.startswith("attrs.") else getattr(built, path)
        if isinstance(value, datetime):
            actual = _utc(actual)
        assert actual == value, (path, actual)


def test_parser_factory_uses_the_builtin_pipelines():
    for fmt, pipeline_id in FORMAT_PIPELINES.items():
        parser = parsers.ParserFactory.create_parser(fmt)
        assert type(parser).__name__ == f"PipelineParser[{pipeline_id}]"
    with pytest.raises(parsers.ParseError, match="nginx-access"):
        parsers.ParserFactory.create_parser("nginx").parse("not an access log")


def test_builtins_are_registered_and_valid():
    records = builtin_records()
    assert set(FORMAT_PIPELINES.values()) <= set(records)
    assert all(r.builtin and r.enabled for r in records.values())
