"""
Backup and restore (Phase 12, docs/deployment.md).

ClickHouse's own BACKUP/RESTORE, to S3 through the `logforge_backups` named
collection (infra/docker/clickhouse/config.d/s3_storage.xml: credentials stay
in the server's configuration, not in SQL). A backup is the files under
`<bucket>/<name>/`, so a new server with the same configuration restores it. Every piece of tenant configuration
(users, roles, rules, pipelines, saved searches, dashboards, packs,
retention, cases, AI settings) is a table in the same database, so one
database backup covers data and configuration.

Each backup also writes `<name>.manifest.json` beside it: the rows of every
table when it was taken, which `verify` compares a restore against.

    python -m backup create [--base NAME]         full, or incremental on top of NAME
    python -m backup list
    python -m backup restore NAME [--as DATABASE] restore (to another database to inspect it first)
    python -m backup verify NAME [--database DATABASE]
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

COLLECTION = "logforge_backups"


def _where(name: str) -> str:
    return f"S3({COLLECTION}, '{check_name(name)}')"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_VIEWS = ("MaterializedView", "View", "LiveView", "WindowView", "Dictionary")
_COLLAPSING = ("Replacing", "Summing", "Aggregating", "Collapsing")


class BackupError(ValueError):
    pass


def check_name(name: str) -> str:
    if not name or not _NAME.match(name) or ".." in name:
        raise BackupError(f"invalid name {name!r}")
    return name


def name_for(now: datetime) -> str:
    return f"logforge-{now:%Y%m%d-%H%M%S}"


def _status(result: Any) -> str:
    """BACKUP and RESTORE answer (id, status); drivers return it as text or as a list."""
    if isinstance(result, (list, tuple)):
        return str(result[-1]) if result else ""
    return str(result).split()[-1] if result else ""


def _counts(client, database: str) -> Dict[str, int]:
    """Rows per table, as queries see them. Engines that collapse rows as they
    merge (Replacing, Summing, Aggregating, Collapsing) are counted with
    FINAL: their raw rows shrink after a restore with nothing lost."""
    rows = client.query("SELECT name, engine, total_rows FROM system.tables WHERE database = {db:String} "
                        "AND NOT is_temporary AND name NOT LIKE '.inner%' AND name NOT LIKE '\\_rehydrate\\_%'",
                        parameters={"db": database}).result_rows
    out = {}
    for name, engine, n in rows:
        if engine in _VIEWS:
            continue
        # count(), not system.tables.total_rows: deleted rows (DELETE, ALTER
        # DELETE) stay in total_rows until merged away
        final = " FINAL" if any(k in engine for k in _COLLAPSING) else ""
        n = client.query(f"SELECT count() FROM {database}.`{name}`{final}").result_rows[0][0]
        out[name] = int(n or 0)
    return out


def create(client, objects, database: str, name: str, base: Optional[str] = None,
           now: Optional[datetime] = None) -> Dict[str, Any]:
    check_name(name)
    check_name(database)
    settings = ""
    if base:
        check_name(base)
        try:
            objects.get_json(f"{base}.manifest.json")
        except Exception:
            raise BackupError(f"no backup named {base!r} to build on") from None
        settings = f" SETTINGS base_backup = {_where(base)}"
    counts = _counts(client, database)
    result = client.command(f"BACKUP DATABASE {database} TO {_where(name)}{settings}")
    status = _status(result)
    manifest = {"name": name, "database": database, "base": base,
                "created_at": (now or datetime.now(timezone.utc)).isoformat(), "tables": counts}
    objects.put_json(f"{name}.manifest.json", manifest)
    return {**manifest, "status": status}


def restore(client, objects, name: str, as_database: Optional[str] = None,
            exists: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
    check_name(name)
    manifest = objects.get_json(f"{name}.manifest.json")
    source = manifest["database"]
    target = check_name(as_database) if as_database else source
    exists = exists or (lambda db: bool(client.query("SELECT count() FROM system.databases WHERE name = {db:String}",
                                                     parameters={"db": db}).result_rows[0][0]))
    if exists(target):
        raise BackupError(f"database {target!r} exists: restore into a new database (--as), or drop it first")
    rename = f" AS {target}" if target != source else ""
    result = client.command(f"RESTORE DATABASE {source}{rename} FROM {_where(name)}")
    return {"name": name, "database": target, "status": _status(result)}


def verify(client, objects, name: str, database: Optional[str] = None) -> Dict[str, Any]:
    """Each table's rows now against the backup's manifest. Fewer rows is a mismatch."""
    manifest = objects.get_json(f"{check_name(name)}.manifest.json")
    now = _counts(client, database or manifest["database"])
    mismatches = []
    for table, rows in sorted(manifest["tables"].items()):
        got = now.get(table)
        if got is None or got < rows:
            mismatches.append({"table": table, "backed_up": rows, "restored": got})
    return {"name": name, "database": database or manifest["database"], "tables": len(manifest["tables"]),
            "rows": sum(manifest["tables"].values()), "ok": not mismatches, "mismatches": mismatches}


def list_backups(objects) -> List[Dict[str, Any]]:
    out = []
    for key in objects.keys():
        if key.endswith(".manifest.json"):
            m = objects.get_json(key)
            out.append({"name": m.get("name") or key[:-len(".manifest.json")], "created_at": m.get("created_at"),
                        "base": m.get("base"), "tables": len(m.get("tables", {})),
                        "rows": sum(m.get("tables", {}).values())})
    return sorted(out, key=lambda b: b["created_at"] or "", reverse=True)


class S3Manifests:
    """The backups bucket, for manifests (ClickHouse writes the backups themselves)."""

    def __init__(self, bucket: Optional[str] = None):
        from tier_manager import S3Objects

        self.bucket = bucket or os.getenv("LOGFORGE_BACKUP_BUCKET", "logforge-backups")
        self.s3 = S3Objects(self.bucket).s3

    def put_json(self, key: str, data: Dict[str, Any]) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=json.dumps(data, indent=2).encode(),
                           ContentType="application/json")

    def get_json(self, key: str) -> Dict[str, Any]:
        return json.loads(self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read())

    def keys(self, prefix: str = "") -> List[str]:
        out, token = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix, "Delimiter": "/"}
            if token:
                kw["ContinuationToken"] = token
            page = self.s3.list_objects_v2(**kw)
            out += [o["Key"] for o in page.get("Contents", [])]
            if not page.get("IsTruncated"):
                return out
            token = page["NextContinuationToken"]


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    from tier_manager import from_env

    parser = argparse.ArgumentParser(description="Back up and restore Logforge's ClickHouse database")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("create")
    c.add_argument("--name")
    c.add_argument("--base", help="incremental on top of this backup")
    sub.add_parser("list")
    r = sub.add_parser("restore")
    r.add_argument("name")
    r.add_argument("--as", dest="as_database")
    v = sub.add_parser("verify")
    v.add_argument("name")
    v.add_argument("--database")
    args = parser.parse_args(argv)
    client = from_env().client
    from app_config import clickhouse_settings

    database = clickhouse_settings()["database"]
    objects = S3Manifests()
    if args.command == "create":
        out: Any = create(client, objects, database, args.name or name_for(datetime.now(timezone.utc)), args.base)
    elif args.command == "list":
        out = list_backups(objects)
    elif args.command == "restore":
        out = restore(client, objects, args.name, args.as_database)
        out["verify"] = verify(client, objects, args.name, out["database"])
    else:
        out = verify(client, objects, args.name, args.database)
    print(json.dumps(out, indent=2, default=str))
    return 0 if not isinstance(out, dict) or out.get("verify", out).get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
