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
      const now = new Date()
      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
      const [fwRes, auditRes, retRes, holdRes] = await Promise.allSettled([
        apiClient.get('/v1/enterprise/compliance/reports', {
          compliance_framework: 'SOC2',
          period_start: monthAgo.toISOString(),
          period_end: now.toISOString()
        }),
        apiClient.get('/v1/enterprise/audit-logs', {
          start_time: monthAgo.toISOString(),
          end_time: now.toISOString()
        }),
        apiClient.get('/v1/enterprise/compliance/retention-policies'),
        apiClient.get('/v1/enterprise/compliance/legal-holds')
      ])

      if (fwRes.status === 'fulfilled' && fwRes.value?.data) {
        const data = fwRes.value.data
        setFrameworks(data.frameworks || data.reports || (Array.isArray(data) ? data : []))
      }

      if (auditRes.status === 'fulfilled' && auditRes.value?.data) {
        const data = auditRes.value.data
        setAuditLogs(data.audit_logs || data.logs || data.entries || (Array.isArray(data) ? data : []))
      }

      if (retRes.status === 'fulfilled' && retRes.value?.data) {
        const data = retRes.value.data
        setRetentionPolicies(data.policies || (Array.isArray(data) ? data : []))
      }

      if (holdRes.status === 'fulfilled' && holdRes.value?.data) {
        const data = holdRes.value.data
        setLegalHolds(data.holds || (Array.isArray(data) ? data : []))
      }
    } catch (error) {
      console.error('Failed to load compliance data:', error)
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
        return 'text-slate-400 bg-slate-500/20 border-slate-500/30'
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
        return <Clock className="w-4 h-4 text-slate-400" />
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
            <p className="text-slate-400 mt-1">Monitor compliance status, audit logs, and data governance</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={loadData}
              className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
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
                <p className="text-slate-400 text-sm">Compliance Status</p>
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
                <p className="text-slate-400 text-sm">Control Status</p>
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
                <p className="text-slate-400 text-sm">Audit Events</p>
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
                <p className="text-slate-400 text-sm">Legal Holds</p>
                <p className="text-2xl font-bold text-white">{legalHolds.filter(h => h.status === 'active').length}</p>
                <p className="text-xs text-orange-400 mt-1">Active Holds</p>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-800/50 p-1 rounded-lg w-fit">
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
                  : 'text-slate-400 hover:text-white'
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
                {frameworks.length === 0 && (
                  <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-12 text-center">
                    <Shield className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <h3 className="text-lg font-semibold text-white mb-2">No Compliance Frameworks Configured</h3>
                    <p className="text-slate-400 text-sm max-w-md mx-auto">
                      Configure compliance frameworks (SOC2, HIPAA, PCI DSS, GDPR) to track your security posture and audit readiness.
                    </p>
                  </div>
                )}
                {frameworks.map((framework) => (
                  <div
                    key={framework.id}
                    className={`bg-slate-800/50 border rounded-lg overflow-hidden ${
                      framework.enabled ? 'border-white/5' : 'border-slate-800 opacity-60'
                    }`}
                  >
                    {/* Framework Header */}
                    <div
                      onClick={() => framework.enabled && setExpandedFramework(expandedFramework === framework.id ? null : framework.id)}
                      className={`p-4 ${framework.enabled ? 'cursor-pointer hover:bg-white/[0.02]' : ''} transition-colors`}
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
                                <span className="px-2 py-0.5 bg-slate-700 text-slate-400 text-xs rounded">
                                  Disabled
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-slate-400 mt-1">{framework.description}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-6">
                          {framework.enabled && (
                            <>
                              <div className="text-center">
                                <p className="text-2xl font-bold text-white">{framework.overallScore}%</p>
                                <p className="text-xs text-slate-500">Score</p>
                              </div>
                              <div className="text-right text-sm">
                                <p className="text-slate-400">Last: {formatDate(framework.lastAssessment)}</p>
                                <p className="text-slate-500">Next: {formatDate(framework.nextAssessment)}</p>
                              </div>
                              {expandedFramework === framework.id ? (
                                <ChevronDown className="w-5 h-5 text-slate-400" />
                              ) : (
                                <ChevronRight className="w-5 h-5 text-slate-400" />
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Expanded Controls */}
                    {expandedFramework === framework.id && framework.enabled && (
                      <div className="border-t border-white/5 p-4 space-y-3">
                        {framework.controls.map((category) => (
                          <div key={category.id} className="border border-white/10 rounded-lg overflow-hidden">
                            <button
                              onClick={() => setExpandedCategory(expandedCategory === category.id ? null : category.id)}
                              className="w-full flex items-center justify-between p-3 bg-slate-700/50 hover:bg-slate-700 transition-colors"
                            >
                              <span className="text-white font-medium">{category.name}</span>
                              <div className="flex items-center gap-3">
                                <span className="text-sm text-slate-400">
                                  {category.controls.filter(c => c.status === 'pass').length}/{category.controls.length} passing
                                </span>
                                {expandedCategory === category.id ? (
                                  <ChevronDown className="w-4 h-4 text-slate-400" />
                                ) : (
                                  <ChevronRight className="w-4 h-4 text-slate-400" />
                                )}
                              </div>
                            </button>
                            {expandedCategory === category.id && (
                              <div className="p-3 space-y-2">
                                {category.controls.map((control) => (
                                  <div
                                    key={control.id}
                                    className="flex items-start gap-3 p-3 bg-slate-800/50 rounded-lg"
                                  >
                                    {getStatusIcon(control.status)}
                                    <div className="flex-1">
                                      <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium text-white">{control.id}</span>
                                        <span className="text-sm text-slate-300">{control.name}</span>
                                      </div>
                                      <p className="text-xs text-slate-500 mt-1">{control.description}</p>
                                      {control.remediation && (
                                        <p className="text-xs text-yellow-400 mt-2 flex items-center gap-1">
                                          <AlertCircle className="w-3 h-3" />
                                          {control.remediation}
                                        </p>
                                      )}
                                    </div>
                                    <span className="text-xs text-slate-500">
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
              <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 overflow-hidden">
                <div className="p-4 border-b border-white/5 flex items-center justify-between">
                  <div className="relative w-64">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Search audit logs..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500 text-sm"
                    />
                  </div>
                  <button className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm">
                    <Filter className="w-4 h-4" />
                    Filters
                  </button>
                </div>
                {auditLogs.length === 0 ? (
                  <div className="p-12 text-center">
                    <FileText className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <h3 className="text-lg font-semibold text-white mb-2">No Audit Logs</h3>
                    <p className="text-slate-400 text-sm">Audit log entries will appear as users interact with the system.</p>
                  </div>
                ) : (
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/5">
                      <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">Timestamp</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">User</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">Action</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">Resource</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">Details</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">IP Address</th>
                      <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">Result</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-white/[0.02]">
                        <td className="px-4 py-3 text-sm text-slate-300">
                          {formatTimeAgo(log.timestamp)}
                        </td>
                        <td className="px-4 py-3 text-sm text-white">{log.user}</td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-1 bg-slate-700 text-slate-300 text-xs rounded font-mono">
                            {log.action}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-300">{log.resource}</td>
                        <td className="px-4 py-3 text-sm text-slate-400 max-w-xs truncate">{log.details}</td>
                        <td className="px-4 py-3 text-sm text-slate-500 font-mono">{log.ip_address}</td>
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
                )}
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
                {retentionPolicies.length === 0 ? (
                  <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-12 text-center">
                    <Archive className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <h3 className="text-lg font-semibold text-white mb-2">No Retention Policies</h3>
                    <p className="text-slate-400 text-sm">Configure data retention policies to manage storage and compliance requirements.</p>
                  </div>
                ) : (
                <div className="grid gap-4">
                  {retentionPolicies.map((policy) => (
                    <div
                      key={policy.id}
                      className={`bg-slate-800/50 border rounded-lg p-4 ${
                        policy.enabled ? 'border-white/5' : 'border-slate-800 opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-blue-500/20 rounded-lg">
                            <Archive className="w-5 h-5 text-blue-400" />
                          </div>
                          <div>
                            <h3 className="text-white font-semibold">{policy.name}</h3>
                            <p className="text-sm text-slate-400">Type: {policy.dataType}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-6 text-sm">
                          <div className="text-center">
                            <p className="text-white font-medium">{policy.retentionDays}d</p>
                            <p className="text-xs text-slate-500">Retention</p>
                          </div>
                          {policy.archiveAfterDays && (
                            <div className="text-center">
                              <p className="text-white font-medium">{policy.archiveAfterDays}d</p>
                              <p className="text-xs text-slate-500">Archive After</p>
                            </div>
                          )}
                          {policy.deleteAfterDays && (
                            <div className="text-center">
                              <p className="text-white font-medium">{policy.deleteAfterDays}d</p>
                              <p className="text-xs text-slate-500">Delete After</p>
                            </div>
                          )}
                          <span className={`px-2 py-1 rounded text-xs ${
                            policy.enabled
                              ? 'bg-green-500/20 text-green-400'
                              : 'bg-slate-500/20 text-slate-400'
                          }`}>
                            {policy.enabled ? 'Active' : 'Disabled'}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                )}
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
                  <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-8 text-center">
                    <Lock className="w-12 h-12 mx-auto mb-3 text-slate-600" />
                    <p className="text-slate-400">No legal holds active</p>
                  </div>
                ) : (
                  <div className="grid gap-4">
                    {legalHolds.map((hold) => (
                      <div
                        key={hold.id}
                        className={`bg-slate-800/50 border rounded-lg p-4 ${
                          hold.status === 'active'
                            ? 'border-orange-500/30'
                            : 'border-white/5 opacity-60'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4">
                            <div className={`p-3 rounded-lg ${
                              hold.status === 'active'
                                ? 'bg-orange-500/20'
                                : 'bg-slate-500/20'
                            }`}>
                              <Lock className={`w-5 h-5 ${
                                hold.status === 'active' ? 'text-orange-400' : 'text-slate-400'
                              }`} />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="text-white font-semibold">{hold.name}</h3>
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                  hold.status === 'active'
                                    ? 'bg-orange-500/20 text-orange-400'
                                    : 'bg-slate-500/20 text-slate-400'
                                }`}>
                                  {hold.status.toUpperCase()}
                                </span>
                              </div>
                              <p className="text-sm text-slate-400 mt-1">{hold.description}</p>
                              <p className="text-sm text-slate-500 mt-2">{hold.reason}</p>
                              <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                                <span>Created by: {hold.createdBy}</span>
                                <span>Created: {formatDate(hold.createdAt)}</span>
                              </div>
                              <div className="flex gap-1 mt-2">
                                {hold.affectedData.map((data) => (
                                  <span key={data} className="px-2 py-0.5 bg-slate-700 text-slate-300 text-xs rounded">
                                    {data}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>
                          {hold.status === 'active' && (
                            <button className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm rounded-lg transition-colors">
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
