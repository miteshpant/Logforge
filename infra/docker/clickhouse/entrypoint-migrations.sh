#!/bin/sh

# ClickHouse Migration Entrypoint
# This script waits for ClickHouse to be ready and then runs migrations

set -e

echo "🚀 Starting ClickHouse migration process..."

# Wait for ClickHouse to be ready with retries
wait_for_clickhouse() {
    echo "⏳ Waiting for ClickHouse to be ready..."
    max_attempts=30
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
           "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/?query=SELECT%201" > /dev/null 2>&1; then
            echo "✅ ClickHouse is ready!"
            return 0
        fi
        
        echo "⏳ Attempt $attempt/$max_attempts - ClickHouse not ready yet, waiting 2 seconds..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "❌ ClickHouse failed to become ready after $max_attempts attempts"
    exit 1
}

# Wait for ClickHouse to be ready
wait_for_clickhouse

# Run migrations
echo "🔄 Running ClickHouse migrations..."
/run_migrations.sh

echo "✅ Migration process completed successfully!"