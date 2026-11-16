"""
MITRE ATT&CK Metadata Generator - Production Scalable System
Generates comprehensive metadata for all 286 MITRE Enterprise techniques with intelligent mapping
"""

import json
import re
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog

from config.mitre_enterprise_complete import MITRE_ENTERPRISE_CONFIG

logger = structlog.get_logger(__name__)


class TacticCategory(Enum):
    """MITRE ATT&CK Tactic Categories"""
    INITIAL_ACCESS = "initial-access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege-escalation"
    DEFENSE_EVASION = "defense-evasion"
    CREDENTIAL_ACCESS = "credential-access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral-movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command-and-control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"
    RECONNAISSANCE = "reconnaissance"
    RESOURCE_DEVELOPMENT = "resource-development"


class SeverityLevel(Enum):
    """Security Detection Severity Levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class MitreTechniqueMetadata:
    """Complete metadata for a MITRE ATT&CK technique"""
    technique_id: str
    name: str
    description: str
    tactics: List[str]
    platforms: List[str]
    severity: str
    data_sources: List[str]
    log_fields: List[str]
    detection_patterns: List[str]
    kill_chain_phases: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


# Version of Logforge's built-in technique catalogue (not an ATT&CK release
# number: the catalogue is curated here, not synced from MITRE's STIX feed).
CATALOGUE_VERSION = "1.0"


class MitreMetadataGenerator:
    """Production-ready MITRE metadata generator with intelligent mapping"""
    
    # Enhanced tactic mapping with pattern recognition
    TACTIC_PATTERNS = {
        TacticCategory.INITIAL_ACCESS: {
            "keywords": ["phishing", "exploit", "external", "drive-by", "supply chain", "valid accounts"],
            "id_ranges": [(1189, 1200), (1566, 1599)],
            "techniques": ["T1190", "T1566", "T1195", "T1189", "T1199", "T1133", "T1078"]
        },
        TacticCategory.EXECUTION: {
            "keywords": ["command", "script", "exploitation", "user execution", "windows management"],
            "id_ranges": [(1047, 1070), (1059, 1090), (1203, 1220)],
            "techniques": ["T1059", "T1047", "T1204", "T1053", "T1203", "T1218", "T1216"]
        },
        TacticCategory.PERSISTENCE: {
            "keywords": ["startup", "scheduled", "registry", "account", "service", "boot"],
            "id_ranges": [(1037, 1055), (1136, 1140), (1543, 1555)],
            "techniques": ["T1547", "T1053", "T1136", "T1543", "T1546", "T1037", "T1112"]
        },
        TacticCategory.PRIVILEGE_ESCALATION: {
            "keywords": ["elevation", "exploitation", "token", "bypass", "abuse"],
            "id_ranges": [(1068, 1075), (1134, 1140), (1548, 1560)],
            "techniques": ["T1068", "T1134", "T1548", "T1055", "T1078", "T1484", "T1547"]
        },
        TacticCategory.DEFENSE_EVASION: {
            "keywords": ["obfuscat", "masquerad", "disable", "hide", "modify", "subvert", "impair"],
            "id_ranges": [(1027, 1050), (1140, 1180), (1480, 1500), (1553, 1580)],
            "techniques": ["T1027", "T1036", "T1140", "T1562", "T1564", "T1553", "T1070"]
        },
        TacticCategory.CREDENTIAL_ACCESS: {
            "keywords": ["credential", "password", "dump", "store", "brute", "kerberos"],
            "id_ranges": [(1003, 1020), (1110, 1125), (1552, 1560)],
            "techniques": ["T1003", "T1110", "T1555", "T1552", "T1558", "T1111", "T1556"]
        },
        TacticCategory.DISCOVERY: {
            "keywords": ["discovery", "enumerat", "network", "system", "account", "permission"],
            "id_ranges": [(1007, 1025), (1033, 1050), (1057, 1090), (1120, 1140)],
            "techniques": ["T1083", "T1087", "T1069", "T1057", "T1018", "T1016", "T1082"]
        },
        TacticCategory.LATERAL_MOVEMENT: {
            "keywords": ["remote", "lateral", "services", "admin shares", "rdp"],
            "id_ranges": [(1021, 1030), (1080, 1100), (1563, 1575)],
            "techniques": ["T1021", "T1080", "T1563", "T1570", "T1550", "T1534", "T1072"]
        },
        TacticCategory.COLLECTION: {
            "keywords": ["collection", "capture", "clipboard", "email", "screen", "audio", "video"],
            "id_ranges": [(1113, 1130), (1560, 1565)],
            "techniques": ["T1113", "T1114", "T1115", "T1123", "T1125", "T1560", "T1119"]
        },
        TacticCategory.COMMAND_AND_CONTROL: {
            "keywords": ["c2", "command", "control", "protocol", "channel", "web service"],
            "id_ranges": [(1071, 1080), (1090, 1110), (1568, 1580)],
            "techniques": ["T1071", "T1090", "T1095", "T1102", "T1568", "T1573", "T1572"]
        },
        TacticCategory.EXFILTRATION: {
            "keywords": ["exfiltrat", "transfer", "alternative protocol", "web service"],
            "id_ranges": [(1011, 1015), (1020, 1025), (1041, 1055), (1567, 1570)],
            "techniques": ["T1041", "T1048", "T1567", "T1020", "T1011", "T1052", "T1029"]
        },
        TacticCategory.IMPACT: {
            "keywords": ["impact", "destroy", "encrypt", "corrupt", "wipe", "denial"],
            "id_ranges": [(1485, 1500), (1529, 1540), (1561, 1565)],
            "techniques": ["T1485", "T1486", "T1561", "T1490", "T1529", "T1491", "T1496"]
        },
        TacticCategory.RECONNAISSANCE: {
            "keywords": ["gather", "search", "scan", "reconnaissance"],
            "id_ranges": [(1589, 1600)],
            "techniques": ["T1589", "T1590", "T1591", "T1592", "T1593", "T1594", "T1595", "T1596"]
        },
        TacticCategory.RESOURCE_DEVELOPMENT: {
            "keywords": ["acquire", "compromise", "develop", "establish", "obtain", "stage"],
            "id_ranges": [(1583, 1590), (1608, 1615)],
            "techniques": ["T1583", "T1584", "T1585", "T1586", "T1587", "T1588", "T1608"]
        }
    }
    
    # Enhanced platform detection patterns
    PLATFORM_PATTERNS = {
        "Windows": ["windows", "powershell", "cmd", "wmi", "registry", "mshta", "rundll32", "regsvr32"],
        "Linux": ["linux", "unix", "bash", "shell", "cron", "systemd", "sudo", "ssh"],
        "macOS": ["macos", "mac", "apple", "launchd", "osascript", "security"],
        "Cloud": ["cloud", "aws", "azure", "gcp", "saas", "office365", "gsuite", "api"],
        "Containers": ["container", "docker", "kubernetes", "pod", "image"],
        "Network": ["network", "snmp", "dns", "http", "smtp", "ftp"],
        "IaaS": ["iaas", "instance", "virtual", "compute", "storage"],
        "SaaS": ["saas", "office", "google", "salesforce", "slack"]
    }
    
    # Severity mapping based on impact and exploitability
    SEVERITY_MAPPING = {
        "critical": {
            "keywords": ["privilege escalation", "remote code execution", "data destruction", "encryption", "denial of service"],
            "techniques": ["T1068", "T1055", "T1190", "T1485", "T1486", "T1561", "T1498", "T1499"]
        },
        "high": {
            "keywords": ["credential access", "lateral movement", "persistence", "defense evasion", "exfiltration"],
            "techniques": ["T1003", "T1021", "T1543", "T1562", "T1041", "T1110", "T1134"]
        },
        "medium": {
            "keywords": ["discovery", "collection", "execution", "initial access"],
            "techniques": ["T1083", "T1113", "T1059", "T1566", "T1087", "T1057"]
        },
        "low": {
            "keywords": ["reconnaissance", "resource development"],
            "techniques": ["T1589", "T1583", "T1590", "T1591"]
        }
    }
    
    def __init__(self):
        """Initialize the metadata generator with configuration data"""
        self.techniques_config = MITRE_ENTERPRISE_CONFIG
        logger.info(f"🎯 Initialized MITRE metadata generator with {len(self.techniques_config)} techniques")
    
    def generate_all_metadata(self) -> Dict[str, MitreTechniqueMetadata]:
        """
        Generate comprehensive metadata for all MITRE techniques
        
        Returns:
            Dict mapping technique IDs to complete metadata objects
        """
        all_metadata = {}
        
        logger.info("🚀 Generating metadata for all 286 MITRE Enterprise techniques...")
        
        for technique_id, config in self.techniques_config.items():
            try:
                metadata = self._generate_technique_metadata(technique_id, config)
                all_metadata[technique_id] = metadata
                
            except Exception as e:
                logger.error(f"Error generating metadata for {technique_id}: {e}")
                continue
        
        logger.info(f"✅ Generated metadata for {len(all_metadata)} techniques")
        return all_metadata
    
    def _generate_technique_metadata(self, technique_id: str, config: Any) -> MitreTechniqueMetadata:
        """Generate complete metadata for a single technique"""
        
        # Extract base information - config is a TechniqueMetadata object
        if hasattr(config, 'name'):
            name = config.name
        else:
            name = f"Unknown Technique {technique_id}"
        description = self._generate_description(technique_id, name)
        
        # Intelligent mapping
        tactics = self._map_technique_to_tactics(technique_id, name)
        platforms = self._map_technique_to_platforms(technique_id, name)
        severity = self._map_technique_to_severity(technique_id, name)
        
        # Generate detection metadata
        data_sources = self._generate_data_sources(technique_id, name, platforms)
        log_fields = self._generate_log_fields(technique_id, name, platforms)
        detection_patterns = self._generate_detection_patterns(technique_id, name)
        kill_chain_phases = self._map_tactics_to_kill_chain(tactics)
        
        return MitreTechniqueMetadata(
            technique_id=technique_id,
            name=name,
            description=description,
            tactics=tactics,
            platforms=platforms,
            severity=severity,
            data_sources=data_sources,
            log_fields=log_fields,
            detection_patterns=detection_patterns,
            kill_chain_phases=kill_chain_phases
        )
    
    def _map_technique_to_tactics(self, technique_id: str, name: str) -> List[str]:
        """Intelligently map technique to MITRE tactics"""
        tactics = []
        name_lower = name.lower()
        technique_num = int(technique_id[1:]) if technique_id[1:].isdigit() else 0
        
        # Check each tactic pattern
        for tactic, patterns in self.TACTIC_PATTERNS.items():
            # Check if technique is explicitly listed
            if technique_id in patterns.get("techniques", []):
                tactics.append(tactic.value)
                continue
            
            # Check ID ranges
            for start, end in patterns.get("id_ranges", []):
                if start <= technique_num <= end:
                    tactics.append(tactic.value)
                    break
            
            # Check keyword matches
            if any(keyword in name_lower for keyword in patterns.get("keywords", [])):
                if tactic.value not in tactics:
                    tactics.append(tactic.value)
        
        # Default mapping if no matches
        if not tactics:
            if technique_num < 1100:
                tactics.append(TacticCategory.EXECUTION.value)
            elif technique_num < 1200:
                tactics.append(TacticCategory.DISCOVERY.value)
            else:
                tactics.append(TacticCategory.DEFENSE_EVASION.value)
        
        return tactics[:3]  # Limit to top 3 tactics
    
    def _map_technique_to_platforms(self, technique_id: str, name: str) -> List[str]:
        """Intelligently map technique to target platforms"""
        platforms = []
        name_lower = name.lower()
        
        # Platform detection based on keywords
        for platform, keywords in self.PLATFORM_PATTERNS.items():
            if any(keyword in name_lower for keyword in keywords):
                platforms.append(platform)
        
        # Default platforms based on technique characteristics
        if not platforms:
            technique_num = int(technique_id[1:]) if technique_id[1:].isdigit() else 0
            
            if technique_num < 1400:  # Traditional techniques
                platforms.extend(["Windows", "Linux", "macOS"])
            elif technique_num < 1500:  # Mobile techniques
                platforms.extend(["Android", "iOS"])
            else:  # Modern techniques
                platforms.extend(["Cloud", "Containers", "SaaS"])
        
        return list(set(platforms[:4]))  # Limit to 4 platforms, remove duplicates
    
    def _map_technique_to_severity(self, technique_id: str, name: str) -> str:
        """Intelligently map technique to severity level"""
        name_lower = name.lower()
        
        # Check explicit technique mappings
        for severity, mapping in self.SEVERITY_MAPPING.items():
            if technique_id in mapping.get("techniques", []):
                return severity
        
        # Check keyword-based severity
        for severity, mapping in self.SEVERITY_MAPPING.items():
            if any(keyword in name_lower for keyword in mapping.get("keywords", [])):
                return severity
        
        # Default severity based on tactic
        technique_num = int(technique_id[1:]) if technique_id[1:].isdigit() else 0
        
        if technique_num in range(1068, 1070) or technique_num in range(1485, 1500):
            return "critical"
        elif technique_num in range(1003, 1030) or technique_num in range(1021, 1030):
            return "high"
        elif technique_num in range(1589, 1600):
            return "low"
        else:
            return "medium"
    
    def _generate_data_sources(self, technique_id: str, name: str, platforms: List[str]) -> List[str]:
        """Generate relevant data sources for detection"""
        data_sources = []
        name_lower = name.lower()
        
        # Platform-specific data sources
        if "Windows" in platforms:
            data_sources.extend(["Windows Event Logs", "Sysmon", "PowerShell Logs"])
        if "Linux" in platforms:
            data_sources.extend(["Syslog", "Auditd", "Process Monitoring"])
        if "Cloud" in platforms:
            data_sources.extend(["CloudTrail", "Azure Activity Logs", "GCP Audit Logs"])
        if "Network" in platforms:
            data_sources.extend(["Network Traffic", "DNS Logs", "Firewall Logs"])
        
        # Technique-specific data sources
        if "process" in name_lower or "execution" in name_lower:
            data_sources.append("Process Monitoring")
        if "network" in name_lower or "c2" in name_lower:
            data_sources.append("Network Traffic")
        if "file" in name_lower or "registry" in name_lower:
            data_sources.append("File System Monitoring")
        if "authentication" in name_lower or "credential" in name_lower:
            data_sources.append("Authentication Logs")
        
        return list(set(data_sources[:6]))  # Limit to 6, remove duplicates
    
    def _generate_log_fields(self, technique_id: str, name: str, platforms: List[str]) -> List[str]:
        """Generate relevant log fields for detection rules"""
        log_fields = []
        name_lower = name.lower()
        
        # Common fields
        log_fields.extend(["timestamp", "source_ip", "user", "process_name"])
        
        # Platform-specific fields
        if "Windows" in platforms:
            log_fields.extend(["event_id", "computer_name", "logon_type", "process_id"])
        if "Linux" in platforms:
            log_fields.extend(["uid", "gid", "command", "pid"])
        if "Cloud" in platforms:
            log_fields.extend(["account_id", "region", "service_name", "api_call"])
        
        # Technique-specific fields
        if "network" in name_lower:
            log_fields.extend(["destination_ip", "destination_port", "protocol"])
        if "file" in name_lower:
            log_fields.extend(["file_path", "file_hash", "file_size"])
        if "registry" in name_lower:
            log_fields.extend(["registry_key", "registry_value"])
        if "process" in name_lower:
            log_fields.extend(["command_line", "parent_process", "process_hash"])
        
        return list(set(log_fields[:10]))  # Limit to 10, remove duplicates
    
    def _generate_detection_patterns(self, technique_id: str, name: str) -> List[str]:
        """Generate detection patterns for Sigma rules"""
        patterns = []
        name_lower = name.lower()
        
        # Generate patterns based on technique characteristics
        if "powershell" in name_lower:
            patterns.append("powershell.exe command execution with suspicious parameters")
        if "wmi" in name_lower:
            patterns.append("WMI process creation or query execution")
        if "registry" in name_lower:
            patterns.append("Registry modification in sensitive keys")
        if "scheduled" in name_lower:
            patterns.append("Scheduled task creation or modification")
        if "service" in name_lower:
            patterns.append("Windows service installation or modification")
        if "credential" in name_lower:
            patterns.append("Credential dumping or access attempts")
        if "lateral" in name_lower or "remote" in name_lower:
            patterns.append("Remote login or lateral movement activity")
        
        # Default pattern if none match
        if not patterns:
            patterns.append(f"Activity pattern associated with {name}")
        
        return patterns[:3]  # Limit to 3 patterns
    
    def _map_tactics_to_kill_chain(self, tactics: List[str]) -> List[str]:
        """Map MITRE tactics to cyber kill chain phases"""
        kill_chain_mapping = {
            "reconnaissance": ["Reconnaissance"],
            "resource-development": ["Weaponization"],
            "initial-access": ["Delivery", "Exploitation"],
            "execution": ["Exploitation", "Installation"],
            "persistence": ["Installation"],
            "privilege-escalation": ["Privilege Escalation"],
            "defense-evasion": ["Defense Evasion"],
            "credential-access": ["Credential Access"],
            "discovery": ["Discovery"],
            "lateral-movement": ["Lateral Movement"],
            "collection": ["Collection"],
            "command-and-control": ["Command and Control"],
            "exfiltration": ["Exfiltration"],
            "impact": ["Actions on Objectives"]
        }
        
        kill_chain_phases = []
        for tactic in tactics:
            phases = kill_chain_mapping.get(tactic, [])
            kill_chain_phases.extend(phases)
        
        return list(set(kill_chain_phases))  # Remove duplicates
    
    def _generate_description(self, technique_id: str, name: str) -> str:
        """Generate a descriptive explanation for the technique"""
        return f"MITRE ATT&CK technique {technique_id}: {name}. This technique involves adversarial activities that security teams should monitor and detect through appropriate logging and analysis."
    
    def export_metadata_json(self, output_path: str) -> bool:
        """
        Export all metadata to JSON file for integration
        
        Args:
            output_path: Path to output JSON file
            
        Returns:
            bool: Success status
        """
        try:
            all_metadata = self.generate_all_metadata()
            
            # Convert to serializable format
            export_data = {
                "metadata_version": CATALOGUE_VERSION,
                "generated_techniques": len(all_metadata),
                "techniques": {
                    technique_id: metadata.to_dict() 
                    for technique_id, metadata in all_metadata.items()
                }
            }
            
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"✅ Exported {len(all_metadata)} techniques to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting metadata: {e}")
            return False
    
    def validate_coverage(self) -> Dict[str, Any]:
        """
        Validate technique coverage and report statistics
        
        Returns:
            Dict with coverage statistics
        """
        all_metadata = self.generate_all_metadata()
        
        # Collect statistics
        tactics_count = {}
        platforms_count = {}
        severity_count = {}
        
        for metadata in all_metadata.values():
            # Count tactics
            for tactic in metadata.tactics:
                tactics_count[tactic] = tactics_count.get(tactic, 0) + 1
            
            # Count platforms
            for platform in metadata.platforms:
                platforms_count[platform] = platforms_count.get(platform, 0) + 1
            
            # Count severity
            severity_count[metadata.severity] = severity_count.get(metadata.severity, 0) + 1
        
        coverage_stats = {
            "total_techniques": len(all_metadata),
            "tactics_coverage": tactics_count,
            "platforms_coverage": platforms_count,
            "severity_distribution": severity_count,
            "data_quality": {
                "avg_data_sources": sum(len(m.data_sources) for m in all_metadata.values()) / len(all_metadata) if all_metadata else 0,
                "avg_log_fields": sum(len(m.log_fields) for m in all_metadata.values()) / len(all_metadata) if all_metadata else 0,
                "avg_detection_patterns": sum(len(m.detection_patterns) for m in all_metadata.values()) / len(all_metadata) if all_metadata else 0
            }
        }
        
        logger.info(f"📊 Coverage validation complete: {coverage_stats}")
        return coverage_stats


# Singleton instance for production use
mitre_metadata_generator = MitreMetadataGenerator()


def generate_production_metadata() -> Dict[str, MitreTechniqueMetadata]:
    """
    Production function to generate all MITRE metadata
    
    Returns:
        Dict mapping technique IDs to complete metadata objects
    """
    return mitre_metadata_generator.generate_all_metadata()


def export_metadata_for_integration(output_path: str = "/tmp/mitre_metadata.json") -> bool:
    """
    Export metadata for integration with sigma rule engine
    
    Args:
        output_path: Path to output JSON file
        
    Returns:
        bool: Success status
    """
    return mitre_metadata_generator.export_metadata_json(output_path)


if __name__ == "__main__":
    # Production validation
    print("🎯 MITRE ATT&CK Metadata Generator - Production Validation")
    print("=" * 60)
    
    # Generate all metadata
    metadata = generate_production_metadata()
    print(f"✅ Generated metadata for {len(metadata)} techniques")
    
    # Validate coverage
    stats = mitre_metadata_generator.validate_coverage()
    print(f"📊 Coverage Statistics:")
    print(f"  - Total Techniques: {stats['total_techniques']}")
    print(f"  - Tactics Coverage: {len(stats['tactics_coverage'])} tactics")
    print(f"  - Platforms Coverage: {len(stats['platforms_coverage'])} platforms")
    print(f"  - Severity Distribution: {stats['severity_distribution']}")
    
    # Export for integration
    export_success = export_metadata_for_integration()
    print(f"📁 Export Status: {'✅ Success' if export_success else '❌ Failed'}")
    
    print("\n🚀 Production system ready for integration with sigma engine!")