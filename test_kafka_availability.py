#!/usr/bin/env python3
"""
Simple test to check Kafka availability
"""

import sys
import os

# Add the API directory to Python path
sys.path.insert(0, '/Users/miteshpant/projects/Logforge/apps/api')

print("Testing Kafka availability...")

try:
    import aiokafka
    print("✅ aiokafka is available")
    print(f"aiokafka version: {aiokafka.__version__}")
except ImportError as e:
    print(f"❌ aiokafka is not available: {e}")

try:
    from events.kafka_publisher import create_kafka_publisher, kafka_available
    print(f"✅ kafka_publisher module loaded, kafka_available: {kafka_available}")
    
    if kafka_available:
        print("✅ Creating Kafka publisher...")
        publisher = create_kafka_publisher()
        if publisher:
            print("✅ Kafka publisher created successfully")
        else:
            print("❌ Kafka publisher creation returned None")
    
except ImportError as e:
    print(f"❌ kafka_publisher import failed: {e}")

try:
    from events.publishers import register_default_publishers, publisher_manager
    print("✅ Publishers module loaded")
    
    print("Checking registered publishers...")
    if publisher_manager.publishers:
        for name, publisher in publisher_manager.publishers.items():
            print(f"  - {name}: {type(publisher).__name__}")
    else:
        print("  No publishers registered")
        
    print("Re-running publisher registration...")
    register_default_publishers()
    
    if publisher_manager.publishers:
        for name, publisher in publisher_manager.publishers.items():
            print(f"  - {name}: {type(publisher).__name__}")
    else:
        print("  Still no publishers registered")
        
except ImportError as e:
    print(f"❌ publishers import failed: {e}")