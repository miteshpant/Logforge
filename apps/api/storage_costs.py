"""
Cost visibility (Phase 12): what a tenant ingests, by source and level; what
it stores, per tier; what its retention costs at steady state; and the noise
a Phase 4 pipeline `drop` step would cut.

Storage per tier is an estimate for hot and warm: ClickHouse parts mix
tenants, so a tenant's bytes are its rows on each tier times the table's
average compressed bytes per row there. Cold (Parquet) bytes are exact, from
the archive manifest. Prices per GB-month are configuration
(storage_tiers.yml `prices`): list prices to replace with your own.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Sequence, Tuple

import storage_tiers as st

GB = 1024 ** 3
NOISY_LEVELS = ("debug", "trace", "verbose")
NOISE_SHARE = 0.05       # a debug/trace stream above 5% of events
DOMINANT_SHARE = 0.25    # any single info stream above 25% of events
Row = Tuple[str, str, int, int]  # service, level, events, raw bytes


def bytes_per_row(parts: Dict[str, Tuple[int, int]]) -> Dict[str, float]:
    """{disk: (rows, bytes on disk)} -> compressed bytes per row, per disk and overall ("all")."""
    out = {disk: round(b / r, 1) for disk, (r, b) in parts.items() if r}
    rows = sum(r for r, _ in parts.values())
    out["all"] = round(sum(b for _, b in parts.values()) / rows, 1) if rows else 0.0
    return out


def steady_state(daily_events: float, stored_bpe: float, archive_bpe: float, hot_days: int, policy: st.Policy,
                 prices: Dict[str, float]) -> Dict[str, Any]:
    """Bytes per tier once the policy has run for a full archive period, and their monthly cost."""
    hot = min(hot_days, policy.searchable_days)
    warm = max(0, policy.searchable_days - hot_days)
    cold = max(0, policy.archive_days - policy.searchable_days) if policy.archive_days else 0
    out: Dict[str, Any] = {}
    for tier, days, bpe in (("hot", hot, stored_bpe), ("warm", warm, stored_bpe), ("cold", cold, archive_bpe)):
        out[tier] = {"days": days, "gb": daily_events * days * bpe / GB}
    out["monthly_cost"] = {tier: out[tier]["gb"] * prices.get(tier, 0.0) for tier in ("hot", "warm", "cold")}
    out["monthly_cost"]["total"] = sum(out["monthly_cost"].values())
    return out


def projection(per_day: Dict[date, Tuple[int, int]], today: date, days: int = 7) -> Dict[str, Any]:
    """Average of the last `days` full days (today is partial): events and raw bytes per day and per month."""
    full = [per_day[d] for d in (today - timedelta(days=i) for i in range(1, days + 1)) if d in per_day]
    n = len(full)
    events = sum(e for e, _ in full) / n if n else 0
    raw = sum(b for _, b in full) / n if n else 0
    return {"days_used": n, "daily_events": round(events), "daily_raw_bytes": round(raw),
            "monthly_events": round(events * 30), "monthly_raw_bytes": round(raw * 30)}


def by_source(rows: Sequence[Row]) -> List[Dict[str, Any]]:
    total = sum(r[2] for r in rows) or 1
    acc: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"events": 0, "raw_bytes": 0, "levels": {}})
    for service, level, events, raw in rows:
        entry = acc[service]
        entry["events"] += events
        entry["raw_bytes"] += raw
        entry["levels"][level] = entry["levels"].get(level, 0) + events
    out = [{"service": s, **v, "share": v["events"] / total} for s, v in acc.items()]
    return sorted(out, key=lambda x: -x["events"])


def noise(rows: Sequence[Row]) -> List[Dict[str, Any]]:
    """Streams worth dropping or sampling, with the Phase 4 pipeline step that would."""
    total = sum(r[2] for r in rows) or 1
    if len({r[0] for r in rows}) < 2 and len(rows) < 2:
        return []
    found = []
    for service, level, events, raw in rows:
        share = events / total
        lvl = (level or "").lower()
        if lvl in NOISY_LEVELS and share >= NOISE_SHARE:
            why = f"{lvl} lines from {service} are {share:.0%} of events"
        elif lvl in ("info", "", "notice") and share >= DOMINANT_SHARE:
            why = f"{lvl or 'unlevelled'} lines from {service} are {share:.0%} of events: drop what nobody searches"
        else:
            continue
        found.append({"service": service, "level": level, "events": events, "raw_bytes": raw, "share": share,
                      "reason": why, "routing": {"services": [service]},
                      "drop_step": {"drop": {}, "if": f"level == '{level}'"}})
    return sorted(found, key=lambda f: -f["share"])


def report(client, cfg: st.Config, policies: Dict[str, st.Policy], tenant_id: str, today: date,
           window_days: int = 30) -> Dict[str, Any]:
    """The tenant's cost picture (blocking): ingest, storage per tier, projections, noise."""
    from datetime import datetime, time, timezone

    start = datetime.combine(today - timedelta(days=window_days - 1), time(0), tzinfo=timezone.utc)
    hot_cut = datetime.combine(today - timedelta(days=cfg.hot_days - 1), time(0), tzinfo=timezone.utc)
    logs = cfg.data_types["logs"]
    rows = client.query(
        f"SELECT toDate({logs.ts}) AS day, service, level, count(), sum(length(msg) + length(attrs)) "
        f"FROM {logs.table} WHERE customer_id = {{tenant:String}} AND {logs.ts} >= {{start:DateTime64(3)}} "
        "GROUP BY day, service, level", parameters={"tenant": tenant_id, "start": start}).result_rows
    per_day: Dict[date, List[int]] = defaultdict(lambda: [0, 0])
    streams: Dict[Tuple[str, str], List[int]] = defaultdict(lambda: [0, 0])
    for day, service, level, events, raw in rows:
        per_day[day][0] += int(events)
        per_day[day][1] += int(raw)
        streams[(service, level)][0] += int(events)
        streams[(service, level)][1] += int(raw)
    stream_rows = [(s, lvl, e, b) for (s, lvl), (e, b) in streams.items()]

    tables = [d.table for d in cfg.data_types.values()]
    parts: Dict[str, Dict[str, Tuple[int, int]]] = defaultdict(dict)
    for table, disk, n, size in client.query(
            "SELECT table, disk_name, sum(rows), sum(bytes_on_disk) FROM system.parts WHERE active AND "
            "database = currentDatabase() AND table IN {tables:Array(String)} GROUP BY table, disk_name",
            parameters={"tables": tables}).result_rows:
        parts[table][disk] = (int(n), int(size))
    cold = {dtype: (int(days), int(n), int(size)) for dtype, days, n, size in client.query(
        "SELECT data_type, count(), sum(r), sum(b) FROM (SELECT data_type, day, argMax(rows, updated_at) AS r, "
        "argMax(bytes, updated_at) AS b, argMax(status, updated_at) AS s FROM archive_manifest_mt "
        "WHERE customer_id = {tenant:String} GROUP BY data_type, day) WHERE s = 'archived' GROUP BY data_type",
        parameters={"tenant": tenant_id}).result_rows}

    storage = []
    for name, dtype in cfg.data_types.items():
        hot_rows, warm_rows = client.query(
            f"SELECT countIf({dtype.ts} >= {{cut:DateTime64(3)}}), countIf({dtype.ts} < {{cut:DateTime64(3)}}) "
            f"FROM {dtype.table} WHERE customer_id = {{tenant:String}}",
            parameters={"tenant": tenant_id, "cut": hot_cut}).result_rows[0]
        ratio = bytes_per_row(parts.get(dtype.table, {}))
        bpe = ratio["all"]
        cold_days, cold_rows, cold_bytes = cold.get(name, (0, 0, 0))
        storage.append({"data_type": name, "bytes_per_row": bpe,
                        "hot": {"rows": int(hot_rows), "bytes": round(int(hot_rows) * bpe)},
                        "warm": {"rows": int(warm_rows), "bytes": round(int(warm_rows) * bpe)},
                        "cold": {"rows": cold_rows, "bytes": cold_bytes, "days": cold_days}})

    logs_storage = storage[0]
    archive_bpe = (cold["logs"][2] / cold["logs"][1]) if cold.get("logs") and cold["logs"][1] else None
    proj = projection({d: (v[0], v[1]) for d, v in per_day.items()}, today)
    steady = steady_state(proj["daily_events"], logs_storage["bytes_per_row"],
                          archive_bpe if archive_bpe is not None else logs_storage["bytes_per_row"],
                          cfg.hot_days, policies["logs"], cfg.prices)
    return {"window_days": window_days, "today": today.isoformat(),
            "ingest": {"per_day": [{"day": d.isoformat(), "events": v[0], "raw_bytes": v[1]}
                                   for d, v in sorted(per_day.items())],
                       "events": sum(v[0] for v in per_day.values()),
                       "raw_bytes": sum(v[1] for v in per_day.values()),
                       "by_source": by_source(stream_rows)[:25]},
            "storage": storage,
            "projection": {**proj, "logs_policy": policies["logs"].__dict__, "steady_state": steady,
                           "archive_bytes_per_row": archive_bpe, "archive_ratio_assumed": archive_bpe is None},
            "prices": cfg.prices, "noise": noise(stream_rows)[:10],
            "notes": ["Hot and warm bytes are estimates: the tenant's rows on each tier (by age) times the "
                      "table's average compressed bytes per row. Cold bytes are the archive files' sizes.",
                      "Raw bytes are message and attribute bytes as received.",
                      "Prices are configuration (storage_tiers.yml), not quotes."]}
