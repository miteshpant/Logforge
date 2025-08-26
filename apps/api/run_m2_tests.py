"""
M2 Test Runner for Logforge Advanced Query Engine & Dashboard Framework
Comprehensive test execution and validation script
"""

import subprocess
import sys
import time
import os
from pathlib import Path
import json


class M2TestRunner:
    """Test runner for M2 implementations"""
    
    def __init__(self):
        self.api_dir = Path(__file__).parent
        self.test_results = {}
        self.start_time = time.time()
    
    def print_header(self, title: str):
        """Print formatted header"""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)
    
    def print_step(self, step: str):
        """Print test step"""
        print(f"\n🔄 {step}")
        print("-" * 60)
    
    def run_command(self, command: list, description: str) -> bool:
        """Run command and capture result"""
        print(f"Running: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                cwd=self.api_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                print(f"✅ {description}: PASSED")
                if result.stdout:
                    print("Output:", result.stdout[:500])
                self.test_results[description] = "PASSED"
                return True
            else:
                print(f"❌ {description}: FAILED")
                if result.stderr:
                    print("Error:", result.stderr[:500])
                if result.stdout:
                    print("Output:", result.stdout[:500])
                self.test_results[description] = "FAILED"
                return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {description}: TIMEOUT")
            self.test_results[description] = "TIMEOUT"
            return False
        except Exception as e:
            print(f"💥 {description}: ERROR - {e}")
            self.test_results[description] = "ERROR"
            return False
    
    def check_dependencies(self) -> bool:
        """Check if required dependencies are available"""
        self.print_step("Checking Dependencies")
        
        dependencies = [
            (["python", "--version"], "Python interpreter"),
            (["pip", "--version"], "Pip package manager")
        ]
        
        all_good = True
        for cmd, desc in dependencies:
            if not self.run_command(cmd, desc):
                all_good = False
        
        # Check if pytest is available
        try:
            import pytest
            print("✅ pytest is available")
        except ImportError:
            print("❌ pytest not available, installing...")
            if not self.run_command(["pip", "install", "pytest", "pytest-asyncio"], "Install pytest"):
                all_good = False
        
        # Check for other required modules
        required_modules = [
            "fastapi", "pydantic", "datetime", "asyncio", 
            "requests", "json", "pathlib"
        ]
        
        missing_modules = []
        for module in required_modules:
            try:
                __import__(module)
                print(f"✅ {module} is available")
            except ImportError:
                print(f"❌ {module} not available")
                missing_modules.append(module)
        
        if missing_modules:
            print(f"⚠️  Missing modules: {missing_modules}")
            print("   These may need to be installed for full functionality")
        
        return all_good
    
    def run_unit_tests(self) -> bool:
        """Run unit tests for M2 components"""
        self.print_step("Running M2 Unit Tests")
        
        test_files = [
            ("tests/test_m2_comprehensive.py", "M2 Comprehensive Unit Tests"),
            ("tests/test_m2_api_endpoints.py", "M2 API Endpoint Tests")
        ]
        
        all_passed = True
        for test_file, description in test_files:
            test_path = self.api_dir / test_file
            if test_path.exists():
                cmd = ["python", "-m", "pytest", str(test_path), "-v", "--tb=short", "--asyncio-mode=auto"]
                if not self.run_command(cmd, description):
                    all_passed = False
            else:
                print(f"⚠️  Test file not found: {test_file}")
                all_passed = False
        
        return all_passed
    
    def run_syntax_checks(self) -> bool:
        """Run syntax and import checks"""
        self.print_step("Running Syntax and Import Checks")
        
        files_to_check = [
            ("query_engine.py", "Query Engine Syntax"),
            ("dashboard_engine.py", "Dashboard Engine Syntax"),
            ("main.py", "Main API Syntax"),
            ("test_m2_comprehensive.py", "Unit Test Syntax"),
            ("test_api_endpoints_m2.py", "API Test Syntax"),
            ("dashboard_demo.py", "Demo Script Syntax")
        ]
        
        all_passed = True
        for file_name, description in files_to_check:
            file_path = self.api_dir / file_name
            if file_path.exists():
                cmd = ["python", "-m", "py_compile", str(file_path)]
                if not self.run_command(cmd, description):
                    all_passed = False
            else:
                print(f"⚠️  File not found: {file_name}")
                self.test_results[description] = "NOT_FOUND"
        
        return all_passed
    
    def run_import_tests(self) -> bool:
        """Test that all modules can be imported"""
        self.print_step("Testing Module Imports")
        
        modules_to_test = [
            "query_engine",
            "dashboard_engine", 
            "dashboard_demo"
        ]
        
        all_passed = True
        for module in modules_to_test:
            cmd = ["python", "-c", f"import {module}; print(f'✅ {module} imported successfully')"]
            if not self.run_command(cmd, f"Import {module}"):
                all_passed = False
        
        return all_passed
    
    def run_api_validation(self) -> bool:
        """Validate API endpoints are properly defined"""
        self.print_step("API Endpoint Validation")
        
        # Test that main.py can be loaded without errors
        cmd = ["python", "-c", 
               "from main import app; "
               "routes = [r.path for r in app.routes if hasattr(r, 'path')]; "
               "print(f'✅ API loaded with {len(routes)} routes')"]
        
        return self.run_command(cmd, "API Application Loading")
    
    def run_demo_validation(self) -> bool:
        """Validate demo scripts"""
        self.print_step("Demo Script Validation")
        
        # Test demo script help
        cmd = ["python", "dashboard_demo.py", "--help"]
        return self.run_command(cmd, "Dashboard Demo Help")
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        self.print_header("M2 TEST REPORT")
        
        total_time = time.time() - self.start_time
        
        passed = sum(1 for result in self.test_results.values() if result == "PASSED")
        failed = sum(1 for result in self.test_results.values() if result == "FAILED") 
        errors = sum(1 for result in self.test_results.values() if result == "ERROR")
        timeouts = sum(1 for result in self.test_results.values() if result == "TIMEOUT")
        not_found = sum(1 for result in self.test_results.values() if result == "NOT_FOUND")
        total = len(self.test_results)
        
        print(f"Execution Time: {total_time:.2f} seconds")
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"💥 Errors: {errors}")
        print(f"⏰ Timeouts: {timeouts}")
        print(f"⚠️  Not Found: {not_found}")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")
        
        if failed > 0 or errors > 0:
            print("\n❌ FAILED TESTS:")
            for test, result in self.test_results.items():
                if result in ["FAILED", "ERROR"]:
                    print(f"   • {test}: {result}")
        
        print("\n📊 DETAILED RESULTS:")
        for test, result in self.test_results.items():
            status_emoji = {
                "PASSED": "✅",
                "FAILED": "❌", 
                "ERROR": "💥",
                "TIMEOUT": "⏰",
                "NOT_FOUND": "⚠️"
            }.get(result, "❓")
            print(f"   {status_emoji} {test}: {result}")
        
        # Overall assessment
        print("\n🎯 OVERALL ASSESSMENT:")
        if success_rate >= 90:
            print("🟢 EXCELLENT: M2 implementation is ready for production")
        elif success_rate >= 75:
            print("🟡 GOOD: M2 implementation is mostly ready, minor fixes needed")
        elif success_rate >= 50:
            print("🟠 FAIR: M2 implementation needs significant improvements")
        else:
            print("🔴 POOR: M2 implementation has major issues requiring attention")
        
        return success_rate >= 75  # Consider success if 75%+ pass rate
    
    def save_test_results(self):
        """Save test results to file"""
        results_file = self.api_dir / "m2_test_results.json"
        
        test_summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "execution_time_seconds": time.time() - self.start_time,
            "results": self.test_results,
            "summary": {
                "total": len(self.test_results),
                "passed": sum(1 for r in self.test_results.values() if r == "PASSED"),
                "failed": sum(1 for r in self.test_results.values() if r == "FAILED"),
                "errors": sum(1 for r in self.test_results.values() if r == "ERROR")
            }
        }
        
        try:
            with open(results_file, 'w') as f:
                json.dump(test_summary, f, indent=2)
            print(f"\n💾 Test results saved to: {results_file}")
        except Exception as e:
            print(f"⚠️  Could not save test results: {e}")
    
    def run_full_test_suite(self) -> bool:
        """Run complete M2 test suite"""
        self.print_header("LOGFORGE M2 COMPREHENSIVE TEST SUITE")
        print(f"Testing Advanced Query Engine & Dashboard Framework")
        print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        test_steps = [
            (self.check_dependencies, "Dependency Check"),
            (self.run_syntax_checks, "Syntax Validation"),
            (self.run_import_tests, "Import Testing"),
            (self.run_api_validation, "API Validation"),
            (self.run_demo_validation, "Demo Validation"),
            (self.run_unit_tests, "Unit Testing")
        ]
        
        overall_success = True
        
        for test_func, test_name in test_steps:
            self.print_step(f"Phase: {test_name}")
            try:
                success = test_func()
                if not success:
                    overall_success = False
                    print(f"❌ {test_name} had failures")
                else:
                    print(f"✅ {test_name} completed successfully")
            except Exception as e:
                print(f"💥 {test_name} crashed: {e}")
                overall_success = False
                self.test_results[f"{test_name} (crashed)"] = "ERROR"
        
        # Generate final report
        final_success = self.generate_test_report()
        self.save_test_results()
        
        return overall_success and final_success


def main():
    """Main test runner"""
    runner = M2TestRunner()
    
    print("🚀 Starting Logforge M2 Test Suite...")
    
    success = runner.run_full_test_suite()
    
    if success:
        print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print("   M2 Advanced Query Engine & Dashboard Framework is ready!")
        print("\n📖 Next Steps:")
        print("   1. Start the API: docker compose up -d")
        print("   2. Run dashboard demo: python dashboard_demo.py")
        print("   3. Access API docs: http://localhost:8080/docs")
        print("   4. View dashboards: http://localhost:8080/v1/dashboards")
        return 0
    else:
        print("\n❌ TESTS FAILED!")
        print("   Please review the test results and fix any issues.")
        print("   Check the detailed report above for specific problems.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)