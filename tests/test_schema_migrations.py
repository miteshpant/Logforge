"""
Tests for ENH-021 -- versioned schema migration runner.

`infra/docker/clickhouse/migrations/` held numbered SQL files, but
`compose.yml` mounts only `init_simple.sql`, so migrations 001-009 were never
applied automatically. The application compensated with runtime
`CREATE TABLE IF NOT EXISTS` from `DatabaseLayer`, putting DDL in application
code and letting environments drift.

Automatic DDL is dangerous, so the emphasis here is on the safety properties:
opt-in, idempotent, checksummed, ordered, halting on failure, and refusing
destructive statements by default.
"""

from pathlib import Path

import pytest

from schema_migrations import (
    MigrationError,
    MigrationRunner,
    discover_migrations,
)

REAL_MIGRATIONS = (
    Path(__file__).resolve().parent.parent
    / "infra" / "docker" / "clickhouse" / "migrations"
)


class _FakeClient:
    """Records DDL instead of executing it."""

    def __init__(self, applied=None, fail_on=None):
        self.commands = []
        self.inserts = []
        self._applied = applied or {}
        self._fail_on = fail_on

    def command(self, sql, *args, **kwargs):
        if self._fail_on and self._fail_on in sql:
            raise RuntimeError("simulated DDL failure")
        self.commands.append(sql)
        return None

    def query(self, sql, *args, **kwargs):
        class _Result:
            result_rows = [[v, c] for v, c in self._applied.items()]

        return _Result()

    def insert(self, table, rows, column_names=None):
        self.inserts.append((table, rows))


def _write(directory, name, sql):
    path = directory / name
    path.write_text(sql, encoding="utf-8")
    return path


@pytest.fixture
def migrations_dir(tmp_path):
    directory = tmp_path / "migrations"
    directory.mkdir()
    return directory


# ---------------------------------------------------------------------------
# Discovery and ordering
# ---------------------------------------------------------------------------


def test_discovers_migration_files(migrations_dir):
    _write(migrations_dir, "001_first.sql", "CREATE TABLE a (x String) ENGINE=Memory;")
    _write(migrations_dir, "002_second.sql", "CREATE TABLE b (x String) ENGINE=Memory;")

    found = discover_migrations(migrations_dir)

    assert [m.version for m in found] == ["001", "002"]


def test_migrations_are_ordered_numerically(migrations_dir):
    """
    Lexical sorting would place 010 between 001 and 002, applying a later
    migration before an earlier one.
    """
    for name in ("001_a.sql", "002_b.sql", "010_j.sql", "009_i.sql"):
        _write(migrations_dir, name, "SELECT 1;")

    versions = [m.version for m in discover_migrations(migrations_dir)]

    assert versions == ["001", "002", "009", "010"]


def test_files_without_a_version_prefix_are_skipped(migrations_dir):
    _write(migrations_dir, "001_ok.sql", "SELECT 1;")
    _write(migrations_dir, "notes.sql", "SELECT 1;")

    assert [m.version for m in discover_migrations(migrations_dir)] == ["001"]


def test_missing_directory_is_not_an_error():
    assert discover_migrations(Path("/nonexistent/path")) == []


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


def test_pending_migrations_are_reported(migrations_dir):
    _write(migrations_dir, "001_a.sql", "SELECT 1;")
    _write(migrations_dir, "002_b.sql", "SELECT 1;")

    runner = MigrationRunner(_FakeClient(), migrations_dir)
    plan = runner.plan()

    assert plan["pending"] == ["001", "002"]


def test_applied_migrations_are_not_reapplied(migrations_dir):
    sql = "CREATE TABLE a (x String) ENGINE=Memory;"
    _write(migrations_dir, "001_a.sql", sql)

    migration = discover_migrations(migrations_dir)[0]
    client = _FakeClient(applied={"001": migration.checksum})

    result = MigrationRunner(client, migrations_dir).run()

    assert result["applied_now"] == []
    assert not any("CREATE TABLE a" in c for c in client.commands)


