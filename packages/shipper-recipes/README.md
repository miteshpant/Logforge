# Logforge Shipper Configuration Recipes

This directory contains production-ready configuration recipes for popular log shippers to send logs to Logforge.

## Supported Shippers

- **Vector** - High-performance log shipper
- **Fluent Bit** - Lightweight log processor  
- **Fluentd** - Data collector for unified logging layer
- **Filebeat** - Elastic's log shipper
- **Logstash** - Elasticsearch data processing pipeline

## Configuration Files

### Vector Configurations
- `vector/` - Vector configuration files
  - `vector-basic.toml` - Basic file monitoring
  - `vector-nginx.toml` - Nginx access log parsing
  - `vector-syslog.toml` - Syslog collection
  - `vector-kubernetes.toml` - Kubernetes logs
  - `vector-docker.toml` - Docker container logs

### Fluent Bit Configurations
- `fluent-bit/` - Fluent Bit configuration files
  - `fluent-bit-basic.conf` - Basic log collection
  - `fluent-bit-nginx.conf` - Nginx log processing
  - `fluent-bit-kubernetes.conf` - Kubernetes environment
  - `fluent-bit-docker.conf` - Docker containers

### Fluentd Configurations
- `fluentd/` - Fluentd configuration files
  - `fluentd-basic.conf` - Basic setup
  - `fluentd-multi-source.conf` - Multiple log sources

## Quick Start

1. Choose the appropriate configuration for your environment
2. Update the Logforge API endpoint URL
3. Configure authentication if required
4. Test with your log sources
5. Deploy to production

## API Endpoints

Logforge supports multiple ingestion endpoints:

- `/v1/ingest/logs` - Generic JSON logs
- `/v1/ingest/nginx` - Nginx access logs  
- `/v1/ingest/syslog` - Syslog messages
- `/v1/ingest/cef` - Common Event Format
- `/v1/ingest/text` - Plain text logs
- `/v1/ingest/otlp` - OpenTelemetry logs

## Performance Tuning

See the `performance-tuning.md` file for optimization guidelines for high-throughput environments.

## Support

For issues with these configurations, please open an issue in the main Logforge repository.