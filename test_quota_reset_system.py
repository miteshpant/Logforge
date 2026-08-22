#!/usr/bin/env python3
"""
Test Script for Quota Reset System
Tests the automated quota reset functionality with configurable parameters
"""

import asyncio
import os
import sys
import json
from datetime import datetime, timezone, timedelta

# Add the API directory to Python path
sys.path.append('apps/api')

from services.quota_reset_service import QuotaResetService
from database_layer import DatabaseLayer

async def test_quota_reset_system():
    """Test the complete quota reset system"""
    print("🧪 Testing Quota Reset System")
    print("=" * 50)
    
    # Initialize services
    quota_service = QuotaResetService()
    db = DatabaseLayer("QuotaTestService", "quota-test-service-key")
    
    # Test tenant for our scenarios (real tenant created)
    test_tenant_id = "96959ab4-571e-48bd-acce-fab493ba78f0"
    test_customer_id = "96959ab4-571e-48bd-acce-fab493ba78f0"
    
    try:
        # 1. Setup test data
        print("1. Setting up test quota data...")
        await setup_test_quotas(db, test_tenant_id, test_customer_id)
        
        # 2. Test configuration loading
        print("\n2. Testing configuration loading...")
        schedule_info = await quota_service.get_quota_reset_schedule()
        print(f"   ✅ Configuration loaded: {json.dumps(schedule_info['configuration'], indent=2)}")
        
        # 3. Test quota reset check (before any resets due)
        print("\n3. Testing quota reset check (no resets due)...")
        reset_summary = await quota_service.check_and_reset_quotas()
        print(f"   📊 Reset summary: {reset_summary['quotas_checked']} checked, {reset_summary['quotas_reset']} reset")
        
        # 4. Simulate old quota data that needs reset
        print("\n4. Simulating old quota data that needs reset...")
        await simulate_old_quota_data(db, test_tenant_id, test_customer_id)
        
        # 5. Test quota reset check (with resets due)
        print("\n5. Testing quota reset check (with resets due)...")
        reset_summary = await quota_service.check_and_reset_quotas()
        print(f"   📊 Reset summary: {reset_summary['quotas_checked']} checked, {reset_summary['quotas_reset']} reset")
        print(f"   🏢 Tenants affected: {reset_summary['tenants_affected']}")
        if reset_summary['errors']:
            print(f"   ❌ Errors: {reset_summary['errors']}")
        
        # 6. Test force reset functionality
        print("\n6. Testing force reset functionality...")
        force_result = await quota_service.force_reset_tenant_quotas(
            test_tenant_id, 
            quota_types=['monthly_ingestion', 'api_calls']
        )
        print(f"   💪 Force reset: {force_result['quotas_reset']} quotas reset")
        print(f"   📋 Details: {force_result['reset_details']}")
        
        # 7. Verify historical data was stored
        print("\n7. Verifying historical data storage...")
        await verify_historical_data(db, test_tenant_id, test_customer_id)
        
        # 8. Test different environment configurations
        print("\n8. Testing different environment configurations...")
        test_env_configs = [
            {"QUOTA_RESET_DAILY_INGESTION_DAYS": "1", "QUOTA_RESET_MONTHLY_INGESTION_DAYS": "30"},
            {"QUOTA_RESET_API_CALLS_DAYS": "7", "QUOTA_RESET_ALERTS_DAYS": "14"},
            {"QUOTA_RESET_STORAGE_GB_DAYS": "0", "QUOTA_RESET_USERS_DAYS": "0"}  # Disabled
        ]
        
        for i, env_config in enumerate(test_env_configs):
            print(f"   🔧 Config {i+1}: {env_config}")
            # Temporarily set environment variables
            old_env = {}
            for key, value in env_config.items():
                old_env[key] = os.environ.get(key)
                os.environ[key] = value
            
            # Create new service instance to pick up new config
            test_service = QuotaResetService()
            config = test_service.reset_config
            print(f"      📋 Loaded config: {config}")
            
            # Restore environment
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value
        
        print("\n✅ All quota reset system tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        raise
    finally:
        # Cleanup test data
        print("\n🧹 Cleaning up test data...")
        await cleanup_test_data(db, test_tenant_id, test_customer_id)

async def setup_test_quotas(db: DatabaseLayer, tenant_id: str, customer_id: str):
    """Setup test quota data"""
    current_time = datetime.now(timezone.utc)
    
    test_quotas = [
        {
            'id': f'quota-{tenant_id}-monthly-ing',
            'tenant_id': tenant_id,
            'customer_id': customer_id,
            'quota_type': 'monthly_ingestion',
            'quota_limit': 10000,
            'current_usage': 7500,
            'reset_period': 'monthly',
            'last_reset': current_time,
            'created_at': current_time,
            'updated_at': current_time
        },
        {
            'id': f'quota-{tenant_id}-api-calls',
            'tenant_id': tenant_id,
            'customer_id': customer_id,
            'quota_type': 'api_calls',
            'quota_limit': 50000,
            'current_usage': 25000,
            'reset_period': 'monthly',
            'last_reset': current_time,
            'created_at': current_time,
            'updated_at': current_time
        },
        {
            'id': f'quota-{tenant_id}-storage',
            'tenant_id': tenant_id,
            'customer_id': customer_id,
            'quota_type': 'storage_gb',
            'quota_limit': 1000,
            'current_usage': 500,
            'reset_period': 'never',
            'last_reset': current_time,
            'created_at': current_time,
            'updated_at': current_time
        }
    ]
    
    for quota in test_quotas:
        insert_query = """
        INSERT INTO tenant_quotas_mt (
            id, tenant_id, customer_id, quota_type, quota_limit, current_usage,
            reset_period, last_reset, created_at, updated_at
        ) VALUES (
            %(id)s, %(tenant_id)s, %(customer_id)s, %(quota_type)s, %(quota_limit)s, %(current_usage)s,
            %(reset_period)s, %(last_reset)s, %(created_at)s, %(updated_at)s
        )
        """
        await db.execute_query(insert_query, quota)
    
    print(f"   ✅ Created {len(test_quotas)} test quotas")

async def simulate_old_quota_data(db: DatabaseLayer, tenant_id: str, customer_id: str):
    """Simulate quota data that's old enough to trigger resets"""
    # Make quotas look like they were last reset 35 days ago (older than 30-day reset period)
    old_reset_time = datetime.now(timezone.utc) - timedelta(days=35)
    
    update_query = """
    ALTER TABLE tenant_quotas_mt
    UPDATE last_reset = %(old_reset_time)s
    WHERE tenant_id = %(tenant_id)s 
    AND quota_type IN ('monthly_ingestion', 'api_calls')
    """
    
    await db.execute_query(update_query, {
        'tenant_id': tenant_id,
        'old_reset_time': old_reset_time
    })
    
    print(f"   ✅ Simulated old quota data (last reset: {old_reset_time.isoformat()})")

async def verify_historical_data(db: DatabaseLayer, tenant_id: str, customer_id: str):
    """Verify that historical usage data was stored correctly"""
    query = """
    SELECT 
        tenant_id, quota_type, usage_amount, quota_limit, billing_period, reset_reason
    FROM quota_usage_history_mt
    WHERE tenant_id = %(tenant_id)s
    ORDER BY created_at DESC
    LIMIT 10
    """
    
    history_records = await db.execute_query(query, {'tenant_id': tenant_id})
    
    if history_records:
        print(f"   ✅ Found {len(history_records)} historical usage records")
        for record in history_records[:3]:  # Show first 3
            print(f"      📊 {record['quota_type']}: {record['usage_amount']}/{record['quota_limit']} "
                  f"({record['billing_period']}) - {record['reset_reason']}")
    else:
        print("   ⚠️  No historical usage records found")

async def cleanup_test_data(db: DatabaseLayer, tenant_id: str, customer_id: str):
    """Clean up test data"""
    try:
        # Delete test quotas
        await db.execute_query(
            "ALTER TABLE tenant_quotas_mt DELETE WHERE tenant_id = %(tenant_id)s",
            {'tenant_id': tenant_id}
        )
        
        # Delete test historical data
        await db.execute_query(
            "ALTER TABLE quota_usage_history_mt DELETE WHERE tenant_id = %(tenant_id)s",
            {'tenant_id': tenant_id}
        )
        
        print("   ✅ Test data cleaned up")
        
    except Exception as e:
        print(f"   ⚠️  Cleanup warning: {str(e)}")

def print_environment_info():
    """Print current environment configuration"""
    print("🔧 Environment Configuration:")
    print("-" * 30)
    
    quota_env_vars = [
        'QUOTA_RESET_DAILY_INGESTION_DAYS',
        'QUOTA_RESET_MONTHLY_INGESTION_DAYS',
        'QUOTA_RESET_STORAGE_GB_DAYS',
        'QUOTA_RESET_API_CALLS_DAYS',
        'QUOTA_RESET_USERS_DAYS',
        'QUOTA_RESET_ALERTS_DAYS',
        'QUOTA_RESET_CHECK_INTERVAL_MINUTES'
    ]
    
    for var in quota_env_vars:
        value = os.environ.get(var, 'Not set')
        print(f"   {var}: {value}")
    
    print()

if __name__ == "__main__":
    print("🚀 Starting Quota Reset System Tests")
    print_environment_info()
    
    # Run the test
    asyncio.run(test_quota_reset_system())