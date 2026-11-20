"""
Pipeline drafts from sample logs (Phase 9). Paste a few lines; get an
ingest pipeline (Phase 4) that parses them, checked by simulation.

* heuristic(): without AI. Candidate parsers (JSON, CEF, LEEF, syslog, web
  access logs, key=value, CSV, and a pattern learned from the columns of the
  lines) are each simulated on the samples; the one that parses the most
  lines, extracting the most fields, wins. A timestamp found among the
  extracted fields gets a date step.
* validate(): runs a definition over the samples with the Phase 4 simulator:
  how many lines parsed (ran without failing and gained fields), the fields
  extracted with an example, and the first failures.
* draft(): the model's pipeline, validated the same way, with one repair
  round given the failures; if the heuristic draft parses more lines, that
  is returned instead.
"""

import asyncio
import json

from ai.pipeline_draft import draft, heuristic, validate
from ai.providers import ChatResult, Usage
from ai.redaction import Redactor


def run(coro):
    return asyncio.run(coro)


def kinds(definition):
    return [next(k for k in step if k not in ("if", "tag", "ignore_failure", "on_failure", "description"))
            for step in definition["processors"]]


JSON_LINES = ['{"time": "2026-11-19T10:00:00Z", "user": "alice", "action": "login", "ok": true}',
              '{"time": "2026-11-19T10:00:05Z", "user": "bob", "action": "logout", "ok": true}']
KV_LINES = ['src=10.0.0.1 dst=10.0.0.2 action=allow bytes=120', 'src=10.0.0.3 dst=10.0.0.9 action=deny bytes=0']
SYSLOG_LINES = ["Nov 19 10:01:02 web-01 sshd[1201]: Accepted publickey for deploy from 10.0.1.20 port 51514",
                "Nov 19 10:02:11 web-01 sshd[1205]: Failed password for root from 203.0.113.50 port 40112"]
ACCESS_LINES = ['203.0.113.7 - - [19/Nov/2026:10:00:01 +0000] "GET /index.html HTTP/1.1" 200 512 "-" "curl/8.0"',
                '198.51.100.2 - - [19/Nov/2026:10:00:02 +0000] "POST /login HTTP/1.1" 401 33 "-" "Mozilla/5.0"']
CSV_LINES = ["2026-11-19 10:00:00,alice,login,success", "2026-11-19 10:00:09,bob,login,failure",
             "2026-11-19 10:01:00,carol,logout,success"]
COLUMN_LINES = ["2 123456789012 eni-0a1b 203.0.113.14 10.0.1.25 51544 22 6 12 4210 ACCEPT OK",
                "2 123456789012 eni-0a1b 10.0.1.25 198.51.100.9 443 50122 6 40 98012 ACCEPT OK",
                "2 123456789012 eni-0a1b 192.0.2.77 10.0.1.25 0 0 1 1 84 REJECT OK"]


def test_json_lines():
    d = heuristic(JSON_LINES)
    assert kinds(d.pipeline)[:2] == ["json", "date"] and d.report["parsed"] == 2 and d.report["total"] == 2
    assert {"attrs.user", "attrs.action"} <= set(d.report["fields"])


def test_key_value_lines():
    d = heuristic(KV_LINES)
    assert kinds(d.pipeline)[0] == "kv" and d.report["parsed"] == 2
    assert d.report["fields"]["attrs.src"] == "10.0.0.1"


def test_syslog_lines_are_split_into_header_and_message():
    d = heuristic(SYSLOG_LINES)
    assert kinds(d.pipeline)[0] == "syslog" and d.report["parsed"] == 2
    assert "host" in d.report["fields"] and "service" in d.report["fields"]


def test_web_access_logs_use_the_grok_pattern_and_parse_the_time():
    d = heuristic(ACCESS_LINES)
    assert kinds(d.pipeline)[:2] == ["grok", "date"] and d.report["parsed"] == 2
    assert any(v in (200, "200") for v in d.report["fields"].values())


def test_csv_lines_get_columns():
    d = heuristic(CSV_LINES)
    assert kinds(d.pipeline)[0] == "csv" and d.report["parsed"] == 3
    assert d.pipeline["processors"][0]["csv"]["columns"][0] == "timestamp"


def test_fixed_columns_become_a_learned_pattern():
    d = heuristic(COLUMN_LINES)
    assert kinds(d.pipeline)[0] == "regex" and d.report["parsed"] == 3
    fields = d.report["fields"]
    # IPs and numbers are named by what they hold; constant columns are matched, not captured
    assert fields["attrs.ip_1"] == "203.0.113.14" and fields["attrs.ip_2"] == "10.0.1.25"
    assert not any(v == "123456789012" for v in fields.values())


def test_free_text_is_not_parsed_and_says_so():
    d = heuristic(["the quick brown fox", "jumped over the lazy dog today"])
    assert d.report["parsed"] == 0 and "couldn't" in d.explanation


def test_drafts_keep_events_that_fail_to_parse():
    d = heuristic(JSON_LINES + ["not json"])
    assert d.report["parsed"] == 2 and d.report["total"] == 3
    assert d.pipeline["on_failure"] and d.report["failures"][0]["sample"] == "not json"


def test_validate_rejects_an_invalid_definition():
    report = validate({"processors": [{"grok": {"field": "msg"}}]}, ["x"])
    assert not report["valid"] and "patterns" in report["error"]


class Scripted:
    name, model, external = "s", "s-1", False

    def __init__(self, *texts):
        self.texts, self.sent = list(texts), []

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        self.sent.append(messages)
        return ChatResult(text=self.texts.pop(0), tool_calls=[], stop_reason="end", usage=Usage(10, 5), model="s-1")


def _answer(processors, explanation="Parses the lines."):
    return json.dumps({"pipeline": {"name": "draft", "processors": processors}, "explanation": explanation})


def test_the_model_draft_is_simulated_and_repaired():
    regex = {"regex": {"field": "msg", "patterns": [r"^(?P<who>\w+) did (?P<what>\w+)$"]}}
    provider = Scripted(_answer([{"grok": {"field": "msg", "patterns": ["%{NOPE:x}"]}}]), _answer([regex]))
    out = run(draft(["alice did login", "bob did logout"], provider, redactor=Redactor([])))
    assert out.mode == "ai" and out.report["parsed"] == 2 and kinds(out.pipeline) == ["regex"]
    assert len(provider.sent) == 2 and "simulat" in provider.sent[1][-1].content.lower()


def test_a_heuristic_draft_that_parses_more_wins():
    provider = Scripted(_answer([{"kv": {"field": "msg"}}]), _answer([{"kv": {"field": "msg"}}]))
    out = run(draft(JSON_LINES, provider, redactor=Redactor([])))
    assert out.mode == "heuristic" and "heuristic_parsed_more" in out.flags


def test_samples_are_redacted_before_they_are_sent():
    provider = Scripted(_answer([{"kv": {"field": "msg"}}]))
    run(draft(["user=alice password=hunter2 action=login"], provider, redactor=Redactor([])))
    assert "hunter2" not in provider.sent[0][-1].content
