"""
Versioned ClickHouse schema migration runner (ENH-021).

`infra/docker/clickhouse/migrations/` holds numbered SQL files and a
`run_migrations.sh`, but `compose.yml` mounts only `init_simple.sql`, so
migrations 001-009 were never applied automatically. The application compensated
by issuing `CREATE TABLE IF NOT EXISTS` from `DatabaseLayer` at runtime, which
puts DDL in application code and lets environments drift apart.

Safety properties
-----------------
Executing DDL automatically is exactly the kind of change that must not surprise
an operator, so this is built to be safe by construction:

* **Opt-in.** Does nothing unless `RUN_MIGRATIONS_ON_STARTUP=true`. Default is a
  dry-run report of what *would* apply.
* **Idempotent.** Applied versions are recorded in `schema_migrations`; a
  migration runs at most once.
* **Checksummed.** If a file changes after being applied, that is reported as
  drift rather than silently re-run or silently ignored.
* **Ordered and halting.** Migrations apply in version order and stop at the
  first failure, so a partial run cannot leave later migrations applied over a
  missing earlier one.
* **Never destructive by default.** Statements matching DROP/TRUNCATE/DELETE are
  refused unless `ALLOW_DESTRUCTIVE_MIGRATIONS=true`, so a careless file cannot
  destroy data during a routine deploy.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

MIGRATIONS_TABLE = "schema_migrations"

# Statements that can destroy data. Refused unless explicitly allowed.
DESTRUCTIVE_PATTERN = re.compile(
    r"\b(DROP\s+(TABLE|DATABASE|VIEW)|TRUNCATE\s+TABLE|DELETE\s+FROM)\b",
    re.IGNORECASE,
)


class MigrationError(RuntimeError):
    """Raised when a migration cannot be applied."""


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()

    def statements(self) -> List[str]:
        """
        Split the file into individual statements.

        ClickHouse's HTTP interface executes one statement per request, so
        multi-statement files must be split. Comments are stripped first so a
        semicolon inside a comment cannot split a statement.
        """
        without_comments = "\n".join(
            line for line in self.sql.splitlines()
            if not line.strip().startswith("--")
        )
        return [s.strip() for s in without_comments.split(";") if s.strip()]

    def is_destructive(self) -> bool:
        return bool(DESTRUCTIVE_PATTERN.search(self.sql))


def discover_migrations(directory: Path) -> List[Migration]:
    """Load migrations from disk, ordered by version."""
    if not directory.exists():
        return []

    migrations = []
    for path in sorted(directory.glob("*.sql")):
        match = re.match(r"^(\d+)[_-](.+)$", path.stem)
        if not match:
            logger.warning(
                "Skipping file with no version prefix", file=path.name
            )
            continue
        version, name = match.groups()
        migrations.append(
            Migration(
                version=version,
                name=name,
                path=path,
                sql=path.read_text(encoding="utf-8"),
            )
        )

    # Sort numerically, so 010 follows 009 rather than sorting between 001 and 002.
    migrations.sort(key=lambda m: int(m.version))
    return migrations


def _default_migrations_dir() -> Optional[Path]:
    """
    Locate `infra/docker/clickhouse/migrations` relative to this file.

    In a repo checkout this file lives at `apps/api/`, two levels below the
    repo root; in a container image the code is copied to a shallow path such
    as `/app`, where the directory does not exist at all. Walking every parent
    (instead of hard-coding `parents[2]`, which raises IndexError at `/app`)
    handles both layouts; returns None when the directory is nowhere to be
    found so the caller can decide whether that is fatal.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "infra" / "docker" / "clickhouse" / "migrations"
        if candidate.is_dir():
            return candidate
    return None


