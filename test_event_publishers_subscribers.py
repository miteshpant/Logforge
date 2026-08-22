#!/usr/bin/env python3
"""
Test Event Publishers and Subscribers
Simple test to verify publisher/subscriber functionality
"""

import asyncio
import sys
import os

# Add the apps/api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps', 'api'))

from events.base import BaseEvent, EventFactory, EventMetadata, EventPriority
from events.publishers import publisher_manager, MockEventPublisher, PublisherConfig
from events.subscribers import subscriber_manager, MockEventSubscriber, SubscriberConfig, EventHandler


class TestEventHandler(EventHandler):
    """Test event handler for validation"""
    
    def __init__(self):
        self.handled_events = []
    
    async def handle(self, event: BaseEvent) -> bool:
        """Handle test events"""
        print(f"✅ Handler received event: {event.event_type} (ID: {event.metadata.event_id})")
        self.handled_events.append(event)
        return True
    
    def get_supported_event_types(self) -> list[str]:
        """Support test events"""
        return ["test.event", "test.batch_event"]
    
    def get_handler_name(self) -> str:
        """Get handler name"""
        return "test_handler"


async def test_mock_publisher_subscriber():
    """Test mock publisher and subscriber functionality"""
    print("🧪 Testing Mock Publisher and Subscriber...")
    
    # Create test handler
    test_handler = TestEventHandler()
    
    # Setup mock publisher
    publisher_config = PublisherConfig(
        name="test_publisher",
        enabled=True,
        max_batch_size=1  # Immediate publishing
    )
    
    mock_publisher = MockEventPublisher(publisher_config)
    await mock_publisher.start()
    
    # Setup mock subscriber
    subscriber_config = SubscriberConfig(
        name="test_subscriber",
        consumer_group="test-group",
        event_types=["test.event", "test.batch_event"],
        enabled=True
    )
    
    mock_subscriber = MockEventSubscriber(subscriber_config)
    mock_subscriber.register_handler(test_handler)
    await mock_subscriber.start()
    
    # Create test events
    event1 = EventFactory.create_event(
        event_type="test.event",
        customer_id="test-customer-123",
        data={"message": "Hello World", "test_id": 1},
        priority=EventPriority.HIGH
    )
    
    event2 = EventFactory.create_event(
        event_type="test.batch_event", 
        customer_id="test-customer-456",
        data={"message": "Batch Test", "test_id": 2},
        priority=EventPriority.MEDIUM
    )
    
    # Test single event publishing
    print(f"📤 Publishing single event: {event1.event_type}")
    success = await mock_publisher.publish(event1)
    assert success, "Failed to publish single event"
    print(f"✅ Single event published successfully")
    
    # Test batch publishing
    print(f"📤 Publishing batch of events...")
    batch_results = await mock_publisher.publish_batch([event2])
    assert all(batch_results.values()), "Failed to publish batch events"
    print(f"✅ Batch events published successfully")
    
    # Test subscriber event handling
    print(f"📥 Testing subscriber event handling...")
    
    # Manually handle events with subscriber (since we're using mock)
    for event in mock_publisher.published_events:
        success = await mock_subscriber.handle_event(event)
        assert success, f"Failed to handle event {event.metadata.event_id}"
    
    # Verify handler received events
    assert len(test_handler.handled_events) == 2, f"Expected 2 events, got {len(test_handler.handled_events)}"
    
    # Check metrics
    pub_metrics = mock_publisher.metrics.to_dict()
    sub_metrics = mock_subscriber.metrics.to_dict()
    
    print(f"📊 Publisher Metrics: {pub_metrics}")
    print(f"📊 Subscriber Metrics: {sub_metrics}")
    
    assert pub_metrics["events_published"] == 2, f"Expected 2 published events, got {pub_metrics['events_published']}"
    assert sub_metrics["events_consumed"] == 2, f"Expected 2 consumed events, got {sub_metrics['events_consumed']}"
    
    # Test health checks
    pub_health = await mock_publisher.health_check()
    sub_health = mock_subscriber.is_started
    
    assert pub_health, "Publisher health check failed"
    assert sub_health, "Subscriber health check failed"
    
    # Cleanup
    await mock_publisher.close()
    await mock_subscriber.stop()
    
    print("✅ Mock publisher/subscriber test completed successfully!")


