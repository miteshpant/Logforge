'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Shield,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Download,
  RefreshCw,
  FileText,
  Calendar,
  Lock,
  Eye,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  Search,
  Filter,
  Archive,
  Trash2,
  Settings,
  ClipboardCheck,
  AlertCircle
} from 'lucide-react'

interface ComplianceFramework {
  id: string
  name: string
  shortName: string
  description: string
  enabled: boolean
  status: 'compliant' | 'non_compliant' | 'partial' | 'not_assessed'
  lastAssessment?: string
  nextAssessment?: string
  controls: ControlCategory[]
  overallScore: number
}

interface ControlCategory {
  id: string
  name: string
  controls: Control[]
}

interface Control {
  id: string
  name: string
  description: string
  status: 'pass' | 'fail' | 'warning' | 'not_applicable'
  evidence?: string[]
  lastChecked?: string
  remediation?: string
}

interface AuditLogEntry {
  id: string
  timestamp: string
  user: string
  action: string
  resource: string
  details: string
  ip_address: string
  result: 'success' | 'failure'
}

interface RetentionPolicy {
  id: string
  name: string
  dataType: string
  retentionDays: number
  archiveAfterDays?: number
  deleteAfterDays?: number
  enabled: boolean
}

interface LegalHold {
  id: string
  name: string
  description: string
  createdBy: string
  createdAt: string
  status: 'active' | 'released'
  affectedData: string[]
  reason: string
}

