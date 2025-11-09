# Event-Driven Development Guide
## Complete Guide to Publishers, Handlers, Topics & Debugging

### 📋 Overview
This guide covers how to implement event-driven components in the Logforge system from scratch, including publishers, subscribers, topics, and comprehensive debugging strategies.

---

## 🏗️ Architecture Overview

```
Event Flow:
Publisher → Event Manager → Kafka Topic → Event Consumer → Handler Logic
```

**Key Components:**
- **Publishers**: Emit events to topics
- **Subscribers**: Listen to topics and handle events
- **Topics**: Kafka topics for event routing
- **Event Manager**: Central event orchestration
- **Event Constants**: Define event types and topic mappings

---

## 🚀 Step-by-Step Implementation

### Step 1: Define Event Constants

**File**: `/apps/api/events/constants.py`

```python
# 1. Add your event type constant
EVENT_MY_NEW_EVENT = "my.new.event"

# 2. Add to appropriate event type list
MY_EVENT_TYPES = [
    EVENT_MY_NEW_EVENT,
]

# 3. Map event to topic
EVENT_TYPE_TO_TOPIC = {
    EVENT_MY_NEW_EVENT: TOPIC_MY_EVENTS,  # Define topic if needed
}

# 4. Define topic if new
TOPIC_MY_EVENTS = "my-events"

# 5. Add to all topics list
KAFKA_TOPICS = [
    TOPIC_LOG_EVENTS,
    TOPIC_SECURITY_EVENTS,
    TOPIC_MY_EVENTS,  # Add your topic
]
```

### Step 2: Create Event Publisher

**File**: `/apps/api/events/publishers/my_event_publisher.py`

```python
"""
My Event Publisher - Publishes my.new.event events
"""
from typing import Dict, Any
from datetime import datetime, timezone

from ..base import BaseEventPublisher
from ..models import BaseEvent, EventMetadata, EventPriority
from ..constants import EVENT_MY_NEW_EVENT


class MyEventPublisher(BaseEventPublisher):
    """Publisher for my custom events"""
    
    async def publish_my_event(self, 
                              data: Dict[str, Any], 
                              customer_id: str,
                              priority: EventPriority = EventPriority.MEDIUM) -> bool:
        """
        Publish my custom event
        
        Args:
            data: Event payload data
            customer_id: Customer identifier
            priority: Event priority level
            
        Returns:
            bool: True if published successfully
        """
        try:
            # Create event payload
            event_data = {
                "payload": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_service": "my-service",
                "event_version": "1.0"
            }
            
            # Create event
            event = BaseEvent(
                event_type=EVENT_MY_NEW_EVENT,
                customer_id=customer_id,
                data=event_data,
                metadata=EventMetadata(
                    source_service="my-service",
                    priority=priority,
                    correlation_id=self._generate_correlation_id()
                )
            )
            
            # Publish event
            success = await self.publisher_manager.publish(event)
            
            if success:
                self.logger.info(f"Published {EVENT_MY_NEW_EVENT} for customer {customer_id}")
            else:
                self.logger.error(f"Failed to publish {EVENT_MY_NEW_EVENT} for customer {customer_id}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error publishing my event: {e}")
            return False
    
    def _generate_correlation_id(self) -> str:
        """Generate unique correlation ID for event tracking"""
        import uuid
        return f"my-event-{uuid.uuid4().hex[:8]}"
```

### Step 3: Create Event Subscriber/Handler

**File**: `/apps/api/events/subscribers/my_event_subscriber.py`

