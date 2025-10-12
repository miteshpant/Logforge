# Event-Driven Architecture Implementation Plan
**Version**: 1.0  
**Created**: 2025-10-12  
**Status**: Planning Phase  
**Estimated Duration**: 4-5 weeks  

## Overview
Complete migration from current synchronous/background thread usage tracking to a comprehensive event-driven architecture supporting real-time alerts, usage tracking, UI updates, and system monitoring.

## Project Structure

### Phase Completion Tracking
- [ ] **Phase 1**: Event Infrastructure Foundation (Week 1)
- [ ] **Phase 2**: Usage Tracking Migration (Week 2) 
- [ ] **Phase 3**: Alert Engine Integration (Week 3)
- [ ] **Phase 4**: Real-time UI & Advanced Features (Week 4)
- [ ] **Phase 5**: Testing, Optimization & Cleanup (Week 5)

---

## Phase 1: Event Infrastructure Foundation (Week 1)

### 1.1 Core Event Framework (Day 1-2)

#### Files to Create:
```
apps/api/events/
├── __init__.py
├── base.py                     # Base event classes and interfaces
├── publishers.py               # Event publishing infrastructure  
├── subscribers.py              # Event subscription infrastructure
├── partitioning.py            # Customer partitioning logic
├── topics.py                  # Topic definitions and configurations
└── middleware.py              # Event middleware for FastAPI
```

#### 1.1.1 Base Event Framework
**File**: `apps/api/events/base.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - BaseEvent class with customer_id, timestamp, event_type
# - EventPublisher interface
# - EventSubscriber interface  
# - Event validation and serialization
# - Error handling and retry logic
```

#### 1.1.2 Topic Configuration
**File**: `apps/api/events/topics.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Topic definitions for all event types
# - Partition count and retention policies
# - Event routing rules
# - Topic creation and management utilities
```

#### 1.1.3 Customer Partitioning
**File**: `apps/api/events/partitioning.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - CustomerPartitionManager class
# - Hash-based partition assignment
# - Partition scaling logic
# - Customer-to-partition mapping cache
```

### 1.2 Kafka Integration (Day 2-3)

#### Files to Create:
```
apps/api/events/kafka/
├── __init__.py
├── producer.py                # Kafka producer implementation
├── consumer.py                # Kafka consumer implementation
├── admin.py                   # Kafka admin operations
└── config.py                  # Kafka configuration
```

#### 1.2.1 Kafka Producer
**File**: `apps/api/events/kafka/producer.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - AsyncKafkaProducer wrapper
# - Partition-aware message publishing
# - Error handling and retries
# - Performance metrics collection
# - Graceful shutdown handling
```

#### 1.2.2 Kafka Consumer
**File**: `apps/api/events/kafka/consumer.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - AsyncKafkaConsumer wrapper
# - Consumer group management
# - Partition assignment strategy
# - Message processing pipeline
# - Offset management and error recovery
```

#### 1.2.3 Topic Management
**File**: `apps/api/events/kafka/admin.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Topic creation and configuration
# - Partition scaling operations
# - Health monitoring utilities
# - Topic metadata management
```

### 1.3 Event Type Definitions (Day 3-4)

#### Files to Create:
```
apps/api/events/types/
├── __init__.py
├── usage_events.py            # Usage tracking event definitions
├── alert_events.py            # Alert-related event definitions
├── log_events.py              # Log lifecycle event definitions
├── tenant_events.py           # Tenant management event definitions
├── system_events.py           # System monitoring event definitions
└── ui_events.py               # Real-time UI event definitions
```

#### 1.3.1 Usage Events
**File**: `apps/api/events/types/usage_events.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Event Types to Implement:
# - UsageAPICallEvent
# - UsageIngestionBatchEvent  
# - UsageQueryExecutionEvent
# - UsageStorageEvent
# - UsageQuotaExceededEvent
# - UsageCostCalculatedEvent
```