const generateMockFrameworks = (): ComplianceFramework[] => [
  {
    id: 'soc2',
    name: 'SOC 2 Type II',
    shortName: 'SOC2',
    description: 'Service Organization Control 2 - Security, Availability, Confidentiality',
    enabled: true,
    status: 'compliant',
    lastAssessment: '2024-01-15T00:00:00Z',
    nextAssessment: '2024-07-15T00:00:00Z',
    overallScore: 94,
    controls: [
      {
        id: 'cc6',
        name: 'Logical and Physical Access',
        controls: [
          { id: 'cc6.1', name: 'Access Control Policy', description: 'Access control policies are established', status: 'pass', lastChecked: '2024-01-15T00:00:00Z' },
          { id: 'cc6.2', name: 'User Authentication', description: 'Users are authenticated before access', status: 'pass', lastChecked: '2024-01-15T00:00:00Z' },
          { id: 'cc6.3', name: 'Access Removal', description: 'Access is removed upon termination', status: 'pass', lastChecked: '2024-01-15T00:00:00Z' },
          { id: 'cc6.6', name: 'Encryption', description: 'Data is encrypted in transit and at rest', status: 'pass', lastChecked: '2024-01-15T00:00:00Z' },
        ]
      },
      {
        id: 'cc7',
        name: 'System Operations',
        controls: [
          { id: 'cc7.1', name: 'Security Monitoring', description: 'Security events are monitored', status: 'pass', lastChecked: '2024-01-15T00:00:00Z' },
          { id: 'cc7.2', name: 'Anomaly Detection', description: 'Anomalies are detected and reported', status: 'pass', lastChecked: '2024-01-15T00:00:00Z' },
          { id: 'cc7.3', name: 'Incident Response', description: 'Incidents are responded to timely', status: 'warning', lastChecked: '2024-01-15T00:00:00Z', remediation: 'Update incident response runbook' },
        ]
      },
      {
        id: 'cc8',
        name: 'Change Management',
        controls: [
          { id: 'cc8.1', name: 'Change Authorization', description: 'Changes are authorized before implementation', status: 'pass', lastChecked: '2024-01-15T00:00:00Z' },
        ]
      }
    ]
  },
  {
    id: 'hipaa',
    name: 'HIPAA',
    shortName: 'HIPAA',
    description: 'Health Insurance Portability and Accountability Act',
    enabled: true,
    status: 'partial',
    lastAssessment: '2024-01-10T00:00:00Z',
    nextAssessment: '2024-04-10T00:00:00Z',
    overallScore: 78,
    controls: [
      {
        id: 'admin',
        name: 'Administrative Safeguards',
        controls: [
          { id: '164.308.a1', name: 'Security Management', description: 'Policies and procedures to prevent security violations', status: 'pass', lastChecked: '2024-01-10T00:00:00Z' },
          { id: '164.308.a3', name: 'Workforce Security', description: 'Access management for workforce members', status: 'pass', lastChecked: '2024-01-10T00:00:00Z' },
          { id: '164.308.a5', name: 'Security Awareness', description: 'Security awareness and training program', status: 'warning', lastChecked: '2024-01-10T00:00:00Z', remediation: 'Schedule annual security training' },
        ]
      },
      {
        id: 'technical',
        name: 'Technical Safeguards',
        controls: [
          { id: '164.312.a1', name: 'Access Control', description: 'Unique user identification and access controls', status: 'pass', lastChecked: '2024-01-10T00:00:00Z' },
          { id: '164.312.b', name: 'Audit Controls', description: 'Hardware, software, and procedural audit mechanisms', status: 'pass', lastChecked: '2024-01-10T00:00:00Z' },
          { id: '164.312.d', name: 'Authentication', description: 'Person or entity authentication', status: 'fail', lastChecked: '2024-01-10T00:00:00Z', remediation: 'Implement MFA for all users accessing PHI' },
          { id: '164.312.e', name: 'Transmission Security', description: 'Encryption of ePHI in transit', status: 'pass', lastChecked: '2024-01-10T00:00:00Z' },
        ]
      }
    ]
  },
  {
    id: 'pci',
    name: 'PCI DSS 4.0',
    shortName: 'PCI',
    description: 'Payment Card Industry Data Security Standard',
    enabled: true,
    status: 'compliant',
    lastAssessment: '2024-01-20T00:00:00Z',
    nextAssessment: '2025-01-20T00:00:00Z',
    overallScore: 96,
    controls: [
      {
        id: 'req1',
        name: 'Network Security Controls',
        controls: [
          { id: '1.1', name: 'Network Segmentation', description: 'Install and maintain network security controls', status: 'pass', lastChecked: '2024-01-20T00:00:00Z' },
          { id: '1.2', name: 'Firewall Configuration', description: 'Apply secure configurations', status: 'pass', lastChecked: '2024-01-20T00:00:00Z' },
        ]
      },
      {
        id: 'req3',
        name: 'Protect Stored Account Data',
        controls: [
          { id: '3.1', name: 'Data Retention', description: 'Keep cardholder data storage to a minimum', status: 'pass', lastChecked: '2024-01-20T00:00:00Z' },
          { id: '3.5', name: 'Key Management', description: 'Protect stored cardholder data with strong encryption', status: 'pass', lastChecked: '2024-01-20T00:00:00Z' },
        ]
      },
      {
        id: 'req10',
        name: 'Log and Monitor Access',
        controls: [
          { id: '10.1', name: 'Audit Logging', description: 'Implement audit trails for all access', status: 'pass', lastChecked: '2024-01-20T00:00:00Z' },
          { id: '10.2', name: 'Log Monitoring', description: 'Review logs daily', status: 'pass', lastChecked: '2024-01-20T00:00:00Z' },
        ]
      }
    ]
  },
  {
    id: 'gdpr',
    name: 'GDPR',
    shortName: 'GDPR',
    description: 'General Data Protection Regulation',
    enabled: false,
    status: 'not_assessed',
    overallScore: 0,
    controls: []
  }
]

