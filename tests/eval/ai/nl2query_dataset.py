#!/usr/bin/env python3
"""
Generate the natural-language -> LogforgeQL evaluation sets (Phase 9), one per
schema, from templates over the values in the Phase 6 seeded week of events
(tests/test_analyst_questions_live.make_events):

    datasets/nl2query_auth.jsonl   auth and VPN sign-ins (outcome, user, source IP, country)
    datasets/nl2query_http.jsonl   web and API requests (status, method, path, duration, bytes, agent)
    datasets/nl2query_dns.jsonl    DNS queries (domain, host)

Each item: {id, schema, question, expected_query}. Questions come in several
phrasings per template; values are drawn from the seed so every expected
query returns rows. Every expected query is compiled here, and executed
against the seeded data by tests/test_nl2query_eval_live.py.

Limitation: templated questions are more regular than an analyst's; the
set measures the shapes analysts ask most, not open-ended phrasing.

    python tests/eval/ai/nl2query_dataset.py     # rewrites the three files
"""

from __future__ import annotations

import itertools
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "apps" / "api"))

USERS = [f"u{i:03d}" for i in (3, 9, 17, 25, 33, 42, 50, 58, 66, 77, 84, 91, 95, 99)]
HOSTS = ["h01", "h02", "h04", "h07", "h09", "h12", "h14", "h16", "h18", "h19"]
OK_USERS = [u for u in USERS if int(u[1:]) < 90]   # u090+ only ever fail to log in (the seed's attackers)
IPS = ["203.0.113.1", "203.0.113.4", "203.0.113.9", "203.0.113.15", "10.0.3.4", "10.0.12.7"]
COUNTRIES = {"US": "the US", "DE": "Germany", "IN": "India", "BR": "Brazil", "GB": "the UK", "CN": "China"}
DOMAINS = ["api.github.com", "login.microsoftonline.com", "pool.ntp.org", "cdn.jsdelivr.net", "example.com",
           "x7f3k.badcdn.net"]
AGENTS = {"curl": "curl/8.4", "python": "python-requests/2.31", "sqlmap": "sqlmap/1.7"}
METHODS = ["GET", "POST", "PUT"]
STATUSES = [404, 500, 503]

AUTH = 'service in ["auth", "vpn"]'
FAIL = 'attrs.outcome = "failure"'
OK = 'attrs.outcome = "success"'
HTTP = 'service in ["api", "web"]'
DNS = 'service = "dns"'


def _items(templates):
    """templates: (phrasings, query, {slot: values}). A value is a plain
    string, or (shown in the question, used in the query)."""
    out = []
    for phrasings, query, slots in templates:
        names = list(slots)
        for values in itertools.product(*(slots[n] for n in names)) if names else [()]:
            q = query
            filled = []
            for name, value in zip(names, values):
                shown, actual = value if isinstance(value, tuple) else (value, value)
                q = q.replace("{" + name + "}", str(actual))
                filled.append((name, shown))
            for phrasing in phrasings:
                question = phrasing
                for name, shown in filled:
                    question = question.replace("{" + name + "}", str(shown))
                out.append((question, q))
    return out


