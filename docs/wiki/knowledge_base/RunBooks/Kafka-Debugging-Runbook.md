# Kafka Debugging Runbook for Logforge

## Overview
This runbook provides comprehensive CLI commands and troubleshooting procedures for debugging Kafka/RedPanda issues in the Logforge event-driven architecture.

## Table of Contents
1. [Environment Setup](#environment-setup)
2. [Basic Health Checks](#basic-health-checks)
3. [Topic Management](#topic-management)
4. [Producer/Publisher Debugging](#producerpublisher-debugging)
5. [Consumer/Subscriber Debugging](#consumersubscriber-debugging)
6. [Message Flow Debugging](#message-flow-debugging)
7. [Performance Monitoring](#performance-monitoring)
8. [Common Issues & Solutions](#common-issues--solutions)
9. [Emergency Procedures](#emergency-procedures)

---

## Environment Setup

### Container Status Check
```bash
# Check all Logforge containers
docker ps --filter name=logforge

# Check specific RedPanda container
docker ps --filter name=logforge-redpanda

# Check container health
docker inspect logforge-redpanda | grep -A5 Health
```

### Network Connectivity
```bash
# Test RedPanda connectivity from API container
docker exec logforge-api curl -f http://redpanda:9092 || echo "Connection failed"

# Check if RedPanda ports are accessible
docker exec logforge-redpanda netstat -tlnp | grep :9092
```

### Environment Variables
```bash
# Check Kafka environment variables in API container
docker exec logforge-api env | grep KAFKA

# Expected variables:
# KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
# KAFKA_SECURITY_PROTOCOL=PLAINTEXT
```

---

## Basic Health Checks

### RedPanda Cluster Health
```bash
# Check cluster health
docker exec logforge-redpanda rpk cluster health

# Check cluster info
docker exec logforge-redpanda rpk cluster info

# Check node status
docker exec logforge-redpanda rpk cluster status
```

### API Container Kafka Connectivity
```bash
# Check API logs for Kafka connection issues
docker logs logforge-api | grep -E "(kafka|Kafka|producer|consumer|Failed|Error)"

# Check for specific connection errors
docker logs logforge-api | grep -E "(Failed to start|Connection|Timeout)"
```

---

## Topic Management

### List Topics
```bash
# List all topics
docker exec logforge-redpanda rpk topic list

# List topics with detailed info
docker exec logforge-redpanda rpk topic list --detailed

# Using deploy script
./deploy.sh topics
```

### Topic Details
```bash
# Describe specific topic
docker exec logforge-redpanda rpk topic describe log-events

# Get topic configuration
docker exec logforge-redpanda rpk topic describe log-events --configs

# Check topic partitions
docker exec logforge-redpanda rpk topic describe log-events --print-partitions
```

### Topic Creation/Management
```bash
# Create topic manually
docker exec logforge-redpanda rpk topic create test-topic \
  --partitions 10 \
  --replicas 1 \
  --config retention.ms=604800000

# Delete topic
docker exec logforge-redpanda rpk topic delete test-topic

# Recreate all topics using our script
python infra/setup_kafka_topics.py --environment development --force-recreate

# Validate topic configuration
python infra/setup_kafka_topics.py --environment development --validate-only
```

### Expected Logforge Topics
```bash
# Verify all required topics exist
TOPICS=(
  "usage-events"      # 10 partitions, replication: 1
  "alert-events"      # 5 partitions, replication: 1  
  "log-events"        # 10 partitions, replication: 1
  "tenant-events"     # 20 partitions, replication: 1
  "ui-realtime-events" # 20 partitions, replication: 1
  "system-events"     # 10 partitions, replication: 1
)

for topic in "${TOPICS[@]}"; do
  echo "Checking $topic:"
  docker exec logforge-redpanda rpk topic describe $topic | head -5
done
```

---

## Producer/Publisher Debugging

### Check Publisher Status in Logs
```bash
# Check publisher initialization
docker logs logforge-api | grep -E "(KafkaEventPublisher|Publisher|publisher.*started)"

# Look for publisher errors
docker logs logforge-api | grep -E "(Failed to start.*publisher|publisher.*error)"

# Check current publisher status
docker logs logforge-api | grep -E "publisher_enabled.*publisher_started"
```

### Test Message Production
```bash
# Produce test message using rpk
docker exec logforge-redpanda rpk topic produce log-events <<EOF
{"event_type": "test", "message": "test message", "timestamp": "$(date -Iseconds)"}
EOF

# Produce message with key
echo "test-key:test-message" | docker exec -i logforge-redpanda rpk topic produce log-events --key-delimiter :

# Produce multiple messages
for i in {1..5}; do
  echo "test-message-$i" | docker exec -i logforge-redpanda rpk topic produce log-events
done
```

### Monitor Producer Metrics
```bash
# Check producer lag and metrics via logs
docker logs logforge-api | grep -E "(Event published|Failed to publish|batch.*published)"

# Monitor real-time publishing
docker logs logforge-api --follow | grep -E "(publish|producer)"
```

---

## Consumer/Subscriber Debugging

### List Consumer Groups
```bash
# List all consumer groups
docker exec logforge-redpanda rpk group list

# Expected groups:
# - logforge-events-usage
# - logforge-events-alerts
# - logforge-events-logs
# - logforge-events-tenant
# - logforge-events-ui
# - logforge-events-system
```

### Consumer Group Details
```bash
# Describe specific consumer group
docker exec logforge-redpanda rpk group describe logforge-events-logs

# Check consumer lag
docker exec logforge-redpanda rpk group describe logforge-events-logs --detailed

# List group members
docker exec logforge-redpanda rpk group list --detailed
```

### Check Consumer Status in Logs
```bash
# Check consumer initialization
docker logs logforge-api | grep -E "(KafkaEventSubscriber|Consumer|subscription_state)"

# Look for consumer errors
docker logs logforge-api | grep -E "(Failed to start.*subscriber|consumer.*error)"

# Check partition assignments
docker logs logforge-api | grep -E "(Setting newly assigned partitions|partition.*assigned)"
```

### Reset Consumer Group
```bash
# Reset consumer group to earliest
docker exec logforge-redpanda rpk group seek logforge-events-logs --to start

# Reset to latest
docker exec logforge-redpanda rpk group seek logforge-events-logs --to end

# Reset to specific offset
docker exec logforge-redpanda rpk group seek logforge-events-logs --to @1000
```

---

## Message Flow Debugging

### Consume Messages
```bash
# Consume from beginning
docker exec logforge-redpanda rpk topic consume log-events --from beginning

# Consume latest messages
docker exec logforge-redpanda rpk topic consume log-events --from latest --num 10

# Consume with metadata
docker exec logforge-redpanda rpk topic consume log-events --print-headers --print-timestamp --from beginning

# Consume specific partition
docker exec logforge-redpanda rpk topic consume log-events --partitions 1 --from beginning
```

### End-to-End Message Testing
```bash
# 1. Send test log via API (requires valid auth token)
curl -X POST http://localhost:7080/v1/ingest/logs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Customer-ID: YOUR_CUSTOMER_ID" \
  -d '{"message": "test event flow", "level": "info"}'

# 2. Check if event was published (in another terminal)
docker logs logforge-api --follow | grep -E "(Event published|Log batch ingestion event published)"

# 3. Verify message in Kafka
docker exec logforge-redpanda rpk topic consume log-events --from latest --num 1

# 4. Check if consumer processed it
docker logs logforge-api --follow | grep -E "(Processing event|Processing log event)"
```

### Message Inspection
```bash
# Consume with detailed format
docker exec logforge-redpanda rpk topic consume log-events \
  --format '%t\t%p\t%o\t%k\t%v\n' \
  --from beginning --num 5

# Pretty print JSON messages
docker exec logforge-redpanda rpk topic consume log-events --from latest --num 1 | jq .
```

---

## Performance Monitoring

### Topic Statistics
```bash
# Get topic size and message count
docker exec logforge-redpanda rpk topic describe log-events --print-watermarks

# Monitor message throughput
watch -n 5 'docker exec logforge-redpanda rpk topic list'
```

### Consumer Lag Monitoring
```bash
# Monitor all consumer groups lag
watch -n 10 'docker exec logforge-redpanda rpk group list --detailed'

# Monitor specific group
watch -n 5 'docker exec logforge-redpanda rpk group describe logforge-events-logs'
```

### Container Resource Usage
```bash
# Check RedPanda container resources
docker stats logforge-redpanda --no-stream

# Check API container resources  
docker stats logforge-api --no-stream

# Check memory usage
docker exec logforge-redpanda free -h

# Check disk usage
docker exec logforge-redpanda df -h
```

---

## Common Issues & Solutions

### Issue 1: Publishers Not Starting
**Symptoms:**
```
Failed to start KafkaEventPublisher: `security_protocol` should be SSL or PLAINTEXT
```

**Diagnosis:**
```bash
# Check environment variables
docker exec logforge-api env | grep KAFKA

# Check events.yml configuration
docker exec logforge-api cat config/events.yml | grep -A5 -B5 security_protocol
```

**Solution:**
```bash
# Fix Docker Compose environment variables
# Add to infra/docker/compose.yml under api service:
# - KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
# - KAFKA_SECURITY_PROTOCOL=PLAINTEXT

# Restart API container
docker compose -f infra/docker/compose.yml restart api
```

### Issue 2: Compression Library Errors
**Symptoms:**
```
Failed to start KafkaEventPublisher: Compression library for lz4 not found
```

**Solution:**
```bash
# Change compression in events.yml from lz4/snappy to gzip
sed -i 's/compression_type: "lz4"/compression_type: "gzip"/g' apps/api/config/events.yml
sed -i 's/compression_type: "snappy"/compression_type: "gzip"/g' apps/api/config/events.yml

# Restart API
docker compose -f infra/docker/compose.yml restart api
```

### Issue 3: Topics Not Created
**Symptoms:**
```
Topic 'log-events' does not exist
```

**Diagnosis & Solution:**
```bash
# Check if topics exist
./deploy.sh topics

# Recreate topics
python infra/setup_kafka_topics.py --environment development --force-recreate

# Or use deploy script
./deploy.sh cleanup
./deploy.sh deploy
```

### Issue 4: Publisher Not Started
**Symptoms:**
```
publisher_enabled=True publisher_started=False
Failed to publish to kafka_main: Publisher not started
```

**Diagnosis:**
```bash
# Check API startup logs for publisher errors
docker logs logforge-api | grep -E "(Failed to start.*publisher|KafkaEventPublisher.*start)"

# Check if EventPublisherManager started
docker logs logforge-api | grep "Event publisher manager started"
```

### Issue 5: Consumer Group Lag
**Symptoms:**
- Messages not being processed
- High consumer lag

**Diagnosis & Solution:**
```bash
# Check consumer lag
docker exec logforge-redpanda rpk group describe logforge-events-logs

# Check if consumers are running
docker logs logforge-api | grep -E "(consumer|subscription_state)"

# Reset consumer group if needed
docker exec logforge-redpanda rpk group seek logforge-events-logs --to latest
```

---

## Emergency Procedures

### Complete System Reset
```bash
# 1. Stop all containers
./deploy.sh cleanup

# 2. Remove all volumes (CAUTION: Data loss!)
docker volume rm $(docker volume ls -q | grep logforge) 2>/dev/null || true

# 3. Full redeploy
./deploy.sh deploy

# 4. Verify all topics
./deploy.sh topics

# 5. Test message flow
# (Send test log via API and monitor logs)
```

### RedPanda Container Recovery
```bash
# 1. Check RedPanda container status
docker ps -a --filter name=logforge-redpanda

# 2. Restart RedPanda if unhealthy
docker compose -f infra/docker/compose.yml restart redpanda

# 3. Wait for health check
while ! docker exec logforge-redpanda rpk cluster health; do
  echo "Waiting for RedPanda to be healthy..."
  sleep 5
done

# 4. Recreate topics if needed
python infra/setup_kafka_topics.py --environment development --validate-only || \
python infra/setup_kafka_topics.py --environment development --force-recreate
```

### API Container Recovery
```bash
# 1. Check API logs for errors
docker logs logforge-api --tail 50

# 2. Restart API container
docker compose -f infra/docker/compose.yml restart api

# 3. Verify event system started
docker logs logforge-api | tail -20 | grep -E "(Event.*started|publisher.*started)"

# 4. Test a simple request
curl -f http://localhost:7080/health || echo "API not responding"
```

---

## Quick Reference Commands

### Daily Health Check
```bash
# Run this daily to check system health
echo "=== Logforge Kafka Health Check ==="
echo "1. Container Status:"
docker ps --filter name=logforge --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\n2. Topics:"
./deploy.sh topics

echo -e "\n3. Consumer Groups:"
docker exec logforge-redpanda rpk group list

echo -e "\n4. Recent API Events:"
docker logs logforge-api --since 1h | grep -E "(Event published|Processing event)" | tail -5
```

### Event Flow Test
```bash
# Quick test of complete event flow
echo "Testing event flow..."

# Monitor in background
docker logs logforge-api --follow | grep -E "(publish|Event)" &
MONITOR_PID=$!

# Send test request (replace with valid token/customer)
# curl -X POST http://localhost:7080/v1/ingest/logs ...

# Stop monitoring after 10 seconds
sleep 10
kill $MONITOR_PID 2>/dev/null || true

echo "Event flow test complete"
```

---

## Configuration Files Reference

### Key Configuration Files
- **Docker Compose**: `/infra/docker/compose.yml`
- **Events Config**: `/apps/api/config/events.yml`
- **Topic Setup Script**: `/infra/setup_kafka_topics.py`
- **Deploy Script**: `/deploy.sh`

### Important Log Patterns
- Publisher Status: `publisher_enabled.*publisher_started`
- Event Published: `Event published successfully.*event_id`
- Event Consumed: `Processing event.*event_id`
- Publisher Errors: `Failed to start.*Publisher`
- Consumer Errors: `Failed to start.*Subscriber`

---

## Monitoring & Alerting

### Key Metrics to Monitor
1. **Topic Message Count**: Growing message count indicates healthy publishing
2. **Consumer Lag**: Should be close to 0 for real-time processing
3. **Publisher Success Rate**: Monitor failed publish attempts
4. **Container Health**: All containers should be healthy
5. **Disk Usage**: RedPanda data directory usage

### Alert Conditions
- Consumer lag > 1000 messages
- Publisher failure rate > 5%
- Any container unhealthy for > 2 minutes
- Topic partition count mismatch
- Missing required topics

---

This runbook should be updated as new issues are discovered and resolved. Keep it as a living document alongside your Kafka infrastructure.