#### 1.3.2 Alert Events
**File**: `apps/api/events/types/alert_events.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Event Types to Implement:
# - AlertRuleCreatedEvent
# - AlertRuleUpdatedEvent
# - AlertRuleDeletedEvent
# - AlertTriggeredEvent
# - AlertResolvedEvent
# - AlertAcknowledgedEvent
```

#### 1.3.3 Log Events
**File**: `apps/api/events/types/log_events.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Event Types to Implement:
# - LogBatchIngestedEvent
# - LogParsingFailedEvent
# - LogRealtimeBatchEvent (for alert evaluation)
# - LogArchivedEvent
# - LogTTLExpiredEvent
# - LogRestoredEvent
```

### 1.4 Integration with Dependencies (Day 4-5)

#### Files to Modify:
```
apps/api/
├── dependencies.py            # Add event system initialization
├── main.py                    # Integrate event middleware
└── app_config.py              # Add event system configuration
```

#### 1.4.1 Dependencies Integration
**File**: `apps/api/dependencies.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Modifications Required:
# - Initialize event publisher/subscriber systems
# - Add event system to lifespan management
# - Configure topic creation on startup
# - Add graceful shutdown for event systems
```

#### 1.4.2 FastAPI Integration
**File**: `apps/api/main.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Modifications Required:
# - Add event middleware to FastAPI app
# - Configure event-based request tracking
# - Add event system health endpoints
```

### 1.5 Docker & Configuration (Day 5)

#### Files to Create/Modify:
```
infra/docker/
├── compose.yml                # Add Kafka/Redpanda topics configuration
└── kafka-setup/
    ├── topics.sh              # Topic creation script
    └── partitions.yml         # Partition configuration
```

#### 1.5.1 Kafka Topic Setup
**File**: `infra/docker/kafka-setup/topics.sh`
```bash
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Topics to Create:
# - usage-events (100 partitions)
# - alert-events (50 partitions)
# - log-events (100 partitions)
# - tenant-events (20 partitions)
# - ui-realtime-events (200 partitions)
# - system-events (10 partitions)
```

---

## Phase 2: Usage Tracking Migration (Week 2)

### 2.1 New Usage Tracking Service (Day 6-7)

#### Files to Create:
```
apps/api/services/
├── usage_tracking_service.py  # New event-driven usage tracking
└── billing_service.py         # Enhanced billing with events
```

#### 2.1.1 Usage Tracking Service
**File**: `apps/api/services/usage_tracking_service.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Event-driven usage processing
# - Batch usage record insertion
# - Real-time quota management
# - Cost calculation with pricing.yml
# - Usage analytics and reporting
# - Buffer management for high-throughput
```

#### 2.1.2 Enhanced Billing Service
**File**: `apps/api/services/billing_service.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Event-based cost calculation
# - Multi-tier pricing support
# - Usage forecasting
# - Billing analytics
# - Invoice generation events
```

### 2.2 Usage Event Publishers (Day 7-8)

#### Files to Create:
```
apps/api/events/publishers/
├── __init__.py
├── usage_publisher.py         # Usage event publishing
├── api_usage_publisher.py     # API call usage events
└── ingestion_publisher.py     # Log ingestion usage events
```

#### 2.2.1 Usage Publisher
**File**: `apps/api/events/publishers/usage_publisher.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - publish_api_usage()
# - publish_ingestion_usage()
# - publish_query_usage()
# - publish_storage_usage()
# - publish_quota_event()
# - Error handling and retries
```

### 2.3 Middleware Migration (Day 8-9)

#### Files to Modify:
```
apps/api/
├── authn_authz_middleware.py  # Replace blocking usage tracking
└── routers/
    ├── ingestion.py           # Replace background thread tracking
    ├── query.py               # Add query usage events
    └── storage.py             # Add storage usage events
```

