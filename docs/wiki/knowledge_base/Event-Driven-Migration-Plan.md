# Event-Driven Log Processing Migration Plan

## Overview
Migrate from direct database processing to event-driven architecture for 1M RPS capability while maintaining zero downtime and data consistency.

## Current Architecture
```
API Ingestion → process_logs_and_tracking_background() → ClickHouse + Event Notification
```

## Target Architecture  
```
API Ingestion → publish_log_event() → 202 Accepted
Event Queue → LogEventHandler → event_processing.*() → ClickHouse
```

---

## Migration Phases

### Phase 1: Create Modular Event Processing 
**Duration**: 1-2 days  
**Risk**: Low (No changes to existing flow)

#### 1.1 Create `event_processing.py`
Break down `process_logs_and_tracking_background()` into focused functions:

```python
# apps/api/event_processing.py
async def process_log_batch(logs: List[LogEntry], customer_id: str) -> bool
async def track_usage_stats(customer_id: str, feature: str, bytes_processed: int, cost: float) -> bool  
async def update_tenant_quotas(customer_id: str, usage_delta: dict) -> bool
async def track_ingestion_metrics(customer_id: str, endpoint: str, log_count: int, bytes: int) -> bool
async def handle_log_ingestion_event(event_data: dict) -> bool  # Main orchestrator
```

#### 1.2 Update LogEventHandler
Connect handler to new processing functions:

```python
# apps/api/events/handlers.py
class LogEventHandler:
    async def handle_logs_batch_ingested(self, event):
        await handle_log_ingestion_event(event.data)
```

**Validation**: 
- Functions compile and import successfully
- No circular dependencies
- Unit tests pass

---

### Phase 2: Implement Dual Processing
**Duration**: 1 day  
**Risk**: Low (Parallel processing for validation)

#### 2.1 Enable Dual Processing
- Keep existing `process_logs_and_tracking_background()` unchanged
- Subscribers also process events via `event_processing.*()` 
- Monitor for doubled data in all tables

#### 2.2 Add Validation Metrics
```python
# Track processing in both paths
log_processing_metrics = {
    'direct_path_count': 0,
    'event_path_count': 0,
    'consistency_errors': 0
}
```

**Validation**:
- All tables show 2x data (expected duplication)
- Event processing latency < 100ms
- No processing errors in logs
- Data consistency between both paths

---

### Phase 3: Performance Testing & Validation
**Duration**: 2-3 days  
**Risk**: Medium (Load testing under dual processing)

#### 3.1 Load Testing
- Test with increasing load: 1K, 10K, 100K RPS
- Monitor both processing paths
- Verify event queue can handle burst traffic
- Measure API response times

#### 3.2 Data Validation Scripts
```bash
# Compare record counts
./scripts/validate_dual_processing.sh

# Check data consistency
./scripts/compare_processing_results.sh
```

#### 3.3 Performance Benchmarks
- API response time: Target <1ms after cutover
- Event processing latency: <100ms p95
- Consumer lag: <1000 messages under load
- Data consistency: 100% match between paths

**Validation**:
- System handles target load with dual processing
- Event processing keeps up with ingestion rate
- Zero data inconsistencies detected
- Performance metrics meet targets

---

### Phase 4: Gradual Cutover
**Duration**: 1 day  
**Risk**: Medium (Production traffic cutover)

#### 4.1 Modify API Response (Feature Flag)
```python
# Add feature flag for async processing
async def ingest_logs():
    if ENABLE_ASYNC_PROCESSING:
        # Publish event only, return 202
        await publish_log_event(...)
        return 202  # Accepted
    else:
        # Current synchronous processing
        await process_logs_and_tracking_background(...)
        return 200  # OK
```

#### 4.2 Gradual Traffic Migration
- Start with 10% traffic on async processing
- Monitor metrics and error rates
- Gradually increase: 25% → 50% → 75% → 100%

#### 4.3 Cleanup Direct Processing
Once 100% traffic on async:
- Remove `process_logs_and_tracking_background()` from API calls
- Keep function for emergency rollback
- Remove doubled data from validation period

**Validation**:
- API response times drop to <1ms
- Event processing handles 100% load
- No data loss during cutover
- System ready for 1M RPS scaling

---

## Rollback Plan

### Emergency Rollback
If issues detected at any phase:

```python
# Immediate rollback flag
EMERGENCY_ROLLBACK = True

if EMERGENCY_ROLLBACK:
    # Disable event processing
    # Return to direct processing
    # Stop subscribers temporarily
```

### Phase-Specific Rollbacks
- **Phase 1**: Simply don't use new functions
- **Phase 2**: Disable subscribers, continue direct processing  
- **Phase 3**: Reduce load, analyze issues
- **Phase 4**: Flip feature flag back to synchronous

---

## Monitoring & Alerts

### Key Metrics
```
- API response time (target: <1ms after cutover)
- Event processing latency (target: <100ms p95)  
- Consumer lag (target: <1000 messages)
- Data consistency (target: 100%)
- Error rates (target: <0.1%)
```

### Alert Conditions
- Consumer lag > 5000 messages
- Event processing latency > 500ms  
- Data inconsistency detected
- Error rate > 1%
- API response time > 10ms (after cutover)

---

## Success Criteria

### Phase 1 Success
- [ ] `event_processing.py` created with all functions
- [ ] LogEventHandler updated
- [ ] No circular import errors
- [ ] All tests pass

### Phase 2 Success  
- [ ] Dual processing active
- [ ] 2x data visible in all tables
- [ ] Event processing latency <100ms
- [ ] No processing errors

### Phase 3 Success
- [ ] System handles 100K RPS with dual processing
- [ ] Data consistency 100%
- [ ] Performance benchmarks met
- [ ] Load testing passes

### Phase 4 Success
- [ ] API response time <1ms
- [ ] 100% traffic on async processing
- [ ] Zero data loss
- [ ] System ready for 1M RPS scaling

---

## Risk Mitigation

### Technical Risks
- **Data Loss**: Comprehensive monitoring and rollback procedures
- **Performance Degradation**: Gradual rollout with metrics
- **Circular Dependencies**: Careful module design and testing
- **Event Queue Overflow**: Proper partitioning and consumer scaling

### Business Risks
- **Downtime**: Zero-downtime migration strategy
- **Data Inconsistency**: Validation phase with dual processing
- **Customer Impact**: Feature flag for gradual rollout

---

## Implementation Timeline

```
Week 1:
├── Day 1-2: Phase 1 Implementation
├── Day 3: Phase 2 Implementation  
├── Day 4-5: Phase 3 Testing

Week 2:
├── Day 1: Phase 4 Preparation
├── Day 2: Gradual Cutover
├── Day 3-5: Monitoring and Optimization
```

**Total Duration**: 10 days
**Go-Live**: End of Week 2
**Result**: 1M RPS capable event-driven architecture

---

This migration plan ensures zero downtime while transitioning to a scalable, event-driven architecture capable of handling 1M requests per second.