```python
"""
My Event Subscriber - Handles my.new.event events
"""
from typing import Dict, Any
import json

from ..base import EventSubscriber
from ..models import BaseEvent, SubscriberConfig
from ..constants import EVENT_MY_NEW_EVENT, TOPIC_MY_EVENTS


class MyEventSubscriber(EventSubscriber):
    """Subscriber for my custom events"""
    
    def __init__(self):
        super().__init__()
        self.my_service = self._get_my_service()  # Initialize your service
        
    async def handle_event(self, event: BaseEvent) -> bool:
        """
        Handle my custom event
        
        Args:
            event: The event to process
            
        Returns:
            bool: True if handled successfully
        """
        try:
            # Filter for your event type
            if event.event_type != EVENT_MY_NEW_EVENT:
                return True  # Skip non-matching events
            
            customer_id = event.customer_id
            event_data = event.data
            
            self.logger.info(f"Processing {EVENT_MY_NEW_EVENT} for customer {customer_id}")
            
            # Extract event payload
            payload = event_data.get("payload", {})
            
            # Your business logic here
            result = await self._process_my_event(payload, customer_id)
            
            if result:
                self.logger.info(f"Successfully processed {EVENT_MY_NEW_EVENT}")
                
                # Optional: Publish follow-up events
                await self._publish_follow_up_event(result, customer_id)
                
                return True
            else:
                self.logger.error(f"Failed to process {EVENT_MY_NEW_EVENT}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error handling my event: {e}")
            return False
    
    async def _process_my_event(self, payload: Dict[str, Any], customer_id: str) -> Dict[str, Any]:
        """
        Process the event payload
        
        Args:
            payload: Event payload data
            customer_id: Customer identifier
            
        Returns:
            Dict: Processing result
        """
        # Implement your business logic
        try:
            # Example: Call your service
            result = await self.my_service.process_data(payload, customer_id)
            
            # Example: Store in database
            await self._store_event_result(result, customer_id)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in _process_my_event: {e}")
            return {}
    
    async def _store_event_result(self, result: Dict[str, Any], customer_id: str):
        """Store event processing result"""
        # Implement storage logic
        pass
    
    async def _publish_follow_up_event(self, result: Dict[str, Any], customer_id: str):
        """Publish follow-up events if needed"""
        # Example: Publish completion event
        pass
    
    async def get_subscription_info(self) -> SubscriberConfig:
        """Configure subscription settings"""
        return SubscriberConfig(
            subscriber_group="my-event-processor",  # Unique group name
            topics=[TOPIC_MY_EVENTS],
            event_types=[EVENT_MY_NEW_EVENT],
            max_retries=3,
            retry_delay_seconds=5
        )
    
    def _get_my_service(self):
        """Initialize your service dependency"""
        # Import and return your service
        pass
```

### Step 4: Register Subscriber

**File**: `/apps/api/events/subscribers/__init__.py`

```python
# Add your subscriber to the imports
from .my_event_subscriber import MyEventSubscriber

# Add to SUBSCRIBERS list
SUBSCRIBERS = [
    LogIngestionSubscriber(),
    AlertEngineSubscriber(),
    MyEventSubscriber(),  # Add your subscriber
]
```

### Step 5: Using the Publisher

**Example**: In your service or API endpoint

```python
from events.publishers.my_event_publisher import MyEventPublisher

class MyService:
    def __init__(self):
        self.event_publisher = MyEventPublisher()
    
    async def do_something(self, data: Dict[str, Any], customer_id: str):
        """Example service method that publishes events"""
        
        # Your business logic
        result = await self._process_data(data)
        
        # Publish event
        event_success = await self.event_publisher.publish_my_event(
            data={
                "action": "data_processed",
                "result": result,
                "metadata": {"source": "my_service"}
            },
            customer_id=customer_id,
            priority=EventPriority.HIGH
        )
        
        if not event_success:
            self.logger.warning("Failed to publish event, but continuing...")
        
        return result
```

---

## 🐛 Debugging Guide

### 1. Event Publishing Issues

**Problem**: Events not being published

**Debug Steps**:

```bash
# 1. Check Kafka connectivity
docker logs logforge-kafka

# 2. Check event manager logs
grep "EventManager" /path/to/logs/app.log

# 3. Verify topic exists
docker exec -it logforge-kafka kafka-topics.sh --list --bootstrap-server localhost:9092

# 4. Check publisher logs
grep "MyEventPublisher" /path/to/logs/app.log
```

