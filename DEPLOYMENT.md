# Logforge Deployment Guide

## Quick Start

Deploy the entire Logforge platform with a single command:

```bash
./deploy.sh
```

This will:
1. ✅ Check prerequisites (Docker, Python)
2. 🧹 Clean up any existing containers
3. 🚀 Start infrastructure (ClickHouse, MinIO, RedPanda)
4. ⏳ Wait for services to be healthy
5. 📋 Create all Kafka topics with correct partitions
6. ✅ Validate topic setup
7. 🎯 Start application services (API, UI)

## Available Commands

```bash
./deploy.sh deploy    # Full deployment (default)
./deploy.sh cleanup   # Stop and remove all containers
./deploy.sh status    # Show service status
./deploy.sh topics    # List Kafka topics
./deploy.sh logs api  # Show API logs (or any service)
```

## Services & URLs

After deployment, services are available at:

| Service | URL | Purpose |
|---------|-----|---------|
| **API** | http://localhost:7080 | FastAPI backend |
| **UI** | http://localhost:3001 | Next.js frontend |
| **ClickHouse** | http://localhost:8124 | Database |
| **MinIO** | http://localhost:9004 | S3 storage (admin/admin123) |
| **RedPanda** | http://localhost:18081 | Kafka console |

## Kafka Topics Created

The deployment automatically creates these topics:

| Topic | Partitions | Purpose |
|-------|------------|---------|
| `usage-events` | 10 | Usage and billing events |
| `alert-events` | 5 | Alert-related events |
| `log-events` | 10 | Log lifecycle events |
| `tenant-events` | 20 | Tenant management events |
| `ui-realtime-events` | 20 | Real-time UI events |
| `system-events` | 10 | System monitoring events |

## Prerequisites

- **Docker** and **Docker Compose** installed
- **Python 3.x** installed
- Ports 3001, 7080, 8124, 9003-9004, 18081-18082, 19092, 19644 available

## Troubleshooting

### Check service status
```bash
./deploy.sh status
```

### View logs for any service
```bash
./deploy.sh logs api        # API logs
./deploy.sh logs redpanda   # RedPanda logs
./deploy.sh logs clickhouse # ClickHouse logs
```

### Verify topics
```bash
./deploy.sh topics
```

### Clean restart
```bash
./deploy.sh cleanup
./deploy.sh deploy
```

## Production Deployment

For production environments:

1. **Update environment**: Change `--environment development` to `--environment production` in `deploy.sh`
2. **Scale resources**: Increase partition counts and replica factors in `apps/api/config/events.yml`
3. **Security**: Configure proper authentication, TLS, and network security
4. **Monitoring**: Set up log aggregation and monitoring
5. **Backups**: Configure regular backups for ClickHouse and MinIO

## Event System Architecture

The platform includes a comprehensive event-driven architecture:

- **Event Publishing**: All log ingestion publishes events to Kafka
- **Event Processing**: Dedicated consumers process events for analytics
- **Customer Partitioning**: Events are partitioned by customer ID for isolation
- **Reliable Delivery**: Events are persisted and processed asynchronously

## Development

For development with auto-reload:
```bash
./deploy.sh deploy
# API and UI containers will auto-reload on code changes
```