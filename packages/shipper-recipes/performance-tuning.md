# Logforge Shipper Performance Tuning Guide

This guide provides optimization recommendations for high-throughput log shipping to Logforge.

## General Principles

### 1. Batching Configuration
- **Batch Size**: Aim for 1000-5000 logs per batch
- **Batch Timeout**: 2-10 seconds depending on latency requirements
- **Max Batch Size**: 1-5MB per batch for optimal network utilization

### 2. Buffer Configuration
- **Memory Buffers**: Use memory buffers for performance
- **Buffer Size**: 10k-50k events depending on available RAM
- **Overflow Strategy**: `drop_newest` for high-volume, `block` for critical logs

### 3. Network Optimization
- **Connection Pooling**: Enable HTTP keep-alive
- **Compression**: Use gzip compression for large batches
- **Retry Strategy**: Exponential backoff with max 3-5 attempts
- **Timeout**: 30-60 seconds for request timeout

## Vector Performance Tuning

### High Throughput Configuration
```toml
[sources.high_volume]
type = "file"
include = ["/var/log/**/*.log"]
max_read_bytes = 2048000  # 2MB chunks

[sinks.logforge_optimized]
type = "http"
inputs = ["transform"]
uri = "http://logforge:8080/v1/ingest/logs"

# Optimized batching
[sinks.logforge_optimized.batch]
max_bytes = 5242880      # 5MB
max_events = 5000
timeout_secs = 5

# High-performance buffer
[sinks.logforge_optimized.buffer]
type = "memory"
max_events = 50000
when_full = "drop_newest"

# Connection pooling
[sinks.logforge_optimized.request]
timeout_secs = 60
rate_limit_num = 50000
concurrency = 10         # Parallel requests
```

### CPU Optimization
- Use native parsers instead of regex where possible
- Minimize complex transformations
- Use `remap` instead of multiple filter stages

## Fluent Bit Performance Tuning

### High Throughput Configuration
```conf
[SERVICE]
    Flush             2
    Workers           4
    HTTP_Server       On
    storage.path      /tmp/flb-storage/
    storage.sync      off
    storage.checksum  off

[INPUT]
    Name              tail
    Refresh_Interval  5
    Rotate_Wait       10
    storage.type      filesystem
    storage.pause_on_chunks_overlimit  off

[OUTPUT]
    Name              http
    Workers           8
    Retry_Limit       3
    storage.total_limit_size  500M
    Compress          gzip
```

### Memory Optimization
- Set appropriate `Mem_Buf_Limit` on inputs
- Use filesystem storage for high-volume scenarios
- Configure `storage.total_limit_size` based on available disk

## Kubernetes Specific Optimizations

### Resource Limits
```yaml
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi
```

### Node Affinity
Deploy log shippers on nodes with:
- Adequate CPU for parsing/transformation
- Sufficient memory for buffering
- Good network connectivity to Logforge

### Volume Mounts
```yaml
volumeMounts:
- name: varlog
  mountPath: /var/log
  readOnly: true
- name: varlibdockercontainers
  mountPath: /var/lib/docker/containers
  readOnly: true
- name: storage
  mountPath: /tmp/fluent-bit/
```

## Network Performance

### Load Balancing
- Use multiple Logforge API instances behind a load balancer
- Distribute load across instances using consistent hashing
- Consider geographic distribution for global deployments

### Endpoint Selection
Choose the most appropriate endpoint for your log type:
- `/v1/ingest/logs` - General JSON logs (most flexible)
- `/v1/ingest/nginx` - Nginx access logs (optimized parsing)
- `/v1/ingest/syslog` - Syslog messages (native format)
- `/v1/ingest/logs/batch` - High-volume batch ingestion

## Monitoring and Metrics

### Vector Metrics
```toml
[sinks.prometheus_metrics]
type = "prometheus_exporter"
inputs = []
address = "0.0.0.0:9090"
```

Key metrics to monitor:
- `vector_processed_events_total`
- `vector_component_errors_total` 
- `vector_buffer_events`
- `vector_sink_requests_total`

### Fluent Bit Metrics
Enable HTTP server for metrics:
```conf
[SERVICE]
    HTTP_Server   On
    HTTP_Port     2020
```

Monitor:
- Input rate: `/api/v1/metrics/prometheus`
- Buffer usage: memory and filesystem utilization
- Output errors: HTTP 4xx/5xx responses

## Troubleshooting Performance Issues

### High Latency
1. Check network connectivity to Logforge
2. Reduce batch timeout for lower latency
3. Increase concurrent connections
4. Verify Logforge API performance

### Low Throughput
1. Increase batch size and buffer limits
2. Add more workers/concurrency
3. Optimize parsing and transformations
4. Check for backpressure from Logforge

### Memory Issues
1. Reduce buffer sizes
2. Use filesystem storage
3. Implement log sampling for non-critical logs
4. Increase resource limits in Kubernetes

### Dropping Logs
1. Change buffer overflow strategy to `block`
2. Increase buffer sizes
3. Add more shipper instances
4. Implement log prioritization

## Production Checklist

- [ ] Load test shipper configuration
- [ ] Configure monitoring and alerting
- [ ] Set up log rotation and cleanup
- [ ] Test failover scenarios
- [ ] Document configuration parameters
- [ ] Establish backup log storage
- [ ] Configure security (TLS, authentication)
- [ ] Set up log sampling for high-volume sources

## Performance Baselines

Expected throughput per shipper instance:
- **Vector**: 50k-100k events/sec
- **Fluent Bit**: 30k-80k events/sec
- **Network**: 100-500 MB/sec depending on log size

Adjust expectations based on:
- Log message size
- Parsing complexity
- Network latency
- Available resources