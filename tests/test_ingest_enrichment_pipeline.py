"""
Ingest enrichment runs inside smart ingestion (Phase 3): the stored log
entries and the normalized events handed to detection both carry
attrs.threat, from one lookup per event.
"""

import asyncio

import threat_intel_store
from services.smart_ingestion_service import SmartIngestionService
from test_ingest_enrichment import index


def test_stored_and_normalized_events_carry_the_stamp(monkeypatch):
    monkeypatch.setattr(threat_intel_store, "_index", index())
    service = SmartIngestionService()
    raw = [{"service": "fw", "msg": "conn", "src_ip": "10.0.1.15", "attrs": {"dst_ip": "162.243.103.246"}},
           {"service": "fw", "msg": "conn", "src_ip": "10.0.1.15", "attrs": {"dst_ip": "93.184.216.34"}}]
    result = asyncio.run(service.process_logs_with_normalization(raw, "acme", "json"))
    assert result.log_entries[0].attrs["threat"]["indicators"][0]["value"] == "162.243.103.246"
    assert "threat" not in (result.log_entries[1].attrs or {})
    normalized = result.normalized_data[0]
    attrs = normalized.get("attrs") or {}
    assert attrs.get("threat", {}).get("matched") is True
