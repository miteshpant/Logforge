"""
Built-in pipelines (Phase 4): the formats Logforge parses out of the box,
expressed as ordinary pipelines (filled in by P4.5). Tenants can select them
by name, copy them, or shadow them with a pipeline of the same id.
"""

from __future__ import annotations

from typing import Any, Dict, List

BUILTIN_DEFINITIONS: List[Dict[str, Any]] = []


def builtin_records():
    from pipeline_store import PipelineRecord

    return {r.id: r for r in (PipelineRecord.from_dict({**d, "builtin": True}) for d in BUILTIN_DEFINITIONS)}