#### 2.3.1 Middleware Update
**File**: `apps/api/authn_authz_middleware.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Changes Required:
# - Remove blocking track_usage_with_cost_calculation()
# - Add non-blocking usage event publishing
# - Maintain API response time <100ms
# - Add usage event middleware
```

#### 2.3.2 Ingestion Router Update
**File**: `apps/api/routers/ingestion.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Changes Required:
# - Remove process_logs_and_tracking_background()
# - Add event-driven usage tracking
# - Maintain ingestion performance >50k EPS
# - Add real-time log events for alerts
```

### 2.4 Usage Event Subscribers (Day 9-10)

#### Files to Create:
```
apps/api/events/subscribers/
├── __init__.py
├── usage_subscriber.py        # Main usage event processor
├── quota_subscriber.py        # Quota management subscriber
└── analytics_subscriber.py    # Usage analytics subscriber
```

#### 2.4.1 Usage Subscriber
**File**: `apps/api/events/subscribers/usage_subscriber.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Process usage events in batches
# - Update usage_records_mt table
# - Update tenant_quotas_mt table
# - Handle event ordering per customer
# - Error recovery and retry logic
```

---

## Phase 3: Alert Engine Integration (Week 3)

### 3.1 Alert Engine Event Integration (Day 11-12)

#### Files to Modify:
```
apps/api/
├── alert_engine.py            # Add event-driven rule management
└── services/
    └── alert_service.py       # Add alert event publishing
```

#### 3.1.1 Alert Engine Updates
**File**: `apps/api/alert_engine.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Enhancements Required:
# - Event-driven rule loading (already implemented)
# - Real-time log evaluation subscriber
# - Alert instance event publishing
# - Performance optimization for high-throughput
# - Customer-specific rule caching
```

#### 3.1.2 Alert Service Updates
**File**: `apps/api/services/alert_service.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Changes Required:
# - Publish AlertRuleCreatedEvent on rule creation
# - Publish AlertRuleUpdatedEvent on rule updates
# - Publish AlertRuleDeletedEvent on rule deletion
# - Trigger alert engine reloads via events
```

### 3.2 Real-time Alert Evaluation (Day 12-13)

#### Files to Create:
```
apps/api/events/subscribers/
├── alert_subscriber.py        # Alert rule management subscriber
└── realtime_alert_subscriber.py # Real-time log evaluation
```

#### 3.2.1 Alert Subscriber
**File**: `apps/api/events/subscribers/alert_subscriber.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Handle alert rule CRUD events
# - Update alert engine rule cache
# - Start/stop rule evaluation tasks
# - Customer-specific rule reloading
```

#### 3.2.2 Real-time Alert Subscriber
**File**: `apps/api/events/subscribers/realtime_alert_subscriber.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Process real-time log batch events
# - Fast log filtering against rule conditions
# - Trigger alerts for matching patterns
# - Maintain sub-second alert latency
```

### 3.3 Alert Instance Management (Day 13-14)

#### Files to Create:
```
apps/api/events/publishers/
└── alert_publisher.py         # Alert instance event publishing

apps/api/events/subscribers/
└── notification_subscriber.py # Alert notification handling
```

#### 3.3.1 Alert Publisher
**File**: `apps/api/events/publishers/alert_publisher.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - publish_alert_triggered()
# - publish_alert_resolved()
# - publish_alert_acknowledged()
# - publish_notification_sent()
# - Include alert context and metrics
```

#### 3.3.2 Notification Subscriber
**File**: `apps/api/events/subscribers/notification_subscriber.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Handle alert triggered events
# - Send notifications via multiple channels
# - Track notification delivery status
# - Handle notification failures and retries
```

---

## Phase 4: Real-time UI & Advanced Features (Week 4)

### 4.1 WebSocket Infrastructure (Day 15-16)

#### Files to Create:
```
apps/api/websocket/
├── __init__.py
├── connection_manager.py      # WebSocket connection management
├── event_streamer.py          # Event-to-WebSocket streaming
└── handlers.py                # WebSocket message handlers

apps/api/routers/
└── websocket.py               # WebSocket router
```