def auth_items():
    countries = [(name, code) for code, name in COUNTRIES.items()]
    return _items([
        (["How many failed logins were there?", "Count the failed sign-ins", "Number of failed logins"],
         f"| where {AUTH} and {FAIL} | stats count() as count", {}),
        (["How many successful logins were there?", "Count successful sign-ins"],
         f"| where {AUTH} and {OK} | stats count() as count", {}),
        (["Failed logins per {by}", "How many failed logins per {by}?", "Count failed sign-ins by {by}"],
         f"| where {AUTH} and {FAIL} | stats count() as count by {{by}}",
         {"by": [("user", "user_id"), ("source IP", "src_ip"), ("country", "attrs.country"), ("host", "host")]}),
        (["Which users failed to log in the most?", "Top 10 users with failed logins",
          "Users with the most failed sign-ins"],
         f"| where {AUTH} and {FAIL} | top limit=10 user_id", {}),
        (["Which source IPs had the most failed logins?", "Top 10 IPs by failed logins"],
         f"| where {AUTH} and {FAIL} | top limit=10 src_ip", {}),
        (["Failed logins for user {user}", "How many times did {user} fail to log in?",
          "Show failed sign-ins of {user}"],
         f'| where {AUTH} and {FAIL} and user_id = "{{user}}" | stats count() as count', {"user": USERS}),
        (["Successful logins of {user} by country", "Where did {user} log in from?"],
         f'| where {AUTH} and {OK} and user_id = "{{user}}" | stats count() as count by attrs.country',
         {"user": OK_USERS}),
        (["Logins from {country}", "How many sign-ins came from {country}?"],
         f'| where {AUTH} and attrs.country = "{{country}}" | stats count() as count', {"country": countries}),
        (["How many distinct users logged in successfully from {country}?",
          "Number of different users signing in from {country}"],
         f'| where {AUTH} and {OK} and attrs.country = "{{country}}" | stats dc(user_id) as users',
         {"country": countries}),
        (["Failed logins from {ip}", "How many failed logins came from {ip}?"],
         f'| where {AUTH} and {FAIL} and src_ip = "{{ip}}" | stats count() as count', {"ip": IPS}),
        (["Which users did {ip} try to log in as?", "Users targeted from {ip}"],
         f'| where {AUTH} and {FAIL} and src_ip = "{{ip}}" | stats count() as count by user_id',
         {"ip": [ip for ip in IPS if ip.startswith("203.")]}),
        (["Failed logins over time", "Trend of failed sign-ins per day"],
         f"| where {AUTH} and {FAIL} | timechart span=1d count()", {}),
        (["Logins per outcome", "Break down sign-ins by outcome"],
         f"| where {AUTH} | stats count() as count by attrs.outcome", {}),
        (["Failed logins on host {host}", "How many failed logins hit {host}?"],
         f'| where {AUTH} and {FAIL} and host = "{{host}}" | stats count() as count', {"host": HOSTS}),
        (["Failed logins of {user} per source IP", "Where did {user}'s failed logins come from?"],
         f'| where {AUTH} and {FAIL} and user_id = "{{user}}" | stats count() as count by src_ip', {"user": USERS}),
        (["How many times did {user} log in successfully?", "Successful sign-ins of {user}"],
         f'| where {AUTH} and {OK} and user_id = "{{user}}" | stats count() as count', {"user": USERS}),
        (["Successful logins from {ip}", "Which users logged in successfully from {ip}?"],
         f'| where {AUTH} and {OK} and src_ip = "{{ip}}" | stats count() as count by user_id', {"ip": IPS}),
        (["Logins on host {host} by outcome", "Sign-in outcomes on {host}"],
         f'| where {AUTH} and host = "{{host}}" | stats count() as count by attrs.outcome', {"host": HOSTS}),
    ])


def http_items():
    return _items([
        (["How many requests returned a server error?", "Count 5xx responses", "Number of server errors"],
         f"| where {HTTP} and status >= 500 | stats count() as count", {}),
        (["Requests with status {status}", "How many {status} responses were there?", "Count HTTP {status}s"],
         f"| where {HTTP} and status = {{status}} | stats count() as count", {"status": STATUSES}),
        (["Requests per {by}", "How many requests per {by}?", "Break down requests by {by}"],
         f"| where {HTTP} | stats count() as count by {{by}}",
         {"by": [("status", "status"), ("method", "attrs.method"), ("host", "host"), ("service", "service")]}),
        (["Server errors per {by}", "5xx responses by {by}"],
         f"| where {HTTP} and status >= 500 | stats count() as count by {{by}}",
         {"by": [("host", "host"), ("method", "attrs.method"), ("service", "service")]}),
        (["How many {method} requests were there?", "Count {method} requests"],
         f'| where {HTTP} and attrs.method = "{{method}}" | stats count() as count', {"method": METHODS}),
        (["Average response time of {method} requests", "Mean duration of {method} requests"],
         f'| where {HTTP} and attrs.method = "{{method}}" | stats avg(attrs.duration_ms) as avg_ms',
         {"method": METHODS}),
        (["95th percentile response time per service", "p95 duration by service"],
         f"| where {HTTP} | stats p95(attrs.duration_ms) as p95 by service", {}),
        (["Total bytes sent per host", "Sum of bytes by host"],
         f"| where {HTTP} | stats sum(attrs.bytes) as bytes by host", {}),
        (["Most common user agents", "Top 10 user agents"],
         f"| where {HTTP} | top limit=10 attrs.user_agent", {}),
        (["Requests from {agent}", "How many requests came from {agent}?"],
         f'| where {HTTP} and attrs.user_agent = "{{agent}}" | stats count() as count',
         {"agent": [(k, v) for k, v in AGENTS.items()]}),
        (["Requests from {agent} per host", "Which hosts did {agent} hit?"],
         f'| where {HTTP} and attrs.user_agent = "{{agent}}" | stats count() as count by host',
         {"agent": [(k, v) for k, v in AGENTS.items()]}),
        (["Requests on host {host}", "How many requests did {host} serve?"],
         f'| where {HTTP} and host = "{{host}}" | stats count() as count', {"host": HOSTS}),
        (["Server errors on host {host}", "5xx responses from {host}"],
         f'| where {HTTP} and status >= 500 and host = "{{host}}" | stats count() as count', {"host": HOSTS}),
        (["Server errors over time", "Daily count of 5xx responses"],
         f"| where {HTTP} and status >= 500 | timechart span=1d count()", {}),
        (["Requests from {ip}", "How many requests came from {ip}?"],
         f'| where {HTTP} and src_ip = "{{ip}}" | stats count() as count', {"ip": IPS}),
        (["Status codes returned by {host}", "Requests on {host} by status"],
         f'| where {HTTP} and host = "{{host}}" | stats count() as count by status', {"host": HOSTS}),
        (["Average response time on {host}", "Mean duration of requests served by {host}"],
         f'| where {HTTP} and host = "{{host}}" | stats avg(attrs.duration_ms) as avg_ms', {"host": HOSTS}),
        (["Requests from {user}", "How many requests did {user} make?"],
         f'| where {HTTP} and user_id = "{{user}}" | stats count() as count', {"user": USERS}),
        (["Status {status} responses per host", "Which hosts returned {status}?"],
         f"| where {HTTP} and status = {{status}} | stats count() as count by host", {"status": STATUSES}),
        (["Requests per path on {host}", "Which paths did {host} serve?"],
         f'| where {HTTP} and host = "{{host}}" | stats count() as count by attrs.uri', {"host": HOSTS}),
        (["{method} requests per status", "Status codes of {method} requests"],
         f'| where {HTTP} and attrs.method = "{{method}}" | stats count() as count by status', {"method": METHODS}),
    ])


