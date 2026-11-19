"""
Running ingest pipelines (Phase 4).

context_for(tenant) builds what processors look up: the operator's GeoIP
ranges and asset/user tables (enrichment_processors) and the tenant's
threat-intel indicator sets (threat_intel_store).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog

from pipeline_processors import ProcessorContext

logger = structlog.get_logger(__name__)


async def context_for(tenant_id: str, now: Optional[datetime] = None) -> ProcessorContext:
    from enrichment_processors import get_enrichers

    now = now or datetime.now(timezone.utc)
    enrichers = get_enrichers()
    tables = {}
    if enrichers.assets:
        tables["assets"] = enrichers.assets.rows
    if enrichers.users:
        tables["users"] = enrichers.users.rows
    intel = {}
    try:
        from threat_intel_store import get_indicator_index

        intel = await get_indicator_index().tenant_set(tenant_id, now)
    except Exception as e:  # intel is optional for pipelines
        logger.warning(f"Threat intel unavailable for pipelines of {tenant_id}: {e}")
    return ProcessorContext(tenant_id=tenant_id, now=now, geo=enrichers.geo, tables=tables, intel=intel)


# -- running at ingest ---------------------------------------------------------

PIPELINE_FIELD = "logforge_pipeline"  # the pipeline a shipper asked for (X-Logforge-Pipeline header or field)


def _registry():
    from pipeline_store import get_pipeline_registry

    return get_pipeline_registry()


def _dlq():
    from pipeline_dlq import PipelineDLQ

    return PipelineDLQ()


async def _publish_dead_letters(tenant_id: str, entries: List[Dict[str, Any]]) -> None:
    """Best effort: announce dead letters on the event bus (logs.parsing.failed)."""
    try:
        import dependencies

        publisher = getattr(dependencies, "log_event_publisher", None)
        if publisher is None:
            return
        for entry in entries[:100]:
            await publisher.publish_parsing_failed(
                customer_id=tenant_id, log_info={"log_id": entry["id"], "content": entry["event"].get("msg", "")},
                error_details={"error_message": entry["error"], "error_type": "pipeline_failure"},
                parser_name=f"pipeline:{entry['pipeline_id']}")
    except Exception as e:
        logger.warning(f"Dead-letter events not published for {tenant_id}: {e}")


def _dead_letter(record_id: str, version: int, error: Dict[str, Any], snapshot: str, now: datetime) -> Dict[str, Any]:
    return {"id": str(uuid.uuid4()), "pipeline_id": record_id, "pipeline_version": version,
            "processor": error.get("processor", ""), "processor_index": error.get("index", -1),
            "tag": error.get("tag", ""), "error": error["message"][:4000], "event": json.loads(snapshot),
            "failed_at": now}


async def run_ingest_pipelines(tenant_id: str, raw_logs: List[Dict[str, Any]], docs: List[Dict[str, Any]],
                               registry=None, dlq=None, now: Optional[datetime] = None
                               ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Run each event through its pipeline. Returns (events to store, summary).

    `raw_logs[i]` is the event as received and `docs[i]` the same event after
    metadata enrichment; failures dead-letter the received form."""
    summary = {"events": len(docs), "processed": 0, "dropped": 0, "failed": 0}
    registry = registry or _registry()
    requested_any = any(isinstance(d, dict) and d.get(PIPELINE_FIELD) for d in docs)
    try:
        router = await registry.router(tenant_id)
    except Exception as e:
        logger.error(f"Pipelines unavailable for {tenant_id}; storing events unprocessed: {e}")
        for doc in docs:
            doc.pop(PIPELINE_FIELD, None)
        return docs, summary
    if not requested_any and not router.ordered and router.default is None:
        return docs, summary  # nothing routes here: no cost

    now = now or datetime.now(timezone.utc)
    ctx = None
    kept: List[Dict[str, Any]] = []
    dead: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []  # (dead-letter entry, reason for attrs)
    for raw, doc in zip(raw_logs, docs):
        requested = doc.pop(PIPELINE_FIELD, None)
        record = router.select(doc, requested)
        if record is None and not requested:
            kept.append(doc)
            continue
        snapshot = json.dumps({k: v for k, v in raw.items() if k != PIPELINE_FIELD}, default=str)
        summary["processed"] += 1
        if record is None:
            summary["failed"] += 1
            error = {"message": f"pipeline {requested!r} not found or disabled"}
            dead.append((_dead_letter(requested, 0, error, snapshot, now),
                         {"pipeline": requested, "processor": "", "error": error["message"]}))
            continue
        if ctx is None:
            ctx = await context_for(tenant_id, now)
        result = record.pipeline.run(doc, ctx, stats=registry.stats(tenant_id, record))
        if result.status == "dropped":
            summary["dropped"] += 1
            continue
        if result.status == "failed":
            summary["failed"] += 1
            dead.append((_dead_letter(record.id, record.version, result.error, snapshot, now),
                         {"pipeline": record.id, "processor": result.error.get("processor", ""),
                          "error": result.error["message"]}))
            continue
        out = result.doc
        attrs = out.get("attrs") if isinstance(out.get("attrs"), dict) else {}
        out["attrs"] = attrs
        route = out.pop("_route", None)
        if route:
            attrs["route"] = route
        attrs["pipeline"] = {"id": record.id, "version": record.version}
        kept.append(out)

    if dead:
        entries = [entry for entry, _ in dead]
        try:
            await (dlq or _dlq()).add(tenant_id, entries)
            await _publish_dead_letters(tenant_id, entries)
        except Exception as e:
            # The dead-letter queue is down: store the originals rather than lose them.
            logger.error(f"Dead-letter queue unavailable for {tenant_id}; storing {len(dead)} failed events "
                         f"unprocessed: {e}")
            for entry, info in dead:
                original = dict(entry["event"])
                original["attrs"] = {**(original.get("attrs") or {}), "pipeline_error": info}
                original.setdefault("customer_id", tenant_id)
                kept.append(original)
    return kept, summary