class MigrationRunner:
    """Applies pending migrations, recording what has been applied."""

    def __init__(self, client, migrations_dir: Optional[Path] = None):
        self.client = client
        if migrations_dir is not None:
            self.migrations_dir: Optional[Path] = Path(migrations_dir)
        else:
            env_dir = os.getenv("MIGRATIONS_DIR")
            self.migrations_dir = Path(env_dir) if env_dir else _default_migrations_dir()

    # -- policy ----------------------------------------------------------

    @staticmethod
    def is_enabled() -> bool:
        """Migrations apply only when explicitly enabled."""
        return os.getenv("RUN_MIGRATIONS_ON_STARTUP", "false").strip().lower() in {
            "true", "1", "yes"
        }

    @staticmethod
    def destructive_allowed() -> bool:
        return os.getenv("ALLOW_DESTRUCTIVE_MIGRATIONS", "false").strip().lower() in {
            "true", "1", "yes"
        }

    # -- bookkeeping -----------------------------------------------------

    def ensure_migrations_table(self) -> None:
        self.client.command(
            f"""
            CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
                version String,
                name String,
                checksum String,
                applied_at DateTime DEFAULT now(),
                success UInt8 DEFAULT 1
            ) ENGINE = MergeTree()
            ORDER BY version
            """
        )

    def applied_migrations(self) -> Dict[str, str]:
        """{version: checksum} for migrations already applied successfully."""
        try:
            result = self.client.query(
                f"SELECT version, checksum FROM {MIGRATIONS_TABLE} WHERE success = 1"
            )
            return {row[0]: row[1] for row in result.result_rows}
        except Exception as exc:
            logger.warning("Could not read migration history", error=str(exc))
            return {}

    def _record(self, migration: Migration) -> None:
        self.client.insert(
            MIGRATIONS_TABLE,
            [[migration.version, migration.name, migration.checksum, 1]],
            column_names=["version", "name", "checksum", "success"],
        )

    # -- planning --------------------------------------------------------

    def plan(self) -> Dict[str, Any]:
        """
        Report what would happen, without changing anything.

        This is the default behaviour, so an operator can see the state of a
        deployment before allowing any DDL to run.
        """
        if self.migrations_dir is None:
            raise MigrationError(
                "No migrations directory configured: MIGRATIONS_DIR is unset "
                "and infra/docker/clickhouse/migrations was not found in any "
                "parent of the application directory."
            )
        migrations = discover_migrations(self.migrations_dir)
        applied = self.applied_migrations()

        pending, drifted = [], []
        for migration in migrations:
            recorded = applied.get(migration.version)
            if recorded is None:
                pending.append(migration)
            elif recorded != migration.checksum:
                # Applied, but the file has changed since. Re-running could be
                # destructive and ignoring it hides real drift, so it is
                # surfaced for a human decision.
                drifted.append(migration)

        return {
            "discovered": [m.version for m in migrations],
            "applied": sorted(applied),
            "pending": [m.version for m in pending],
            "drifted": [m.version for m in drifted],
            "destructive_pending": [
                m.version for m in pending if m.is_destructive()
            ],
            "_pending_objects": pending,
        }

    # -- execution -------------------------------------------------------

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply pending migrations in version order.

        Stops at the first failure: continuing past one would apply later
        migrations over a schema that never received an earlier change.
        """
        self.ensure_migrations_table()
        plan = self.plan()

        if plan["drifted"]:
            logger.error(
                "Migration files changed after being applied -- schema drift",
                drifted=plan["drifted"],
            )

        pending = plan.pop("_pending_objects")

        if dry_run:
            logger.info("Migration dry run", **{
                k: v for k, v in plan.items() if not k.startswith("_")
            })
            return {**plan, "applied_now": [], "dry_run": True}

        applied_now = []
        for migration in pending:
            if migration.is_destructive() and not self.destructive_allowed():
                raise MigrationError(
                    f"Migration {migration.version}_{migration.name} contains "
                    "destructive statements (DROP/TRUNCATE/DELETE). Set "
                    "ALLOW_DESTRUCTIVE_MIGRATIONS=true to permit it, after "
                    "confirming you have a backup."
                )

            logger.info(
                "Applying migration",
                version=migration.version,
                name=migration.name,
            )

            try:
                for statement in migration.statements():
                    self.client.command(statement)
            except Exception as exc:
                logger.error(
                    "Migration failed; halting",
                    version=migration.version,
                    error=str(exc),
                )
                raise MigrationError(
                    f"Migration {migration.version}_{migration.name} failed: {exc}"
                ) from exc

            self._record(migration)
            applied_now.append(migration.version)

        return {**plan, "applied_now": applied_now, "dry_run": False}


def run_migrations_if_enabled(client) -> Dict[str, Any]:
    """
    Entry point for application startup.

    Always reports the migration state. Applies changes only when
    `RUN_MIGRATIONS_ON_STARTUP=true`, so the default deployment behaviour is
    observation, not mutation.
    """
    runner = MigrationRunner(client)
    enabled = runner.is_enabled()

    if runner.migrations_dir is None or not runner.migrations_dir.is_dir():
        # In container images the code is copied without the repo's infra/
        # tree, so the directory is legitimately absent unless mounted or
        # pointed to via MIGRATIONS_DIR.
        if enabled:
            raise MigrationError(
                "RUN_MIGRATIONS_ON_STARTUP is enabled but the migrations "
                f"directory is unavailable (resolved: {runner.migrations_dir}). "
                "Set MIGRATIONS_DIR or mount infra/docker/clickhouse/migrations "
                "into the container."
            )
        logger.warning(
            "Migrations directory unavailable; migration state cannot be "
            "reported for this deployment",
            resolved=str(runner.migrations_dir),
        )
        return {
            "discovered": [], "applied": [], "pending": [], "drifted": [],
            "destructive_pending": [], "applied_now": [],
            "dry_run": True, "unavailable": True,
        }

    try:
        result = runner.run(dry_run=not enabled)
    except Exception as exc:
        logger.error("Migration runner failed", error=str(exc))
        raise

    if not enabled and result["pending"]:
        logger.warning(
            "Pending schema migrations are NOT being applied "
            "(RUN_MIGRATIONS_ON_STARTUP is not enabled)",
            pending=result["pending"],
        )

    return result
