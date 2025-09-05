#!/usr/bin/env python3
"""
M4 Individual Functionality Test
Tests security analytics, Sigma rules, threat intelligence, and MITRE ATT&CK integration
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from base_test import BaseTestSuite

class M4TestSuite(BaseTestSuite):
    """Test M4 Security Analytics/SIEM functionality"""
    
    def __init__(self):
        super().__init__("M4 Security Analytics/SIEM")
    
    # Remove setup_test_tenant - BaseTestSuite handles tenant creation
    
    async def test_security_health(self):
        """Test security analytics health check"""
        print("🔄 Testing security analytics health...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/security/health",
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Security health check failed: {response.text}"
                result = response.json()
                
                # Verify health response structure
                assert "status" in result
                assert "timestamp" in result
                
                # Check that key security metrics are present
                assert "sigma_rules_count" in result
                assert "threat_intel_count" in result
                assert "security_events_count" in result
                
                # Verify expected counts based on CLAUDE.md
                assert result["sigma_rules_count"] >= 4, "Should have at least 4 default Sigma rules"
                assert result["threat_intel_count"] >= 8, "Should have at least 8 threat intelligence indicators"
                
                print("✅ Security analytics health successful")
                self.test_results["security_health"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Security analytics health failed: {str(e)}")
                self.test_results["security_health"] = f"FAIL: {str(e)}"
                return False
    
    async def test_security_dashboard(self):
        """Test security dashboard with MITRE ATT&CK metrics"""
        print("🔄 Testing security dashboard...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/security/dashboard",
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Security dashboard failed: {response.text}"
                result = response.json()
                
                # Verify dashboard structure
                assert "total_events" in result
                assert "events_by_severity" in result
                assert "events_by_technique" in result
                assert "recent_events" in result
                assert "threat_intel_stats" in result
                
                # Check threat intel stats
                threat_stats = result["threat_intel_stats"]
                assert "total_indicators" in threat_stats
                assert "by_type" in threat_stats
                assert "by_severity" in threat_stats
                
                # Should have expected IOC counts
                assert threat_stats["total_indicators"] >= 8
                
                print("✅ Security dashboard successful")
                self.test_results["security_dashboard"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Security dashboard failed: {str(e)}")
                self.test_results["security_dashboard"] = f"FAIL: {str(e)}"
                return False
    
    async def test_sigma_rules(self):
        """Test Sigma rule management"""
        print("🔄 Testing Sigma rules...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # List existing Sigma rules
                response = await client.get(
                    f"{self.base_url}/v1/security/sigma-rules",
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Sigma rules list failed: {response.text}"
                result = response.json()
                
                # Verify rules structure - response is direct array
                assert isinstance(result, list), "Sigma rules response should be a list"
                
                # Should have default rules (at least 4 according to CLAUDE.md)
                assert len(result) >= 4, "Should have at least 4 default Sigma rules"
                
                # Check rule structure
                if result:
                    rule = result[0]
                    assert "id" in rule
                    assert "title" in rule
                    assert "description" in rule
                    assert "attack_techniques" in rule  # Not mitre_techniques
                    assert "severity" in rule
                    assert "status" in rule
                
                # Test creating a custom Sigma rule
                custom_rule = {
                    "title": "M4 Test Custom Rule",
                    "description": "Test rule for M4 validation",
                    "severity": "medium",
                    "logsource": {
                        "product": "windows",
                        "service": "security"
                    },
                    "detection": {
                        "selection": {
                            "EventID": 4625,
                            "LogonType": 3
                        },
                        "condition": "selection"
                    },
                    "fields": ["TargetUserName", "IpAddress"],
                    "falsepositives": ["Legitimate failed network logons"],
                    "tags": ["attack.credential_access", "attack.t1110"],
                    "attack_techniques": ["T1110"],
                    "enabled": True
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/security/sigma-rules",
                    json=custom_rule,
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Custom Sigma rule creation failed: {response.text}"
                rule_result = response.json()
                
                assert "rule_id" in rule_result
                assert "message" in rule_result  # API returns "message", not "status"
                
                # Store rule ID for testing
                self.test_rule_id = rule_result["rule_id"]
                
                print("✅ Sigma rules successful")
                self.test_results["sigma_rules"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Sigma rules failed: {str(e)}")
                if hasattr(e, 'response'):
                    print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                self.test_results["sigma_rules"] = f"FAIL: {str(e)}"
                return False
    
    async def test_sigma_rule_testing(self):
        """Test Sigma rule evaluation"""
        print("🔄 Testing Sigma rule testing...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Skip if no test rule ID
                if not hasattr(self, 'test_rule_id'):
                    print("⚠️ No test rule available for testing")
                    self.test_results["sigma_rule_testing"] = "SKIP: No test rule"
                    return True
                
                # Test rule evaluation
                test_data = {
                    "test_events": [
                        {
                            "EventID": 4625,
                            "LogonType": 3,
                            "TargetUserName": "testuser",
                            "IpAddress": "192.168.1.100",
                            "timestamp": datetime.now().isoformat()
                        }
                    ]
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/security/sigma-rules/{self.test_rule_id}/test",
                    json=test_data,
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Sigma rule testing failed: {response.text}"
                result = response.json()
                
                # Verify test response (actual API structure)
                assert "result" in result
                assert result["result"] in ["triggered", "no_match"]
                assert "event" in result
                
                print("✅ Sigma rule testing successful")
                self.test_results["sigma_rule_testing"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Sigma rule testing failed: {str(e)}")
                self.test_results["sigma_rule_testing"] = f"FAIL: {str(e)}"
                return False
    
    async def test_security_events(self):
        """Test security event management"""
        print("🔄 Testing security events...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # List security events
                response = await client.get(
                    f"{self.base_url}/v1/security/events",
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Security events list failed: {response.text}"
                result = response.json()
                
                # API returns direct array of events, not nested structure
                assert isinstance(result, list), "Security events should be a list"
                
                # Events can be empty - that's valid
                
                # Test event status update if events exist
                if result:
                    event = result[0]
                    event_id = event["event_id"]
                    
                    # Update event status
                    status_update = {
                        "status": "investigating",
                        "notes": "M4 test investigation"
                    }
                    
                    response = await client.put(
                        f"{self.base_url}/v1/security/events/{event_id}/status",
                        json=status_update,
                        headers=self.auth_headers
                    )
                    
                    assert response.status_code == 200, f"Event status update failed: {response.text}"
                    update_result = response.json()
                    assert "status" in update_result
                
                print("✅ Security events successful")
                self.test_results["security_events"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Security events failed: {str(e)}")
                self.test_results["security_events"] = f"FAIL: {str(e)}"
                return False
    
    async def test_threat_hunting(self):
        """Test threat hunting campaigns"""
        print("🔄 Testing threat hunting...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Create a threat hunting campaign
                hunting_campaign = {
                    "name": "M4 Test Hunting Campaign",
                    "description": "Test campaign for M4 validation",
                    "query": {
                        "start_time": (datetime.now() - timedelta(hours=24)).isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "filters": [
                            {
                                "field": "level",
                                "operator": "eq",
                                "value": "ERROR"
                            }
                        ]
                    },
                    "mitre_techniques": ["T1110", "T1059"],
                    "iocs": ["192.168.1.100", "malicious-domain.com"]
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/security/threat-hunting",
                    json=hunting_campaign,
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Threat hunting failed: {response.text}"
                result = response.json()
                
                # Verify hunting results (actual API response structure)
                assert "message" in result
                assert "events_found" in result  
                assert "events" in result
                assert isinstance(result["events_found"], int)
                assert isinstance(result["events"], list)
                
                print("✅ Threat hunting successful")
                self.test_results["threat_hunting"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Threat hunting failed: {str(e)}")
                self.test_results["threat_hunting"] = f"FAIL: {str(e)}"
                return False
    
    async def test_threat_intelligence(self):
        """Test threat intelligence IOCs"""
        print("🔄 Testing threat intelligence...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # List threat intelligence indicators
                response = await client.get(
                    f"{self.base_url}/v1/security/threat-intel",
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Threat intelligence failed: {response.text}"
                result = response.json()
                
                # API returns direct array of IOCs, not nested structure
                assert isinstance(result, list), "Threat intelligence should be a list"
                
                # Should have default IOCs (8 according to CLAUDE.md)
                assert len(result) >= 8, "Should have at least 8 default threat intelligence indicators"
                
                # Check IOC structure if indicators exist
                if result:
                    ioc = result[0]
                    assert "value" in ioc  # The actual IOC value  
                    assert "indicator_type" in ioc  # domain, ip, hash, etc.
                    assert "threat_type" in ioc  # malware, c2, phishing
                    assert "confidence" in ioc  # confidence score
                    assert "source" in ioc
                    assert isinstance(ioc["confidence"], int)
                    assert 0 <= ioc["confidence"] <= 100
                
                print("✅ Threat intelligence successful")
                self.test_results["threat_intelligence"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Threat intelligence failed: {str(e)}")
                self.test_results["threat_intelligence"] = f"FAIL: {str(e)}"
                return False
    
    async def test_mitre_attack_techniques(self):
        """Test MITRE ATT&CK technique mapping"""
        print("🔄 Testing MITRE ATT&CK techniques...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Get MITRE ATT&CK techniques
                response = await client.get(
                    f"{self.base_url}/v1/security/mitre-attack/techniques",
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"MITRE ATT&CK techniques failed: {response.text}"
                result = response.json()
                
                # API returns flat dict with technique IDs as keys, not nested structure
                assert isinstance(result, dict), "MITRE techniques should be a dictionary"
                
                # Should have techniques mapped  
                assert len(result) > 0, "Should have MITRE ATT&CK techniques"
                
                # Check technique structure (technique ID as key)
                if result:
                    technique_id = list(result.keys())[0]  # Get first technique ID
                    technique = result[technique_id]
                    
                    assert technique_id.startswith("T"), "Technique ID should start with T"
                    assert len(technique_id) >= 5, "Technique ID should be T#### format"
                    assert "name" in technique
                    assert "tactic" in technique
                
                print("✅ MITRE ATT&CK techniques successful")
                self.test_results["mitre_attack_techniques"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ MITRE ATT&CK techniques failed: {str(e)}")
                self.test_results["mitre_attack_techniques"] = f"FAIL: {str(e)}"
                return False
    
    async def run_all_tests(self):
        """Run all M4 tests using base class runner"""
        print("📝 Testing: Security analytics, Sigma rules, threat intelligence, MITRE ATT&CK")
        
        # Run tests in order
        tests = [
            self.test_security_health,
            self.test_security_dashboard,
            self.test_sigma_rules,
            self.test_sigma_rule_testing,
            self.test_security_events,
            self.test_threat_hunting,
            self.test_threat_intelligence,
            self.test_mitre_attack_techniques
        ]
        
        return await super().run_all_tests(tests)

if __name__ == "__main__":
    test_suite = M4TestSuite()
    success = asyncio.run(test_suite.run_all_tests())
    exit(0 if success else 1)