const generateMockAuditLogs = (): AuditLogEntry[] => [
  { id: '1', timestamp: new Date(Date.now() - 300000).toISOString(), user: 'admin@company.com', action: 'LOGIN', resource: 'System', details: 'Successful login', ip_address: '10.0.1.100', result: 'success' },
  { id: '2', timestamp: new Date(Date.now() - 600000).toISOString(), user: 'alice@company.com', action: 'EXPORT', resource: 'Logs', details: 'Exported 1500 log entries', ip_address: '10.0.1.101', result: 'success' },
  { id: '3', timestamp: new Date(Date.now() - 900000).toISOString(), user: 'bob@company.com', action: 'ROLE_CHANGE', resource: 'User: carol', details: 'Changed role from Viewer to Developer', ip_address: '10.0.1.102', result: 'success' },
  { id: '4', timestamp: new Date(Date.now() - 1200000).toISOString(), user: 'unknown', action: 'LOGIN', resource: 'System', details: 'Failed login attempt', ip_address: '185.220.101.33', result: 'failure' },
  { id: '5', timestamp: new Date(Date.now() - 1500000).toISOString(), user: 'admin@company.com', action: 'CONFIG_CHANGE', resource: 'Alert Rules', details: 'Created new alert rule: High Error Rate', ip_address: '10.0.1.100', result: 'success' },
]

const generateMockRetentionPolicies = (): RetentionPolicy[] => [
  { id: '1', name: 'Application Logs', dataType: 'logs', retentionDays: 90, archiveAfterDays: 30, deleteAfterDays: 365, enabled: true },
  { id: '2', name: 'Security Events', dataType: 'security', retentionDays: 365, archiveAfterDays: 90, deleteAfterDays: 730, enabled: true },
  { id: '3', name: 'Traces', dataType: 'traces', retentionDays: 30, archiveAfterDays: 14, deleteAfterDays: 90, enabled: true },
  { id: '4', name: 'Metrics', dataType: 'metrics', retentionDays: 180, archiveAfterDays: 60, deleteAfterDays: 365, enabled: true },
  { id: '5', name: 'Audit Logs', dataType: 'audit', retentionDays: 730, deleteAfterDays: 2555, enabled: true },
]

const generateMockLegalHolds = (): LegalHold[] => [
  {
    id: '1',
    name: 'Investigation Case #2024-001',
    description: 'Data preservation for ongoing investigation',
    createdBy: 'legal@company.com',
    createdAt: '2024-01-05T00:00:00Z',
    status: 'active',
    affectedData: ['logs', 'security', 'audit'],
    reason: 'Legal investigation - preserve all data from 2023-12-01 to 2024-01-15'
  },
  {
    id: '2',
    name: 'Audit Preparation 2024',
    description: 'SOC 2 audit preparation',
    createdBy: 'compliance@company.com',
    createdAt: '2024-01-10T00:00:00Z',
    status: 'active',
    affectedData: ['audit', 'security'],
    reason: 'Preserve audit-related data for upcoming SOC 2 assessment'
  }
]

