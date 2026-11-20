"""
Archive search (Phase 12): LogforgeQL over a tenant's Parquet archives.

The query compiles as usual (the tenant and the window are bound in the
innermost SELECT), but reads the tenant's archived days for the window
through the `logforge_archive` named collection instead of logs_raw_mt. Only
the days in the manifest are read, by exact object key.

    {"query": "error | stats count() by service", "source": "archive",
     "start_time": "2025-12-01T00:00:00Z", "end_time": "2026-02-01T00:00:00Z"}
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

import storage_tiers as st

COLLECTION = "logforge_archive"
MAX_WINDOW_DAYS = int(os.getenv("LOGFORGE_MAX_ARCHIVE_WINDOW_DAYS", "366"))


def source(tenant_id: str, data_type: str, days: Iterable[date]) -> str:
    """The s3() table function reading exactly these days' archives."""
    days = sorted(set(days))
    if not days:
        raise ValueError("no archived days")
    st.archive_key(tenant_id, data_type, days[0])  # validates the path parts
    names = [f"{day:%Y/%m/%d}" for day in days]
    glob = names[0] if len(names) == 1 else "{" + ",".join(names) + "}"
    return f"s3({COLLECTION}, filename = '{tenant_id}/{data_type}/{glob}.parquet', format = 'Parquet')"


def days_in(archived: Dict[date, Any], start: datetime, end: datetime) -> List[date]:
    return sorted(day for day in archived if start.date() <= day <= end.date())


PLACEHOLDER = "_logforge_archive_source_"


def compile_archive(query: str, tenant_id: str, days: List[date], start: datetime, end: datetime,
                    variables: Optional[Dict[str, Any]] = None, lookups=None):
    """Compile against a placeholder table name (the compiler accepts only
    plain names), then read the archives in its place."""
    import dataclasses

    from logql_pipeline import compile_pipeline

    compiled = compile_pipeline(query, customer_id=tenant_id, start=start, end=end, table=PLACEHOLDER,
                                variables=variables or {}, lookups=lookups, rollup=False)
    return dataclasses.replace(compiled, sql=compiled.sql.replace(PLACEHOLDER, source(tenant_id, "logs", days)))
