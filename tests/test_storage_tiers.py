"""
Storage tiers (Phase 12): retention policies per tenant and data type, and the
plan that ages a tenant's data from ClickHouse to Parquet archives and out.

Hot and warm are ClickHouse volumes (local disk, then S3). Parts mix tenants,
so the move from hot to warm is deployment-wide (`hot_days`). Per tenant and
data type: how many days stay searchable in ClickHouse, and how long the
Parquet archive of each day is kept.
"""

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import storage_tiers as st  # noqa: E402


def test_config_ships_the_four_data_types_with_defaults():
    cfg = st.load_config()
    assert set(cfg.data_types) == {"logs", "security", "traces", "metrics"}
    assert cfg.data_types["logs"].table == "logs_raw_mt"
    assert cfg.data_types["logs"].ts == "ts"
    assert cfg.data_types["security"].ts == "created_at"
    assert cfg.hot_days >= 1
    for name, policy in cfg.defaults.items():
        st.validate(policy, cfg)  # the shipped defaults are valid
        assert policy.data_type == name


def test_validate_rejects_bad_policies():
    cfg = st.load_config()
    with pytest.raises(st.PolicyError, match="searchable"):
        st.validate(st.Policy("logs", 0, 365), cfg)
    with pytest.raises(st.PolicyError, match="searchable"):
        st.validate(st.Policy("logs", cfg.max_searchable_days + 1, 0), cfg)
    with pytest.raises(st.PolicyError, match="archive"):
        st.validate(st.Policy("logs", 30, 10), cfg)  # archive must outlast searchable
    with pytest.raises(st.PolicyError, match="archive"):
        st.validate(st.Policy("logs", 30, cfg.max_archive_days + 1), cfg)
    with pytest.raises(st.PolicyError, match="data type"):
        st.validate(st.Policy("blobs", 30, 0), cfg)
    st.validate(st.Policy("logs", 30, 0), cfg)  # no archive: deleted after 30 days
    st.validate(st.Policy("logs", 30, 30), cfg)


def test_effective_policies_overlay_tenant_choices_on_defaults():
    cfg = st.load_config()
    stored = [st.Policy("logs", 14, 730)]
    effective = st.effective(stored, cfg)
    assert effective["logs"] == st.Policy("logs", 14, 730)
    assert effective["security"] == cfg.defaults["security"]


TODAY = date(2026, 11, 20)


def d(n):
    """n days before TODAY."""
    return date.fromordinal(TODAY.toordinal() - n)


def test_plan_archives_days_leaving_clickhouse_before_deleting_them():
    policy = st.Policy("logs", 30, 365)
    days = {d(29): 10, d(30): 10, d(31): 7, d(40): 5}
    actions = st.plan(policy, TODAY, days, archived={})
    # day 29 is still searchable; days 30+ are past the 30 searchable days
    assert [(a.kind, a.day) for a in actions] == [("archive", d(40)), ("archive", d(31)), ("archive", d(30))]


def test_plan_deletes_only_days_whose_archive_matches():
    policy = st.Policy("logs", 30, 365)
    days = {d(31): 7, d(40): 5}
    archived = {d(31): 7, d(40): 4}  # day 40 gained a late event since it was archived
    actions = st.plan(policy, TODAY, days, archived)
    assert [(a.kind, a.day) for a in actions] == [("archive", d(40)), ("delete", d(31))]


def test_plan_without_archive_deletes_directly():
    policy = st.Policy("logs", 30, 0)
    actions = st.plan(policy, TODAY, {d(31): 7, d(2): 1}, archived={})
    assert [(a.kind, a.day) for a in actions] == [("delete", d(31))]


def test_plan_expires_archives_past_the_archive_period():
    policy = st.Policy("logs", 30, 365)
    archived = {d(365): 9, d(366): 9, d(400): 3, d(100): 2}
    actions = st.plan(policy, TODAY, {}, archived)
    assert [(a.kind, a.day) for a in actions] == [("expire", d(400)), ("expire", d(366)), ("expire", d(365))]


def test_plan_with_archive_shortened_below_searchable_never_loses_unarchived_data():
    # archive_days == searchable_days: a day is archived, then deleted from
    # ClickHouse and expired from the archive on the same run, never before
    policy = st.Policy("logs", 30, 30)
    actions = st.plan(policy, TODAY, {d(30): 4}, archived={})
    assert [(a.kind, a.day) for a in actions] == [("archive", d(30))]
    actions = st.plan(policy, TODAY, {d(30): 4}, archived={d(30): 4})
    assert [(a.kind, a.day) for a in actions] == [("delete", d(30)), ("expire", d(30))]


def test_archive_path_is_per_tenant_type_and_day():
    assert st.archive_key("t-1", "logs", date(2026, 1, 2)) == "t-1/logs/2026/01/02.parquet"
    with pytest.raises(st.PolicyError):
        st.archive_key("../other", "logs", date(2026, 1, 2))
    with pytest.raises(st.PolicyError):
        st.archive_key("t-1", "logs/x", date(2026, 1, 2))


def test_table_ttl_moves_to_warm_and_caps_at_the_longest_searchable_period():
    cfg = st.load_config()
    ttl = st.table_ttl(cfg.data_types["logs"], cfg)
    assert f"toDateTime(ts) + toIntervalDay({cfg.hot_days}) TO VOLUME 'warm'" in ttl
    assert f"toDateTime(ts) + toIntervalDay({cfg.max_searchable_days}) DELETE" in ttl
    assert "TO VOLUME" not in st.table_ttl(cfg.data_types["logs"], cfg, warm=False)
