"""
Tests for LF-017 / LF-022 -- every log query runs over a bounded time window.

`GET /v1/logs` had no time-range parameters at all, so ClickHouse read every
monthly partition for the tenant before applying LIMIT. `POST /v1/query/logql`
went the other way and returned 400 unless the caller supplied an explicit
range -- the endpoint's own docstring example failed.

Pinned here, for the shared `resolve_time_window` helper:
* omitted bounds default to the last hour ending now -- never unbounded;
* `since` accepts the documented relative forms (15m / 24h / 7d);
* invalid input and inverted or over-wide ranges are 400s, not slow successes;
* naive datetimes are treated as UTC.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from routers.query import (
    DEFAULT_QUERY_WINDOW,
    _parse_since,
    resolve_time_window,
)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_omitted_bounds_default_to_last_hour():
    before = datetime.now(timezone.utc)
    start, end = resolve_time_window()
    after = datetime.now(timezone.utc)

    assert before <= end <= after
    assert end - start == DEFAULT_QUERY_WINDOW
    assert DEFAULT_QUERY_WINDOW == timedelta(hours=1)


def test_explicit_range_is_respected():
    start_in = datetime(2026, 8, 15, 0, 0, tzinfo=timezone.utc)
    end_in = datetime(2026, 8, 15, 6, 0, tzinfo=timezone.utc)
    start, end = resolve_time_window(start_in, end_in)
    assert (start, end) == (start_in, end_in)


def test_iso_strings_with_z_suffix_are_parsed():
    start, end = resolve_time_window(
        "2026-08-15T00:00:00Z", "2026-08-15T06:00:00Z"
    )
    assert start == datetime(2026, 8, 15, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 15, 6, 0, tzinfo=timezone.utc)


def test_naive_datetimes_are_treated_as_utc():
    start, end = resolve_time_window(
        datetime(2026, 8, 15, 0, 0), datetime(2026, 8, 15, 1, 0)
    )
    assert start.tzinfo is not None and end.tzinfo is not None
    assert start == datetime(2026, 8, 15, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Relative ranges (LF-022 `since`)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "since,expected",
    [
        ("15m", timedelta(minutes=15)),
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("2w", timedelta(weeks=2)),
        ("90s", timedelta(seconds=90)),
    ],
)
def test_since_parses_documented_forms(since, expected):
    assert _parse_since(since) == expected


def test_since_produces_window_ending_now():
    start, end = resolve_time_window(since="15m")
    assert end - start == timedelta(minutes=15)


@pytest.mark.parametrize("bad", ["", "15", "m", "15x", "abc", "-5m"])
def test_invalid_since_is_a_400(bad):
    with pytest.raises(HTTPException) as exc:
        _parse_since(bad)
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------


def test_inverted_range_is_a_400():
    with pytest.raises(HTTPException) as exc:
        resolve_time_window("2026-08-15T06:00:00Z", "2026-08-15T00:00:00Z")
    assert exc.value.status_code == 400


def test_over_wide_range_is_a_400(monkeypatch):
    monkeypatch.setenv("LOGFORGE_MAX_QUERY_WINDOW_DAYS", "31")
    with pytest.raises(HTTPException) as exc:
        resolve_time_window("2026-01-01T00:00:00Z", "2026-08-01T00:00:00Z")
    assert exc.value.status_code == 400
    assert "31" in str(exc.value.detail)


def test_max_window_is_configurable(monkeypatch):
    monkeypatch.setenv("LOGFORGE_MAX_QUERY_WINDOW_DAYS", "365")
    start, end = resolve_time_window(
        "2026-01-01T00:00:00Z", "2026-08-01T00:00:00Z"
    )
    assert end - start == timedelta(days=212)


def test_garbage_datetime_is_a_400():
    with pytest.raises(HTTPException) as exc:
        resolve_time_window("not-a-date", None)
    assert exc.value.status_code == 400
