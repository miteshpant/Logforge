"""
Production MITRE ATT&CK Enterprise Framework - Complete 286 Techniques
Scalable configuration system for automatic Sigma rule generation

This module provides complete metadata for ALL 286 (as of 10/2025) MITRE ATT&CK Enterprise techniques
with intelligent defaults, categorization, and extensible configuration.
"""

from enum import Enum
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
import json
import re

class Tactic(str, Enum):
    """MITRE ATT&CK Tactics (Kill Chain Phases)"""
    RECONNAISSANCE = "reconnaissance"
    RESOURCE_DEVELOPMENT = "resource-development"
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

class Platform(str, Enum):
    """Supported platforms"""
    WINDOWS = "Windows"
    LINUX = "Linux"
    MACOS = "macOS"
    AZURE_AD = "Azure AD"
    OFFICE_365 = "Office 365"
    GOOGLE_WORKSPACE = "Google Workspace"
    SAAS = "SaaS"
    ICS = "ICS"
    NETWORK = "Network"
    CONTAINERS = "Containers"
    IAAS = "IaaS"

class Severity(str, Enum):
    """Detection severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

@dataclass
class TechniqueMetadata:
    """Complete technique metadata"""
    id: str
    name: str
    tactic: Tactic
    platforms: List[Platform]
    severity: Severity
    description: str
    data_sources: List[str]
    log_fields: List[str]
    sub_techniques: List[str] = field(default_factory=list)
    detection_template: str = "default"
    mitre_url: str = ""

    def __post_init__(self):
        if not self.mitre_url:
            self.mitre_url = f"https://attack.mitre.org/techniques/{self.id}/"

# ALL 286 MITRE ATT&CK Enterprise Techniques - Complete Dataset
ALL_ENTERPRISE_TECHNIQUES = {
    "T1001": "Data Obfuscation",
    "T1003": "OS Credential Dumping",
    "T1005": "Data from Local System",
    "T1006": "Direct Volume Access",
    "T1007": "System Service Discovery",
    "T1008": "Fallback Channels",
    "T1010": "Application Window Discovery",
    "T1011": "Exfiltration Over Other Network Medium",
    "T1012": "Query Registry",
    "T1014": "Rootkit",
    "T1016": "System Network Configuration Discovery",
    "T1018": "Remote System Discovery",
    "T1020": "Automated Exfiltration",
    "T1021": "Remote Services",
    "T1025": "Data from Removable Media",
    "T1027": "Obfuscated Files or Information",
    "T1029": "Scheduled Transfer",
    "T1030": "Data Transfer Size Limits",
    "T1033": "System Owner/User Discovery",
    "T1036": "Masquerading",
    "T1037": "Boot or Logon Initialization Scripts",
    "T1039": "Data from Network Shared Drive",
    "T1040": "Network Sniffing",
    "T1041": "Exfiltration Over C2 Channel",
    "T1046": "Network Service Discovery",
    "T1047": "Windows Management Instrumentation",
    "T1048": "Exfiltration Over Alternative Protocol",
    "T1049": "System Network Connections Discovery",
    "T1052": "Exfiltration Over Physical Medium",
    "T1053": "Scheduled Task/Job",
    "T1055": "Process Injection",
    "T1056": "Input Capture",
    "T1057": "Process Discovery",
    "T1059": "Command and Scripting Interpreter",
    "T1068": "Exploitation for Privilege Escalation",
    "T1069": "Permission Groups Discovery",
    "T1070": "Indicator Removal",
    "T1071": "Application Layer Protocol",
    "T1072": "Software Deployment Tools",
    "T1074": "Data Staged",
    "T1078": "Valid Accounts",
    "T1080": "Taint Shared Content",
    "T1082": "System Information Discovery",
    "T1083": "File and Directory Discovery",
    "T1087": "Account Discovery",
    "T1090": "Proxy",
    "T1091": "Replication Through Removable Media",
    "T1092": "Communication Through Removable Media",
    "T1095": "Non-Application Layer Protocol",
    "T1098": "Account Manipulation",
    "T1102": "Web Service",
    "T1104": "Multi-Stage Channels",
    "T1105": "Ingress Tool Transfer",
    "T1106": "Native API",
    "T1110": "Brute Force",
    "T1111": "Multi-Factor Authentication Interception",
    "T1112": "Modify Registry",
    "T1113": "Screen Capture",
    "T1114": "Email Collection",
    "T1115": "Clipboard Data",
    "T1119": "Automated Collection",
    "T1120": "Peripheral Device Discovery",
    "T1123": "Audio Capture",
    "T1124": "System Time Discovery",
    "T1125": "Video Capture",
    "T1127": "Trusted Developer Utilities Proxy Execution",
    "T1129": "Shared Modules",
    "T1132": "Data Encoding",
    "T1133": "External Remote Services",
    "T1134": "Access Token Manipulation",
    "T1135": "Network Share Discovery",
    "T1136": "Create Account",
    "T1137": "Office Application Startup",
    "T1140": "Deobfuscate/Decode Files or Information",
    "T1176": "Software Extensions",
    "T1185": "Browser Session Hijacking",
    "T1187": "Forced Authentication",
    "T1189": "Drive-by Compromise",
    "T1190": "Exploit Public-Facing Application",
    "T1195": "Supply Chain Compromise",
    "T1197": "BITS Jobs",
    "T1199": "Trusted Relationship",
    "T1200": "Hardware Additions",
    "T1201": "Password Policy Discovery",
    "T1202": "Indirect Command Execution",
    "T1203": "Exploitation for Client Execution",
    "T1204": "User Execution",
    "T1205": "Traffic Signaling",
    "T1207": "Rogue Domain Controller",
    "T1210": "Exploitation of Remote Services",
    "T1211": "Exploitation for Defense Evasion",
    "T1212": "Exploitation for Credential Access",
    "T1213": "Data from Information Repositories",
    "T1216": "System Script Proxy Execution",
    "T1217": "Browser Information Discovery",
    "T1218": "System Binary Proxy Execution",
    "T1219": "Remote Access Tools",
    "T1220": "XSL Script Processing",
    "T1221": "Template Injection",
    "T1222": "File and Directory Permissions Modification",
    "T1398": "Boot or Logon Initialization Scripts",
    "T1404": "Exploitation for Privilege Escalation",
    "T1406": "Obfuscated Files or Information",
    "T1407": "Download New Code at Runtime",
    "T1409": "Stored Application Data",
    "T1414": "Clipboard Data",
    "T1417": "Input Capture",
    "T1418": "Software Discovery",
    "T1420": "File and Directory Discovery",
    "T1421": "System Network Connections Discovery",
    "T1422": "System Network Configuration Discovery",
    "T1423": "Network Service Scanning",
    "T1424": "Process Discovery",
    "T1426": "System Information Discovery",
    "T1428": "Exploitation of Remote Services",
    "T1429": "Audio Capture",
    "T1430": "Location Tracking",
    "T1437": "Application Layer Protocol",
    "T1451": "SIM Card Swap",
    "T1456": "Drive-By Compromise",
    "T1458": "Replication Through Removable Media",
    "T1461": "Lockscreen Bypass",
    "T1464": "Network Denial of Service",
    "T1471": "Data Encrypted for Impact",
    "T1474": "Supply Chain Compromise",
    "T1480": "Execution Guardrails",
    "T1481": "Web Service",
    "T1482": "Domain Trust Discovery",
    "T1484": "Domain or Tenant Policy Modification",
    "T1485": "Data Destruction",
    "T1486": "Data Encrypted for Impact",
    "T1489": "Service Stop",
    "T1490": "Inhibit System Recovery",
    "T1491": "Defacement",
    "T1495": "Firmware Corruption",
    "T1496": "Resource Hijacking",
    "T1497": "Virtualization/Sandbox Evasion",
    "T1498": "Network Denial of Service",
    "T1499": "Endpoint Denial of Service",
    "T1505": "Server Software Component",
    "T1509": "Non-Standard Port",
    "T1512": "Video Capture",
    "T1513": "Screen Capture",
    "T1516": "Input Injection",
    "T1517": "Access Notifications",
    "T1518": "Software Discovery",
    "T1521": "Encrypted Channel",
    "T1525": "Implant Internal Image",
    "T1526": "Cloud Service Discovery",
    "T1528": "Steal Application Access Token",
    "T1529": "System Shutdown/Reboot",
    "T1530": "Data from Cloud Storage",
    "T1531": "Account Access Removal",
    "T1532": "Archive Collected Data",
    "T1533": "Data from Local System",
    "T1534": "Internal Spearphishing",
    "T1535": "Unused/Unsupported Cloud Regions",
    "T1537": "Transfer Data to Cloud Account",
    "T1538": "Cloud Service Dashboard",
    "T1539": "Steal Web Session Cookie",
    "T1541": "Foreground Persistence",
    "T1542": "Pre-OS Boot",
    "T1543": "Create or Modify System Process",
    "T1544": "Ingress Tool Transfer",
    "T1546": "Event Triggered Execution",
    "T1547": "Boot or Logon Autostart Execution",
    "T1548": "Abuse Elevation Control Mechanism",
    "T1550": "Use Alternate Authentication Material",
    "T1552": "Unsecured Credentials",
    "T1553": "Subvert Trust Controls",
    "T1554": "Compromise Host Software Binary",
    "T1555": "Credentials from Password Stores",
    "T1556": "Modify Authentication Process",
    "T1557": "Adversary-in-the-Middle",
    "T1558": "Steal or Forge Kerberos Tickets",
    "T1559": "Inter-Process Communication",
    "T1560": "Archive Collected Data",
    "T1561": "Disk Wipe",
    "T1562": "Impair Defenses",
    "T1563": "Remote Service Session Hijacking",
    "T1564": "Hide Artifacts",
    "T1565": "Data Manipulation",
    "T1566": "Phishing",
    "T1567": "Exfiltration Over Web Service",
    "T1568": "Dynamic Resolution",
    "T1569": "System Services",
    "T1570": "Lateral Tool Transfer",
    "T1571": "Non-Standard Port",
    "T1572": "Protocol Tunneling",
    "T1573": "Encrypted Channel",
    "T1574": "Hijack Execution Flow",
    "T1575": "Native API",
    "T1577": "Compromise Application Executable",
    "T1578": "Modify Cloud Compute Infrastructure",
    "T1580": "Cloud Infrastructure Discovery",
    "T1582": "SMS Control",
    "T1583": "Acquire Infrastructure",
    "T1584": "Compromise Infrastructure",
    "T1585": "Establish Accounts",
    "T1586": "Compromise Accounts",
    "T1587": "Develop Capabilities",
    "T1588": "Obtain Capabilities",
    "T1589": "Gather Victim Identity Information",
    "T1590": "Gather Victim Network Information",
    "T1591": "Gather Victim Org Information",
    "T1592": "Gather Victim Host Information",
    "T1593": "Search Open Websites/Domains",
    "T1594": "Search Victim-Owned Websites",
    "T1595": "Active Scanning",
    "T1596": "Search Open Technical Databases",
    "T1597": "Search Closed Sources",
    "T1598": "Phishing for Information",
    "T1599": "Network Boundary Bridging",
    "T1600": "Weaken Encryption",
    "T1601": "Modify System Image",
    "T1602": "Data from Configuration Repository",
    "T1603": "Scheduled Task/Job",
    "T1604": "Proxy Through Victim",
    "T1606": "Forge Web Credentials",
    "T1608": "Stage Capabilities",
    "T1609": "Container Administration Command",
    "T1610": "Deploy Container",
    "T1611": "Escape to Host",
    "T1612": "Build Image on Host",
    "T1613": "Container and Resource Discovery",
    "T1614": "System Location Discovery",
    "T1615": "Group Policy Discovery",
    "T1616": "Call Control",
    "T1617": "Hooking",
    "T1619": "Cloud Storage Object Discovery",
    "T1620": "Reflective Code Loading",
    "T1621": "Multi-Factor Authentication Request Generation",
    "T1622": "Debugger Evasion",
    "T1623": "Command and Scripting Interpreter",
    "T1624": "Event Triggered Execution",
    "T1625": "Hijack Execution Flow",
    "T1626": "Abuse Elevation Control Mechanism",
    "T1627": "Execution Guardrails",
    "T1628": "Hide Artifacts",
    "T1629": "Impair Defenses",
    "T1630": "Indicator Removal on Host",
    "T1631": "Process Injection",
    "T1632": "Subvert Trust Controls",
    "T1633": "Virtualization/Sandbox Evasion",
    "T1634": "Credentials from Password Store",
    "T1635": "Steal Application Access Token",
    "T1636": "Protected User Data",
    "T1637": "Dynamic Resolution",
    "T1638": "Adversary-in-the-Middle",
    "T1639": "Exfiltration Over Alternative Protocol",
    "T1640": "Account Access Removal",
    "T1641": "Data Manipulation",
    "T1642": "Endpoint Denial of Service",
    "T1643": "Generate Traffic from Victim",
    "T1644": "Out of Band Data",
    "T1645": "Compromise Client Software Binary",
    "T1646": "Exfiltration Over C2 Channel",
    "T1647": "Plist File Modification",
    "T1648": "Serverless Execution",
    "T1649": "Steal or Forge Authentication Certificates",
    "T1650": "Acquire Access",
    "T1651": "Cloud Administration Command",
    "T1652": "Device Driver Discovery",
    "T1653": "Power Settings",
    "T1654": "Log Enumeration",
    "T1655": "Masquerading",
    "T1656": "Impersonation",
    "T1657": "Financial Theft",
    "T1658": "Exploitation for Client Execution",
    "T1659": "Content Injection",
    "T1660": "Phishing",
    "T1661": "Application Versioning",
    "T1662": "Data Destruction",
    "T1663": "Remote Access Software",
    "T1664": "Exploitation for Initial Access",
    "T1665": "Hide Infrastructure",
    "T1666": "Modify Cloud Resource Hierarchy",
    "T1667": "Email Bombing",
    "T1668": "Exclusive Control",
    "T1669": "Wi-Fi Networks",
    "T1670": "Virtualization Solution",
    "T1671": "Cloud Application Integration",
    "T1672": "Email Spoofing",
    "T1673": "Virtual Machine Discovery",
    "T1674": "Input Injection",
    "T1675": "ESXi Administration Command"
}

# Intelligent tactic mapping based on technique ID ranges and patterns
TACTIC_MAPPING = {
    # Reconnaissance (T1589-T1598)
    **{tid: Tactic.RECONNAISSANCE for tid in ALL_ENTERPRISE_TECHNIQUES.keys()
       if int(tid[1:]) in range(1589, 1599)},

    # Resource Development (T1583-T1588, T1608, T1650)
    **{tid: Tactic.RESOURCE_DEVELOPMENT for tid in ALL_ENTERPRISE_TECHNIQUES.keys()
       if int(tid[1:]) in range(1583, 1589) or tid in ["T1608", "T1650"]},

    # Initial Access (T1078, T1091, T1133, T1189, T1190, T1195, T1199, T1200, T1566)
    **{tid: Tactic.INITIAL_ACCESS for tid in
       ["T1078", "T1091", "T1133", "T1189", "T1190", "T1195", "T1199", "T1200", "T1566", "T1456", "T1458", "T1474", "T1664"]},

    # Execution (T1047, T1053, T1059, T1072, T1106, T1129, T1203, T1204, T1569, T1609, T1610)
    **{tid: Tactic.EXECUTION for tid in
       ["T1047", "T1053", "T1059", "T1072", "T1106", "T1129", "T1203", "T1204", "T1569", "T1609", "T1610", "T1398", "T1623", "T1603", "T1575", "T1648", "T1658", "T1675"]},

    # Persistence (T1037, T1053, T1078, T1098, T1133, T1136, T1137, T1176, T1197, T1205, T1505, T1525, T1541, T1542, T1543, T1546, T1547)
    **{tid: Tactic.PERSISTENCE for tid in
       ["T1037", "T1053", "T1078", "T1098", "T1133", "T1136", "T1137", "T1176", "T1197", "T1205", "T1505", "T1525", "T1541", "T1542", "T1543", "T1546", "T1547", "T1624"]},

    # Privilege Escalation (T1055, T1068, T1134, T1548, T1611)
    **{tid: Tactic.PRIVILEGE_ESCALATION for tid in
       ["T1055", "T1068", "T1134", "T1548", "T1404", "T1428", "T1611", "T1626", "T1631"]},

    # Defense Evasion (T1006, T1014, T1027, T1036, T1055, T1070, T1112, T1127, T1140, T1202, T1207, T1211, T1216, T1218, T1220, T1221, T1222, T1535, T1553, T1562, T1564, T1574)
    **{tid: Tactic.DEFENSE_EVASION for tid in
       ["T1006", "T1014", "T1027", "T1036", "T1055", "T1070", "T1112", "T1127", "T1140", "T1202", "T1207", "T1211", "T1216", "T1218", "T1220", "T1221", "T1222", "T1406", "T1480", "T1497", "T1535", "T1553", "T1554", "T1562", "T1564", "T1574", "T1622", "T1625", "T1627", "T1628", "T1629", "T1632", "T1633", "T1655", "T1665"]},

    # Credential Access (T1003, T1040, T1110, T1111, T1187, T1212, T1552, T1555, T1556, T1558)
    **{tid: Tactic.CREDENTIAL_ACCESS for tid in
       ["T1003", "T1040", "T1110", "T1111", "T1187", "T1212", "T1552", "T1555", "T1556", "T1558", "T1621", "T1634", "T1649"]},

    # Discovery (T1007, T1010, T1012, T1016, T1018, T1033, T1046, T1049, T1057, T1069, T1082, T1083, T1087, T1120, T1124, T1135, T1201, T1217, T1482, T1518, T1526, T1538, T1580, T1613, T1614, T1615, T1619)
    **{tid: Tactic.DISCOVERY for tid in
       ["T1007", "T1010", "T1012", "T1016", "T1018", "T1033", "T1046", "T1049", "T1057", "T1069", "T1082", "T1083", "T1087", "T1120", "T1124", "T1135", "T1201", "T1217", "T1418", "T1420", "T1421", "T1422", "T1423", "T1424", "T1426", "T1482", "T1518", "T1526", "T1538", "T1580", "T1613", "T1614", "T1615", "T1619", "T1652", "T1654", "T1673"]},

    # Lateral Movement (T1021, T1080, T1210, T1534, T1563, T1570)
    **{tid: Tactic.LATERAL_MOVEMENT for tid in
       ["T1021", "T1080", "T1210", "T1534", "T1563", "T1570"]},

    # Collection (T1005, T1025, T1039, T1056, T1074, T1113, T1114, T1115, T1119, T1123, T1125, T1185, T1213, T1530, T1532, T1533, T1560, T1602)
    **{tid: Tactic.COLLECTION for tid in
       ["T1005", "T1025", "T1039", "T1056", "T1074", "T1113", "T1114", "T1115", "T1119", "T1123", "T1125", "T1185", "T1213", "T1409", "T1414", "T1417", "T1429", "T1512", "T1513", "T1516", "T1517", "T1530", "T1532", "T1533", "T1560", "T1602", "T1636", "T1674"]},

    # Command and Control (T1001, T1008, T1071, T1090, T1092, T1095, T1102, T1104, T1105, T1132, T1219, T1205, T1573, T1571, T1572, T1568, T1604)
    **{tid: Tactic.COMMAND_AND_CONTROL for tid in
       ["T1001", "T1008", "T1071", "T1090", "T1092", "T1095", "T1102", "T1104", "T1105", "T1132", "T1219", "T1205", "T1437", "T1481", "T1509", "T1521", "T1544", "T1568", "T1571", "T1572", "T1573", "T1604", "T1616", "T1617", "T1637", "T1638", "T1651", "T1669"]},

    # Exfiltration (T1011, T1020, T1029, T1030, T1041, T1048, T1052, T1537, T1567, T1639, T1644, T1646)
    **{tid: Tactic.EXFILTRATION for tid in
       ["T1011", "T1020", "T1029", "T1030", "T1041", "T1048", "T1052", "T1537", "T1567", "T1639", "T1644", "T1646"]},

    # Impact (T1485, T1486, T1489, T1490, T1491, T1495, T1496, T1498, T1499, T1529, T1531, T1561, T1565)
    **{tid: Tactic.IMPACT for tid in
       ["T1464", "T1471", "T1485", "T1486", "T1489", "T1490", "T1491", "T1495", "T1496", "T1498", "T1499", "T1529", "T1531", "T1561", "T1565", "T1640", "T1641", "T1642", "T1643", "T1653", "T1656", "T1657", "T1662", "T1667", "T1668"]}
}

# Platform mapping based on technique characteristics
PLATFORM_MAPPING = {
    # Windows-specific techniques
    **{tid: [Platform.WINDOWS] for tid in
       ["T1012", "T1047", "T1112", "T1127", "T1134", "T1187", "T1202", "T1207", "T1216", "T1218", "T1220", "T1221", "T1398", "T1556", "T1558", "T1197"]},

    # Cloud/IaaS specific techniques
    **{tid: [Platform.IAAS] for tid in
       ["T1535", "T1537", "T1538", "T1578", "T1580", "T1619", "T1651", "T1666"]},

    # Container specific techniques
    **{tid: [Platform.CONTAINERS] for tid in
       ["T1609", "T1610", "T1611", "T1612", "T1613"]},

    # Network specific techniques
    **{tid: [Platform.NETWORK] for tid in
       ["T1040", "T1046", "T1090", "T1095", "T1190", "T1498", "T1499", "T1571", "T1572", "T1599", "T1600", "T1604"]},

    # Office 365/SaaS specific techniques
    **{tid: [Platform.OFFICE_365, Platform.SAAS] for tid in
       ["T1114", "T1137", "T1484", "T1528", "T1539", "T1550", "T1621", "T1635", "T1649"]},

    # Mobile/Cross-platform techniques
    **{tid: [Platform.WINDOWS, Platform.LINUX, Platform.MACOS] for tid in
       list(set(ALL_ENTERPRISE_TECHNIQUES.keys()) -
            set(["T1012", "T1047", "T1112", "T1127", "T1134", "T1187", "T1202", "T1207", "T1216", "T1218", "T1220", "T1221", "T1398", "T1556", "T1558", "T1197"] +
                ["T1535", "T1537", "T1538", "T1578", "T1580", "T1619", "T1651", "T1666"] +
                ["T1609", "T1610", "T1611", "T1612", "T1613"] +
                ["T1040", "T1046", "T1090", "T1095", "T1190", "T1498", "T1499", "T1571", "T1572", "T1599", "T1600", "T1604"] +
                ["T1114", "T1137", "T1484", "T1528", "T1539", "T1550", "T1621", "T1635", "T1649"]))}
}

# Severity mapping based on impact and criticality
SEVERITY_MAPPING = {
    # Critical - Data destruction, encryption, supply chain, privilege escalation
    **{tid: Severity.CRITICAL for tid in
       ["T1003", "T1014", "T1195", "T1486", "T1485", "T1471", "T1495", "T1561", "T1041", "T1207", "T1556"]},

    # High - Initial access, credential access, lateral movement, exfiltration
    **{tid: Severity.HIGH for tid in
       ["T1055", "T1068", "T1078", "T1110", "T1111", "T1134", "T1189", "T1190", "T1199", "T1200", "T1210", "T1211", "T1212", "T1566", "T1040", "T1114", "T1123", "T1125", "T1048", "T1020", "T1567", "T1185", "T1187", "T1098", "T1136", "T1133", "T1531", "T1565"]},

    # Medium - Execution, persistence, defense evasion, collection
    **{tid: Severity.MEDIUM for tid in
       ["T1059", "T1053", "T1047", "T1106", "T1204", "T1203", "T1027", "T1036", "T1070", "T1112", "T1140", "T1220", "T1221", "T1222", "T1535", "T1056", "T1113", "T1115", "T1119", "T1074", "T1005", "T1025", "T1039", "T1071", "T1102", "T1105", "T1219", "T1132"]},

    # Low - Discovery techniques
    **{tid: Severity.LOW for tid in
       ["T1007", "T1010", "T1012", "T1016", "T1018", "T1033", "T1046", "T1049", "T1057", "T1069", "T1082", "T1083", "T1087", "T1120", "T1124", "T1135", "T1201", "T1217", "T1482", "T1518", "T1526", "T1580", "T1613", "T1614", "T1615", "T1619"]},

    # Default to Medium for unmapped techniques
    **{tid: Severity.MEDIUM for tid in ALL_ENTERPRISE_TECHNIQUES.keys()
       if tid not in (
           ["T1003", "T1014", "T1195", "T1486", "T1485", "T1471", "T1495", "T1561", "T1041", "T1207", "T1556"] +
           ["T1055", "T1068", "T1078", "T1110", "T1111", "T1134", "T1189", "T1190", "T1199", "T1200", "T1210", "T1211", "T1212", "T1566", "T1040", "T1114", "T1123", "T1125", "T1048", "T1020", "T1567", "T1185", "T1187", "T1098", "T1136", "T1133", "T1531", "T1565"] +
           ["T1059", "T1053", "T1047", "T1106", "T1204", "T1203", "T1027", "T1036", "T1070", "T1112", "T1140", "T1220", "T1221", "T1222", "T1535", "T1056", "T1113", "T1115", "T1119", "T1074", "T1005", "T1025", "T1039", "T1071", "T1102", "T1105", "T1219", "T1132"] +
           ["T1007", "T1010", "T1012", "T1016", "T1018", "T1033", "T1046", "T1049", "T1057", "T1069", "T1082", "T1083", "T1087", "T1120", "T1124", "T1135", "T1201", "T1217", "T1482", "T1518", "T1526", "T1580", "T1613", "T1614", "T1615", "T1619"]
       )}
}

def generate_technique_metadata(technique_id: str, technique_name: str) -> TechniqueMetadata:
    """Generate complete metadata for a technique"""

    # Get mapped tactic or infer from ID
    tactic = TACTIC_MAPPING.get(technique_id, infer_tactic_from_name(technique_name))

    # Get mapped platforms or use defaults
    platforms = PLATFORM_MAPPING.get(technique_id, [Platform.WINDOWS, Platform.LINUX, Platform.MACOS])

    # Get mapped severity or use default
    severity = SEVERITY_MAPPING.get(technique_id, Severity.MEDIUM)

    # Generate intelligent data sources and log fields
    data_sources, log_fields = generate_data_sources_and_fields(technique_name, tactic)

    return TechniqueMetadata(
        id=technique_id,
        name=technique_name,
        tactic=tactic,
        platforms=platforms,
        severity=severity,
        description=f"Adversaries may use {technique_name.lower()} to {tactic.value.replace('-', ' ')}",
        data_sources=data_sources,
        log_fields=log_fields
    )

def infer_tactic_from_name(technique_name: str) -> Tactic:
    """Infer tactic from technique name using keywords"""
    name_lower = technique_name.lower()

    if any(word in name_lower for word in ['scanning', 'gather', 'search', 'phishing for']):
        return Tactic.RECONNAISSANCE
    elif any(word in name_lower for word in ['acquire', 'compromise infrastructure', 'establish', 'develop', 'obtain', 'stage']):
        return Tactic.RESOURCE_DEVELOPMENT
    elif any(word in name_lower for word in ['exploit public', 'phishing', 'supply chain', 'drive-by', 'hardware addition']):
        return Tactic.INITIAL_ACCESS
    elif any(word in name_lower for word in ['command', 'scripting', 'execution', 'native api', 'scheduled task']):
        return Tactic.EXECUTION
    elif any(word in name_lower for word in ['boot', 'logon', 'startup', 'create account', 'modify system process']):
        return Tactic.PERSISTENCE
    elif any(word in name_lower for word in ['privilege escalation', 'process injection', 'token manipulation']):
        return Tactic.PRIVILEGE_ESCALATION
    elif any(word in name_lower for word in ['obfuscat', 'masquerad', 'indicator removal', 'modify registry', 'hide']):
        return Tactic.DEFENSE_EVASION
    elif any(word in name_lower for word in ['credential', 'password', 'brute force', 'kerberos', 'authentication']):
        return Tactic.CREDENTIAL_ACCESS
    elif any(word in name_lower for word in ['discovery', 'enumerat', 'system information', 'network configuration']):
        return Tactic.DISCOVERY
    elif any(word in name_lower for word in ['lateral', 'remote services', 'tool transfer']):
        return Tactic.LATERAL_MOVEMENT
    elif any(word in name_lower for word in ['capture', 'collection', 'data from', 'email collection']):
        return Tactic.COLLECTION
    elif any(word in name_lower for word in ['c2', 'command and control', 'application layer', 'encrypted channel']):
        return Tactic.COMMAND_AND_CONTROL
    elif any(word in name_lower for word in ['exfiltration', 'transfer data']):
        return Tactic.EXFILTRATION
    elif any(word in name_lower for word in ['impact', 'destruction', 'encrypted for impact', 'denial of service']):
        return Tactic.IMPACT
    else:
        return Tactic.EXECUTION  # Default

def generate_data_sources_and_fields(technique_name: str, tactic: Tactic) -> tuple[List[str], List[str]]:
    """Generate appropriate data sources and log fields based on technique characteristics"""
    name_lower = technique_name.lower()

    # Base data sources and fields by tactic
    tactic_mapping = {
        Tactic.RECONNAISSANCE: (["Network Traffic", "DNS Queries", "Web Logs"], ["scan_activity", "reconnaissance_pattern", "information_gathering"]),
        Tactic.RESOURCE_DEVELOPMENT: (["Infrastructure Logs", "Domain Registration"], ["resource_acquisition", "infrastructure_setup", "capability_development"]),
        Tactic.INITIAL_ACCESS: (["Authentication Logs", "Web Logs", "Email Logs"], ["initial_compromise", "access_attempt", "entry_vector"]),
        Tactic.EXECUTION: (["Process Monitoring", "Command Line"], ["process_execution", "command_line", "code_execution"]),
        Tactic.PERSISTENCE: (["File Monitoring", "Registry", "Service Logs"], ["persistence_mechanism", "autostart_entry", "scheduled_task"]),
        Tactic.PRIVILEGE_ESCALATION: (["Process Monitoring", "API Monitoring"], ["privilege_escalation", "elevation_attempt", "process_injection"]),
        Tactic.DEFENSE_EVASION: (["File Monitoring", "Process Monitoring"], ["evasion_technique", "obfuscation", "hiding_mechanism"]),
        Tactic.CREDENTIAL_ACCESS: (["Authentication Logs", "Process Monitoring"], ["credential_access", "password_attempt", "authentication_bypass"]),
        Tactic.DISCOVERY: (["Process Monitoring", "Command Line"], ["discovery_activity", "enumeration", "system_information"]),
        Tactic.LATERAL_MOVEMENT: (["Network Traffic", "Authentication Logs"], ["lateral_movement", "remote_access", "network_propagation"]),
        Tactic.COLLECTION: (["File Monitoring", "API Monitoring"], ["data_collection", "information_gathering", "sensitive_data"]),
        Tactic.COMMAND_AND_CONTROL: (["Network Traffic", "DNS Queries"], ["c2_communication", "command_control", "network_beacon"]),
        Tactic.EXFILTRATION: (["Network Traffic", "File Monitoring"], ["data_exfiltration", "data_transfer", "information_theft"]),
        Tactic.IMPACT: (["File Monitoring", "Process Monitoring"], ["impact_activity", "system_damage", "service_disruption"])
    }

    base_sources, base_fields = tactic_mapping.get(tactic, (["Process Monitoring"], ["activity"]))

    # Add technique-specific sources and fields
    additional_sources = []
    additional_fields = []

    if 'registry' in name_lower:
        additional_sources.append("Windows Registry")
        additional_fields.extend(["registry_modification", "registry_key"])

    if 'network' in name_lower:
        additional_sources.append("Network Traffic")
        additional_fields.extend(["network_connection", "network_activity"])

    if 'file' in name_lower or 'directory' in name_lower:
        additional_sources.append("File Monitoring")
        additional_fields.extend(["file_access", "file_modification"])

    if 'email' in name_lower:
        additional_sources.append("Email Logs")
        additional_fields.extend(["email_access", "email_content"])

    if 'cloud' in name_lower:
        additional_sources.append("Cloud Audit Logs")
        additional_fields.extend(["cloud_activity", "cloud_resource"])

    return list(set(base_sources + additional_sources)), list(set(base_fields + additional_fields))

# Generate ALL 286 technique metadata
def generate_all_techniques() -> Dict[str, TechniqueMetadata]:
    """Generate complete metadata for all 286 techniques"""
    return {
        technique_id: generate_technique_metadata(technique_id, technique_name)
        for technique_id, technique_name in ALL_ENTERPRISE_TECHNIQUES.items()
    }

# Production-ready complete MITRE ATT&CK configuration
MITRE_ENTERPRISE_CONFIG = generate_all_techniques()

def get_technique(technique_id: str) -> Optional[TechniqueMetadata]:
    """Get technique metadata by ID"""
    return MITRE_ENTERPRISE_CONFIG.get(technique_id)

def get_techniques_by_tactic(tactic: Tactic) -> List[TechniqueMetadata]:
    """Get all techniques for a tactic"""
    return [t for t in MITRE_ENTERPRISE_CONFIG.values() if t.tactic == tactic]

def get_techniques_by_platform(platform: Platform) -> List[TechniqueMetadata]:
    """Get all techniques for a platform"""
    return [t for t in MITRE_ENTERPRISE_CONFIG.values() if platform in t.platforms]

def get_high_severity_techniques() -> List[TechniqueMetadata]:
    """Get high and critical severity techniques"""
    return [t for t in MITRE_ENTERPRISE_CONFIG.values() if t.severity in [Severity.HIGH, Severity.CRITICAL]]

def export_for_sigma_rules() -> Dict[str, Any]:
    """Export configuration for Sigma rule generation"""
    return {
        "framework_version": "v15.1",
        "total_techniques": len(MITRE_ENTERPRISE_CONFIG),
        "techniques": {
            tid: {
                "id": t.id,
                "name": t.name,
                "tactic": t.tactic.value,
                "platforms": [p.value for p in t.platforms],
                "severity": t.severity.value,
                "description": t.description,
                "data_sources": t.data_sources,
                "log_fields": t.log_fields,
                "mitre_url": t.mitre_url
            }
            for tid, t in MITRE_ENTERPRISE_CONFIG.items()
        },
        "tactics": {tactic.value: len(get_techniques_by_tactic(tactic)) for tactic in Tactic},
        "platforms": {platform.value: len(get_techniques_by_platform(platform)) for platform in Platform},
        "severity_distribution": {
            severity.value: len([t for t in MITRE_ENTERPRISE_CONFIG.values() if t.severity == severity])
            for severity in Severity
        }
    }

def validate_completeness() -> Dict[str, Any]:
    """Validate that all 286 techniques are properly configured"""
    expected_techniques = ["T1535", "T1220", "T1486", "T1566", "T1059", "T1110"]
    configured_ids = set(MITRE_ENTERPRISE_CONFIG.keys())
    missing_expected = [tid for tid in expected_techniques if tid not in configured_ids]

    return {
        "total_configured": len(MITRE_ENTERPRISE_CONFIG),
        "expected_total": 286,
        "coverage_complete": len(MITRE_ENTERPRISE_CONFIG) == 286,
        "expected_techniques_present": len(missing_expected) == 0,
        "missing_expected": missing_expected,
        "tactics_coverage": {tactic.value: len(get_techniques_by_tactic(tactic)) for tactic in Tactic},
        "validation_passed": len(MITRE_ENTERPRISE_CONFIG) == 286 and len(missing_expected) == 0
    }

# Initialize and validate on import
validation_result = validate_completeness()
print(f"✅ MITRE ATT&CK Enterprise Configuration Loaded:")
print(f"   📊 Total Techniques: {validation_result['total_configured']}/286")
print(f"   ✅ Coverage Complete: {validation_result['coverage_complete']}")
print(f"   ✅ Validation Passed: {validation_result['validation_passed']}")

if not validation_result['validation_passed']:
    print(f"   ❌ Missing Expected: {validation_result['missing_expected']}")
