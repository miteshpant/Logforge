"""
Threat-intel enrichment benchmark (Phase 3 acceptance: ingest throughput
drops by less than 10% with enrichment on).

Two measurements:

* **in-process**: the cost per event of `ingest_enrichment.enrich_events`
  against N synthetic indicators (IPs, domains with parent-domain lookups,
  URLs), with the same traffic run against an empty set as the baseline;
* **live A/B** (`--live`): POST /v1/ingest/logs/batch throughput for a
  dedicated benchmark tenant with no indicators, then with N indicators
  loaded into threat_indicators_mt, interleaved over several rounds; the
  medians are compared. Indicators are removed again afterwards.

    BENCH_EMAIL=bench@bench.example BENCH_PASSWORD='Bench-Pass-123!' \\
      python tests/bench/enrichment_bench.py --indicators 100000 --live \\
      --out docs/benchmarks/enrichment.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from threat_intel import Indicator  # noqa: E402

TENANT = "bench"


def synthetic_indicators(n: int, seed: int = 11) -> List[Indicator]:
    """n unique public indicators: 60% IPs, 30% domains, 10% URLs."""
    rng = random.Random(seed)
    out: List[Indicator] = []
    seen = set()
    while len(out) < n:
        roll = len(out) % 10
        if roll < 6:
            value, kind = f"{rng.randint(23, 99)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}", "ip"
        elif roll < 9:
            value, kind = f"c2-{rng.getrandbits(40):x}.bad{rng.randint(0, 999)}.example", "domain"
        else:
            value, kind = f"http://drop-{rng.getrandbits(40):x}.example/{rng.getrandbits(24):x}.bin", "url"
        if (kind, value) in seen:
            continue
        seen.add((kind, value))
        out.append(Indicator(value=value, indicator_type=kind, threat_type="botnet_cc", confidence=80,
                             source="bench"))
    return out


def traffic(size: int, run_id: str, indicators: List[Indicator], hit_rate: float = 0.001,
            seed: int = 5) -> List[Dict[str, Any]]:
    """Firewall, DNS and proxy events; about `hit_rate` of them hit an indicator."""
    rng = random.Random(f"{seed}-{run_id}")
    by_type = {k: [i.value for i in indicators if i.indicator_type == k] for k in ("ip", "domain", "url")}
    events = []
    for i in range(size):
        hit = rng.random() < hit_rate
        kind = i % 3
        if kind == 0:
            dst = rng.choice(by_type["ip"]) if hit and by_type["ip"] else f"203.0.113.{rng.randint(1, 254)}"
            attrs = {"dst_ip": dst, "dst_port": 443, "event_type": "network_connection"}
            service = "firewall"
        elif kind == 1:
            name = (f"www.{rng.choice(by_type['domain'])}" if hit and by_type["domain"]
                    else f"host{rng.randint(1, 999)}.corp.example")
            attrs = {"query": name, "event_type": "dns_query"}
            service = "dns"
        else:
            url = (rng.choice(by_type["url"]) if hit and by_type["url"]
                   else f"https://cdn{rng.randint(1, 50)}.example/static/{rng.randint(1, 9999)}.js")
            attrs = {"url": url, "http_method": "GET"}
            service = "proxy"
        events.append({"service": service, "level": "info", "msg": f"bench {run_id} {i}",
                       "src_ip": f"10.0.{i % 4}.{i % 250 + 1}", "attrs": attrs})
    return events


class _Index:
    def __init__(self, indicators: List[Indicator]):
        self.sets: Dict[str, Dict[str, Indicator]] = {}
        for i in indicators:
            self.sets.setdefault(i.indicator_type, {})[i.normalized()] = i

    async def tenant_set(self, tenant_id, now=None):
        return self.sets


async def enrich(events: List[Dict[str, Any]], indicators: List[Indicator]) -> Dict[str, Any]:
    from enrichment_processors import Enrichers
    from ingest_enrichment import enrich_events

    return await enrich_events(TENANT, events, index=_Index(indicators), enrichers=Enrichers())


def compare(off: Dict[str, Any], on: Dict[str, Any], limit_pct: float = 10) -> Dict[str, Any]:
    off_eps, on_eps = float(off["events_per_second"]), float(on["events_per_second"])
    drop = round(100 * (off_eps - on_eps) / off_eps, 2) if off_eps else 0.0
    return {"off_eps": off_eps, "on_eps": on_eps, "drop_pct": drop, "limit_pct": limit_pct, "pass": drop < limit_pct}


def in_process(indicators: List[Indicator], events: int = 30_000, rounds: int = 5) -> Dict[str, Any]:
    def per_event(index_indicators):
        timings = []
        for r in range(rounds):
            batch = traffic(events, f"inproc-{r}", indicators)
            start = time.perf_counter()
            asyncio.run(enrich(batch, index_indicators))
            timings.append((time.perf_counter() - start) / events)
        return statistics.median(timings)

    empty, loaded = per_event([]), per_event(indicators)
    return {"indicators": len(indicators), "events": events, "rounds": rounds,
            "us_per_event_without_intel": round(empty * 1e6, 2), "us_per_event_with_intel": round(loaded * 1e6, 2),
            "added_us_per_event": round((loaded - empty) * 1e6, 2)}


# -- live A/B ---------------------------------------------------------------

def _load_indicators(tenant_id: str, indicators: List[Indicator]) -> None:
    from perf_bench import clickhouse

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.000")
    for start in range(0, len(indicators), 20_000):
        rows = "\n".join(json.dumps({"tenant_id": tenant_id, "indicator_type": i.indicator_type, "value": i.normalized(),
                                     "threat_type": i.threat_type, "confidence": i.confidence, "source": "bench",
                                     "feed_id": "bench", "tags": [], "updated_at": now, "deleted": 0})
                         for i in indicators[start:start + 20_000])
        clickhouse(f"INSERT INTO threat_indicators_mt FORMAT JSONEachRow\n{rows}")


def _clear_indicators(tenant_id: str) -> None:
    from perf_bench import clickhouse

    clickhouse(f"ALTER TABLE threat_indicators_mt DELETE WHERE tenant_id = '{tenant_id}' AND feed_id = 'bench' "
               "SETTINGS mutations_sync = 1")


def _ingest(client, indicators, batches: int, batch_size: int) -> Dict[str, Any]:
    run_id = uuid.uuid4().hex[:8]
    payloads = [traffic(batch_size, f"{run_id}-{b}", indicators) for b in range(batches)]
    start = time.perf_counter()
    for payload in payloads:
        client.post("/v1/ingest/logs/batch", payload)
    seconds = time.perf_counter() - start
    return {"events_per_second": round(batch_size * batches / seconds, 1), "seconds": round(seconds, 3)}


def _settle(client, quiet_s: float = 0.3, streak: int = 3, timeout_s: float = 600) -> None:
    """Wait until the API has drained the previous run's post-ingest work:
    `streak` one-event probes in a row answered within `quiet_s`."""
    deadline, good = time.time() + timeout_s, 0
    while good < streak and time.time() < deadline:
        start = time.perf_counter()
        client.post("/v1/ingest/logs/batch", [{"service": "bench-settle", "level": "info", "msg": "probe"}])
        good = good + 1 if time.perf_counter() - start < quiet_s else 0
        time.sleep(1)


def live_ab(connect, indicators: List[Indicator], rounds: int = 3, batches: int = 20,
            batch_size: int = 1000, index_ttl_s: int = 65) -> Dict[str, Any]:
    """`connect()` returns a fresh logged-in client (tokens expire during long runs).
    Rounds alternate which side goes first, so drift affects both equally."""
    tenant_id = connect().tenant_id
    if not all(c.isalnum() or c == "-" for c in tenant_id):
        raise ValueError("unexpected tenant id")
    _clear_indicators(tenant_id)
    runs: Dict[str, List[Dict[str, Any]]] = {"off": [], "on": []}

    def measure(side: str) -> None:
        if side == "on":
            _load_indicators(tenant_id, indicators)
        else:
            _clear_indicators(tenant_id)
        time.sleep(index_ttl_s)  # the API's indicator index reloads after its TTL
        client = connect()
        _ingest(client, indicators, 1, batch_size)  # warm-up (loads the index)
        _settle(client)
        runs[side].append(_ingest(client, indicators, batches, batch_size))
        _settle(client)

    try:
        for r in range(rounds):
            for side in (("off", "on") if r % 2 == 0 else ("on", "off")):
                measure(side)
            print(f"round {r + 1}: off {runs['off'][-1]['events_per_second']} ev/s, "
                  f"on {runs['on'][-1]['events_per_second']} ev/s", flush=True)
    finally:
        _clear_indicators(tenant_id)
    median = lambda side: {"events_per_second": statistics.median(x["events_per_second"] for x in runs[side])}  # noqa: E731
    return {"rounds": rounds, "batches": batches, "batch_size": batch_size, **runs,
            **compare(median("off"), median("on"))}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Threat-intel enrichment benchmark")
    parser.add_argument("--api", default=os.getenv("LOGFORGE_API_URL", "http://localhost:7080"))
    parser.add_argument("--indicators", type=int, default=100_000)
    parser.add_argument("--live", action="store_true", help="also run the live ingest A/B")
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--batches", type=int, default=10)
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    indicators = synthetic_indicators(args.indicators)
    results: Dict[str, Any] = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "environment": {"host": platform.platform(), "python": platform.python_version(),
                                               "cpus": os.cpu_count()},
                               "in_process": in_process(indicators)}
    print(f"in-process: {results['in_process']}", flush=True)
    if args.live:
        from perf_bench import login

        email, password = os.getenv("BENCH_EMAIL"), os.getenv("BENCH_PASSWORD")
        if not email or not password:
            print("Set BENCH_EMAIL and BENCH_PASSWORD (a user of a dedicated benchmark tenant).", file=sys.stderr)
            return 2
        results["live_ingest"] = live_ab(lambda: login(args.api, email, password), indicators, rounds=args.rounds,
                                          batches=args.batches)
        live = results["live_ingest"]
        print(f"live ingest: off {live['off_eps']} ev/s, on {live['on_eps']} ev/s, drop {live['drop_pct']}%")
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