def test_running_twice_applies_each_migration_once(migrations_dir):
    _write(migrations_dir, "001_a.sql", "CREATE TABLE a (x String) ENGINE=Memory;")

    client = _FakeClient()
    first = MigrationRunner(client, migrations_dir).run()

    migration = discover_migrations(migrations_dir)[0]
    client_second = _FakeClient(applied={"001": migration.checksum})
    second = MigrationRunner(client_second, migrations_dir).run()

    assert first["applied_now"] == ["001"]
    assert second["applied_now"] == []


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


def test_modified_migration_is_reported_as_drift(migrations_dir):
    """
    Re-running a changed file could be destructive; ignoring it hides real
    drift. Surfacing it forces a human decision.
    """
    _write(migrations_dir, "001_a.sql", "SELECT 1;")
    client = _FakeClient(applied={"001": "a-stale-checksum"})

    plan = MigrationRunner(client, migrations_dir).plan()

    assert plan["drifted"] == ["001"]
    assert plan["pending"] == []


def test_unchanged_migration_is_not_drift(migrations_dir):
    _write(migrations_dir, "001_a.sql", "SELECT 1;")
    migration = discover_migrations(migrations_dir)[0]

    plan = MigrationRunner(
        _FakeClient(applied={"001": migration.checksum}), migrations_dir
    ).plan()

    assert plan["drifted"] == []


# ---------------------------------------------------------------------------
# Destructive statement refusal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE logs_raw_mt;",
        "TRUNCATE TABLE logs_raw_mt;",
        "DELETE FROM logs_raw_mt WHERE 1;",
        "drop database logforge;",
    ],
)
def test_destructive_migrations_are_refused_by_default(migrations_dir, sql, monkeypatch):
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_MIGRATIONS", raising=False)
    _write(migrations_dir, "001_danger.sql", sql)

    with pytest.raises(MigrationError, match="destructive"):
        MigrationRunner(_FakeClient(), migrations_dir).run()


def test_destructive_migrations_run_when_explicitly_allowed(migrations_dir, monkeypatch):
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_MIGRATIONS", "true")
    _write(migrations_dir, "001_danger.sql", "DROP TABLE old_table;")

    result = MigrationRunner(_FakeClient(), migrations_dir).run()

    assert result["applied_now"] == ["001"]


def test_additive_migrations_are_not_flagged_destructive(migrations_dir):
    _write(
        migrations_dir,
        "001_add.sql",
        "ALTER TABLE t ADD COLUMN IF NOT EXISTS c String DEFAULT '';",
    )

    assert discover_migrations(migrations_dir)[0].is_destructive() is False


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


def test_failure_halts_remaining_migrations(migrations_dir):
    """
    Continuing past a failure would apply later migrations over a schema that
    never received an earlier change.
    """
    _write(migrations_dir, "001_ok.sql", "CREATE TABLE ok (x String) ENGINE=Memory;")
    _write(migrations_dir, "002_bad.sql", "CREATE TABLE bad (x String) ENGINE=Memory;")
    _write(migrations_dir, "003_never.sql", "CREATE TABLE never (x String) ENGINE=Memory;")

    client = _FakeClient(fail_on="bad")

    with pytest.raises(MigrationError):
        MigrationRunner(client, migrations_dir).run()

    assert not any("never" in c for c in client.commands)


def test_failed_migration_is_not_recorded_as_applied(migrations_dir):
    _write(migrations_dir, "001_bad.sql", "CREATE TABLE bad (x String) ENGINE=Memory;")
    client = _FakeClient(fail_on="bad")

    with pytest.raises(MigrationError):
        MigrationRunner(client, migrations_dir).run()

    assert client.inserts == [], "A failed migration must not be recorded"


# ---------------------------------------------------------------------------
# Opt-in behaviour
# ---------------------------------------------------------------------------


def test_migrations_are_opt_in(monkeypatch):
    monkeypatch.delenv("RUN_MIGRATIONS_ON_STARTUP", raising=False)
    assert MigrationRunner.is_enabled() is False


def test_migrations_enabled_by_environment(monkeypatch):
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "true")
    assert MigrationRunner.is_enabled() is True