**Common Issues**:
- Kafka not running: `docker-compose up kafka`
- Topic doesn't exist: Add to `KAFKA_TOPICS` in constants.py
- Serialization errors: Check event data structure
- Connection timeouts: Check network and Kafka health

### 2. Event Consumption Issues

**Problem**: Events published but not consumed

**Debug Steps**:

```python
# 1. Add debug logging to subscriber
async def handle_event(self, event: BaseEvent) -> bool:
    self.logger.info(f"Received event: {event.event_type}")
    self.logger.info(f"Event data: {json.dumps(event.data, indent=2)}")
    # ... rest of handler
```

```bash
# 2. Check consumer group status
docker exec -it logforge-kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group my-event-processor

# 3. Check subscriber registration
grep "MyEventSubscriber" /path/to/logs/app.log

# 4. Monitor topic messages
docker exec -it logforge-kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic my-events --from-beginning
```

**Common Issues**:
- Subscriber not registered: Check `__init__.py` imports
- Wrong event type filter: Verify `EVENT_MY_NEW_EVENT` constant
- Consumer group issues: Reset offset or change group name
- Handler exceptions: Check error logs

### 3. Event Flow Debugging

**Debug Event End-to-End**:

```python
# Add correlation ID tracking
class MyEventPublisher(BaseEventPublisher):
    async def publish_my_event(self, data, customer_id):
        correlation_id = f"debug-{uuid.uuid4().hex[:8]}"
        
        self.logger.info(f"[{correlation_id}] Publishing event for customer {customer_id}")
        
        event = BaseEvent(
            # ... event setup
            metadata=EventMetadata(
                correlation_id=correlation_id,
                # ... other metadata
            )
        )
        
        success = await self.publisher_manager.publish(event)
        self.logger.info(f"[{correlation_id}] Publish result: {success}")
        return success

class MyEventSubscriber(EventSubscriber):
    async def handle_event(self, event: BaseEvent) -> bool:
        correlation_id = event.metadata.correlation_id if event.metadata else "unknown"
        
        self.logger.info(f"[{correlation_id}] Received event: {event.event_type}")
        
        # ... processing logic
        
        self.logger.info(f"[{correlation_id}] Processing complete")
        return True
```

### 4. Performance Debugging

**Monitor Event Processing Performance**:

```python
import time
from datetime import datetime

class MyEventSubscriber(EventSubscriber):
    async def handle_event(self, event: BaseEvent) -> bool:
        start_time = time.time()
        
        try:
            # Your processing logic
            result = await self._process_my_event(payload, customer_id)
            
            processing_time = (time.time() - start_time) * 1000
            self.logger.info(f"Event processing took {processing_time:.2f}ms")
            
            if processing_time > 1000:  # Warn if >1s
                self.logger.warning(f"Slow event processing: {processing_time:.2f}ms")
            
            return True
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self.logger.error(f"Event failed after {processing_time:.2f}ms: {e}")
            return False
```

### 5. Common Debugging Commands

```bash
# Check Kafka topics
docker exec -it logforge-kafka kafka-topics.sh --list --bootstrap-server localhost:9092

# Monitor specific topic
docker exec -it logforge-kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic my-events

# Check consumer groups
docker exec -it logforge-kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list

# Reset consumer group offset (careful!)
docker exec -it logforge-kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group my-event-processor --reset-offsets --to-earliest --topic my-events --execute

# Check application logs
tail -f /path/to/logs/app.log | grep -E "(MyEvent|ERROR|WARN)"

# Check Kafka logs
docker logs logforge-kafka | tail -100

# Monitor event processing rate
grep "Processing.*EVENT_MY_NEW_EVENT" /path/to/logs/app.log | wc -l
```

---

## ✅ Testing Your Implementation

### 1. Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch

