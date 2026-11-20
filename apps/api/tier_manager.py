"""
TierManager (Phase 12): carries out storage_tiers.plan against ClickHouse and
object storage.

    ensure_tables()   each tiered table on the `tiered` storage policy (when
                      the server has it) with TTL: hot_days TO VOLUME 'warm',
                      max_searchable_days DELETE. Existing parts aren't
                      rewritten (materialize_ttl_after_modify = 0); they move
                      as ClickHouse's background TTL merges reach them.
    run(today)        for every tenant and data type: archive each day past
                      its searchable period to Parquet (written by ClickHouse
                      itself through the `logforge_archive` named collection),
                      read the file back and count it, delete the day from
                      ClickHouse only when the counts match, and expire
                      archives past the archive period.

`python -m tier_manager run` runs it once (a Kubernetes CronJob); the API runs
it hourly in-process when LOGFORGE_RETENTION_JOB is on (compose).
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import storage_tiers as st

ARCHIVE_COLLECTION = "logforge_archive"
MAX_REHYDRATE_DAYS = 31
MAX_REHYDRATE_KEEP_DAYS = 30


def _start(day: date) -> datetime:
    return datetime.combine(day, time(0), tzinfo=timezone.utc)


class S3Objects:
    """The archive bucket, for what ClickHouse can't do: object sizes and deletes."""

    def __init__(self, bucket: str):
        import boto3

        endpoint = os.getenv("LOGFORGE_S3_ENDPOINT") or f"http://{os.getenv('MINIO_ENDPOINT', 'minio:9000')}"
        self.bucket = bucket
        self.s3 = boto3.client("s3", endpoint_url=endpoint, region_name=os.getenv("LOGFORGE_S3_REGION", "us-east-1"),
                               aws_access_key_id=os.getenv("LOGFORGE_S3_ACCESS_KEY") or os.getenv("MINIO_ACCESS_KEY"),
                               aws_secret_access_key=os.getenv("LOGFORGE_S3_SECRET_KEY") or os.getenv("MINIO_SECRET_KEY"))

    def ensure_buckets(self, *buckets: str) -> None:
        for bucket in buckets:
            try:
                self.s3.head_bucket(Bucket=bucket)
            except Exception:
                self.s3.create_bucket(Bucket=bucket)

    def size(self, key: str) -> int:
        return int(self.s3.head_object(Bucket=self.bucket, Key=key)["ContentLength"])

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)


