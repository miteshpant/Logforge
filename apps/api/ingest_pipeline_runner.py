"""
Running ingest pipelines (Phase 4).

context_for(tenant) builds what processors look up: the operator's GeoIP
ranges and asset/user tables (enrichment_processors) and the tenant's
threat-intel indicator sets (threat_intel_store).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

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