#### 4.1.1 WebSocket Manager
**File**: `apps/api/websocket/connection_manager.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Customer-specific connection pools
# - Connection lifecycle management
# - Authentication and authorization
# - Connection health monitoring
```

#### 4.1.2 Event Streamer
**File**: `apps/api/websocket/event_streamer.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Subscribe to UI-relevant events
# - Stream events to customer WebSocket connections
# - Event filtering and rate limiting
# - Real-time dashboard updates
```

### 4.2 UI Event Subscribers (Day 16-17)

#### Files to Create:
```
apps/api/events/subscribers/
├── ui_subscriber.py           # Main UI event processor
├── dashboard_subscriber.py    # Dashboard update subscriber
└── livestream_subscriber.py   # Live log streaming subscriber
```

#### 4.2.1 UI Subscriber
**File**: `apps/api/events/subscribers/ui_subscriber.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Process UI-relevant events
# - Transform events for frontend consumption
# - Stream to WebSocket connections
# - Handle connection failures gracefully
```

### 4.3 Frontend Event Integration (Day 17-18)

#### Files to Create:
```
apps/ui/lib/
├── event-client.ts            # WebSocket event client
├── event-handlers.ts          # Event handling utilities
└── real-time-hooks.ts         # React hooks for real-time data

apps/ui/components/
├── RealTimeAlerts.tsx         # Real-time alert notifications
├── LiveLogStream.tsx          # Live log streaming component
└── UsageMetrics.tsx           # Real-time usage dashboard
```

#### 4.3.1 Event Client
**File**: `apps/ui/lib/event-client.ts`
```typescript
// Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
// Implementation Requirements:
// - WebSocket connection management
// - Event type handling and routing
// - Connection retry logic
// - Authentication integration
```

### 4.4 Advanced Analytics (Day 18-19)

#### Files to Create:
```
apps/api/services/
├── analytics_service.py       # Event-driven analytics
└── forecasting_service.py     # Usage forecasting

apps/api/events/subscribers/
└── analytics_subscriber.py    # Analytics event processor
```

#### 4.4.1 Analytics Service
**File**: `apps/api/services/analytics_service.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Real-time usage analytics
# - Customer behavior analysis
# - Performance metrics aggregation
# - Cost optimization insights
```

---

## Phase 5: Testing, Optimization & Cleanup (Week 5)

### 5.1 Integration Testing (Day 20-21)

#### Files to Create:
```
tests/events/
├── __init__.py
├── test_event_system.py       # End-to-end event system tests
├── test_usage_tracking.py     # Usage tracking accuracy tests
├── test_alert_integration.py  # Alert system integration tests
└── test_performance.py        # Performance benchmarking

tests/integration/
└── test_event_driven_flows.py # Complete workflow tests
```

#### 5.1.1 Event System Tests
**File**: `tests/events/test_event_system.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Test Coverage:
# - Event publishing and consumption
# - Customer partition isolation
# - Event ordering guarantees
# - Error handling and recovery
# - Performance under load
```

### 5.2 Performance Optimization (Day 21-22)

#### Files to Create:
```
apps/api/events/
├── performance.py             # Performance monitoring
└── optimization.py            # Performance optimizations

docs/wiki/knowledge_base/
└── Event-System-Performance-Guide.md
```

#### 5.2.1 Performance Monitoring
**File**: `apps/api/events/performance.py`
```python
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Implementation Requirements:
# - Event processing latency metrics
# - Throughput monitoring
# - Memory usage optimization
# - Consumer lag monitoring
```

### 5.3 Documentation (Day 22-23)

#### Files to Create:
```
docs/wiki/knowledge_base/
├── Event-System-Architecture.md
├── Event-Types-Reference.md
├── Performance-Tuning-Guide.md
├── Troubleshooting-Guide.md
└── Migration-Guide.md
```