class TestMyEventPublisher:
    
    @pytest.mark.asyncio
    async def test_publish_my_event_success(self):
        """Test successful event publishing"""
        publisher = MyEventPublisher()
        
        with patch.object(publisher.publisher_manager, 'publish', return_value=True) as mock_publish:
            result = await publisher.publish_my_event(
                data={"test": "data"},
                customer_id="test-customer"
            )
            
            assert result is True
            mock_publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_my_event_failure(self):
        """Test event publishing failure"""
        publisher = MyEventPublisher()
        
        with patch.object(publisher.publisher_manager, 'publish', return_value=False) as mock_publish:
            result = await publisher.publish_my_event(
                data={"test": "data"},
                customer_id="test-customer"
            )
            
            assert result is False

class TestMyEventSubscriber:
    
    @pytest.mark.asyncio
    async def test_handle_event_success(self):
        """Test successful event handling"""
        subscriber = MyEventSubscriber()
        
        event = BaseEvent(
            event_type=EVENT_MY_NEW_EVENT,
            customer_id="test-customer",
            data={"payload": {"test": "data"}}
        )
        
        with patch.object(subscriber, '_process_my_event', return_value={"success": True}):
            result = await subscriber.handle_event(event)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_handle_wrong_event_type(self):
        """Test handling wrong event type"""
        subscriber = MyEventSubscriber()
        
        event = BaseEvent(
            event_type="wrong.event.type",
            customer_id="test-customer",
            data={}
        )
        
        result = await subscriber.handle_event(event)
        assert result is True  # Should skip non-matching events
```

### 2. Integration Tests

```python
@pytest.mark.asyncio
async def test_end_to_end_event_flow():
    """Test complete event flow from publish to consume"""
    
    # Setup
    publisher = MyEventPublisher()
    test_data = {"test": "integration"}
    customer_id = "test-customer"
    
    # Publish event
    publish_success = await publisher.publish_my_event(test_data, customer_id)
    assert publish_success
    
    # Wait for processing (in real test, use proper event waiting)
    await asyncio.sleep(1)
    
    # Verify event was processed (check database, logs, etc.)
    # This depends on your specific implementation
```

---

## 📚 Best Practices

### 1. Event Design
- **Use descriptive event names**: `user.registered` not `user.event`
- **Include correlation IDs**: For debugging and tracing
- **Version your events**: Plan for schema evolution
- **Keep events small**: Large payloads slow processing

### 2. Error Handling
- **Always return bool**: `True` for success, `False` for retry
- **Log with correlation IDs**: Enable event tracing
- **Handle partial failures**: Don't fail entire batch for one item
- **Use circuit breakers**: Prevent cascade failures

### 3. Performance
- **Batch when possible**: Group related events
- **Use async/await**: Don't block event loop
- **Monitor processing time**: Alert on slow handlers
- **Cache frequently used data**: Reduce database hits

### 4. Monitoring
- **Track event rates**: Publishing and consumption
- **Monitor lag**: Time between publish and consume
- **Alert on failures**: High error rates or processing delays
- **Use correlation IDs**: End-to-end event tracing

---

## 🔧 Troubleshooting Checklist

**Event Not Published?**
- [ ] Kafka running and accessible
- [ ] Topic exists in `KAFKA_TOPICS`
- [ ] Event type mapped in `EVENT_TYPE_TO_TOPIC`
- [ ] Publisher manager initialized
- [ ] No serialization errors in logs

**Event Not Consumed?**
- [ ] Subscriber registered in `__init__.py`
- [ ] Correct event type filter in handler
- [ ] Consumer group has access to topic
- [ ] No exceptions in handler logic
- [ ] Handler returns `True` for success

**Slow Processing?**
- [ ] Check database query performance
- [ ] Monitor external API calls
- [ ] Review handler complexity
- [ ] Check for blocking operations
- [ ] Monitor memory usage

**Data Loss?**
- [ ] Handlers return `True` on success
- [ ] No unhandled exceptions
- [ ] Kafka retention settings adequate
- [ ] Consumer group offsets advancing
- [ ] No partition rebalancing issues

---

This guide provides a complete foundation for implementing event-driven components in Logforge. Start with simple events and gradually add complexity as needed. Always test thoroughly and monitor in production!