export default function CompliancePage() {
  const [frameworks, setFrameworks] = useState<ComplianceFramework[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([])
  const [retentionPolicies, setRetentionPolicies] = useState<RetentionPolicy[]>([])
  const [legalHolds, setLegalHolds] = useState<LegalHold[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'frameworks' | 'audit' | 'retention' | 'legal'>('frameworks')
  const [expandedFramework, setExpandedFramework] = useState<string | null>(null)
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setIsLoading(true)
      const [fwRes, auditRes, retRes, holdRes] = await Promise.all([
        apiClient.get('/v1/compliance/frameworks').catch(() => null),
        apiClient.get('/v1/compliance/audit-logs').catch(() => null),
        apiClient.get('/v1/compliance/retention-policies').catch(() => null),
        apiClient.get('/v1/compliance/legal-holds').catch(() => null)
      ])

      setFrameworks(fwRes?.data?.frameworks || generateMockFrameworks())
      setAuditLogs(auditRes?.data?.logs || generateMockAuditLogs())
      setRetentionPolicies(retRes?.data?.policies || generateMockRetentionPolicies())
      setLegalHolds(holdRes?.data?.holds || generateMockLegalHolds())
    } catch (error) {
      console.error('Failed to load compliance data:', error)
      setFrameworks(generateMockFrameworks())
      setAuditLogs(generateMockAuditLogs())
      setRetentionPolicies(generateMockRetentionPolicies())
      setLegalHolds(generateMockLegalHolds())
    } finally {
      setIsLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'compliant':
      case 'pass':
      case 'success':
        return 'text-green-400 bg-green-500/20 border-green-500/30'
      case 'non_compliant':
      case 'fail':
      case 'failure':
        return 'text-red-400 bg-red-500/20 border-red-500/30'
      case 'partial':
      case 'warning':
        return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30'
      default:
        return 'text-gray-400 bg-gray-500/20 border-gray-500/30'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'compliant':
      case 'pass':
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-400" />
      case 'non_compliant':
      case 'fail':
      case 'failure':
        return <XCircle className="w-4 h-4 text-red-400" />
      case 'partial':
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-400" />
      default:
        return <Clock className="w-4 h-4 text-gray-400" />
    }
  }

  const formatDate = (timestamp: string | undefined) => {
    if (!timestamp) return 'N/A'
    return new Date(timestamp).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  }

  const formatTimeAgo = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return 'Just now'
  }

  // Summary stats
  const enabledFrameworks = frameworks.filter(f => f.enabled)
  const compliantCount = enabledFrameworks.filter(f => f.status === 'compliant').length
  const totalControls = enabledFrameworks.reduce((sum, f) => sum + f.controls.reduce((s, c) => s + c.controls.length, 0), 0)
  const passingControls = enabledFrameworks.reduce((sum, f) => sum + f.controls.reduce((s, c) => s + c.controls.filter(ctrl => ctrl.status === 'pass').length, 0), 0)

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Compliance & Audit</h1>
            <p className="text-gray-400 mt-1">Monitor compliance status, audit logs, and data governance</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={loadData}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
              <Download className="w-4 h-4" />
              Export Report
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-green-600/20 to-green-800/20 border border-green-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-green-500/20 rounded-lg">
                <Shield className="w-6 h-6 text-green-400" />
              </div>
              <div>
                <p className="text-gray-400 text-sm">Compliance Status</p>
                <p className="text-2xl font-bold text-white">{compliantCount}/{enabledFrameworks.length}</p>
                <p className="text-xs text-green-400 mt-1">Frameworks Compliant</p>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-blue-600/20 to-blue-800/20 border border-blue-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-500/20 rounded-lg">
                <ClipboardCheck className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <p className="text-gray-400 text-sm">Control Status</p>
                <p className="text-2xl font-bold text-white">{passingControls}/{totalControls}</p>
                <p className="text-xs text-blue-400 mt-1">Controls Passing</p>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-purple-600/20 to-purple-800/20 border border-purple-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-purple-500/20 rounded-lg">
                <Eye className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <p className="text-gray-400 text-sm">Audit Events</p>
                <p className="text-2xl font-bold text-white">{auditLogs.length}</p>
                <p className="text-xs text-purple-400 mt-1">Last 24 hours</p>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-orange-600/20 to-orange-800/20 border border-orange-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-orange-500/20 rounded-lg">
                <Lock className="w-6 h-6 text-orange-400" />
              </div>
              <div>
                <p className="text-gray-400 text-sm">Legal Holds</p>
                <p className="text-2xl font-bold text-white">{legalHolds.filter(h => h.status === 'active').length}</p>
                <p className="text-xs text-orange-400 mt-1">Active Holds</p>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-800/50 p-1 rounded-lg w-fit">
          {[
            { id: 'frameworks', label: 'Frameworks', icon: Shield },
            { id: 'audit', label: 'Audit Logs', icon: FileText },
            { id: 'retention', label: 'Retention Policies', icon: Archive },
            { id: 'legal', label: 'Legal Holds', icon: Lock }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : (
          <>
            {/* Frameworks Tab */}
            {activeTab === 'frameworks' && (
              <div className="space-y-4">
                {frameworks.map((framework) => (
                  <div
                    key={framework.id}
                    className={`bg-gray-800/50 border rounded-lg overflow-hidden ${
                      framework.enabled ? 'border-gray-700' : 'border-gray-800 opacity-60'
                    }`}
                  >
                    {/* Framework Header */}
                    <div
                      onClick={() => framework.enabled && setExpandedFramework(expandedFramework === framework.id ? null : framework.id)}
                      className={`p-4 ${framework.enabled ? 'cursor-pointer hover:bg-gray-700/30' : ''} transition-colors`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className={`p-3 rounded-lg border ${getStatusColor(framework.status)}`}>
                            <Shield className="w-6 h-6" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="text-lg font-semibold text-white">{framework.name}</h3>
                              <span className={`px-2 py-0.5 rounded text-xs font-medium border ${getStatusColor(framework.status)}`}>
                                {framework.status.replace('_', ' ').toUpperCase()}
                              </span>
                              {!framework.enabled && (
                                <span className="px-2 py-0.5 bg-gray-700 text-gray-400 text-xs rounded">
                                  Disabled
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-gray-400 mt-1">{framework.description}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-6">
                          {framework.enabled && (
                            <>
                              <div className="text-center">
                                <p className="text-2xl font-bold text-white">{framework.overallScore}%</p>
                                <p className="text-xs text-gray-500">Score</p>
                              </div>
                              <div className="text-right text-sm">
                                <p className="text-gray-400">Last: {formatDate(framework.lastAssessment)}</p>
                                <p className="text-gray-500">Next: {formatDate(framework.nextAssessment)}</p>
                              </div>
                              {expandedFramework === framework.id ? (
                                <ChevronDown className="w-5 h-5 text-gray-400" />
                              ) : (
                                <ChevronRight className="w-5 h-5 text-gray-400" />
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Expanded Controls */}
                    {expandedFramework === framework.id && framework.enabled && (
                      <div className="border-t border-gray-700 p-4 space-y-3">
                        {framework.controls.map((category) => (
                          <div key={category.id} className="border border-gray-600 rounded-lg overflow-hidden">
                            <button
                              onClick={() => setExpandedCategory(expandedCategory === category.id ? null : category.id)}
                              className="w-full flex items-center justify-between p-3 bg-gray-700/50 hover:bg-gray-700 transition-colors"
                            >
                              <span className="text-white font-medium">{category.name}</span>
                              <div className="flex items-center gap-3">
                                <span className="text-sm text-gray-400">
                                  {category.controls.filter(c => c.status === 'pass').length}/{category.controls.length} passing
                                </span>
                                {expandedCategory === category.id ? (
                                  <ChevronDown className="w-4 h-4 text-gray-400" />
                                ) : (
                                  <ChevronRight className="w-4 h-4 text-gray-400" />
                                )}
                              </div>
                            </button>
                            {expandedCategory === category.id && (
                              <div className="p-3 space-y-2">
                                {category.controls.map((control) => (
                                  <div
                                    key={control.id}
                                    className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg"
                                  >
                                    {getStatusIcon(control.status)}
                                    <div className="flex-1">
                                      <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium text-white">{control.id}</span>
                                        <span className="text-sm text-gray-300">{control.name}</span>
                                      </div>
                                      <p className="text-xs text-gray-500 mt-1">{control.description}</p>
                                      {control.remediation && (
                                        <p className="text-xs text-yellow-400 mt-2 flex items-center gap-1">
                                          <AlertCircle className="w-3 h-3" />
                                          {control.remediation}
                                        </p>
                                      )}
                                    </div>
                                    <span className="text-xs text-gray-500">
                                      {formatDate(control.lastChecked)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Audit Logs Tab */}
            {activeTab === 'audit' && (
              <div className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden">
                <div className="p-4 border-b border-gray-700 flex items-center justify-between">
                  <div className="relative w-64">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search audit logs..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm"
                    />
                  </div>
                  <button className="flex items-center gap-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm">
                    <Filter className="w-4 h-4" />
                    Filters
                  </button>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Timestamp</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">User</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Action</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Resource</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Details</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">IP Address</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Result</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-gray-700/30">
                        <td className="px-4 py-3 text-sm text-gray-300">
                          {formatTimeAgo(log.timestamp)}
                        </td>
                        <td className="px-4 py-3 text-sm text-white">{log.user}</td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-1 bg-gray-700 text-gray-300 text-xs rounded font-mono">
                            {log.action}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-300">{log.resource}</td>
                        <td className="px-4 py-3 text-sm text-gray-400 max-w-xs truncate">{log.details}</td>
                        <td className="px-4 py-3 text-sm text-gray-500 font-mono">{log.ip_address}</td>
                        <td className="px-4 py-3">
                          <span className={`flex items-center gap-1 ${
                            log.result === 'success' ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {getStatusIcon(log.result)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Retention Policies Tab */}
            {activeTab === 'retention' && (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm">
                    <Settings className="w-4 h-4" />
                    Configure Policies
                  </button>
                </div>
                <div className="grid gap-4">
                  {retentionPolicies.map((policy) => (
                    <div
                      key={policy.id}
                      className={`bg-gray-800/50 border rounded-lg p-4 ${
                        policy.enabled ? 'border-gray-700' : 'border-gray-800 opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-blue-500/20 rounded-lg">
                            <Archive className="w-5 h-5 text-blue-400" />
                          </div>
                          <div>
                            <h3 className="text-white font-semibold">{policy.name}</h3>
                            <p className="text-sm text-gray-400">Type: {policy.dataType}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-6 text-sm">
                          <div className="text-center">
                            <p className="text-white font-medium">{policy.retentionDays}d</p>
                            <p className="text-xs text-gray-500">Retention</p>
                          </div>
                          {policy.archiveAfterDays && (
                            <div className="text-center">
                              <p className="text-white font-medium">{policy.archiveAfterDays}d</p>
                              <p className="text-xs text-gray-500">Archive After</p>
                            </div>
                          )}
                          {policy.deleteAfterDays && (
                            <div className="text-center">
                              <p className="text-white font-medium">{policy.deleteAfterDays}d</p>
                              <p className="text-xs text-gray-500">Delete After</p>
                            </div>
                          )}
                          <span className={`px-2 py-1 rounded text-xs ${
                            policy.enabled
                              ? 'bg-green-500/20 text-green-400'
                              : 'bg-gray-500/20 text-gray-400'
                          }`}>
                            {policy.enabled ? 'Active' : 'Disabled'}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Legal Holds Tab */}
            {activeTab === 'legal' && (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <button className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm">
                    <Lock className="w-4 h-4" />
                    Create Legal Hold
                  </button>
                </div>
                {legalHolds.length === 0 ? (
                  <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-8 text-center">
                    <Lock className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                    <p className="text-gray-400">No legal holds active</p>
                  </div>
                ) : (
                  <div className="grid gap-4">
                    {legalHolds.map((hold) => (
                      <div
                        key={hold.id}
                        className={`bg-gray-800/50 border rounded-lg p-4 ${
                          hold.status === 'active'
                            ? 'border-orange-500/30'
                            : 'border-gray-700 opacity-60'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4">
                            <div className={`p-3 rounded-lg ${
                              hold.status === 'active'
                                ? 'bg-orange-500/20'
                                : 'bg-gray-500/20'
                            }`}>
                              <Lock className={`w-5 h-5 ${
                                hold.status === 'active' ? 'text-orange-400' : 'text-gray-400'
                              }`} />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="text-white font-semibold">{hold.name}</h3>
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                  hold.status === 'active'
                                    ? 'bg-orange-500/20 text-orange-400'
                                    : 'bg-gray-500/20 text-gray-400'
                                }`}>
                                  {hold.status.toUpperCase()}
                                </span>
                              </div>
                              <p className="text-sm text-gray-400 mt-1">{hold.description}</p>
                              <p className="text-sm text-gray-500 mt-2">{hold.reason}</p>
                              <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                                <span>Created by: {hold.createdBy}</span>
                                <span>Created: {formatDate(hold.createdAt)}</span>
                              </div>
                              <div className="flex gap-1 mt-2">
                                {hold.affectedData.map((data) => (
                                  <span key={data} className="px-2 py-0.5 bg-gray-700 text-gray-300 text-xs rounded">
                                    {data}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>
                          {hold.status === 'active' && (
                            <button className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded-lg transition-colors">
                              Release Hold
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
