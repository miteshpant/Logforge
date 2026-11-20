"""The reference architecture calculator (Phase 12)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import reference_architecture as ra  # noqa: E402


def test_volumes_follow_the_measured_sizes():
    out = ra.plan(50, events_per_second_per_api=1000)
    events = 50e9 / 297
    assert out["volume"]["events_per_day"] == round(events)
    assert out["volume"]["stored_gib_per_day_per_replica"] == round(events * 29 / 1024 ** 3, 2)
    # 7 hot days and 23 warm days on each of 2 replicas; 335 days of Parquet once
    assert out["steady_state_gib"]["hot_all_replicas"] == round(events * 29 / 1024 ** 3 * 7 * 2)
    assert out["steady_state_gib"]["cold_parquet"] == round(events * 33 / 1024 ** 3 * 335)


def test_api_replicas_cover_peak_and_never_drop_below_two():
    out = ra.plan(50, events_per_second_per_api=1000)
    peak = out["volume"]["peak_events_per_second"]
    assert out["api_replicas"] == max(2, -(-peak // 1000))
    assert ra.plan(1, events_per_second_per_api=100000)["api_replicas"] == 2


def test_total_is_the_sum_and_checked_against_the_target():
    out = ra.plan(50, events_per_second_per_api=1000)
    m = out["monthly_usd"]
    assert abs(m["total"] - sum(m["storage"].values()) - sum(m["compute"].values())) < 0.05
    assert out["yearly_usd"] == round(m["total"] * 12)
    assert out["within_target"] == (m["total"] <= ra.TARGET_PER_MONTH)
