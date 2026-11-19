"""
Lookup tables and managed lists (Phase 6).

A lookup is a small table a tenant uploads (a CSV export of users, assets,
known-good IPs, ...) or maintains as a list (a blocklist). LogforgeQL uses
them with `| lookup <name> <field>` (add the matching row's columns) and
`inlookup("<name>", field)` (is the value in the table?).

Storage (migration 021): metadata per version in lookup_tables_mt, rows per
version in lookup_rows_mt. An upload writes the new rows first and the
metadata last; queries read the version the metadata names, so a replacement
is atomic for readers. Older versions' rows are then deleted.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_ROWS = 100_000
MAX_COLUMNS = 32
MAX_BYTES = 10 * 1024 * 1024
MAX_VALUE = 4096
MAX_LOOKUPS = 200
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_INSERT_BATCH = 10_000


class LookupValidationError(ValueError):
    """A lookup that cannot be stored. The message is shown to the user."""


@dataclass
class LookupTable:
    name: str
    kind: str                  # csv | list
    columns: List[str]
    key: str
    row_count: int
    version: int
    description: str = ""
    updated_at: Optional[datetime] = None
    updated_by: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_public(self) -> Dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "columns": self.columns, "key": self.key,
                "row_count": self.row_count, "version": self.version, "description": self.description,
                "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else
                self.updated_at, "updated_by": self.updated_by}


def check_name(name: str, what: str = "lookup name") -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise LookupValidationError(f"{name!r} is not a valid {what}: use letters, digits and _ (max 64)")
    return name


def _value(text: str, where: str) -> str:
    text = text.strip()
    if len(text) > MAX_VALUE:
        raise LookupValidationError(f"{where}: values can be at most {MAX_VALUE} characters")
    return text


def parse_csv(text: str, key: Optional[str] = None) -> Tuple[List[str], str, Dict[str, Dict[str, str]]]:
    """(columns, key column, {key: {other column: value}}). The first row is
    the header; the key is the first column unless named. A repeated key
    keeps its last row; rows with an empty key are skipped."""
    if not isinstance(text, str) or not text.strip():
        raise LookupValidationError("The CSV is empty")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise LookupValidationError(f"The CSV can be at most {MAX_BYTES // (1024 * 1024)} MB")
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = [h.strip() for h in next(reader)]
    except StopIteration:
        raise LookupValidationError("The CSV is empty") from None
    except csv.Error as e:
        raise LookupValidationError(f"The CSV cannot be read: {e}") from None
    if len(header) > MAX_COLUMNS:
        raise LookupValidationError(f"A lookup can have at most {MAX_COLUMNS} columns")
    for name in header:
        check_name(name, "column name")
    if len(set(header)) != len(header):
        raise LookupValidationError("A column name appears twice in the header")
    key = key or header[0]
    if key not in header:
        raise LookupValidationError(f"The key column {key!r} is not in the header ({', '.join(header)})")
    key_index = header.index(key)
    rows: Dict[str, Dict[str, str]] = {}
    try:
        for line_number, record in enumerate(reader, start=2):
            if not record or all(not cell.strip() for cell in record):
                continue
            if len(record) != len(header):
                raise LookupValidationError(f"line {line_number} has {len(record)} values; the header has "
                                            f"{len(header)}")
            value = _value(record[key_index], f"line {line_number}")
            if not value:
                continue
            if value not in rows and len(rows) >= MAX_ROWS:
                raise LookupValidationError(f"A lookup can have at most {MAX_ROWS} rows")
            rows[value] = {name: _value(cell, f"line {line_number}")
                           for name, cell in zip(header, record) if name != key}
    except csv.Error as e:
        raise LookupValidationError(f"The CSV cannot be read: {e}") from None
    if not rows:
        raise LookupValidationError("The CSV has no rows")
    return header, key, rows


def parse_list(values: List[Any]) -> Tuple[List[str], str, Dict[str, Dict[str, str]]]:
    """A managed list: one column, `value`."""
    if not isinstance(values, list):
        raise LookupValidationError("values must be a list")
    rows: Dict[str, Dict[str, str]] = {}
    for item in values:
        if not isinstance(item, (str, int, float)) or isinstance(item, bool):
            raise LookupValidationError("list values must be strings or numbers")
        text = _value(str(item), "list")
        if text:
            rows[text] = {}
    if len(rows) > MAX_ROWS:
        raise LookupValidationError(f"A list can have at most {MAX_ROWS} values")
    return ["value"], "value", rows


class LookupDAO:
    def __init__(self, db=None):
        if db is None:
            from database_layer import DatabaseLayer

            db = DatabaseLayer("LookupDAO", os.getenv("LOOKUP_SERVICE_KEY", "lookup-dao-service-key"))
        self.db = db

    @staticmethod
    def _record(row: Dict[str, Any]) -> LookupTable:
        return LookupTable(name=row["name"], kind=row["kind"], columns=list(row["columns"]), key=row["key_column"],
                           row_count=int(row["row_count"]), version=int(row["version"]),
                           description=row.get("description", ""), updated_at=row.get("updated_at"),
                           updated_by=row.get("updated_by", ""))

    async def _latest(self, tenant_id: str, name: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"tenant_id": tenant_id}
        where = "tenant_id = %(tenant_id)s"
        if name is not None:
            where += " AND name = %(name)s"
            params["name"] = name
        return await self.db.fetch_all(
            f"SELECT * FROM lookup_tables_mt WHERE {where} ORDER BY name, version DESC LIMIT 1 BY name",
            params) or []

    async def list(self, tenant_id: str) -> List[LookupTable]:
        return [self._record(r) for r in await self._latest(tenant_id) if not r.get("deleted")]

    async def get(self, tenant_id: str, name: str) -> Optional[LookupTable]:
        rows = await self._latest(tenant_id, name)
        if not rows or rows[0].get("deleted"):
            return None
        return self._record(rows[0])

    async def _next_version(self, tenant_id: str, name: str) -> int:
        rows = await self._latest(tenant_id, name)
        return int(rows[0]["version"]) + 1 if rows else 1

    async def save(self, tenant_id: str, name: str, kind: str, columns: List[str], key: str,
                   rows: Dict[str, Dict[str, str]], description: str, actor: str) -> LookupTable:
        version = await self._next_version(tenant_id, name)
        items = list(rows.items())
        for start in range(0, len(items), _INSERT_BATCH):
            batch = items[start:start + _INSERT_BATCH]
            await self.db.insert_rows("lookup_rows_mt", [[tenant_id, name, version, k, v] for k, v in batch],
                                      ["tenant_id", "lookup", "version", "key", "values"])
        now = datetime.now(timezone.utc)
        await self.db.insert_rows(
            "lookup_tables_mt",
            [[tenant_id, name, version, kind, description or "", columns, key, len(rows), 0, now, actor]],
            ["tenant_id", "name", "version", "kind", "description", "columns", "key_column", "row_count", "deleted",
             "updated_at", "updated_by"])
        await self._drop_old_rows(tenant_id, name, version)
        return LookupTable(name=name, kind=kind, columns=columns, key=key, row_count=len(rows), version=version,
                           description=description or "", updated_at=now, updated_by=actor)

    async def _drop_old_rows(self, tenant_id: str, name: str, keep_version: int) -> None:
        try:
            await self.db.execute_update(
                "ALTER TABLE lookup_rows_mt DELETE WHERE tenant_id = %(tenant_id)s AND lookup = %(name)s "
                "AND version < %(version)s", {"tenant_id": tenant_id, "name": name, "version": keep_version})
        except Exception as e:  # old rows are unreachable anyway; cleanup can wait for the next upload
            logger.warning(f"Could not delete old rows of lookup {name}: {e}")

    async def rows(self, tenant_id: str, table: LookupTable, limit: int) -> List[Dict[str, str]]:
        found = await self.db.fetch_all(
            "SELECT key, values FROM lookup_rows_mt WHERE tenant_id = %(tenant_id)s AND lookup = %(name)s "
            "AND version = %(version)s ORDER BY key LIMIT %(limit)s",
            {"tenant_id": tenant_id, "name": table.name, "version": table.version, "limit": int(limit)}) or []
        return [{table.key: r["key"], **{c: dict(r["values"]).get(c, "") for c in table.columns if c != table.key}}
                for r in found]

    async def all_rows(self, tenant_id: str, table: LookupTable) -> Dict[str, Dict[str, str]]:
        found = await self.db.fetch_all(
            "SELECT key, values FROM lookup_rows_mt WHERE tenant_id = %(tenant_id)s AND lookup = %(name)s "
            "AND version = %(version)s", {"tenant_id": tenant_id, "name": table.name, "version": table.version}) or []
        return {r["key"]: dict(r["values"]) for r in found}

    async def delete(self, tenant_id: str, name: str, actor: str) -> None:
        current = await self.get(tenant_id, name)
        if current is None:
            return
        await self.db.insert_rows(
            "lookup_tables_mt",
            [[tenant_id, name, current.version + 1, current.kind, "", current.columns, current.key, 0, 1,
              datetime.now(timezone.utc), actor]],
            ["tenant_id", "name", "version", "kind", "description", "columns", "key_column", "row_count", "deleted",
             "updated_at", "updated_by"])
        await self._drop_old_rows(tenant_id, name, current.version + 1)
