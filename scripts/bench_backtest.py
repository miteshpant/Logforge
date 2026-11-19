"""
Time rule backtests over a tenant's stored logs (docs/benchmarks/backtest.md).

Run inside the API container (it needs the rule cache and ClickHouse):

    docker cp scripts/bench_backtest.py logforge-api:/app/
    docker exec -w /app logforge-api python bench_backtest.py <rule-id> [<rule-id> ...]

Reads the last 7 days of the `bench-backtest` tenant; see the doc for how the
synthetic data set is generated.
"""
import asyncio, logging, os, sys, time, resource
from datetime import datetime, timedelta, timezone
logging.disable(logging.CRITICAL)
from database_layer import DatabaseLayer
from events.management.cache.sigma_rule_cache import SigmaRuleCache
from backtest import run_backtest
async def main():
    db = DatabaseLayer("BacktestService", os.getenv("BACKTEST_SERVICE_KEY", "backtest-service-key"))
    rules = await SigmaRuleCache().get_customer_rules("bench-backtest", include_defaults=True)
    end = datetime.now(timezone.utc) + timedelta(minutes=1); start = end - timedelta(days=7)
    for rid in sys.argv[1:]:
        t = time.monotonic()
        r = await run_backtest(db, rules, rid, "bench-backtest", start, end, max_events=20_000_000, sample_limit=1)
        print(rid, "scanned", r["events_scanned"], "alerts", r["alerts_total"], "prefilter", r["prefilter"],
              f"{time.monotonic() - t:.1f}s", "maxrss_MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)
asyncio.run(main())