class TierManager:
    def __init__(self, client, objects, cfg: Optional[st.Config] = None):
        self.client = client
        self.objects = objects
        self.cfg = cfg or st.load_config()

    # -- tables -------------------------------------------------------------

    def warm_available(self) -> bool:
        rows = self.client.query("SELECT DISTINCT policy_name FROM system.storage_policies").result_rows
        return any(r[0] == self.cfg.warm_policy for r in rows)

    def ensure_tables(self) -> Dict[str, Any]:
        warm = self.warm_available()
        tables = []
        for dtype in self.cfg.data_types.values():
            row = self.client.query("SELECT storage_policy FROM system.tables WHERE database = currentDatabase() "
                                    "AND name = {table:String}", parameters={"table": dtype.table}).result_rows
            if not row:
                tables.append({"table": dtype.table, "status": "missing"})
                continue
            if warm and row[0][0] != self.cfg.warm_policy:
                self.client.command(f"ALTER TABLE {dtype.table} MODIFY SETTING storage_policy = "
                                    f"'{self.cfg.warm_policy}'")
            self.client.command(f"ALTER TABLE {dtype.table} MODIFY TTL {st.table_ttl(dtype, self.cfg, warm=warm)} "
                                "SETTINGS materialize_ttl_after_modify = 0")
            tables.append({"table": dtype.table, "status": "tiered" if warm else "delete_only"})
        return {"warm": warm, "hot_days": self.cfg.hot_days, "max_searchable_days": self.cfg.max_searchable_days,
                "tables": tables}

    # -- policies -----------------------------------------------------------

    def _stored(self, tenant_id: Optional[str] = None) -> Dict[str, List[st.Policy]]:
        where = "WHERE customer_id = {tenant:String} " if tenant_id else ""
        rows = self.client.query(
            "SELECT customer_id, data_type, argMax(searchable_days, updated_at), argMax(archive_days, updated_at) "
            f"FROM tenant_retention_mt {where}GROUP BY customer_id, data_type",
            parameters={"tenant": tenant_id} if tenant_id else None).result_rows
        out: Dict[str, List[st.Policy]] = defaultdict(list)
        for tenant, dtype, searchable, archive in rows:
            if tenant_id and tenant != tenant_id:
                continue
            out[tenant].append(st.Policy(dtype, int(searchable), int(archive)))
        return out

    def policies(self, tenant_id: str) -> Dict[str, st.Policy]:
        return st.effective(self._stored(tenant_id).get(tenant_id, []), self.cfg)

    def set_policy(self, tenant_id: str, policy: st.Policy, user_id: str) -> st.Policy:
        st.validate(policy, self.cfg)
        self.client.command(
            "INSERT INTO tenant_retention_mt (customer_id, data_type, searchable_days, archive_days, updated_by) "
            "SELECT {tenant:String}, {type:String}, {searchable:UInt32}, {archive:UInt32}, {user:String}",
            parameters={"tenant": tenant_id, "type": policy.data_type, "searchable": policy.searchable_days,
                        "archive": policy.archive_days, "user": user_id or ""})
        return policy

    # -- archives -----------------------------------------------------------

    def archived(self, data_type: str, tenant_id: Optional[str] = None) -> Dict[str, Dict[date, Tuple[int, str]]]:
        where = " AND customer_id = {tenant:String}" if tenant_id else ""
        rows = self.client.query(
            "SELECT customer_id, day, argMax(rows, updated_at), argMax(object_key, updated_at) "
            f"FROM archive_manifest_mt WHERE data_type = {{type:String}}{where} GROUP BY customer_id, day "
            "HAVING argMax(status, updated_at) = 'archived'",
            parameters={"type": data_type, **({"tenant": tenant_id} if tenant_id else {})}).result_rows
        out: Dict[str, Dict[date, Tuple[int, str]]] = defaultdict(dict)
        for tenant, day, n, key in rows:
            out[tenant][day] = (int(n), key)
        return out

    def _columns(self, table: str) -> List[str]:
        rows = self.client.query("SELECT name FROM system.columns WHERE database = currentDatabase() AND "
                                 "table = {table:String} AND default_kind NOT IN ('MATERIALIZED', 'ALIAS', 'EPHEMERAL') "
                                 "ORDER BY position", parameters={"table": table}).result_rows
        return [r[0] for r in rows]

    def _manifest(self, tenant_id: str, data_type: str, day: date, key: str, rows: int, size: int,
                  status: str) -> None:
        self.client.command(
            "INSERT INTO archive_manifest_mt (customer_id, data_type, day, object_key, rows, bytes, status, "
            "archived_at) SELECT {tenant:String}, {type:String}, {day:Date}, {key:String}, {rows:UInt64}, "
            "{bytes:UInt64}, {status:String}, now64()",
            parameters={"tenant": tenant_id, "type": data_type, "day": day.isoformat(), "key": key, "rows": rows,
                        "bytes": size, "status": status})

    def archive_day(self, tenant_id: str, dtype: st.DataType, day: date, expected: int) -> int:
        """Write the day's Parquet file, read it back; the rows it holds."""
        key = st.archive_key(tenant_id, dtype.name, day)
        cols = ", ".join(f"`{c}`" for c in self._columns(dtype.table))
        self.client.command(
            f"INSERT INTO FUNCTION s3({ARCHIVE_COLLECTION}, filename = '{key}', format = 'Parquet') "
            f"SELECT {cols} FROM {dtype.table} WHERE customer_id = {{tenant:String}} "
            f"AND {dtype.ts} >= {{start:DateTime64(3)}} AND {dtype.ts} < {{end:DateTime64(3)}} "
            "SETTINGS s3_truncate_on_insert = 1",
            parameters={"tenant": tenant_id, "start": _start(day), "end": _start(day + timedelta(days=1))})
        rows = int(self.client.query(f"SELECT count() FROM s3({ARCHIVE_COLLECTION}, filename = '{key}', "
                                     "format = 'Parquet')").result_rows[0][0])
        if rows == expected:
            self._manifest(tenant_id, dtype.name, day, key, rows, self.objects.size(key), "archived")
        return rows

    # -- rehydration --------------------------------------------------------

    def holds(self, data_type: str, today: date, tenant_id: Optional[str] = None) -> Dict[str, set]:
        """Rehydrated days the retention job leaves alone until their hold ends."""
        where = " AND customer_id = {tenant:String}" if tenant_id else ""
        rows = self.client.query(
            "SELECT customer_id, day FROM rehydrations_mt WHERE data_type = {type:String} "
            f"AND until > {{today:Date}}{where} GROUP BY customer_id, day",
            parameters={"type": data_type, "today": today.isoformat(),
                        **({"tenant": tenant_id} if tenant_id else {})}).result_rows
        out: Dict[str, set] = defaultdict(set)
        for tenant, day in rows:
            out[tenant].add(day)
        return out

    def rehydrate(self, tenant_id: str, data_type: str, first: date, last: date, keep_days: int, user_id: str,
                  today: Optional[date] = None) -> Dict[str, Any]:
        """
        Copy archived days back into ClickHouse and keep them `keep_days`.

        Days are loaded into a staging copy of the table and attached from
        it: attaching doesn't fire the table's materialized views, so the
        entity counts (migration 026) aren't inflated. Days still in
        ClickHouse are skipped, so nothing is duplicated.
        """
        import uuid

        today = today or datetime.now(timezone.utc).date()
        if data_type not in self.cfg.data_types:
            raise st.PolicyError(f"unknown data type {data_type!r}")
        if not 1 <= keep_days <= MAX_REHYDRATE_KEEP_DAYS:
            raise st.PolicyError(f"keep_days must be 1 to {MAX_REHYDRATE_KEEP_DAYS}")
        if first > last:
            raise st.PolicyError("the first day must be on or before the last")
        if (last - first).days + 1 > MAX_REHYDRATE_DAYS:
            raise st.PolicyError(f"rehydrate at most {MAX_REHYDRATE_DAYS} days at a time")
        dtype = self.cfg.data_types[data_type]
        archived = {day: v for day, v in self.archived(data_type, tenant_id).get(tenant_id, {}).items()
                    if first <= day <= last}
        report: Dict[str, Any] = {"rehydrated_days": 0, "rows": 0, "skipped": [], "errors": [],
                                  "until": (today + timedelta(days=keep_days)).isoformat()}
        if not archived:
            return report
        present = {r[0] for r in self.client.query(
            f"SELECT toDate({dtype.ts}) AS day, count() FROM {dtype.table} WHERE customer_id = {{tenant:String}} "
            f"AND toDate({dtype.ts}) IN {{days:Array(Date)}} GROUP BY day",
            parameters={"tenant": tenant_id, "days": [d.isoformat() for d in archived]}).result_rows}
        cols = ", ".join(f"`{c}`" for c in self._columns(dtype.table))
        for day in sorted(archived):
            if day in present:
                report["skipped"].append({"day": day.isoformat(), "reason": "still in ClickHouse"})
                continue
            expected, key = archived[day]
            stage = f"_rehydrate_{uuid.uuid4().hex[:12]}"
            try:
                self.client.command(f"CREATE TABLE {stage} AS {dtype.table}")
                self.client.command(f"INSERT INTO {stage} ({cols}) SELECT {cols} FROM s3({ARCHIVE_COLLECTION}, "
                                    f"filename = '{key}', format = 'Parquet') "
                                    "WHERE customer_id = {tenant:String}", parameters={"tenant": tenant_id})
                for (partition,) in self.client.query(
                        "SELECT DISTINCT partition_id FROM system.parts WHERE database = currentDatabase() "
                        "AND table = {stage:String} AND active", parameters={"stage": stage}).result_rows:
                    self.client.command(f"ALTER TABLE {dtype.table} ATTACH PARTITION ID '{partition}' FROM {stage}")
                got = int(self.client.query(
                    f"SELECT count() FROM {dtype.table} WHERE customer_id = {{tenant:String}} "
                    f"AND toDate({dtype.ts}) = {{day:Date}}",
                    parameters={"tenant": tenant_id, "day": day.isoformat()}).result_rows[0][0])
                self.client.command(
                    "INSERT INTO rehydrations_mt (customer_id, data_type, day, until, rows, requested_by) "
                    "SELECT {tenant:String}, {type:String}, {day:Date}, {until:Date}, {rows:UInt64}, {user:String}",
                    parameters={"tenant": tenant_id, "type": data_type, "day": day.isoformat(),
                                "until": report["until"], "rows": got, "user": user_id or ""})
                report["rehydrated_days"] += 1
                report["rows"] += got
                if got != expected:
                    report["errors"].append(f"{day}: {got} rows in ClickHouse, the archive holds {expected}")
            except Exception as e:
                report["errors"].append(f"{day}: {e}")
            finally:
                self.client.command(f"DROP TABLE IF EXISTS {stage}")
        return report

    # -- the job ------------------------------------------------------------

    def _old_days(self, dtype: st.DataType, today: date, searchable: int) -> Dict[str, Dict[date, int]]:
        cutoff = _start(today - timedelta(days=searchable - 1))
        rows = self.client.query(
            f"SELECT customer_id, toDate({dtype.ts}) AS day, count() FROM {dtype.table} "
            f"WHERE {dtype.ts} < {{cutoff:DateTime64(3)}} GROUP BY customer_id, day",
            parameters={"cutoff": cutoff}).result_rows
        out: Dict[str, Dict[date, int]] = defaultdict(dict)
        for tenant, day, n in rows:
            out[tenant][day] = int(n)
        return out

    def run(self, today: Optional[date] = None, tenants: Optional[List[str]] = None) -> Dict[str, Any]:
        """The retention job, for every tenant, or only `tenants`."""
        today = today or datetime.now(timezone.utc).date()
        report: Dict[str, Any] = {"today": today.isoformat(), "archived": 0, "archived_rows": 0, "deleted_days": 0,
                                  "deleted_rows": 0, "expired": 0, "errors": []}
        stored = self._stored()
        for name, dtype in self.cfg.data_types.items():
            per_tenant = {t: st.effective(p, self.cfg)[name] for t, p in stored.items()}
            shortest = min([self.cfg.defaults[name].searchable_days] +
                           [p.searchable_days for p in per_tenant.values()])
            days = self._old_days(dtype, today, shortest)
            archived = self.archived(name)
            held = self.holds(name, today)
            for tenant in sorted(set(days) | set(archived)):
                if tenants is not None and tenant not in tenants:
                    continue
                policy = per_tenant.get(tenant, self.cfg.defaults[name])
                tenant_days = days.get(tenant, {})
                counts = {day: n for day, (n, _) in archived.get(tenant, {}).items()}
                for action in st.plan(policy, today, tenant_days, counts, held.get(tenant)):
                    if action.kind != "archive":
                        continue
                    try:
                        got = self.archive_day(tenant, dtype, action.day, action.rows)
                    except Exception as e:  # one day failing mustn't stop the rest
                        report["errors"].append(f"{tenant} {name} {action.day}: archive failed: {e}")
                        continue
                    if got == action.rows:
                        counts[action.day] = got
                        report["archived"] += 1
                        report["archived_rows"] += got
                    else:
                        report["errors"].append(f"{tenant} {name} {action.day}: the archive read back "
                                                f"{got} of {action.rows} rows; kept in ClickHouse")
                # second pass: what the archives now allow
                actions = st.plan(policy, today, tenant_days, counts, held.get(tenant))
                drop = [a for a in actions if a.kind == "delete"]
                if drop:
                    try:
                        self.client.command(
                            f"ALTER TABLE {dtype.table} DELETE WHERE customer_id = {{tenant:String}} "
                            f"AND toDate({dtype.ts}) IN {{days:Array(Date)}} SETTINGS mutations_sync = 2",
                            parameters={"tenant": tenant, "days": [a.day.isoformat() for a in drop]})
                        report["deleted_days"] += len(drop)
                        report["deleted_rows"] += sum(a.rows for a in drop)
                    except Exception as e:
                        report["errors"].append(f"{tenant} {name}: delete failed: {e}")
                for action in (a for a in actions if a.kind == "expire"):
                    key = archived.get(tenant, {}).get(action.day, (0, st.archive_key(tenant, name, action.day)))[1]
                    try:
                        self.objects.delete(key)
                        self._manifest(tenant, name, action.day, key, action.rows, 0, "expired")
                        report["expired"] += 1
                    except Exception as e:
                        report["errors"].append(f"{tenant} {name} {action.day}: expire failed: {e}")
        return report


def from_env():
    """A TierManager on the deployment's ClickHouse and archive bucket."""
    import clickhouse_connect

    cfg = st.load_config()
    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"), port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "logforge"), password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DATABASE", "logforge"))
    return TierManager(client, S3Objects(cfg.archive_bucket), cfg)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Storage tiers: set up tables, run retention")
    parser.add_argument("command", choices=["ensure", "run"])
    args = parser.parse_args(argv)
    mgr = from_env()
    if args.command == "ensure":
        mgr.objects.ensure_buckets(mgr.cfg.archive_bucket, mgr.cfg.warm_bucket, mgr.cfg.backup_bucket)
        out = mgr.ensure_tables()
    else:
        out = mgr.run()
    print(json.dumps(out, indent=2, default=str))
    return 1 if out.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
