#!/bin/sh
# HA compose: the Replicated `logforge` database on both replicas (DDL runs
# on every replica), then the schema and migrations once, on ch1, with every
# MergeTree-family table as its Replicated* engine, so data replicates too.
CLICKHOUSE_HOST=ch1 DATABASE_HOSTS="ch1 ch2" REPLICATED_ENGINES=true \
  SCHEMA_FILE=/init_simple.sql MIGRATIONS_DIR=/migrations sh /apply_schema.sh
