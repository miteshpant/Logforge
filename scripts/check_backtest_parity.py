"""
Check that every rule's compiled backtest prefilter (sigma_sql) is valid
ClickHouse SQL and selects every stored row the engine matches (superset).

Run inside the API container, for a tenant with data:

    docker cp scripts/check_backtest_parity.py logforge-api:/app/
    docker exec -w /app logforge-api python check_backtest_parity.py <tenant-id>
"""
import asyncio, json, logging, sys
logging.disable(logging.CRITICAL)
from database_layer import DatabaseLayer
from events.management.cache.sigma_rule_cache import SigmaRuleCache
from sigma_sql import compile_prefilter
from backtest import row_to_event
from detection_replay import detection_matches
from sigma_engine import SigmaConditionEvaluator
T = sys.argv[1]
async def main():
    db = DatabaseLayer("BacktestService", __import__("os").getenv("BACKTEST_SERVICE_KEY", "backtest-service-key"))
    rows = await db.fetch_all("SELECT ts, host, service, level, msg, trace_id, span_id, status, src_ip, user_id, attrs, "
                              "cityHash64(ts, msg, attrs) AS k FROM logs_raw_mt WHERE customer_id = %(t)s", {"t": T})
    events = {r["k"]: row_to_event(r) for r in rows}
    rules = await SigmaRuleCache().get_customer_rules(T, include_defaults=True)
    ev = SigmaConditionEvaluator()
    stats = {"rules": 0, "narrowed": 0, "sql_errors": 0, "missed": 0, "engine_matches": 0, "sql_rows": 0}
    for rule in rules:
        det = rule.get("detection") or {}
        if rule.get("correlation") or not det:
            continue
        stats["rules"] += 1
        sql, params = compile_prefilter(det)
        cond = str(det.get("condition", ""))
        check = dict(det)
        if "count(" in cond:
            check = {"selection": det.get("selection") or {}, "condition": "selection"}
        engine = {k for k, e in events.items() if detection_matches(ev, check, e)}
        stats["engine_matches"] += len(engine)
        if sql is None:
            continue
        stats["narrowed"] += 1
        try:
            got = await db.fetch_all("SELECT cityHash64(ts, msg, attrs) AS k FROM logs_raw_mt WHERE customer_id = %(t)s AND "
                                     + sql, {**params, "t": T})
        except Exception as e:
            stats["sql_errors"] += 1; print("SQL ERROR", rule["id"], str(e)[:200]); continue
        selected = {r["k"] for r in got}
        stats["sql_rows"] += len(selected)
        missed = engine - selected
        if missed:
            stats["missed"] += 1
            print("MISSED", rule["id"], len(missed), json.dumps(events[next(iter(missed))])[:300])
    print(stats, "rows", len(rows))
asyncio.run(main())