def test_dry_run_changes_nothing(migrations_dir):
    _write(migrations_dir, "001_a.sql", "CREATE TABLE a (x String) ENGINE=Memory;")
    client = _FakeClient()

    result = MigrationRunner(client, migrations_dir).run(dry_run=True)

    assert result["dry_run"] is True
    assert result["applied_now"] == []
    assert not any("CREATE TABLE a" in c for c in client.commands)


def test_startup_defaults_to_dry_run(monkeypatch, migrations_dir):
    """The default deployment behaviour must be observation, not mutation."""
    monkeypatch.delenv("RUN_MIGRATIONS_ON_STARTUP", raising=False)
    monkeypatch.setenv("MIGRATIONS_DIR", str(migrations_dir))
    _write(migrations_dir, "001_a.sql", "CREATE TABLE a (x String) ENGINE=Memory;")

    from schema_migrations import run_migrations_if_enabled

    client = _FakeClient()
    result = run_migrations_if_enabled(client)

    assert result["dry_run"] is True
    assert result["pending"] == ["001"]


# ---------------------------------------------------------------------------
# Statement splitting
# ---------------------------------------------------------------------------


def test_multi_statement_files_are_split(migrations_dir):
    _write(
        migrations_dir,
        "001_multi.sql",
        "CREATE TABLE a (x String) ENGINE=Memory;\n"
        "CREATE TABLE b (x String) ENGINE=Memory;\n",
    )

    assert len(discover_migrations(migrations_dir)[0].statements()) == 2


def test_comments_do_not_split_statements(migrations_dir):
    """A semicolon inside a comment must not break a statement in half."""
    _write(
        migrations_dir,
        "001_commented.sql",
        "-- a comment; with a semicolon\n"
        "CREATE TABLE a (x String) ENGINE=Memory;\n",
    )

    statements = discover_migrations(migrations_dir)[0].statements()

    assert len(statements) == 1
    assert statements[0].startswith("CREATE TABLE a")


# ---------------------------------------------------------------------------
# The real migration set
# ---------------------------------------------------------------------------


def test_shipped_migrations_are_discoverable():
    found = discover_migrations(REAL_MIGRATIONS)
    assert found, "No migrations discovered in the repository"


# Migrations that are KNOWINGLY destructive. Each must be gated behind
# ALLOW_DESTRUCTIVE_MIGRATIONS and must document its rollback.
KNOWN_DESTRUCTIVE = {"011_repartition_logs_tables"}


def test_no_unexpected_migration_is_destructive():
    """
    A routine deploy must never destroy data. A destructive migration is
    allowed only if it is on the explicit list -- so one cannot be added by
    accident.
    """
    destructive = {
        f"{m.version}_{m.name}"
        for m in discover_migrations(REAL_MIGRATIONS)
        if m.is_destructive()
    }

    unexpected = destructive - KNOWN_DESTRUCTIVE
    assert not unexpected, (
        f"Unexpected destructive migrations: {unexpected}. If deliberate, add "
        "to KNOWN_DESTRUCTIVE and document the rollback."
    )


@pytest.mark.parametrize("name", sorted(KNOWN_DESTRUCTIVE))
def test_destructive_migrations_are_refused_without_the_flag(name, monkeypatch):
    """
    The safety net that makes shipping a destructive migration acceptable: the
    runner must refuse it during a normal deploy.
    """
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_MIGRATIONS", raising=False)

    migration = next(
        m for m in discover_migrations(REAL_MIGRATIONS)
        if f"{m.version}_{m.name}" == name
    )

    assert migration.is_destructive() is True, (
        f"{name} is listed as destructive but the runner does not detect it, "
        "so it would run unguarded."
    )


@pytest.mark.parametrize("name", sorted(KNOWN_DESTRUCTIVE))
def test_destructive_migrations_document_rollback(name):
    """
    An operator running a destructive migration at 3am must find the recovery
    procedure in the file itself.
    """
    migration = next(
        m for m in discover_migrations(REAL_MIGRATIONS)
        if f"{m.version}_{m.name}" == name
    )

    text = migration.sql.upper()
    assert "ROLLBACK" in text, f"{name} documents no rollback procedure"
    assert "RENAME TABLE" in text, (
        f"{name} must preserve the original table (rename, not drop) so "
        "recovery is possible."
    )


