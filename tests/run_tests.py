#!/usr/bin/env python3
"""
Test runner script for Logforge API comprehensive test suite
"""

import os
import sys
import subprocess
import time
import argparse
from pathlib import Path


def run_command(command, description="", capture_output=True):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description or command}")
    print(f"{'='*60}")
    
    try:
        if capture_output:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            if result.stdout:
                print("STDOUT:")
                print(result.stdout)
            
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
            
            return result.returncode == 0
        else:
            result = subprocess.run(command, shell=True)
            return result.returncode == 0
    
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run Logforge API test suite")
    parser.add_argument("--suite", choices=["unit", "integration", "performance", "all"], 
                       default="all", help="Test suite to run")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--parallel", "-p", action="store_true", help="Run tests in parallel")
    parser.add_argument("--benchmark", action="store_true", help="Include benchmark tests")
    parser.add_argument("--filter", "-k", help="Filter tests by keyword")
    
    args = parser.parse_args()
    
    # Change to the API directory
    api_dir = Path(__file__).parent
    os.chdir(api_dir)
    
    print("Logforge API Test Suite Runner")
    print(f"Working directory: {api_dir}")
    print(f"Test suite: {args.suite}")
    
    # Install test dependencies if needed
    print("\nInstalling test dependencies...")
    if not run_command("pip install -r requirements.txt", "Installing requirements"):
        print("Failed to install requirements")
        return False
    
    # Base pytest command
    pytest_cmd = ["python", "-m", "pytest"]
    
    # Add verbose flag
    if args.verbose:
        pytest_cmd.extend(["-v", "-s"])
    
    # Add parallel execution
    if args.parallel:
        pytest_cmd.extend(["-n", "auto"])
    
    # Add coverage
    if args.coverage:
        pytest_cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
    
    # Add filter
    if args.filter:
        pytest_cmd.extend(["-k", args.filter])
    
    # Determine which tests to run
    test_files = []
    
    if args.suite == "unit" or args.suite == "all":
        test_files.extend([
            "tests/test_parsers.py",
            "tests/test_models.py",
            "tests/test_storage_config.py",
        ])
    
    if args.suite == "integration" or args.suite == "all":
        test_files.extend([
            "tests/test_api.py",
            "tests/test_integration.py",
        ])
    
    if args.suite == "performance" or args.suite == "all":
        test_files.append("tests/test_performance.py")
    
    # Add benchmark marker if requested
    if args.benchmark:
        pytest_cmd.extend(["-m", "not benchmark"])  # Skip by default, or include with marker
    
    # Run the tests
    success = True
    start_time = time.time()
    
    for test_file in test_files:
        if os.path.exists(test_file):
            cmd = " ".join(pytest_cmd + [test_file])
            file_success = run_command(cmd, f"Running {test_file}", capture_output=False)
            success = success and file_success
            
            if not file_success:
                print(f"FAILED: {test_file}")
        else:
            print(f"WARNING: Test file not found: {test_file}")
    
    elapsed = time.time() - start_time
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUITE SUMMARY")
    print(f"{'='*60}")
    print(f"Overall Result: {'PASSED' if success else 'FAILED'}")
    print(f"Total Time: {elapsed:.1f} seconds")
    print(f"Test Suite: {args.suite}")
    print(f"Files Tested: {len(test_files)}")
    
    if args.coverage and success:
        print("\nCoverage report generated in htmlcov/index.html")
    
    # Performance benchmarks summary
    if args.suite in ["performance", "all"]:
        print(f"\n{'='*60}")
        print("PERFORMANCE TARGETS")
        print(f"{'='*60}")
        print("Parser Performance:")
        print("  - JSON Parser: >10,000 logs/sec")
        print("  - Nginx Parser: >10,000 logs/sec") 
        print("  - Syslog Parser: >10,000 logs/sec")
        print("  - CEF Parser: >10,000 logs/sec")
        print("  - Text Parser: >10,000 logs/sec")
        print("\nAPI Performance:")
        print("  - Ingestion P99 Latency: <50ms")
        print("  - Query P99 Latency: <200ms")
        print("  - Concurrent Throughput: >2,000 req/sec")
        print("  - Memory per LogEntry: <2KB")
        print("\nStorage Performance:")
        print("  - Client Creation: >500 clients/sec")
        print("  - Policy Generation: >5,000 policies/sec")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)