async def test_event_manager_integration():
    """Test publisher and subscriber managers"""
    print("🔧 Testing Event Manager Integration...")
    
    # Test publisher manager
    print("📤 Testing Publisher Manager...")
    
    # Register mock publisher
    mock_config = PublisherConfig(name="test_mock", enabled=True)
    publisher_manager.register_publisher("test_mock", MockEventPublisher, mock_config)
    
    await publisher_manager.start()
    
    # Create test event
    test_event = EventFactory.create_event(
        event_type="usage.api_call",
        customer_id="manager-test-customer",
        data={"endpoint": "/api/test", "method": "GET", "response_time": 123}
    )
    
    # Publish through manager
    results = await publisher_manager.publish(test_event, ["test_mock"])
    assert results.get("test_mock"), "Failed to publish through manager"
    print("✅ Publisher manager test passed")
    
    # Test subscriber manager
    print("📥 Testing Subscriber Manager...")
    
    # Register mock subscriber
    mock_sub_config = SubscriberConfig(
        name="test_mock_sub",
        consumer_group="test-manager-group",
        event_types=["usage.api_call"],
        enabled=True
    )
    subscriber_manager.register_subscriber("test_mock_sub", MockEventSubscriber, mock_sub_config)
    
    await subscriber_manager.start()
    
    # Get subscriber and test
    test_subscriber = subscriber_manager.get_subscriber("test_mock_sub")
    assert test_subscriber is not None, "Failed to get subscriber from manager"
    
    # Test event handling
    success = await test_subscriber.handle_event(test_event)
    assert success, "Failed to handle event through manager"
    print("✅ Subscriber manager test passed")
    
    # Test health checks
    pub_health = await publisher_manager.health_check()
    sub_health = await subscriber_manager.health_check()
    
    print(f"📊 Publisher Health: {pub_health}")
    print(f"📊 Subscriber Health: {sub_health}")
    
    assert pub_health.get("test_mock"), "Publisher manager health check failed"
    assert sub_health.get("test_mock_sub"), "Subscriber manager health check failed"
    
    # Test metrics
    pub_metrics = publisher_manager.get_metrics()
    sub_metrics = subscriber_manager.get_metrics()
    
    print(f"📊 Publisher Manager Metrics: {pub_metrics}")
    print(f"📊 Subscriber Manager Metrics: {sub_metrics}")
    
    # Cleanup
    await publisher_manager.close()
    await subscriber_manager.stop()
    
    print("✅ Event manager integration test completed successfully!")


async def test_event_types_and_routing():
    """Test different event types and routing"""
    print("🎯 Testing Event Types and Routing...")
    
    # Test different event types
    event_types = [
        ("usage.api_call", "usage-events"),
        ("alert.triggered", "alert-events"),
        ("log.ingested", "log-events"),
        ("system.health_check", "system-events"),
        ("tenant.created", "tenant-events"),
        ("ui.dashboard_view", "ui-realtime-events")
    ]
    
    for event_type, expected_topic in event_types:
        event = EventFactory.create_event(
            event_type=event_type,
            customer_id="routing-test-customer",
            data={"test": True, "event_type": event_type}
        )
        
        print(f"📝 Created event: {event_type}")
        
        # Verify event creation
        assert event.event_type == event_type
        assert event.customer_id == "routing-test-customer"
        assert event.data["test"] is True
        
        # Test serialization
        event_dict = event.to_dict()
        event_json = event.to_json()
        
        # Test deserialization
        reconstructed_event = BaseEvent.from_dict(event_dict)
        reconstructed_from_json = BaseEvent.from_json(event_json)
        
        assert reconstructed_event.event_type == event_type
        assert reconstructed_from_json.event_type == event_type
        
        print(f"✅ Event {event_type} serialization/deserialization works")
    
    print("✅ Event types and routing test completed successfully!")


async def main():
    """Run all tests"""
    print("🚀 Starting Event Publishers and Subscribers Tests\n")
    
    try:
        # Test 1: Mock functionality
        await test_mock_publisher_subscriber()
        print()
        
        # Test 2: Manager integration  
        await test_event_manager_integration()
        print()
        
        # Test 3: Event types and routing
        await test_event_types_and_routing()
        print()
        
        print("🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)