def test_repartition_migration_preserves_the_original_tables():
    """
    The rewrite must RENAME the old table rather than dropping it, so a failed
    migration is recoverable.
    """
    migration = next(
        m for m in discover_migrations(REAL_MIGRATIONS)
        if "repartition" in m.name
    )
    statements = [s.upper() for s in migration.statements()]

    renames = [s for s in statements if s.startswith("RENAME TABLE")]
    assert any("_OLD" in s for s in renames), (
        "The original table must be renamed to *_old, not dropped."
    )

    executable_drops = [s for s in statements if s.startswith("DROP TABLE")]
    assert not executable_drops, (
        "The migration must not DROP anything; cleanup is a manual step after "
        f"verification. Found: {executable_drops}"
    )


def test_repartition_migration_removes_customer_id_from_partition_key():
    """The actual fix: partition count must become O(months), not O(tenants x months)."""
    migration = next(
        m for m in discover_migrations(REAL_MIGRATIONS)
        if "repartition" in m.name
    )

    executable = " ".join(migration.statements())

    assert "PARTITION BY toYYYYMM(ts)" in executable
    assert "PARTITION BY (customer_id" not in executable


def test_repartition_migration_keeps_customer_id_first_in_sort_order():
    """
    Tenant-scoped queries prune via the sort order, not the partition key.
    Losing `customer_id` from the front of ORDER BY would make every
    tenant-scoped query slower -- trading one problem for a worse one.
    """
    migration = next(
        m for m in discover_migrations(REAL_MIGRATIONS)
        if "repartition" in m.name
    )

    for statement in migration.statements():
        if "ORDER BY" in statement.upper() and "CREATE TABLE" in statement.upper():
            order_by = statement.upper().split("ORDER BY", 1)[1]
            assert order_by.strip().startswith("(CUSTOMER_ID"), (
                f"customer_id must remain first in ORDER BY: {order_by[:60]}"
            )


def test_shipped_migration_versions_are_unique():
    versions = [m.version for m in discover_migrations(REAL_MIGRATIONS)]
    assert len(versions) == len(set(versions)), f"Duplicate versions: {versions}"


def test_security_events_reconciliation_migration_exists():
    """
    The conflicting definitions of security_events_mt are reconciled by an
    additive migration (ENH-021).
    """
    names = [m.name for m in discover_migrations(REAL_MIGRATIONS)]
    assert any("security_events" in n for n in names)


def test_reconciliation_migration_only_adds_columns():
    """It must not drop the legacy columns -- that would destroy data."""
    migration = next(
        m for m in discover_migrations(REAL_MIGRATIONS)
        if "security_events" in m.name
    )

    for statement in migration.statements():
        assert "ADD COLUMN" in statement.upper(), (
            f"Non-additive statement in reconciliation migration: {statement}"
        )
        assert "DROP" not in statement.upper()


# ---------------------------------------------------------------------------
# Runtime DDL
# ---------------------------------------------------------------------------


def test_runtime_ddl_can_be_disabled(monkeypatch):
    """
    Schema should be owned by migrations, not application code. Runtime DDL
    also requires the app's database user to hold privileges it should not need.
    """
    from database_layer import DatabaseLayer

    monkeypatch.setenv("ALLOW_RUNTIME_DDL", "false")
    assert DatabaseLayer._runtime_ddl_enabled() is False


def test_runtime_ddl_defaults_to_enabled(monkeypatch):
    """Default preserves existing behaviour for deployments that rely on it."""
    from database_layer import DatabaseLayer

    monkeypatch.delenv("ALLOW_RUNTIME_DDL", raising=False)
    assert DatabaseLayer._runtime_ddl_enabled() is True


def test_startup_runs_the_migration_check():
    import inspect

    import dependencies

    source = inspect.getsource(dependencies.initialize_engines)
    assert "run_migrations_if_enabled" in source


