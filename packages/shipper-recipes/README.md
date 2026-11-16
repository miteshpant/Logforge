# Logforge Shipper Configuration Recipes

Configuration recipes for sending logs to Logforge from common log shippers.
Each recipe below has been run end to end against a local Logforge stack with
the shipper version listed.

| Shipper | Files | Tested with |
|---|---|---|
| [Vector](https://vector.dev) | `vector/vector-basic.toml` (log files), `vector/vector-nginx.toml` (nginx access + error logs), `vector/vector-kubernetes.toml` (pod logs) | 0.41.1 |
| [Fluent Bit](https://fluentbit.io) | `fluent-bit/fluent-bit-basic.conf` (log files), `fluent-bit/fluent-bit-kubernetes.conf` (pod, nginx, syslog), plus the Lua transforms and `parsers.conf` they load | 3.1.9 |
| [Fluentd](https://www.fluentd.org) | `fluentd/fluentd-basic.conf` (log files, built-in `out_http`) | 1.17.1 |

`vector-basic`, `fluent-bit-basic` and `fluentd-basic` were run end to end;
the Kubernetes and nginx recipes pass the shippers' own config validation
(`vector validate`, `fluent-bit --dry-run`).

## Authentication

Every recipe authenticates with a Logforge **API key** (`lf_...`) read from the
`LOGFORGE_API_KEY` environment variable and sent as
`Authorization: Bearer <key>`. Create one in the UI under **Settings →
Authentication** (API keys), or with `POST /v1/enterprise/auth/api-keys`. The key belongs to a
tenant, so shippers do not send an `X-Customer-ID` header.

```bash
export LOGFORGE_API_KEY=lf_your_key_here
```

## Endpoint

JSON logs go to `POST /v1/ingest/logs/batch`. It accepts the JSON array that
the shippers' HTTP outputs produce (or `{"logs": [...]}`), up to **1000
entries per request**; the recipes cap their batches at that size. Each entry
needs `service` and `msg`; `level`, `host`, `ts`, `trace_id`, `attrs` and the
other `LogEntry` fields are optional. See `docs/api/openapi.yaml` for the full
schema.

Other ingest endpoints, used by the nginx and syslog recipes:

- `/v1/ingest/nginx`, `/v1/ingest/syslog`, `/v1/ingest/cef`, `/v1/ingest/text`
  (and `/batch` variants of each) for raw text formats
- `/v1/ingest/otlp` for OpenTelemetry logs

Request bodies must not be gzip-compressed: the API does not decode
`Content-Encoding: gzip`, so the recipes leave compression off.

## Quick start

1. Pick a recipe and set `LOGFORGE_API_KEY`.
2. Point it at your API: the recipes use `http://localhost:7080` (the compose
   stack), or `http://logforge-api:8080` inside Kubernetes. Fluentd reads
   `LOGFORGE_URL`.
3. Start the shipper and check the Log Explorer.

For example, Vector against a local stack:

```bash
docker run --rm --network host -e LOGFORGE_API_KEY \
  -v "$PWD/vector/vector-basic.toml:/etc/vector/vector.toml:ro" \
  -v /var/log:/var/log:ro \
  timberio/vector:0.41.1-alpine --config /etc/vector/vector.toml
```

## Performance tuning

See `performance-tuning.md` for high-throughput settings.

## Support

For problems with these configurations, open an issue in the Logforge
repository.
