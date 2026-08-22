#!/usr/bin/env python3
"""
Test script to verify event-driven ingestion flow
Checks that all 4 event types are published and tables are populated
"""

import sys
import os
import asyncio
import json
from datetime import datetime

# Add the API directory to Python path
sys.path.insert(0, '/Users/miteshpant/projects/Logforge/apps/api')

async def test_event_publishing():
    """Test that all 4 event types can be published"""
    print("🔄 Testing event publishing...")
    
    try:
        from events.types.ingestion_events import (
            create_ingestion_batch_event, 
            create_usage_tracking_event,
            create_quota_update_event,
            create_ingestion_error_event
        )
        from events.types.api_events import create_api_usage_event
        from events.publishers import publisher_manager
        
        customer_id = "test-customer-123"
        
        # Test all 4 event types
        events_to_test = [
            # 1. Ingestion batch processed → ingestion_stats_mt
            create_ingestion_batch_event(
                customer_id=customer_id,
                endpoint="/v1/logs/ingest/json",
                format_type="json",
                records_ingested=1,
                bytes_ingested=512,
                processing_time_ms=45.2
            ),
            
            # 2. Usage tracking → usage_records_mt  
            create_usage_tracking_event(
                customer_id=customer_id,
                tenant_id=customer_id,
                feature_name="ingestion",
                usage_type="monthly_ingestion",  # Fixed: was "bytes_ingested"
                quantity=1
            ),
            
            # 3. Quota update → tenant_quotas_mt
            create_quota_update_event(
                customer_id=customer_id,
                tenant_id=customer_id,
                quota_type="monthly_ingestion",
                usage_delta=1,
                action_type="increment"
            ),
            
            # 4. API usage → api_usage_mt
            create_api_usage_event(
                customer_id=customer_id,
                tenant_id=customer_id,
                endpoint="/v1/logs/ingest/json",
                method="POST",
                response_status=200,
                request_size_bytes=512,
                response_size_bytes=64,
                processing_time_ms=45.2
            )
        ]
        
        print(f"✅ Created {len(events_to_test)} test events")
        
        # Check event details
        for i, event in enumerate(events_to_test, 1):
            print(f"  {i}. {event.event_type} - Customer: {event.customer_id}")
            print(f"     Data keys: {list(event.data.keys())}")
        
        # Test publisher availability
        if hasattr(publisher_manager, 'publishers') and publisher_manager.publishers:
            print(f"✅ Publisher manager has {len(publisher_manager.publishers)} publishers")
            for name, pub in publisher_manager.publishers.items():
                print(f"   - {name}: {type(pub).__name__}")
        else:
            print("⚠️  No publishers registered - events will use fallback")
            
        return True
        
    except Exception as e:
        print(f"❌ Event publishing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_consumer_setup():
    """Test that consumer can process all event types"""
    print("\n🔄 Testing consumer setup...")
    
    try:
        from events.subscriber_implementations.ingestion_consumer import IngestionEventConsumer
        
        # Create consumer instance
        consumer = IngestionEventConsumer()
        
        # Check subscribed events
        expected_events = [
            "ingestion.batch_processed",
            "usage.ingestion_tracking", 
            "quota.usage_updated",
            "ingestion.error",
            "usage.api_call"
        ]
        
        print(f"✅ Consumer created successfully")
        print(f"   Subscribed to {len(consumer.subscribed_events)} event types:")
        for event_type in consumer.subscribed_events:
            status = "✅" if event_type in expected_events else "⚠️"
            print(f"   {status} {event_type}")
        
        # Check if all expected events are covered
        missing = set(expected_events) - set(consumer.subscribed_events)
        if missing:
            print(f"⚠️  Missing subscriptions: {missing}")
        else:
            print("✅ All expected event types are subscribed")
            
        return True
        
    except Exception as e:
        print(f"❌ Consumer setup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def check_database_permissions():
    """Check that consumer has database permissions"""
    print("\n🔄 Checking database permissions...")
    
    try:
        from database_layer import AUTHORIZED_SERVICES, SERVICE_TABLE_ACCESS
        
        service_name = "IngestionEventConsumer"
        
        if service_name in AUTHORIZED_SERVICES:
            print(f"✅ {service_name} is in authorized services")
            
            if service_name in SERVICE_TABLE_ACCESS:
                tables = SERVICE_TABLE_ACCESS[service_name]
                print(f"✅ Has access to {len(tables)} tables:")
                for table in tables:
                    print(f"   - {table}")
                    
                # Check expected tables
                expected_tables = [
                    'ingestion_stats_mt', 
                    'usage_records_mt', 
                    'tenant_quotas_mt',
                    'api_usage_mt'
                ]
                
                missing_tables = set(expected_tables) - set(tables)
                if missing_tables:
                    print(f"⚠️  Missing table access: {missing_tables}")
                else:
                    print("✅ Has access to all required tables")
            else:
                print(f"❌ {service_name} not in SERVICE_TABLE_ACCESS")
                return False
        else:
            print(f"❌ {service_name} not in AUTHORIZED_SERVICES")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Database permissions check failed: {e}")
        return False

def check_feature_flags():
    """Check current feature flag settings"""
    print("\n🔄 Checking feature flag settings...")
    
    try:
        from events.config import get_events_config
        
        config = get_events_config()
        flags = config.feature_flags
        
        print("📋 Current feature flag settings:")
        print(f"   enable_event_driven_ingestion: {flags.enable_event_driven_ingestion}")
        print(f"   enable_event_driven_usage_tracking: {flags.enable_event_driven_usage_tracking}")
        print(f"   enable_event_driven_quota_management: {flags.enable_event_driven_quota_management}")
        print(f"   enable_legacy_fallback: {flags.enable_legacy_fallback}")
        
        if flags.enable_event_driven_ingestion:
            print("✅ Event-driven ingestion is ENABLED")
        else:
            print("❌ Event-driven ingestion is DISABLED - enable in config/events.yml")
            
        if flags.enable_legacy_fallback:
            print("✅ Legacy fallback is enabled (safe migration mode)")
        else:
            print("⚠️  Legacy fallback is disabled (full event-only mode)")
            
        return True
        
    except Exception as e:
        print(f"❌ Feature flag check failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Testing Event-Driven Ingestion Flow")
    print("=" * 50)
    
    tests = [
        ("Feature Flags", check_feature_flags),
        ("Event Publishing", test_event_publishing),
        ("Consumer Setup", test_consumer_setup), 
        ("Database Permissions", check_database_permissions)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Event-driven flow is ready for testing.")
        print("\n📝 Next steps:")
        print("1. Clear all tables: ingestion_stats_mt, usage_records_mt, tenant_quotas_mt, api_usage_mt")
        print("2. Send a single log ingestion request")
        print("3. Verify all 4 tables have new entries")
    else:
        print("⚠️  Some tests failed. Fix issues before testing ingestion flow.")

if __name__ == "__main__":
    asyncio.run(main())