# ---------------------------------------------------------------------------
# Directory resolution (regression: container startup crash)
# ---------------------------------------------------------------------------


def test_default_resolution_survives_shallow_install(monkeypatch):
    """
    In a container the module lives at a shallow path like /app, where the old
    `Path(__file__).resolve().parents[2]` raised IndexError before the app
    could even start. Resolution must never crash; absence is reported as None.
    """
    import schema_migrations

    monkeypatch.setattr(schema_migrations, "__file__", "/schema_migrations.py")
    assert schema_migrations._default_migrations_dir() is None


def test_migrations_dir_env_var_is_respected(monkeypatch, migrations_dir):
    """
    The old code passed the computed default as os.getenv's second argument,
    evaluating (and crashing on) it even when MIGRATIONS_DIR was set.
    """
    monkeypatch.setenv("MIGRATIONS_DIR", str(migrations_dir))
    runner = MigrationRunner(_FakeClient())
    assert runner.migrations_dir == migrations_dir


def test_enabled_with_missing_dir_fails_explicitly(monkeypatch, tmp_path):
    from schema_migrations import run_migrations_if_enabled

    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "true")
    monkeypatch.setenv("MIGRATIONS_DIR", str(tmp_path / "does_not_exist"))
    with pytest.raises(MigrationError):
        run_migrations_if_enabled(_FakeClient())


def test_disabled_with_missing_dir_reports_unavailable(monkeypatch, tmp_path):
    """Observation mode must not crash startup, and must not pretend the
    migration state is known -- it reports the directory as unavailable."""
    from schema_migrations import run_migrations_if_enabled

    monkeypatch.delenv("RUN_MIGRATIONS_ON_STARTUP", raising=False)
    monkeypatch.setenv("MIGRATIONS_DIR", str(tmp_path / "does_not_exist"))
    client = _FakeClient()
    result = run_migrations_if_enabled(client)
    assert result["unavailable"] is True
    assert result["applied_now"] == []
    assert client.commands == []


# ---------------------------------------------------------------------------
# Shared history table written by run_migrations.sh
# ---------------------------------------------------------------------------
# The compose stack's shell runner creates schema_migrations as
# (migration_name, executed_at). The versioned query failed against it on every
# real deployment, so every migration looked pending: with
# RUN_MIGRATIONS_ON_STARTUP=true they would all have re-run.


class _ShellHistoryClient(_FakeClient):
    """schema_migrations as created by run_migrations.sh."""

    def __init__(self, names):
        super().__init__()
        self._names = names

    def query(self, sql, *args, **kwargs):
        if "SELECT version" in sql:
            raise RuntimeError("Code: 47. Missing columns: 'success' 'checksum' 'version'")
        names = self._names

        class _Result:
            result_rows = [[n] for n in names]

        return _Result()


def test_shell_runner_history_counts_as_applied(migrations_dir):
    _write(migrations_dir, "001_a.sql", "CREATE TABLE a (x String) ENGINE=Memory;")
    _write(migrations_dir, "002_b.sql", "CREATE TABLE b (x String) ENGINE=Memory;")

    client = _ShellHistoryClient(["001_a"])
    plan = MigrationRunner(client, migrations_dir).plan()

    assert plan["applied"] == ["001"]
    assert plan["pending"] == ["002"]
    assert plan["drifted"] == []  # no checksum recorded -> not reported as drift


def test_shell_runner_history_is_not_reapplied_and_is_recorded_compatibly(migrations_dir):
    _write(migrations_dir, "001_a.sql", "CREATE TABLE a (x String) ENGINE=Memory;")
    _write(migrations_dir, "002_b.sql", "CREATE TABLE b (x String) ENGINE=Memory;")

    client = _ShellHistoryClient(["001_a"])
    result = MigrationRunner(client, migrations_dir).run()

    assert result["applied_now"] == ["002"]
    assert not any("CREATE TABLE a" in c for c in client.commands)
    assert client.inserts == [("schema_migrations", [["002_b"]])]
