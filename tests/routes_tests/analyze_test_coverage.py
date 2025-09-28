#!/usr/bin/env python3
"""
Comprehensive Router Test Coverage Analysis
Analyzes each router file against its corresponding test file to identify coverage gaps
"""

import ast
import os
import sys
import re
from typing import Dict, List, Set, Tuple, Any
from pathlib import Path

# Import the mapping
try:
    from router_test_mapping import get_test_file_for_router
except ImportError:
    def get_test_file_for_router(router_file: str) -> str:
        return f"test_{Path(router_file).stem}_router.py"

class RouterAnalyzer:
    """Analyzes router files to extract endpoints and their details"""
    
    def __init__(self, router_file: str):
        self.router_file = router_file
        self.router_name = Path(router_file).stem
        self.endpoints = {}
        self.error_handlers = []
        self.dependencies = []
        
    def analyze(self) -> Dict[str, Any]:
        """Analyze router file and extract all endpoint information"""
        try:
            with open(self.router_file, 'r') as f:
                content = f.read()
                
            # Parse AST
            tree = ast.parse(content)
            
            # Extract endpoints using AST
            self._extract_endpoints_from_ast(tree)
            
            # Extract endpoints using regex (backup method)
            self._extract_endpoints_from_regex(content)
            
            return {
                "router_file": self.router_file,
                "router_name": self.router_name,
                "endpoints": self.endpoints,
                "error_handlers": self.error_handlers,
                "dependencies": self.dependencies,
                "total_endpoints": len(self.endpoints)
            }
            
        except Exception as e:
            return {
                "router_file": self.router_file,
                "router_name": self.router_name,
                "error": str(e),
                "endpoints": {},
                "total_endpoints": 0
            }
    
    def _extract_endpoints_from_ast(self, tree: ast.AST):
        """Extract endpoints using AST parsing"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function has router decorator
                for decorator in node.decorator_list:
                    if self._is_router_decorator(decorator):
                        endpoint_info = self._extract_endpoint_info(decorator, node)
                        if endpoint_info:
                            key = f"{endpoint_info['method']} {endpoint_info['path']}"
                            self.endpoints[key] = endpoint_info
    
    def _extract_endpoints_from_regex(self, content: str):
        """Extract endpoints using regex patterns"""
        # Pattern to match FastAPI route decorators
        patterns = [
            r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
            r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for method, path in matches:
                key = f"{method.upper()} {path}"
                if key not in self.endpoints:
                    self.endpoints[key] = {
                        "method": method.upper(),
                        "path": path,
                        "function_name": "unknown",
                        "has_auth": "unknown",
                        "parameters": [],
                        "response_model": None,
                        "source": "regex"
                    }
    
    def _is_router_decorator(self, decorator) -> bool:
        """Check if decorator is a router decorator"""
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                return (decorator.func.attr in ['get', 'post', 'put', 'delete', 'patch'] and
                       isinstance(decorator.func.value, ast.Name) and
                       decorator.func.value.id in ['router', 'app'])
        return False
    
    def _extract_endpoint_info(self, decorator: ast.Call, func_node: ast.FunctionDef) -> Dict[str, Any]:
        """Extract detailed endpoint information"""
        try:
            method = decorator.func.attr.upper()
            
            # Extract path from first argument
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                path = decorator.args[0].value
            else:
                return None
                
            # Extract parameters from function signature
            parameters = []
            for arg in func_node.args.args:
                param_info = {"name": arg.arg, "type": "Any"}
                if arg.annotation:
                    param_info["type"] = self._extract_type_annotation(arg.annotation)
                parameters.append(param_info)
            
            # Check for authentication dependency
            has_auth = any("RequiredTenant" in self._extract_type_annotation(arg.annotation) or
                          "Depends" in self._extract_type_annotation(arg.annotation) 
                          for arg in func_node.args.args if arg.annotation)
            
            # Extract response model from decorator keywords
            response_model = None
            for keyword in decorator.keywords:
                if keyword.arg == "response_model":
                    response_model = self._extract_type_annotation(keyword.value)
            
            return {
                "method": method,
                "path": path,
                "function_name": func_node.name,
                "has_auth": has_auth,
                "parameters": parameters,
                "response_model": response_model,
                "source": "ast"
            }
            
        except Exception:
            return None
    
    def _extract_type_annotation(self, annotation) -> str:
        """Extract type annotation as string"""
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return f"{self._extract_type_annotation(annotation.value)}.{annotation.attr}"
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value)
        else:
            return "Any"

class TestAnalyzer:
    """Analyzes test files to extract tested scenarios"""
    
    def __init__(self, test_file: str):
        self.test_file = test_file
        self.test_name = Path(test_file).stem
        self.test_methods = []
        self.tested_endpoints = set()
        self.edge_cases = []
        
    def analyze(self) -> Dict[str, Any]:
        """Analyze test file and extract test coverage information"""
        try:
            with open(self.test_file, 'r') as f:
                content = f.read()
                
            # Parse AST
            tree = ast.parse(content)
            
            # Extract test methods
            self._extract_test_methods(tree)
            
            # Extract tested endpoints from HTTP calls
            self._extract_tested_endpoints(content)
            
            # Extract edge cases
            self._extract_edge_cases(content)
            
            return {
                "test_file": self.test_file,
                "test_name": self.test_name,
                "test_methods": self.test_methods,
                "tested_endpoints": list(self.tested_endpoints),
                "edge_cases": self.edge_cases,
                "total_test_methods": len(self.test_methods)
            }
            
        except Exception as e:
            return {
                "test_file": self.test_file,
                "test_name": self.test_name,
                "error": str(e),
                "test_methods": [],
                "tested_endpoints": [],
                "edge_cases": [],
                "total_test_methods": 0
            }
    
    def _extract_test_methods(self, tree: ast.AST):
        """Extract test methods from AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                self.test_methods.append({
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "is_async": isinstance(node, ast.AsyncFunctionDef)
                })
    
    def _extract_tested_endpoints(self, content: str):
        """Extract endpoints that are being tested"""
        # Look for HTTP method calls
        patterns = [
            r'make_authenticated_request\(\s*["\']([A-Z]+)["\'],\s*["\']([^"\']+)["\']',
            r'client\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) == 2:
                    if match[0].upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                        method, path = match
                    else:
                        method, path = match[1], match[0]  # Some patterns have reversed order
                    self.tested_endpoints.add(f"{method.upper()} {path}")
    
    def _extract_edge_cases(self, content: str):
        """Extract edge cases and error scenarios from test content"""
        edge_case_patterns = [
            r'test.*invalid',
            r'test.*error',
            r'test.*not.*found',
            r'test.*unauthorized',
            r'test.*forbidden',
            r'status_code.*40[0-9]',
            r'status_code.*50[0-9]'
        ]
        
        for pattern in edge_case_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            self.edge_cases.extend(matches)

class CoverageAnalyzer:
    """Analyzes coverage gaps between routers and tests"""
    
    def __init__(self):
        self.router_dir = "/Users/miteshpant/projects/Logforge/apps/api/routers"
        self.test_dir = "/Users/miteshpant/projects/Logforge/tests/routes_tests"
        
    def analyze_all(self) -> Dict[str, Any]:
        """Analyze all routers and their corresponding tests"""
        results = {}
        
        # Get all router files
        router_files = self._get_router_files()
        
        for router_file in router_files:
            router_name = Path(router_file).stem
            test_filename = get_test_file_for_router(router_file)
            test_file = os.path.join(self.test_dir, test_filename)
            
            # Skip if no corresponding test file
            if not os.path.exists(test_file):
                results[router_name] = {
                    "status": "NO_TEST_FILE",
                    "router_file": router_file,
                    "test_file": test_file,
                    "coverage": 0
                }
                continue
            
            # Analyze router
            router_analyzer = RouterAnalyzer(router_file)
            router_data = router_analyzer.analyze()
            
            # Analyze test
            test_analyzer = TestAnalyzer(test_file)
            test_data = test_analyzer.analyze()
            
            # Calculate coverage
            coverage_result = self._calculate_coverage(router_data, test_data)
            
            results[router_name] = {
                "status": "ANALYZED",
                "router_data": router_data,
                "test_data": test_data,
                "coverage": coverage_result
            }
        
        return results
    
    def _get_router_files(self) -> List[str]:
        """Get all router files excluding __init__.py"""
        router_files = []
        for file in os.listdir(self.router_dir):
            if file.endswith('.py') and file != '__init__.py':
                router_files.append(os.path.join(self.router_dir, file))
        return sorted(router_files)
    
    def _calculate_coverage(self, router_data: Dict, test_data: Dict) -> Dict[str, Any]:
        """Calculate test coverage for a router"""
        router_endpoints = set(router_data["endpoints"].keys())
        tested_endpoints = set(test_data["tested_endpoints"])
        
        covered_endpoints = router_endpoints.intersection(tested_endpoints)
        uncovered_endpoints = router_endpoints - tested_endpoints
        
        coverage_percentage = (len(covered_endpoints) / len(router_endpoints) * 100) if router_endpoints else 0
        
        return {
            "total_endpoints": len(router_endpoints),
            "covered_endpoints": len(covered_endpoints),
            "uncovered_endpoints": len(uncovered_endpoints),
            "coverage_percentage": round(coverage_percentage, 2),
            "covered_list": list(covered_endpoints),
            "uncovered_list": list(uncovered_endpoints),
            "test_methods_count": test_data["total_test_methods"],
            "edge_cases_count": len(test_data["edge_cases"])
        }

def generate_coverage_report(results: Dict[str, Any]) -> str:
    """Generate a comprehensive coverage report"""
    report = []
    report.append("=" * 80)
    report.append("🧪 COMPREHENSIVE ROUTER TEST COVERAGE ANALYSIS")
    report.append("=" * 80)
    
    total_routers = len(results)
    analyzed_routers = sum(1 for r in results.values() if r["status"] == "ANALYZED")
    missing_tests = sum(1 for r in results.values() if r["status"] == "NO_TEST_FILE")
    
    report.append(f"\n📊 OVERVIEW:")
    report.append(f"   • Total Routers: {total_routers}")
    report.append(f"   • Analyzed Routers: {analyzed_routers}")
    report.append(f"   • Missing Test Files: {missing_tests}")
    
    if missing_tests > 0:
        report.append(f"\n❌ ROUTERS WITHOUT TEST FILES:")
        for name, data in results.items():
            if data["status"] == "NO_TEST_FILE":
                report.append(f"   • {name} -> {data['test_file']}")
    
    report.append(f"\n🎯 DETAILED COVERAGE ANALYSIS:")
    report.append("-" * 80)
    
    coverage_scores = []
    
    for name, data in results.items():
        if data["status"] != "ANALYZED":
            continue
            
        coverage = data["coverage"]
        coverage_scores.append(coverage["coverage_percentage"])
        
        status_icon = "✅" if coverage["coverage_percentage"] >= 80 else "⚠️" if coverage["coverage_percentage"] >= 50 else "❌"
        
        report.append(f"\n{status_icon} {name.upper()}")
        report.append(f"   Coverage: {coverage['coverage_percentage']:.1f}% ({coverage['covered_endpoints']}/{coverage['total_endpoints']} endpoints)")
        report.append(f"   Test Methods: {coverage['test_methods_count']}")
        report.append(f"   Edge Cases: {coverage['edge_cases_count']}")
        
        if coverage["uncovered_endpoints"] > 0:
            report.append(f"   ❌ Uncovered Endpoints:")
            for endpoint in coverage["uncovered_list"]:
                report.append(f"      • {endpoint}")
        
        if coverage["covered_endpoints"] > 0:
            report.append(f"   ✅ Covered Endpoints:")
            for endpoint in coverage["covered_list"][:3]:  # Show first 3
                report.append(f"      • {endpoint}")
            if len(coverage["covered_list"]) > 3:
                report.append(f"      • ... and {len(coverage['covered_list']) - 3} more")
    
    if coverage_scores:
        avg_coverage = sum(coverage_scores) / len(coverage_scores)
        report.append(f"\n📈 OVERALL STATISTICS:")
        report.append(f"   • Average Coverage: {avg_coverage:.1f}%")
        report.append(f"   • Best Coverage: {max(coverage_scores):.1f}%")
        report.append(f"   • Worst Coverage: {min(coverage_scores):.1f}%")
    
    report.append("\n" + "=" * 80)
    
    return "\n".join(report)

def main():
    """Main analysis function"""
    print("🚀 Starting Comprehensive Router Test Coverage Analysis...")
    
    analyzer = CoverageAnalyzer()
    results = analyzer.analyze_all()
    
    report = generate_coverage_report(results)
    print(report)
    
    # Save report to file
    report_file = "/Users/miteshpant/projects/Logforge/tests/routes_tests/coverage_analysis_report.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Full report saved to: {report_file}")
    
    return results

if __name__ == "__main__":
    results = main()