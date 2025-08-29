#!/usr/bin/env python3
"""
Debug script to test the timeseries endpoint and see what it returns
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List

import httpx
from query_engine import QueryAggregation, AggregationType


async def test_timeseries_endpoint():
    """Test the timeseries endpoint to see what it actually returns"""
    
    base_url = "http://localhost:7080"
    customer_id = "test-customer-debug"
    
    # First, let's ingest some test data
    print("🔄 Ingesting test data...")
    
    # Generate test logs
    test_logs = []
    for i in range(10):
        test_logs.append({
            "ts": (datetime.now() - timedelta(hours=i)).isoformat(),
            "service": "test-service",
            "level": "INFO",
            "msg": f"Test message {i}",
            "host": "test-host",
            "trace_id": f"trace-{i}",
            "user_id": "test-user"
        })
    
    # Ingest the test data
    async with httpx.AsyncClient(timeout=30.0) as client:
        bulk_data = {"logs": test_logs}
        headers = {"X-Customer-ID": customer_id}
        
        response = await client.post(
            f"{base_url}/v1/ingest/logs/bulk",
            json=bulk_data,
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to ingest test data: {response.status_code} - {response.text}")
            return
        
        print(f"✅ Ingested {len(test_logs)} test logs")
        
        # Wait a bit for data to be processed
        await asyncio.sleep(2)
        
        # Now test the timeseries endpoint
        print("\n🔄 Testing timeseries endpoint...")
        
        query_request = {
            "start_time": (datetime.now() - timedelta(hours=24)).isoformat(),
            "end_time": datetime.now().isoformat(),
            "aggregations": [
                {
                    "field": "*",
                    "type": "count"
                }
            ],
            "granularity": "hour",
            "filters": [
                {
                    "field": "customer_id",
                    "operator": "eq",
                    "value": customer_id
                }
            ]
        }
        
        print(f"Query request: {json.dumps(query_request, indent=2)}")
        
        response = await client.post(
            f"{base_url}/v1/query/timeseries",
            json=query_request,
            headers=headers
        )
        
        print(f"\nResponse status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Timeseries response:")
            print(json.dumps(result, indent=2, default=str))
            
            # Check what fields are present
            print(f"\nResponse keys: {list(result.keys())}")
            
            if "buckets" in result:
                print(f"✅ Found 'buckets' field with {len(result['buckets'])} entries")
            else:
                print("❌ 'buckets' field missing!")
                
            if "aggregations" in result:
                print(f"Found 'aggregations' field: {result['aggregations']}")
                
        else:
            print(f"❌ Timeseries query failed: {response.status_code}")
            print(f"Error response: {response.text}")


if __name__ == "__main__":
    asyncio.run(test_timeseries_endpoint())