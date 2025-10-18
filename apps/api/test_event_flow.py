#!/usr/bin/env python3
"""
Standalone Event Flow Test
Tests basic event publishing and consumption without API integration
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timezone

# Add the API directory to Python path
sys.path.insert(0, '/Users/miteshpant/projects/Logforge/apps/api')

from events.types.usage_events import create_api_usage_event
from events.publishers import publisher_manager
from events.kafka.consumer import KafkaEventConsumer
from events.config import get_events_config
from events.topics import topic_manager

async def test_publish_event():
    """Test publishing a usage event to Redpanda"""
    print("🚀 Testing Event Publishing...")
    
    # Create a test usage event
    event = create_api_usage_event(
        customer_id="test-customer-123",
        endpoint="/test/endpoint", 
        method="GET",
        response_size=1024,
        processing_time=150.5,
        feature="api_test",
        request_id="test-request-001"
    )
    
    print(f"📝 Created event: {event.event_type} for customer {event.customer_id}")
    
    # Get topic for the event
    topic = topic_manager.get_topic_for_event(event.event_type)
    print(f"📍 Event will be published to topic: {topic}")
    
    try:
        # Use the global publisher manager
        print("✅ Using publisher manager")
        
        # Publish the event
        success = await publisher_manager.publish_event(event)
        print(f"📤 Event published: {success}")
        
        if success:
            print("🎉 Event publishing test PASSED!")
            return True
        else:
            print("❌ Event publishing test FAILED!")
            return False
            
    except Exception as e:
        print(f"💥 Error during publishing: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_consume_event():
    """Test consuming events from Redpanda using rpk"""
    print("\n🔄 Testing Event Consumption with rpk...")
    
    import subprocess
    import json
    
    try:
        # Use rpk to consume messages from usage-events topic
        print("📥 Using rpk to consume from usage-events topic...")
        
        result = subprocess.run([
            "docker", "exec", "logforge-redpanda", "rpk", "topic", "consume", 
            "usage-events", "--num", "1", "--timeout", "5s", "--offset", "start"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            print("🎉 Message found in Redpanda!")
            print(f"📨 Message content: {result.stdout.strip()[:200]}...")
            return True
        else:
            print("⏰ No messages found in topic")
            print(f"rpk stdout: {result.stdout}")
            print(f"rpk stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ rpk consume command timed out")
        return False
    except Exception as e:
        print(f"💥 Error during rpk consumption: {e}")
        return False

async def test_complete_flow():
    """Test complete publish → consume flow"""
    print("\n🌊 Testing Complete Event Flow...")
    
    # Test publishing
    publish_success = await test_publish_event()
    
    if not publish_success:
        print("❌ Publishing failed, skipping consumption test")
        return False
    
    # Wait a moment for message to be available
    print("⏳ Waiting 2 seconds for message to be available...")
    await asyncio.sleep(2)
    
    # Test consumption
    consume_success = await test_consume_event()
    
    if publish_success and consume_success:
        print("\n🎊 COMPLETE FLOW TEST PASSED!")
        return True
    else:
        print("\n💥 COMPLETE FLOW TEST FAILED!")
        return False

if __name__ == "__main__":
    print("🧪 Starting Event Flow Test")
    print("=" * 50)
    
    try:
        result = asyncio.run(test_complete_flow())
        if result:
            print("\n✅ All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)