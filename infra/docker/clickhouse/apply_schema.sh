#!/bin/sh
# Create the database, apply the base schema (init_simple.sql) and run the
# migrations: the first-run setup for deployments where ClickHouse's own
# init doesn't (the HA compose, the Helm chart's migrations hook).
#
#   REPLICATED_ENGINES=true   a Replicated database, and every MergeTree-family
#                             table created as its Replicated* engine
#   CLICKHOUSE_CLUSTER=name   create the database ON CLUSTER (Kubernetes), or
#   DATABASE_HOSTS="h1 h2"    on each of these hosts (the HA compose)
#
# Idempotent: CREATE ... IF NOT EXISTS, and migrations are tracked.
set -e
CLICKHOUSE_HOST=${CLICKHOUSE_HOST:-localhost}
CLICKHOUSE_PORT=${CLICKHOUSE_PORT:-8123}
CLICKHOUSE_USER=${CLICKHOUSE_USER:-logforge}
CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD:-logforge123}
CLICKHOUSE_DATABASE=${CLICKHOUSE_DATABASE:-logforge}
REPLICATED_ENGINES=${REPLICATED_ENGINES:-false}
SCHEMA_FILE=${SCHEMA_FILE:-/init_simple.sql}
HERE=$(dirname "$0")

q() {  # host, statement
  curl -sS --fail-with-body -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
    "http://$1:${CLICKHOUSE_PORT}/?allow_experimental_object_type=1" --data-binary "$2" > /dev/null
}

engine=""
if [ "$REPLICATED_ENGINES" = "true" ]; then
  engine=" ENGINE = Replicated('/clickhouse/databases/${CLICKHOUSE_DATABASE}', '{shard}', '{replica}')"
fi
if [ -n "$CLICKHOUSE_CLUSTER" ]; then
  q "$CLICKHOUSE_HOST" "CREATE DATABASE IF NOT EXISTS ${CLICKHOUSE_DATABASE} ON CLUSTER '${CLICKHOUSE_CLUSTER}'${engine}"
else
  for host in ${DATABASE_HOSTS:-$CLICKHOUSE_HOST}; do
    q "$host" "CREATE DATABASE IF NOT EXISTS ${CLICKHOUSE_DATABASE}${engine}"
  done
fi

# The base schema, split as run_migrations.sh splits migrations; its own
# CREATE DATABASE / USE lines are for the single-node stack.
sed -e 's/--.*$//' -e '/^CREATE DATABASE/d' -e '/^USE /d' "$SCHEMA_FILE" | grep -v '^[[:space:]]*$' |
  tr '\n' ' ' | sed 's/;/;\n/g' > /tmp/schema.sql
if [ "$REPLICATED_ENGINES" = "true" ]; then
  sed -E -i 's/ENGINE[[:space:]]*=[[:space:]]*(Replacing|Summing|Aggregating|Collapsing|VersionedCollapsing)?MergeTree/ENGINE = Replicated\1MergeTree/g' /tmp/schema.sql
fi
while IFS= read -r statement; do
  statement=$(echo "$statement" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  { [ -z "$statement" ] || [ "$statement" = ";" ]; } && continue
  echo "$statement" | curl -sS --fail-with-body -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
    "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/?database=${CLICKHOUSE_DATABASE}&allow_experimental_object_type=1" \
    --data-binary @- > /dev/null || { echo "FAILED: $(echo "$statement" | cut -c1-200)"; exit 1; }
done < /tmp/schema.sql
echo "schema applied"

MIGRATIONS_DIR=${MIGRATIONS_DIR:-/migrations} REPLICATED_ENGINES=$REPLICATED_ENGINES sh "$HERE/run_migrations.sh"
echo "schema ready"
