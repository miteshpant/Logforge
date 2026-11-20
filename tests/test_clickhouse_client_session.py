"""The shared ClickHouse client is used from many threads at once (requests, to_thread
calls, background workers). A client pinned to one ClickHouse session makes the server
reject overlapping queries ("concurrent queries within the same session"), so the
shared client must never get a session id, whatever was imported first."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import dependencies  # noqa: E402


def test_shared_client_has_no_session(monkeypatch):
    seen = {}

    def fake_get_client(**kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(dependencies, "get_client", fake_get_client)
    monkeypatch.setattr(dependencies, "clickhouse_client", None)
    monkeypatch.setattr(dependencies, "config", {
        "clickhouse_host": "h", "clickhouse_port": 8123, "clickhouse_user": "u",
        "clickhouse_password": "p", "clickhouse_database": "d"})
    import clickhouse_connect

    clickhouse_connect.common.set_setting("autogenerate_session_id", True)  # library default
    assert dependencies.get_clickhouse_client() is not None
    assert clickhouse_connect.common.get_setting("autogenerate_session_id") is False
