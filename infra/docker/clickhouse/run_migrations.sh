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
    
    # Clean the file: remove comments and empty lines, split by semicolons
    grep -v '^--' "$migration_file" | grep -v '^$' | tr '\n' ' ' | sed 's/;/;\n/g' > "$temp_file"
    
    # Execute each non-empty statement
    while IFS= read -r statement; do
        # Skip empty statements
        statement=$(echo "$statement" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        if [ -n "$statement" ] && [ "$statement" != ";" ]; then
            echo "  Executing: $(echo "$statement" | cut -c1-60)..."
            if ! echo "$statement" | curl -s -X POST \
                -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
                -H "Content-Type: text/plain" \
                --data-binary @- \
                "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/?database=${CLICKHOUSE_DATABASE}"; then
                echo "❌ Migration $migration_name failed on statement: $statement"
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