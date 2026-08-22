#!/bin/sh

# ClickHouse Migration Runner
# Usage: ./run_migrations.sh [migration_number]
# If no migration number provided, runs all migrations

set -e

CLICKHOUSE_HOST=${CLICKHOUSE_HOST:-localhost}
CLICKHOUSE_PORT=${CLICKHOUSE_PORT:-8123}
CLICKHOUSE_USER=${CLICKHOUSE_USER:-logforge}
CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD:-logforge123}
CLICKHOUSE_DATABASE=${CLICKHOUSE_DATABASE:-logforge}

# Use absolute path for migrations directory (container) or relative path (local)
MIGRATIONS_DIR="${MIGRATIONS_DIR:-$(dirname "$0")/migrations}"

# Function to execute SQL file (handles multi-statement files)
execute_migration() {
    local migration_file="$1"
    local migration_name=$(basename "$migration_file" .sql)

    echo "🔄 Running migration: $migration_name"

    # Read the file and split by semicolons, then execute each statement
    # Remove comments and empty lines, then process each statement
    temp_file="/tmp/migration_temp.sql"

    # Clean the file, then split by semicolons.
    #
    # LF-019: inline comments (`col String, -- note`) MUST be stripped
    # per-line BEFORE the newlines are collapsed. The previous version only
    # removed full-line comments, so after `tr '\n' ' '` an inline `--`
    # commented out the remainder of the whole statement -- ClickHouse then
    # rejected the truncated DDL, and because curl exits 0 on an HTTP 4xx/5xx
    # without --fail*, the migration was still recorded as executed. That is
    # how migration 007 "succeeded" while creating only 1 of its 9 tables.
    # NOTE: this means `--` must not appear inside SQL string literals in
    # migration files (none do today).
    sed 's/--.*$//' "$migration_file" | grep -v '^[[:space:]]*$' | tr '\n' ' ' | sed 's/;/;\n/g' > "$temp_file"

    # Execute each non-empty statement
    while IFS= read -r statement; do
        # Skip empty statements
        statement=$(echo "$statement" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        if [ -n "$statement" ] && [ "$statement" != ";" ]; then
            echo "  Executing: $(echo "$statement" | cut -c1-60)..."
            # LF-019: --fail-with-body makes curl exit non-zero on a
            # ClickHouse error response, so a failed statement actually
            # fails the migration instead of being recorded as success.
            response=$(echo "$statement" | curl -s --fail-with-body -X POST \
                -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
                -H "Content-Type: text/plain" \
                --data-binary @- \
                "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/?database=${CLICKHOUSE_DATABASE}")
            if [ $? -ne 0 ]; then
                echo "❌ Migration $migration_name failed on statement: $statement"
                echo "   ClickHouse response: $response"
                rm -f "$temp_file"
                return 1
            fi
        fi
    done < "$temp_file"

    rm -f "$temp_file"
    echo "✅ Migration $migration_name completed successfully"
}

# Function to check if ClickHouse is accessible
check_clickhouse() {
    echo "🔍 Checking ClickHouse connectivity..."
    if curl -s -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
        "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/?query=SELECT%201" > /dev/null; then
        echo "✅ ClickHouse is accessible"
        return 0
    else
        echo "❌ Cannot connect to ClickHouse"
        return 1
    fi
}

# Function to create migration tracking table
create_migration_table() {
    echo "🏗️  Creating migration tracking table..."
    curl -s -X POST \
        -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
        -H "Content-Type: text/plain" \
        --data "CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_name String,
            executed_at DateTime64(3) DEFAULT now64(3)
        ) ENGINE = MergeTree()
        ORDER BY migration_name
        SETTINGS index_granularity = 8192;" \
        "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/?database=${CLICKHOUSE_DATABASE}" > /dev/null
}

# Function to check whether a migration is destructive.
# Mirrors DESTRUCTIVE_PATTERN in apps/api/schema_migrations.py: files that can
# destroy data are refused unless ALLOW_DESTRUCTIVE_MIGRATIONS=true, so a
# routine `docker compose up` can never rewrite/drop the log tables
# unsupervised (011_repartition_logs_tables.sql documents this contract).
is_destructive_migration() {
    local migration_file="$1"
    grep -qiE '(DROP[[:space:]]+(TABLE|DATABASE|VIEW)|TRUNCATE[[:space:]]+TABLE|DELETE[[:space:]]+FROM)' "$migration_file"
}

# Function to check if migration was already executed
is_migration_executed() {
    local migration_name="$1"
    local result=$(curl -s -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
        "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/?query=SELECT%20count()%20FROM%20schema_migrations%20WHERE%20migration_name%20%3D%20%27${migration_name}%27&database=${CLICKHOUSE_DATABASE}")
    
    if [ "$result" = "1" ]; then
        return 0  # Migration already executed
    else
        return 1  # Migration not executed
    fi
}

# Function to record migration execution
record_migration() {
    local migration_name="$1"
    curl -s -X POST \
        -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
        -H "Content-Type: text/plain" \
        --data "INSERT INTO schema_migrations (migration_name) VALUES ('${migration_name}')" \
        "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/?database=${CLICKHOUSE_DATABASE}" > /dev/null
}

# Main execution
main() {
    echo "🚀 Starting ClickHouse migrations..."
    
    # Check connectivity
    if ! check_clickhouse; then
        exit 1
    fi
    
    # Create migration tracking table
    create_migration_table
    
    # Determine which migrations to run
    if [ $# -eq 1 ]; then
        # Run specific migration
        migration_file="${MIGRATIONS_DIR}/$1.sql"
        if [ -f "$migration_file" ]; then
            migration_name=$(basename "$migration_file" .sql)
            if is_migration_executed "$migration_name"; then
                echo "⚠️  Migration $migration_name already executed, skipping"
            elif is_destructive_migration "$migration_file" && [ "${ALLOW_DESTRUCTIVE_MIGRATIONS:-false}" != "true" ]; then
                echo "⛔ Migration $migration_name contains destructive statements;"
                echo "   refusing without ALLOW_DESTRUCTIVE_MIGRATIONS=true"
                exit 1
            else
                execute_migration "$migration_file"
                record_migration "$migration_name"
            fi
        else
            echo "❌ Migration file not found: $migration_file"
            exit 1
        fi
    else
        # Run all migrations in order
        migration_count=0
        for migration_file in $(ls "${MIGRATIONS_DIR}"/*.sql 2>/dev/null | sort); do
            migration_name=$(basename "$migration_file" .sql)
            if is_migration_executed "$migration_name"; then
                echo "⚠️  Migration $migration_name already executed, skipping"
            elif is_destructive_migration "$migration_file" && [ "${ALLOW_DESTRUCTIVE_MIGRATIONS:-false}" != "true" ]; then
                echo "⛔ Migration $migration_name contains destructive statements; skipped."
                echo "   Apply it in a supervised window with ALLOW_DESTRUCTIVE_MIGRATIONS=true."
            else
                execute_migration "$migration_file"
                record_migration "$migration_name"
                migration_count=$((migration_count + 1))
            fi
        done
        
        if [ $migration_count -eq 0 ]; then
            echo "ℹ️  No new migrations to run"
        else
            echo "🎉 Executed $migration_count migrations successfully"
        fi
    fi
    
    echo "✅ Migration process completed"
}

# Run main function
main "$@"