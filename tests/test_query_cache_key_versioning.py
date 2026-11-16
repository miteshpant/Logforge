"""
The query result cache key must change when the query engine or schema does.

Results were cached for 5 minutes keyed by request body only, so after a deploy
that fixed or changed query compilation the old (possibly wrong) results kept
being served until the TTL ran out -- seen during the QA run.
"""

from services import query_service
from services.query_service import QueryService


def _key(monkeypatch, fingerprint):
    monkeypatch.setattr(query_service, "ENGINE_FINGERPRINT", fingerprint)
    svc = QueryService.__new__(QueryService)
    return svc._generate_cache_key({"query": "error", "limit": 10}, "tenant-1")


def test_key_changes_with_engine_fingerprint(monkeypatch):
    assert _key(monkeypatch, "v1") != _key(monkeypatch, "v2")


def test_key_is_stable_for_same_inputs(monkeypatch):
    assert _key(monkeypatch, "v1") == _key(monkeypatch, "v1")


def test_fingerprint_reflects_engine_source(monkeypatch, tmp_path):
    api = tmp_path / "api"
    (api / "services").mkdir(parents=True)
    (api / "query_engine.py").write_text("A")
    (api / "logql.py").write_text("B")
    monkeypatch.setattr(query_service, "__file__", str(api / "services" / "query_service.py"))
    first = query_service._engine_fingerprint()
    (api / "query_engine.py").write_text("A changed")
    assert query_service._engine_fingerprint() != first
