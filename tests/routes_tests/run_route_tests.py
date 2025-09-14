#!/usr/bin/env python3
"""
Route Tests Runner
Runs comprehensive tests for fixed routes and validates database integration
"""

import asyncio
import sys
import os

# Add project paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'api')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from test_health_router import run_health_router_tests
from test_ingestion_router import run_ingestion_router_tests
from test_query_router import run_query_router_tests
from test_dashboard_router import run_dashboard_router_tests
from test_storage_router import run_storage_router_tests
from test_alerts_router import run_alerts_router_tests

async def run_all_route_tests():
    """Run comprehensive tests for all fixed routes"""
    print("🚀 Starting Comprehensive Route Tests Suite...")
    print("="*60)
    
    test_results = {}
    
    # Test 1: Health Router
    print("\n1️⃣ Testing Health Router (Route 1)...")
    try:
        health_result = await run_health_router_tests()
        test_results["health_router"] = "PASS" if health_result else "FAIL"
    except Exception as e:
        print(f"❌ Health router tests failed: {e}")
        test_results["health_router"] = f"FAIL: {e}"
    
    print("\n" + "="*60)
    
    # Test 2: Ingestion Router  
    print("\n2️⃣ Testing Ingestion Router (Route 2)...")
    try:
        ingestion_result = await run_ingestion_router_tests()
        test_results["ingestion_router"] = "PASS" if ingestion_result else "FAIL"
    except Exception as e:
        print(f"❌ Ingestion router tests failed: {e}")
        test_results["ingestion_router"] = f"FAIL: {e}"
    
    print("\n" + "="*60)
    
    # Test 3: Query Router
    print("\n3️⃣ Testing Query Router (Route 3)...")
    try:
        query_result = await run_query_router_tests()
        test_results["query_router"] = "PASS" if query_result else "FAIL"
    except Exception as e:
        print(f"❌ Query router tests failed: {e}")
        test_results["query_router"] = f"FAIL: {e}"
    
    print("\n" + "="*60)
    
    # Test 4: Dashboard Router
    print("\n4️⃣ Testing Dashboard Router (Route 4)...")
    try:
        dashboard_result = await run_dashboard_router_tests()
        test_results["dashboard_router"] = "PASS" if dashboard_result else "FAIL"
    except Exception as e:
        print(f"❌ Dashboard router tests failed: {e}")
        test_results["dashboard_router"] = f"FAIL: {e}"
    
    print("\n" + "="*60)
    
    # Test 5: Storage Router
    print("\n5️⃣ Testing Storage Router (Route 5)...")
    try:
        storage_result = await run_storage_router_tests()
        test_results["storage_router"] = "PASS" if storage_result else "FAIL"
    except Exception as e:
        print(f"❌ Storage router tests failed: {e}")
        test_results["storage_router"] = f"FAIL: {e}"
    
    print("\n" + "="*60)
    
    # Test 6: Alerts Router
    print("\n6️⃣ Testing Alerts Router (Route 6)...")
    try:
        alerts_result = await run_alerts_router_tests()
        test_results["alerts_router"] = "PASS" if alerts_result else "FAIL"
    except Exception as e:
        print(f"❌ Alerts router tests failed: {e}")
        test_results["alerts_router"] = f"FAIL: {e}"
    
    # Print final summary
    print("\n" + "="*60)
    print("📊 COMPREHENSIVE ROUTE TESTS SUMMARY")
    print("="*60)
    
    passed_routes = 0
    total_routes = len(test_results)
    
    for route_name, result in test_results.items():
        status_icon = "✅" if result == "PASS" else "❌"
        route_display = route_name.replace("_", " ").title()
        print(f"{status_icon} {route_display}: {result}")
        
        if result == "PASS":
            passed_routes += 1
    
    print("="*60)
    print(f"🎯 FINAL RESULTS: {passed_routes}/{total_routes} routes passed comprehensive testing")
    
    if passed_routes == total_routes:
        print("✅ ALL ROUTE TESTS PASSED - Routes are production ready!")
        return True
    else:
        print("❌ SOME ROUTE TESTS FAILED - Review and fix before proceeding")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_route_tests())
    sys.exit(0 if success else 1)