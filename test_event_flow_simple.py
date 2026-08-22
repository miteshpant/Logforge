#!/usr/bin/env python3
"""
Simplified test to verify event-driven ingestion components
Tests components without requiring database connection
"""

import sys
import os

# Add the API directory to Python path
sys.path.insert(0, '/Users/miteshpant/projects/Logforge/apps/api')

print("🚀 Testing Event-Driven Ingestion Components")
print("=" * 50)

def test_event_types():
    """Test that all event types can be created"""
    print("🔄 Testing event type creation...")
    
    try:
        from events.types.ingestion_events import (
            create_ingestion_batch_event, 
            create_usage_tracking_event,
            create_quota_update_event,
            create_ingestion_error_event
        )
        from events.types.api_events import create_api_usage_event
        
        customer_id = "test-customer-123"
        
        # Test all 5 event types
        events = []
        
        # 1. Ingestion batch processed → ingestion_stats_mt
        ingestion_event = create_ingestion_batch_event(
            customer_id=customer_id,
            endpoint="/v1/logs/ingest/json",
            format_type="json",
            records_ingested=1,
            bytes_ingested=512,
            processing_time_ms=45.2
        )
        events.append(("Ingestion Batch", ingestion_event))
        
        # 2. Usage tracking → usage_records_mt  
        usage_event = create_usage_tracking_event(
            customer_id=customer_id,
            tenant_id=customer_id,
            feature_name="ingestion",
            usage_type="monthly_ingestion",  # Fixed: was "bytes_ingested"
            quantity=1
        )
        events.append(("Usage Tracking", usage_event))
        
        # 3. Quota update → tenant_quotas_mt
        quota_event = create_quota_update_event(
            customer_id=customer_id,
            tenant_id=customer_id,
            quota_type="monthly_ingestion",
            usage_delta=1,
            action_type="increment"
        )
        events.append(("Quota Update", quota_event))
        
        # 4. API usage → api_usage_mt
        api_event = create_api_usage_event(
            customer_id=customer_id,
            tenant_id=customer_id,
            endpoint="/v1/logs/ingest/json",
            method="POST",
            response_status=200,
            request_size_bytes=512,
            response_size_bytes=64,
            processing_time_ms=45.2
        )
        events.append(("API Usage", api_event))
        
        # 5. Ingestion error → ingestion_errors_mt
        error_event = create_ingestion_error_event(
            customer_id=customer_id,
            endpoint="/v1/logs/ingest/json",
            error_type="validation_error",
            error_message="Invalid JSON format"
        )
        events.append(("Ingestion Error", error_event))
        
        print(f"✅ Created {len(events)} event types successfully:")
        for name, event in events:
            print(f"   - {name}: {event.event_type}")
            print(f"     Customer: {event.customer_id}")
            print(f"     Data keys: {list(event.data.keys())}")
            
        return True
        
    except Exception as e:
        print(f"❌ Event type creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_consumer_class():
    """Test consumer class creation without database connection"""
    print("\n🔄 Testing consumer class structure...")
    
    try:
        # Import the consumer class definition
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ingestion_consumer", 
            "/Users/miteshpant/projects/Logforge/apps/api/events/subscriber_implementations/ingestion_consumer.py"
        )
        consumer_module = importlib.util.module_from_spec(spec)
        
        # Read the file content to check structure
        with open("/Users/miteshpant/projects/Logforge/apps/api/events/subscriber_implementations/ingestion_consumer.py", 'r') as f:
            content = f.read()
        
        # Check for required components
        required_methods = [
            "class IngestionEventConsumer",
            "def get_subscribed_events",
            "def handle_event", 
            "def handle_batch",
            "def start",
            "def stop",
            "_process_ingestion_stats_batch",
            "_process_usage_tracking_batch", 
            "_process_quota_update_batch",
            "_process_api_usage_batch"
        ]
        
        missing_methods = []
        for method in required_methods:
            if method not in content:
                missing_methods.append(method)
        
        if missing_methods:
            print(f"⚠️  Missing methods: {missing_methods}")
        else:
            print("✅ All required methods found in consumer class")
        
        # Check subscribed events
        if "subscribed_events = [" in content:
            print("✅ Subscribed events list found")
            
            required_events = [
                "ingestion.batch_processed",
                "usage.ingestion_tracking", 
                "quota.usage_updated",
                "ingestion.error",
                "usage.api_call"
            ]
            
            for event_type in required_events:
                if f'"{event_type}"' in content:
                    print(f"   ✅ {event_type}")
                else:
                    print(f"   ❌ Missing: {event_type}")
        
        return len(missing_methods) == 0
        
    except Exception as e:
        print(f"❌ Consumer class test failed: {e}")
        return False

def test_database_permissions():
    """Test database layer permissions configuration"""
    print("\n🔄 Testing database permissions...")
    
    try:
        from database_layer import DatabaseLayer
        
        # Check authorized services
        if "IngestionEventConsumer" in DatabaseLayer.AUTHORIZED_SERVICES:
            print("✅ IngestionEventConsumer in AUTHORIZED_SERVICES")
        else:
            print("❌ IngestionEventConsumer not in AUTHORIZED_SERVICES")
            return False
        
        # Check table access control
        if "IngestionEventConsumer" in DatabaseLayer.TABLE_ACCESS_CONTROL:
            tables = DatabaseLayer.TABLE_ACCESS_CONTROL["IngestionEventConsumer"]
            print(f"✅ Has access to {len(tables)} tables:")
            
            required_tables = [
                'ingestion_stats_mt', 
                'usage_records_mt', 
                'tenant_quotas_mt',
                'ingestion_errors_mt',
                'api_usage_mt'
            ]
            
            for table in required_tables:
                if table in tables:
                    print(f"   ✅ {table}")
                else:
                    print(f"   ❌ Missing: {table}")
                    return False
                    
        else:
            print("❌ IngestionEventConsumer not in TABLE_ACCESS_CONTROL")
            return False
        
        # Check update permissions
        if "IngestionEventConsumer" in DatabaseLayer.UPDATE_ALLOWED_SERVICES:
            print("✅ Has UPDATE permissions")
        else:
            print("❌ Missing UPDATE permissions")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Database permissions test failed: {e}")
        return False

