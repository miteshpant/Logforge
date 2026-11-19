"""
The common schema (Phase 5): OCSF field paths over today's Logforge fields.

config/schema/ocsf_mapping.yml is the published mapping. `ocsf.<path>` in a
rule or a query resolves at read time:

1. an explicit attrs.ocsf.<path>, set by a source-mapping pipeline;
2. otherwise the first non-empty field listed in `from` (a top-level column
   such as src_ip, or attrs.<key>), converted as the entry says.

Nothing extra is stored for events that only need the generic mapping.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

MAPPING_FILE = Path(__file__).resolve().parent / "config" / "schema" / "ocsf_mapping.yml"


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    return yaml.safe_load(MAPPING_FILE.read_text(encoding="utf-8"))


MAPPING: List[Dict[str, Any]] = _load()["fields"]
OCSF_VERSION: str = _load()["ocsf_version"]
BY_PATH: Dict[str, Dict[str, Any]] = {m["ocsf"]: m for m in MAPPING}

# Value conversions named in the mapping.
SEVERITY_IDS = {"trace": 1, "debug": 1, "info": 1, "information": 1, "informational": 1, "notice": 2, "low": 2,
                "warn": 3, "warning": 3, "medium": 3, "error": 4, "err": 4, "high": 4, "critical": 5, "crit": 5,
                "alert": 5, "emergency": 6, "fatal": 6}
SUCCESS = {"success", "succeeded", "successful", "ok", "accepted", "allow", "allowed", "passed", "true", "granted"}
FAILURE = {"failure", "failed", "fail", "denied", "deny", "rejected", "invalid", "error", "blocked", "false",
           "unauthorized", "forbidden"}


def status_id(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    if text in SUCCESS:
        return 1
    if text in FAILURE:
        return 2
    return 99


def _convert(value: Any, how: Optional[str]) -> Any:
    if how is None:
        return value
    if how == "epoch_ms":
        if isinstance(value, datetime):
            stamp = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return int(stamp.timestamp() * 1000)
        if isinstance(value, str):
            try:
                return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
            except ValueError:
                return None
        return value
    if how == "severity_id":
        return SEVERITY_IDS.get(str(value).strip().lower(), 0)
    if how == "status_id":
        return status_id(value)
    if how == "status_name":
        sid = status_id(value)
        return {1: "Success", 2: "Failure", 99: "Other"}.get(sid)
    if how in ("int", "nonzero_int"):
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return None if how == "nonzero_int" and number == 0 else number
    raise ValueError(f"unknown conversion {how!r} in {MAPPING_FILE.name}")


def _get(event: Dict[str, Any], dotted: str) -> Any:
    current: Any = event
    for part in dotted.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def is_mapped(path: str) -> bool:
    return path in BY_PATH


def resolve(event: Dict[str, Any], path: str) -> Any:
    """The value of `ocsf.<path>` for an event (None when absent)."""
    attrs = event.get("attrs") if isinstance(event.get("attrs"), dict) else {}
    explicit = _get(attrs.get("ocsf") or {}, path) if isinstance(attrs.get("ocsf"), dict) else None
    if explicit not in (None, ""):
        return explicit
    entry = BY_PATH.get(path)
    if entry is None:
        return None
    for source in entry.get("from") or []:
        value = _get(event, source)
        if value in (None, ""):
            continue
        converted = _convert(value, entry.get("convert"))
        if converted not in (None, ""):
            return converted
    return None
