# ClickHouse Migration Guide for Production

## Overview
This guide ensures migrations run safely and reliably in production environments.

## Migration Files Location
```
/infra/docker/clickhouse/migrations/
├── 001_initial_schema.sql
├── 002_users_and_auth.sql
├── 007_anomaly_detection_advanced.sql
└── ...
```

## Production Deployment Methods

### Method 1: Docker Exec (Manual)
**Use for**: Initial deployments, testing

```bash
# 1. Copy migration file to container
docker cp migrations/007_anomaly_detection_advanced.sql logforge-clickhouse:/tmp/

# 2. Run migration on correct database
docker exec logforge-clickhouse clickhouse-client \
  --database=logforge \
  --user=logforge \
  --password=logforge123 \
  --multiquery < /tmp/007_anomaly_detection_advanced.sql

# 3. Verify tables created
docker exec logforge-clickhouse clickhouse-client \
  --database=logforge \
  --query "SELECT name FROM system.tables WHERE database = 'logforge' AND name LIKE '%anomaly%'"
```

### Method 2: Migration Runner Script (Recommended)
**Use for**: CI/CD pipelines, automated deployments

The `run_migrations.sh` script includes:
- ✅ Migration tracking (prevents duplicate runs)
- ✅ Automatic rollback on failure
- ✅ Idempotent execution
- ✅ Connectivity checks

```bash
# Run from inside container
docker exec logforge-clickhouse /bin/sh -c "
  export CLICKHOUSE_DATABASE=logforge
  /docker-entrypoint-initdb.d/run_migrations.sh 007_anomaly_detection_advanced
"

# Or run all pending migrations
docker exec logforge-clickhouse /bin/sh -c "
  export CLICKHOUSE_DATABASE=logforge
  /docker-entrypoint-initdb.d/run_migrations.sh
"
```

### Method 3: Init Container (Kubernetes)
**Use for**: Kubernetes deployments

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: clickhouse-migration
spec:
  initContainers:
  - name: run-migrations
    image: clickhouse/clickhouse-server:latest
    command:
    - /bin/sh
    - -c
    - |
      for migration in /migrations/*.sql; do
        clickhouse-client \
          --host=clickhouse-service \
          --database=logforge \
          --user=logforge \
          --password=${CLICKHOUSE_PASSWORD} \
          --multiquery < "$migration"
      done
    volumeMounts:
    - name: migrations
      mountPath: /migrations
  volumes:
  - name: migrations
    configMap:
      name: clickhouse-migrations
```

### Method 4: CI/CD Pipeline (GitHub Actions)
**Use for**: Automated deployments with verification

```yaml
name: Deploy Migrations
on:
  push:
    branches: [main]
    paths:
      - 'infra/docker/clickhouse/migrations/*.sql'

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Migrations
        run: |
          # Connect to production ClickHouse
          docker run --rm \
            -v $(pwd)/infra/docker/clickhouse/migrations:/migrations \
            clickhouse/clickhouse-client:latest \
            --host=${{ secrets.CLICKHOUSE_HOST }} \
            --database=logforge \
            --user=${{ secrets.CLICKHOUSE_USER }} \
            --password=${{ secrets.CLICKHOUSE_PASSWORD }} \
            --multiquery < /migrations/007_anomaly_detection_advanced.sql

      - name: Verify Migration
        run: |
          docker run --rm \
            clickhouse/clickhouse-client:latest \
            --host=${{ secrets.CLICKHOUSE_HOST }} \
            --database=logforge \
            --user=${{ secrets.CLICKHOUSE_USER }} \
            --password=${{ secrets.CLICKHOUSE_PASSWORD }} \
            --query="SELECT count() FROM system.tables WHERE database='logforge' AND name='multi_metric_anomalies_mt'"
```

## Migration Best Practices

### 1. Always Use IF NOT EXISTS
```sql
CREATE TABLE IF NOT EXISTS anomaly_analysis_mt (...);
CREATE INDEX IF NOT EXISTS idx_analysis_root_cause ON ...;
```

### 2. Test Locally First
```bash
# Test in local environment
docker exec logforge-clickhouse clickhouse-client \
  --database=logforge \
  --multiquery < migrations/007_anomaly_detection_advanced.sql

# Verify
docker exec logforge-clickhouse clickhouse-client \
  --database=logforge \
  --query "SHOW TABLES LIKE '%anomaly%'"
```

### 3. Create Migration Tracking Table
```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_name String,
    executed_at DateTime64(3) DEFAULT now64(3),
    checksum String,
    status Enum8('success' = 1, 'failed' = 2) DEFAULT 'success'
) ENGINE = MergeTree()
ORDER BY migration_name;
```

### 4. Record Each Migration
```sql
INSERT INTO schema_migrations (migration_name, checksum)
VALUES ('007_anomaly_detection_advanced', 'sha256_hash_here');
```

### 5. Check Before Running
```sql
SELECT count() FROM schema_migrations
WHERE migration_name = '007_anomaly_detection_advanced';
-- If returns 1, migration already applied
```

## Rollback Strategy

### For Table Creation Failures
```sql
-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS active_multi_metric_anomalies_mv;
DROP TABLE IF EXISTS multi_metric_anomalies_mt;
DROP TABLE IF EXISTS anomaly_analysis_mt;
-- ... continue for all tables
```

### For Data Migration Failures
```sql
-- ReplacingMergeTree tables automatically handle updates
-- Just re-run the migration after fixing issues
```

## Production Checklist

- [ ] Migration file uses `IF NOT EXISTS` for all CREATE statements
- [ ] Migration tested in local/staging environment
- [ ] Database backup created before migration
- [ ] Migration tracking table exists
- [ ] Migration not already applied (check schema_migrations)
- [ ] Correct database specified (logforge, not default)
- [ ] Permissions verified for logforge user
- [ ] Monitoring in place to detect failures
- [ ] Rollback plan documented
- [ ] Team notified of migration window

## Troubleshooting

### Issue: Tables created in wrong database
```bash
# Check which database
docker exec logforge-clickhouse clickhouse-client \
  --query "SELECT database, name FROM system.tables WHERE name LIKE '%anomaly%'"

# Solution: Always specify --database=logforge
```

### Issue: Permission denied
```bash
# Grant permissions
docker exec logforge-clickhouse clickhouse-client --query "
  GRANT ALL ON logforge.* TO logforge;
"
```

### Issue: Migration already applied
```bash
# Check migration tracking
docker exec logforge-clickhouse clickhouse-client \
  --database=logforge \
  --query "SELECT * FROM schema_migrations ORDER BY executed_at DESC LIMIT 10"
```

## Monitoring Post-Migration

```bash
# Verify table row counts
docker exec logforge-clickhouse clickhouse-client \
  --database=logforge \
  --query "
    SELECT name, engine, total_rows
    FROM system.tables
    WHERE database = 'logforge' AND name LIKE '%anomaly%'
    ORDER BY name
  " --format=Pretty

# Check table sizes
docker exec logforge-clickhouse clickhouse-client \
  --database=logforge \
  --query "
    SELECT
      name,
      formatReadableSize(total_bytes) AS size
    FROM system.tables
    WHERE database = 'logforge' AND name LIKE '%anomaly%'
    ORDER BY total_bytes DESC
  " --format=Pretty
```

## Support

For migration issues, check:
1. ClickHouse logs: `docker logs logforge-clickhouse`
2. API logs: `docker logs logforge-api`
3. Migration tracking: `SELECT * FROM schema_migrations`