### 5.4 Legacy Code Cleanup (Day 23-24)

#### Files to Modify/Remove:
```
apps/api/
├── dependencies.py            # Remove old background task functions
├── authn_authz_middleware.py  # Remove old usage tracking code
└── routers/
    └── ingestion.py           # Remove background thread usage tracking
```

---

## Configuration Files

### Environment Variables
**File**: `.env.events.example`
```bash
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:19092
KAFKA_CONSUMER_GROUP_PREFIX=logforge-events
KAFKA_PRODUCER_CLIENT_ID=logforge-producer

# Event System Configuration  
EVENT_BATCH_SIZE=100
EVENT_FLUSH_INTERVAL_MS=1000
EVENT_RETRY_ATTEMPTS=3
EVENT_RETRY_DELAY_MS=500

# Topic Configuration
USAGE_EVENTS_PARTITIONS=100
ALERT_EVENTS_PARTITIONS=50
UI_EVENTS_PARTITIONS=200
```

### Docker Compose Updates
**File**: `infra/docker/compose.yml`
```yaml
# Status: [ ] Not Started [ ] In Progress [ ] Completed [ ] Tested
# Services to Add/Modify:
# - Update redpanda with topic auto-creation
# - Add event system health checks
# - Configure partition counts
# - Add topic retention policies
```

---

## Success Criteria & Validation

### Performance Targets
- [ ] **API Response Time**: <100ms (vs current 150-300ms)
- [ ] **Ingestion Throughput**: >50k EPS maintained
- [ ] **Alert Latency**: <60s schedule-to-notify
- [ ] **UI Update Latency**: <1s event-to-display
- [ ] **Usage Tracking Accuracy**: 100% (vs database verification)

### Functional Validation
- [ ] **Usage Cost Calculation**: Match current pricing.yml calculations
- [ ] **Alert Engine**: Load rules from database automatically
- [ ] **Real-time UI**: Live updates for alerts, logs, usage
- [ ] **Customer Isolation**: Events properly partitioned by customer
- [ ] **Error Recovery**: Handle Kafka downtime gracefully

### Migration Validation
- [ ] **Backward Compatibility**: Old usage tracking still works during migration
- [ ] **Data Consistency**: Event-driven usage matches current tracking
- [ ] **Zero Downtime**: Migration without service interruption
- [ ] **Rollback Plan**: Ability to revert to current system if needed

---

## Progress Tracking

### Daily Standup Questions
1. Which files from today's plan are completed?
2. Any blockers or deviations from the plan?
3. Performance metrics meeting targets?
4. Any new requirements discovered?

### Weekly Milestones
- **Week 1**: Event infrastructure foundation complete
- **Week 2**: Usage tracking migrated to events
- **Week 3**: Alert engine fully event-driven
- **Week 4**: Real-time UI and advanced features
- **Week 5**: Testing, optimization, and production-ready

### Risk Mitigation
- **Kafka Downtime**: Implement event buffering and replay
- **Performance Regression**: Maintain parallel legacy systems during migration
- **Customer Impact**: Customer-specific rollout and monitoring
- **Data Loss**: Event persistence and replay mechanisms

---

## Next Steps

### Immediate Actions (Start of Implementation)
1. **Create directory structure**: `apps/api/events/`
2. **Begin with Phase 1.1**: Implement base event framework
3. **Set up progress tracking**: Update this document with daily progress
4. **Configure development environment**: Kafka topics and partitions

### Session Continuity
**When resuming in a new session, check:**
1. Read this file for current progress status
2. Check Phase completion checkboxes
3. Review any `[IN PROGRESS]` items
4. Update daily progress in this document
5. Proceed with next uncompleted item in sequence

---

**Last Updated**: 2025-10-12  
**Next Review**: Daily during implementation  
**Project Owner**: Development Team  
**Document Status**: Living Document - Update Progress Daily