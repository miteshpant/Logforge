"""Archive search under a data scope: the Parquet read is wrapped in a subquery
carrying the scope's service filter (ClickHouse's additional_table_filters don't
reach the s3() table function), instead of archive search being refused."""
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import archive_query  # noqa: E402
from data_scope import DataScope  # noqa: E402

START, END = datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc)


def compiled(scope=None):
    return archive_query.compile_archive("error | stats count() by service", "t1", [date(2026, 1, 1)], START, END,
                                         scope=scope).sql


def test_unscoped_reads_the_archive_directly():
    assert "FROM s3(logforge_archive" in compiled()


def test_scoped_reads_only_the_scope_services():
    sql = compiled(DataScope(services=("auth", "payments-*")))
    assert "(SELECT * FROM s3(logforge_archive" in sql
    assert "WHERE service IN ('auth') OR service LIKE 'payments-%%')" in sql  # % escaped for formatting


def test_an_empty_scope_reads_nothing():
    assert "WHERE 0)" in compiled(DataScope(services=()))


def test_a_prefix_scope_formats_with_parameters():
    from clickhouse_connect.driver.query import finalize_query

    comp = archive_query.compile_archive("| stats count() by service", "t1", [date(2026, 1, 1)], START, END,
                                         scope=DataScope(services=("payments-*",)))
    assert "LIKE 'payments-%'" in finalize_query(comp.sql, comp.params)
