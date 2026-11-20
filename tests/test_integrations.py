"""
Integrations and actions (Phase 13): templates, secrets, outbound address
checks, and each action kind against a mocked HTTP service.
"""

import asyncio
import json
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from integrations import actions, secrets, templates  # noqa: E402

CTX = {"alert": {"id": "a1", "title": "Brute force on web-1", "severity": "high", "entities": {"src_ip": ["203.0.113.9"]}},
       "case": {"id": "c1", "title": "web-1 compromise"}, "tenant": {"name": "Acme"}}


# -- templates ---------------------------------------------------------------

def test_templates_fill_dotted_paths_and_filters():
    assert templates.render("[{{ alert.severity | upper }}] {{ alert.title }}", CTX) == "[HIGH] Brute force on web-1"
    assert templates.render("{{ alert.entities.src_ip.0 }}", CTX) == "203.0.113.9"
    assert templates.render("{{ alert.owner | default('nobody') }}", CTX) == "nobody"
    assert templates.render("{{ alert.entities | json }}", CTX) == json.dumps(CTX["alert"]["entities"])
    assert templates.render("no placeholders", CTX) == "no placeholders"


def test_templates_cannot_reach_python_internals():
    for bad in ("{{ alert.__class__ }}", "{{ __import__('os') }}", "{{ alert | eval }}"):
        with pytest.raises(templates.TemplateError):
            templates.render(bad, CTX)
    # only dict keys and list indexes are followed, never attributes
    assert templates.render("{{ alert.title.upper }}", CTX) == ""


def test_render_tree_renders_every_string():
    out = templates.render_tree({"a": "{{ case.id }}", "b": ["{{ tenant.name }}", 3]}, CTX)
    assert out == {"a": "c1", "b": ["Acme", 3]}


# -- secrets -----------------------------------------------------------------

def test_secrets_round_trip_and_are_not_readable_without_the_key(monkeypatch):
    monkeypatch.setenv("LOGFORGE_SECRETS_KEY", secrets.new_key())
    box = secrets.SecretBox.from_env()
    sealed = box.seal({"api_token": "s3cr3t-value"})
    assert "s3cr3t-value" not in sealed
    assert box.open(sealed) == {"api_token": "s3cr3t-value"}
    monkeypatch.setenv("LOGFORGE_SECRETS_KEY", secrets.new_key())
    with pytest.raises(secrets.SecretError):
        secrets.SecretBox.from_env().open(sealed)


