# Event System Guide - Simple Usage

This guide explains how to use Logforge's event system in simple terms.

## What is the Event System?

The event system lets different parts of Logforge communicate by sending messages (events) to each other. Think of it like a post office - one service sends a letter (event), and other services can receive and read it.

## Basic Concepts

### 🎯 **Events**
- Messages that carry information about what happened
- Example: "User logged in", "Alert triggered", "Log received"

### 📤 **Publishers** 
- Services that send events
- Like someone writing and mailing letters

### 📥 **Subscribers**
- Services that receive and handle events  
- Like someone reading their mail and taking action

### 🗂️ **Topics**
- Categories of events (like different mailboxes)
- Examples: `usage-events`, `alert-events`, `log-events`

## Quick Start

### 1. Sending an Event (Publishing)

```python
from events.base import EventFactory
from events.publishers import publisher_manager

# Start the publisher system
await publisher_manager.start()

# Create an event
event = EventFactory.create_event(
    event_type="usage.api_call",          # What happened
    customer_id="customer-123",           # Which customer
    data={                                # Details
        "endpoint": "/api/logs",
        "method": "POST", 
        "response_time": 150
    }
)

# Send the event
await publisher_manager.publish(event)
```

### 2. Receiving Events (Subscribing)

```python
from events.subscribers import subscriber_manager, EventHandler

# Create a custom handler
class MyEventHandler(EventHandler):
    async def handle(self, event):
        print(f"Got event: {event.event_type}")
        print(f"Customer: {event.customer_id}")
        print(f"Data: {event.data}")
        return True  # Success
    
    def get_supported_event_types(self):
        return ["usage.api_call"]  # What events I want
    
    def get_handler_name(self):
        return "my_handler"

# Register and start
handler = MyEventHandler()
subscriber = subscriber_manager.get_subscriber("usage_subscriber")
subscriber.register_handler(handler)
await subscriber_manager.start()
```

## Event Types

Events follow a simple pattern: `category.action`

### 📊 **Usage Events** (`usage.*`)
- `usage.api_call` - API was called
- `usage.data_ingested` - Data was stored
- `usage.query_executed` - Search was performed

### 🚨 **Alert Events** (`alert.*`)
- `alert.triggered` - Alert fired
- `alert.resolved` - Alert fixed
- `alert.acknowledged` - Someone saw the alert

### 📝 **Log Events** (`log.*`)
- `log.ingested` - New log received
- `log.parsed` - Log was processed
- `log.indexed` - Log ready for search

### 🏢 **Tenant Events** (`tenant.*`)
- `tenant.created` - New customer added
- `tenant.updated` - Customer info changed

### ⚙️ **System Events** (`system.*`)
- `system.health_check` - Health check performed
- `system.error_occurred` - Something went wrong

## Configuration

Events are configured in `/apps/api/config/events.yml`:

```yaml
# Example configuration
topics:
  usage-events:
    partitions: 100      # How many parallel streams
    retention_ms: 604800000  # Keep for 7 days
  
  alert-events:
    partitions: 50
    retention_ms: 2592000000  # Keep for 30 days
```

## Customer Isolation

Each customer's events go to separate partitions:

```python
from events.partitioning import customer_partition_manager

# Get partition for customer
partition = customer_partition_manager.get_partition(
    customer_id="customer-123",
    topic="usage-events"
)

# Get detailed info
info = customer_partition_manager.get_partition_info(
    customer_id="customer-123", 
    topic="usage-events"
)
print(f"Customer on partition {info.partition} of {info.total_partitions}")
```

## Built-in Handlers

The system comes with ready-to-use handlers:

### 💰 **UsageEventHandler**
- Tracks API usage
- Calculates billing
- Updates quotas
- Handles: `usage.*`, `billing.*`

### 🚨 **AlertEventHandler** 
- Processes alerts
- Sends notifications
- Updates alert states
- Handles: `alert.*`

### 📝 **LogEventHandler**
- Processes log data
- Updates search indexes
- Handles archiving
- Handles: `log.*`

### ⚙️ **SystemEventHandler**
- Monitors system health
- Updates dashboards
- Tracks performance
- Handles: `system.*`

## Testing

Use mock publishers/subscribers for testing:

```python
from events.publishers import MockEventPublisher, PublisherConfig
from events.subscribers import MockEventSubscriber, SubscriberConfig

# Create mock publisher
config = PublisherConfig(name="test", enabled=True)
publisher = MockEventPublisher(config)
await publisher.start()

# Send test event
await publisher.publish(event)

# Check what was sent
print(f"Published {len(publisher.published_events)} events")
```

## Health Monitoring

Check if everything is working:

```python
# Check publisher health
pub_health = await publisher_manager.health_check()
print(f"Publishers: {pub_health}")

# Check subscriber health  
sub_health = await subscriber_manager.health_check()
print(f"Subscribers: {sub_health}")

# Get metrics
pub_metrics = publisher_manager.get_metrics()
sub_metrics = subscriber_manager.get_metrics()
```

## Common Patterns

### 1. **Fire and Forget**
Send event and don't wait for response:

```python
# Just send it
await publisher_manager.publish(event)
# Keep going with other work
```

### 2. **Batch Processing**
Send multiple events together:

```python
events = [event1, event2, event3]
results = await publisher_manager.publish_batch(events)
```

### 3. **Error Handling**
Handle failed events:

```python
try:
    success = await publisher_manager.publish(event)
    if not success:
        print("Event failed to send")
except Exception as e:
    print(f"Error: {e}")
```

## Best Practices

### ✅ **Do**
- Use clear event types (`usage.api_call` not `stuff.happened`)
- Include customer_id for isolation
- Keep event data small and focused
- Handle errors gracefully
- Use built-in handlers when possible

### ❌ **Don't**
- Put sensitive data in events
- Make events too large (>1MB)
- Create too many custom event types
- Forget to handle failures
- Block waiting for events

## Troubleshooting

### **Events not being received**
1. Check if subscriber is started: `await subscriber_manager.start()`
2. Verify event types match handler
3. Check health: `await subscriber_manager.health_check()`

### **Events failing to send**
1. Check publisher health: `await publisher_manager.health_check()`
2. Verify Kafka is running
3. Check event size (must be < 1MB)

### **Slow performance**
1. Check partition distribution
2. Increase parallel workers
3. Use batch publishing
4. Monitor metrics

### **Wrong partition**
```python
# Clear cache to recalculate
customer_partition_manager.clear_cache("usage-events")

# Check current assignment
info = customer_partition_manager.get_partition_info("customer-123", "usage-events")
```

## Example: Complete Usage Tracking

```python
# 1. Setup (do once at startup)
await publisher_manager.start()
await subscriber_manager.start()

# 2. Track API call (in your API endpoint)
event = EventFactory.create_event(
    event_type="usage.api_call",
    customer_id=request.headers.get("X-Customer-ID"),
    data={
        "endpoint": request.path,
        "method": request.method,
        "response_code": 200,
        "response_time_ms": 145,
        "bytes_returned": 1024
    }
)
await publisher_manager.publish(event)

# 3. Handle usage (automatic via UsageEventHandler)
# - Updates billing metrics
# - Checks quotas  
# - Records usage history
```

That's it! The event system handles the complex stuff so you can focus on your business logic.

## Need Help?

- Check logs for error messages
- Use health checks to verify status
- Monitor metrics for performance
- Test with mock publishers/subscribers first