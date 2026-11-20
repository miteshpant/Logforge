"""
Cost visibility (Phase 12): a tenant's ingest by source, storage per tier,
steady-state projections from its retention, and noise worth dropping.
"""

import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import storage_costs as sc  # noqa: E402
import storage_tiers as st  # noqa: E402

GB = 1024 ** 3
PRICES = {"hot": 0.10, "warm": 0.02, "cold": 0.01}


def test_bytes_per_row_per_disk_falls_back_to_the_table_average():
    ratios = sc.bytes_per_row({"default": (1000, 50_000), "s3_warm": (3000, 90_000)})
    assert ratios == {"default": 50.0, "s3_warm": 30.0, "all": 35.0}
    assert sc.bytes_per_row({}) == {"all": 0.0}


def test_steady_state_follows_the_policy():
    policy = st.Policy("logs", 30, 365)
    out = sc.steady_state(daily_events=10_000_000, stored_bpe=30.0, archive_bpe=20.0, hot_days=7, policy=policy,
                          prices=PRICES)
    assert out["hot"]["days"] == 7 and out["warm"]["days"] == 23 and out["cold"]["days"] == 335
    assert out["hot"]["gb"] == pytest.approx(10_000_000 * 30 * 7 / GB, rel=1e-6)
    assert out["cold"]["gb"] == pytest.approx(10_000_000 * 20 * 335 / GB, rel=1e-6)
    assert out["monthly_cost"]["total"] == pytest.approx(
        out["hot"]["gb"] * 0.10 + out["warm"]["gb"] * 0.02 + out["cold"]["gb"] * 0.01, rel=1e-6)


def test_steady_state_without_archive_or_with_short_searchable():
    out = sc.steady_state(1000, 30.0, 20.0, hot_days=7, policy=st.Policy("logs", 3, 0), prices=PRICES)
    assert (out["hot"]["days"], out["warm"]["days"], out["cold"]["days"]) == (3, 0, 0)


def test_projection_uses_the_last_seven_full_days():
    today = date(2026, 11, 20)
    per_day = {today - timedelta(days=i): (100 * i, 1000 * i) for i in range(0, 15)}  # today is partial
    proj = sc.projection(per_day, today)
    # days 1..7: mean events = 100*4, raw = 1000*4
    assert proj["daily_events"] == 400 and proj["daily_raw_bytes"] == 4000
    assert proj["monthly_raw_bytes"] == 4000 * 30
    assert proj["days_used"] == 7
    assert sc.projection({}, today)["daily_events"] == 0


def test_noise_finds_debug_floods_and_dominant_sources():
    rows = [("checkout", "debug", 600, 60_000), ("checkout", "info", 200, 20_000), ("auth", "info", 150, 15_000),
            ("auth", "error", 50, 5_000)]
    found = sc.noise(rows)
    first = found[0]
    assert (first["service"], first["level"]) == ("checkout", "debug")
    assert first["share"] == pytest.approx(0.6)
    assert first["drop_step"] == {"drop": {}, "if": "level == 'debug'"}
    assert first["routing"] == {"services": ["checkout"]}
    assert all(f["level"] != "error" for f in found)  # errors are never suggested for dropping
    assert sc.noise([("a", "info", 10, 100)]) == []  # one quiet source isn't noise


def test_by_source_rolls_levels_up():
    rows = [("checkout", "debug", 600, 60_000), ("checkout", "info", 200, 20_000), ("auth", "info", 200, 20_000)]
    sources = sc.by_source(rows)
    assert sources[0]["service"] == "checkout" and sources[0]["events"] == 800
    assert sources[0]["share"] == pytest.approx(0.8)
    assert sources[0]["levels"] == {"debug": 600, "info": 200}
