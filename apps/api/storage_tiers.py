"""
Storage tiers and retention (Phase 12).

    hot      ClickHouse, local disk          the newest `hot_days` (deployment-wide)
    warm     ClickHouse, S3-backed volume    still searchable, cheaper per GB
    cold     Parquet files in object storage one file per tenant, data type and day

ClickHouse parts mix tenants, so moving data from hot to warm is a table TTL
the same for everyone (`hot_days`). What each tenant chooses, per data type:

    searchable_days   days kept in ClickHouse (hot + warm)
    archive_days      days each day's Parquet archive is kept (0: no archive)

A day older than `searchable_days` is archived, its archive is read back and
counted, and only when the counts match is the day deleted from ClickHouse.
Archives older than `archive_days` expire. The table TTL deletes everything
past `max_searchable_days`, a backstop if the retention job doesn't run.

`plan` decides; `tier_manager.TierManager` carries the plan out.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "storage_tiers.yml"
_SAFE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class DataType:
    name: str
    table: str
    ts: str


@dataclass(frozen=True)
class Policy:
    data_type: str
    searchable_days: int
    archive_days: int  # 0: no archive


@dataclass
class Config:
    hot_days: int
    max_searchable_days: int
    max_archive_days: int
    data_types: Dict[str, DataType]
    defaults: Dict[str, Policy]
    warm_policy: str = "tiered"
    archive_bucket: str = "logforge-archive"
    warm_bucket: str = "logforge-warm"
    backup_bucket: str = "logforge-backups"
    prices: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    kind: str  # archive | delete | expire
    data_type: str
    day: date
    rows: int = 0


_ORDER = {"archive": 0, "delete": 1, "expire": 2}


def load_config(path: Optional[Path] = None) -> Config:
    raw = yaml.safe_load(Path(path or os.getenv("LOGFORGE_STORAGE_TIERS", CONFIG_PATH)).read_text())
    types = {name: DataType(name, spec["table"], spec["ts"]) for name, spec in raw["data_types"].items()}
    defaults = {name: Policy(name, int(spec["searchable_days"]), int(spec["archive_days"]))
                for name, spec in raw["defaults"].items()}
    return Config(hot_days=int(raw["hot_days"]), max_searchable_days=int(raw["max_searchable_days"]),
                  max_archive_days=int(raw["max_archive_days"]), data_types=types, defaults=defaults,
                  warm_policy=raw.get("warm_policy", "tiered"),
                  archive_bucket=os.getenv("LOGFORGE_ARCHIVE_BUCKET", raw.get("archive_bucket", "logforge-archive")),
                  warm_bucket=raw.get("warm_bucket", "logforge-warm"),
                  backup_bucket=os.getenv("LOGFORGE_BACKUP_BUCKET", raw.get("backup_bucket", "logforge-backups")),
                  prices={k: float(v) for k, v in (raw.get("prices") or {}).items()})


def validate(policy: Policy, cfg: Config) -> Policy:
    if policy.data_type not in cfg.data_types:
        raise PolicyError(f"unknown data type {policy.data_type!r} (one of {', '.join(cfg.data_types)})")
    if not 1 <= policy.searchable_days <= cfg.max_searchable_days:
        raise PolicyError(f"searchable_days must be 1 to {cfg.max_searchable_days}")
    if policy.archive_days and not policy.searchable_days <= policy.archive_days <= cfg.max_archive_days:
        raise PolicyError(f"archive_days must be 0 (no archive) or from searchable_days to {cfg.max_archive_days}")
    if policy.archive_days < 0:
        raise PolicyError("archive_days must be 0 (no archive) or positive")
    return policy


def effective(stored: Iterable[Policy], cfg: Config) -> Dict[str, Policy]:
    """The tenant's policy per data type: what it chose, else the default."""
    out = dict(cfg.defaults)
    for policy in stored:
        if policy.data_type in cfg.data_types:
            out[policy.data_type] = policy
    return out


def plan(policy: Policy, today: date, days: Dict[date, int], archived: Dict[date, int],
         held: Optional[Set[date]] = None) -> List[Action]:
    """
    The actions for one tenant and data type.

    days: rows per day still in ClickHouse; archived: rows per archived day;
    held: days rehydrated from the archive and kept until their hold ends.
    """
    actions: List[Action] = []
    age = lambda day: today.toordinal() - day.toordinal()  # noqa: E731
    deleted = set()
    for day, rows in days.items():
        if age(day) < policy.searchable_days or day in (held or ()):
            continue
        if not policy.archive_days:
            actions.append(Action("delete", policy.data_type, day, rows))
            deleted.add(day)
        elif archived.get(day) == rows:
            actions.append(Action("delete", policy.data_type, day, rows))
            deleted.add(day)
        else:
            actions.append(Action("archive", policy.data_type, day, rows))
    keep = policy.archive_days or policy.searchable_days
    for day, rows in archived.items():
        if age(day) >= keep and (day not in days or day in deleted):
            actions.append(Action("expire", policy.data_type, day, rows))
    return sorted(actions, key=lambda a: (a.day, _ORDER[a.kind]))


def archive_key(tenant_id: str, data_type: str, day: date) -> str:
    for part in (tenant_id, data_type):
        if not _SAFE.match(part) or part in (".", ".."):
            raise PolicyError(f"unsafe archive path part {part!r}")
    return f"{tenant_id}/{data_type}/{day:%Y/%m/%d}.parquet"


def table_ttl(data_type: DataType, cfg: Config, warm: bool = True) -> str:
    at = f"toDateTime({data_type.ts})"
    parts = []
    if warm:
        parts.append(f"{at} + toIntervalDay({cfg.hot_days}) TO VOLUME 'warm'")
    parts.append(f"{at} + toIntervalDay({cfg.max_searchable_days}) DELETE")
    return ", ".join(parts)