def dns_items():
    return _items([
        (["How many DNS queries were there?", "Count the DNS lookups"], f"| where {DNS} | stats count() as count", {}),
        (["Most queried domains", "Top 10 domains looked up", "Which domains were queried most?"],
         f"| where {DNS} | top limit=10 attrs.query", {}),
        (["How many times was {domain} queried?", "Lookups of {domain}", "Count DNS queries for {domain}"],
         f'| where {DNS} and attrs.query = "{{domain}}" | stats count() as count', {"domain": DOMAINS}),
        (["Which hosts queried {domain}?", "Hosts that looked up {domain}"],
         f'| where {DNS} and attrs.query = "{{domain}}" | stats count() as count by host', {"domain": DOMAINS}),
        (["DNS queries per host", "How many lookups did each host make?"],
         f"| where {DNS} | stats count() as count by host", {}),
        (["How many different domains did each host query?", "Distinct domains per host"],
         f"| where {DNS} | stats dc(attrs.query) as domains by host", {}),
        (["What did host {host} look up?", "Domains queried by {host}", "DNS lookups from {host} by domain"],
         f'| where {DNS} and host = "{{host}}" | stats count() as count by attrs.query', {"host": HOSTS}),
        (["How many DNS queries came from {host}?", "Lookups made by {host}"],
         f'| where {DNS} and host = "{{host}}" | stats count() as count', {"host": HOSTS}),
        (["DNS queries over time", "Daily DNS lookups"], f"| where {DNS} | timechart span=1d count()", {}),
        (["Which hosts queried {domain} most?", "Top hosts looking up {domain}"],
         f'| where {DNS} and attrs.query = "{{domain}}" | top limit=10 host', {"domain": DOMAINS}),
        (["DNS queries by user {user}", "What domains did {user} look up?"],
         f'| where {DNS} and user_id = "{{user}}" | stats count() as count by attrs.query', {"user": USERS}),
        (["DNS warnings per host", "Hosts with DNS warnings"],
         f'| where {DNS} and level = "warn" | stats count() as count by host', {}),
        (["How many DNS queries did {user} make?", "Lookups by user {user}"],
         f'| where {DNS} and user_id = "{{user}}" | stats count() as count', {"user": USERS}),
        (["How many distinct domains did {host} query?", "Number of different domains looked up by {host}"],
         f'| where {DNS} and host = "{{host}}" | stats dc(attrs.query) as domains', {"host": HOSTS}),
        (["Which users looked up {domain}?", "Users querying {domain}"],
         f'| where {DNS} and attrs.query = "{{domain}}" | stats count() as count by user_id', {"domain": DOMAINS}),
        (["Daily lookups of {domain}", "{domain} queries over time"],
         f'| where {DNS} and attrs.query = "{{domain}}" | timechart span=1d count()', {"domain": DOMAINS}),
    ])


def build():
    import logql_pipeline as lp

    end = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
    sets = {"auth": auth_items(), "http": http_items(), "dns": dns_items()}
    for schema, items in sets.items():
        rows = []
        seen = set()
        for question, query in items:
            if (question, query) in seen:
                continue
            seen.add((question, query))
            lp.compile_pipeline(query, customer_id="dataset-check", start=end - timedelta(days=7), end=end)
            rows.append({"id": f"{schema}-{len(rows) + 1:03d}", "schema": schema, "question": question,
                         "expected_query": query})
        random.Random(7).shuffle(rows)
        path = HERE / "datasets" / f"nl2query_{schema}.jsonl"
        path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
        print(f"{schema}: {len(rows)} items -> {path.relative_to(REPO)}")


if __name__ == "__main__":
    build()
