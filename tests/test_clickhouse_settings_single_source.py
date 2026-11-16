"""
ClickHouse connection settings have a single source of truth.

They used to be re-declared in six modules with different defaults
(app_config: localhost / default / ""; elsewhere: clickhouse / logforge /
logforge123), and the query engine hard-coded clickhouse:8123, ignoring
CLICKHOUSE_HOST/PORT entirely. With a variable unset, parts of the API connected
to different servers or as different users.
"""

import re
from pathlib import Path

API = Path(__file__).resolve().parent.parent / "apps" / "api"


def test_defaults_match_the_compose_stack(monkeypatch):
    from app_config import clickhouse_settings, load_config

    for var in ("CLICKHOUSE_HOST", "CLICKHOUSE_PORT", "CLICKHOUSE_USER",
                "CLICKHOUSE_PASSWORD", "CLICKHOUSE_DATABASE"):
        monkeypatch.delenv(var, raising=False)
    assert clickhouse_settings() == {
        "host": "clickhouse", "port": 8123, "username": "logforge",
        "password": "logforge123", "database": "logforge",
    }
    cfg = load_config()
    assert (cfg["clickhouse_host"], cfg["clickhouse_user"]) == ("clickhouse", "logforge")


def test_environment_overrides_apply(monkeypatch):
    from app_config import clickhouse_settings

    monkeypatch.setenv("CLICKHOUSE_HOST", "localhost")
    monkeypatch.setenv("CLICKHOUSE_PORT", "8124")
    s = clickhouse_settings()
    assert (s["host"], s["port"]) == ("localhost", 8124)


def test_no_module_redeclares_clickhouse_defaults():
    pattern = re.compile(r"""getenv\(\s*['"]CLICKHOUSE_(HOST|PORT|USER|PASSWORD|DATABASE)['"]\s*,""")
    offenders = [
        str(p.relative_to(API))
        for p in API.rglob("*.py")
        if p.name != "app_config.py" and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_query_engine_honours_host_and_port(monkeypatch):
    import query_engine

    captured = {}
    monkeypatch.setattr(query_engine, "_query_engine_instance", None)
    monkeypatch.setenv("CLICKHOUSE_HOST", "localhost")
    monkeypatch.setenv("CLICKHOUSE_PORT", "8124")
    import clickhouse_connect

    monkeypatch.setattr(clickhouse_connect, "get_client", lambda **kw: captured.update(kw) or object())
    query_engine.get_query_engine()
    assert (captured["host"], captured["port"]) == ("localhost", 8124)
