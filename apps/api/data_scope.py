"""
Data scopes (Phase 14): which services' logs a request may read.

A user whose custom roles carry a data scope reads only those services'
logs. The middleware puts the scope in a context variable for the request;
every ClickHouse query the request makes (search, LogforgeQL, dashboards,
the field catalogue, entities, the AI tools...) then carries
`additional_table_filters` for logs_raw_mt, so ClickHouse itself adds the
filter to every read of the table, in subqueries and joins too. Work outside
a request (ingest workers, schedulers) has no scope.

Services are exact names, or prefixes ending in `*` (`payments-*`).
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Optional, Tuple

TABLE = "logs_raw_mt"
_SCOPE: contextvars.ContextVar[Optional["DataScope"]] = contextvars.ContextVar("logforge_data_scope", default=None)


@dataclass(frozen=True)
class DataScope:
    services: Tuple[str, ...]


def _quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def filter_sql(services: Iterable[str]) -> str:
    exact = [s for s in services if not s.endswith("*")]
    prefixes = [s[:-1] for s in services if s.endswith("*")]
    parts = []
    if exact:
        parts.append(f"service IN ({', '.join(_quote(s) for s in exact)})")
    for p in prefixes:
        pattern = p.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        parts.append(f"service LIKE {_quote(pattern)}")
    return " OR ".join(parts) or "0"


def settings_for(scope: Optional[DataScope]) -> Dict[str, str]:
    if scope is None:
        return {}
    return {"additional_table_filters": "{" + _quote(TABLE) + ": " + _quote(filter_sql(scope.services)) + "}"}


def current() -> Optional[DataScope]:
    return _SCOPE.get()


def set_scope(scope: Optional[DataScope]) -> contextvars.Token:
    return _SCOPE.set(scope)


@contextmanager
def scoped(scope: Optional[DataScope]) -> Iterator[None]:
    token = _SCOPE.set(scope)
    try:
        yield
    finally:
        _SCOPE.reset(token)


def install(client_class=None) -> None:
    """Make every query of a ClickHouse client carry the current scope's filter (idempotent)."""
    if client_class is None:
        from clickhouse_connect.driver.httpclient import HttpClient as client_class
    original = client_class._validate_settings
    if getattr(original, "_logforge_scoped", False):
        return

    def _validate_settings(self, settings):
        extra = settings_for(_SCOPE.get())
        if extra:
            settings = {**(settings or {}), **extra}
        return original(self, settings)

    _validate_settings._logforge_scoped = True
    client_class._validate_settings = _validate_settings