def test_secrets_need_a_key_outside_development(monkeypatch):
    monkeypatch.delenv("LOGFORGE_SECRETS_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(secrets.SecretError):
        secrets.SecretBox.from_env()


# -- outbound address checks --------------------------------------------------

def test_private_and_loopback_targets_are_refused_unless_allowed(monkeypatch):
    monkeypatch.delenv("LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS", raising=False)
    for url in ("http://127.0.0.1:8123/", "http://10.0.0.5/hook", "http://169.254.169.254/latest/meta-data",
                "http://localhost/x", "file:///etc/passwd", "ftp://example.com/"):
        with pytest.raises(actions.ActionError):
            actions.check_url(url)
    actions.check_url("https://hooks.slack.com/services/T/B/C")
    monkeypatch.setenv("LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS", "true")
    actions.check_url("http://127.0.0.1:9999/hook")


# -- actions against a mocked service -----------------------------------------

class Recorder:
    def __init__(self, responder):
        self.requests = []
        self.responder = responder

    def client(self):
        def handle(request):
            self.requests.append(request)
            return self.responder(request)
        return httpx.AsyncClient(transport=httpx.MockTransport(handle))


def run(kind, config, secret, inputs, responder=lambda r: httpx.Response(200, json={})):
    rec = Recorder(responder)

    async def go():
        async with rec.client() as http:
            return await actions.run(kind, config, secret, inputs, CTX, http=http)

    return asyncio.run(go()), rec.requests


@pytest.fixture(autouse=True)
def allow_test_hosts(monkeypatch):
    monkeypatch.setenv("LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS", "true")


def test_slack_posts_the_rendered_text():
    out, reqs = run("slack", {}, {"webhook_url": "https://hooks.slack.test/T/B/C"},
                    {"text": ":rotating_light: [{{ alert.severity | upper }}] {{ alert.title }}"})
    assert out.ok and json.loads(reqs[0].content) == {"text": ":rotating_light: [HIGH] Brute force on web-1"}


def test_jira_creates_an_issue_and_returns_its_key_and_url():
    def jira(request):
        assert request.url.path == "/rest/api/2/issue"
        assert request.headers["authorization"].startswith("Basic ")
        body = json.loads(request.content)
        assert body["fields"]["project"] == {"key": "SEC"}
        assert body["fields"]["summary"] == "Brute force on web-1"
        return httpx.Response(201, json={"id": "10001", "key": "SEC-42"})

    out, _ = run("jira_issue", {"base_url": "https://acme.jira.test", "email": "bot@acme.test", "project": "SEC",
                                "issue_type": "Task"},
                 {"api_token": "tok"}, {"summary": "{{ alert.title }}", "description": "Case {{ case.id }}"}, jira)
    assert out.ok and out.output == {"ticket": "SEC-42", "url": "https://acme.jira.test/browse/SEC-42",
                                     "system": "jira"}


def test_github_creates_an_issue():
    def gh(request):
        assert request.url.path == "/repos/acme/secops/issues"
        assert request.headers["authorization"] == "Bearer ghtok"
        return httpx.Response(201, json={"number": 7, "html_url": "https://github.test/acme/secops/issues/7"})

    out, _ = run("github_issue", {"repo": "acme/secops", "base_url": "https://api.github.test"}, {"token": "ghtok"},
                 {"title": "{{ alert.title }}", "body": "x", "labels": ["security"]}, gh)
    assert out.ok and out.output["ticket"] == "acme/secops#7"


def test_pagerduty_opsgenie_teams_and_webhook_payloads():
    out, reqs = run("pagerduty", {"base_url": "https://events.pd.test"}, {"routing_key": "rk"},
                    {"summary": "{{ alert.title }}", "severity": "{{ alert.severity }}"})
    body = json.loads(reqs[0].content)
    assert out.ok and body["routing_key"] == "rk" and body["event_action"] == "trigger"
    assert body["payload"]["severity"] == "error"  # PagerDuty has no "high"
    out, reqs = run("opsgenie", {"base_url": "https://api.og.test"}, {"api_key": "ok"},
                    {"message": "{{ alert.title }}", "priority": "P2"})
    assert out.ok and reqs[0].headers["authorization"] == "GenieKey ok" and reqs[0].url.path == "/v2/alerts"
    out, reqs = run("teams", {}, {"webhook_url": "https://teams.test/webhook"}, {"text": "{{ alert.title }}"})
    assert out.ok and "Brute force" in reqs[0].content.decode()
    out, reqs = run("webhook", {"url": "https://hooks.test/x", "method": "PUT"}, {"signing_secret": "k"},
                    {"body": {"alert": "{{ alert.id }}"}})
    assert out.ok and reqs[0].method == "PUT" and reqs[0].headers["x-logforge-signature"].startswith("sha256=")
    assert json.loads(reqs[0].content) == {"alert": "a1"}


def test_a_failing_service_is_reported_not_raised():
    out, _ = run("slack", {}, {"webhook_url": "https://hooks.slack.test/x"}, {"text": "hi"},
                 lambda r: httpx.Response(500, text="boom"))
    assert not out.ok and "500" in out.error


def test_missing_config_and_unknown_kinds_are_errors():
    with pytest.raises(actions.ActionError, match="api_token"):
        actions.validate("jira_issue", {"base_url": "https://x.test", "email": "a@b.c", "project": "SEC"}, {})
    with pytest.raises(actions.ActionError, match="kind"):
        actions.validate("fax", {}, {})


def test_containment_actions_are_marked():
    assert actions.KINDS["containment_webhook"].containment is True
    assert actions.KINDS["slack"].containment is False