def test_feature_flags():
    """Test feature flags without database connection"""
    print("\n🔄 Testing feature flags configuration...")
    
    try:
        from events.config import EventsConfigManager
        
        # Create config manager but don't load config (to avoid DB connection)
        config_manager = EventsConfigManager()
        
        # Check config file path exists
        config_path = config_manager.config_path
        if os.path.exists(config_path):
            print(f"✅ Config file exists: {config_path}")
        else:
            print(f"⚠️  Config file not found: {config_path}")
            print("   Using default configuration")
        
        # Test default config creation (without database)
        default_config = config_manager._get_default_config()
        flags = default_config.feature_flags
        
        print("✅ Feature flags loaded:")
        print(f"   enable_event_driven_ingestion: {flags.enable_event_driven_ingestion}")
        print(f"   enable_legacy_fallback: {flags.enable_legacy_fallback}")
        
        if flags.enable_event_driven_ingestion:
            print("✅ Event-driven ingestion is ENABLED")
        else:
            print("❌ Event-driven ingestion is DISABLED")
            
        return True
        
    except Exception as e:
        print(f"❌ Feature flags test failed: {e}")
        return False

def test_publisher_availability():
    """Test publisher manager setup"""
    print("\n🔄 Testing publisher availability...")
    
    try:
        from events.publishers import publisher_manager
        
        print("✅ Publisher manager imported successfully")
        
        # Check if publishers are registered
        if hasattr(publisher_manager, 'publishers'):
            if publisher_manager.publishers:
                print(f"✅ {len(publisher_manager.publishers)} publishers registered:")
                for name, pub in publisher_manager.publishers.items():
                    print(f"   - {name}: {type(pub).__name__}")
            else:
                print("⚠️  No publishers currently registered (expected without Kafka)")
                print("   Events will use fallback processing")
        
        return True
        
    except Exception as e:
        print(f"❌ Publisher test failed: {e}")
        return False

def test_integration_points():
    """Test that all integration points are properly configured"""
    print("\n🔄 Testing integration points...")
    
    try:
        # Test that dependencies.py has the event publishing function
        with open("/Users/miteshpant/projects/Logforge/apps/api/dependencies.py", 'r') as f:
            dependencies_content = f.read()
        
        integration_points = [
            "_publish_ingestion_events",
            "create_ingestion_batch_event",
            "create_usage_tracking_event", 
            "create_quota_update_event",
            "create_api_usage_event",
            "publisher_manager.publish_event"
        ]
        
        missing_points = []
        for point in integration_points:
            if point not in dependencies_content:
                missing_points.append(point)
        
        if missing_points:
            print(f"❌ Missing integration points: {missing_points}")
            return False
        else:
            print("✅ All integration points found in dependencies.py")
            
        # Check for feature flag usage
        if "enable_event_driven_ingestion" in dependencies_content:
            print("✅ Feature flag integration found")
        else:
            print("❌ Feature flag integration missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Integration points test failed: {e}")
        return False

def main():
    """Run all tests"""
    tests = [
        ("Event Type Creation", test_event_types),
        ("Consumer Class Structure", test_consumer_class),
        ("Database Permissions", test_database_permissions),
        ("Feature Flags", test_feature_flags),
        ("Publisher Availability", test_publisher_availability),
        ("Integration Points", test_integration_points)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'=' * 20} {test_name} {'=' * 20}")
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 60)
    print("📊 COMPONENT TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} component tests passed")
    
    if passed == total:
        print("\n🎉 All component tests passed! Event-driven flow components are ready.")
        print("\n📝 Ready for Docker testing:")
        print("1. Start Docker: docker compose -f infra/docker/compose.yml up -d")
        print("2. Clear tables: Connect to ClickHouse and truncate all target tables")
        print("3. Send log request: curl -X POST with JSON log data")
        print("4. Verify tables: Check all 5 tables for new entries")
        print("\n📋 Expected table updates:")
        print("   • logs_raw_mt - immediate log storage")
        print("   • ingestion_stats_mt - via ingestion.batch_processed events") 
        print("   • usage_records_mt - via usage.ingestion_tracking events")
        print("   • tenant_quotas_mt - via quota.usage_updated events")
        print("   • api_usage_mt - via usage.api_call events")
        print("   • ingestion_errors_mt - via ingestion.error events (if errors occur)")
        
    else:
        print(f"\n⚠️  {total - passed} component tests failed. Fix issues before Docker testing.")
        print("\n🔧 Common fixes:")
        if not results.get("Event Type Creation", True):
            print("   - Check import paths for event type modules")
        if not results.get("Database Permissions", True):
            print("   - Add missing tables to IngestionEventConsumer permissions") 
        if not results.get("Integration Points", True):
            print("   - Update dependencies.py with event publishing calls")

if __name__ == "__main__":
    main()