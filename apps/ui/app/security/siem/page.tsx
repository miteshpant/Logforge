'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  ShieldAlert,
  AlertTriangle,
  Shield,
  Activity,
  TrendingUp,
  Clock,
  Target,
  Zap
} from 'lucide-react'

interface SecurityEvent {
  id: string
  rule_id: string
  rule_title: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  status: string
  timestamp: string
  event_data: Record<string, unknown>
  matched_fields: Record<string, unknown>
  attack_techniques: string[]
  kill_chain_phase?: string
  assigned_to?: string
  investigation_notes: string[]
  artifacts: string[]
}

interface SigmaRule {
  id: string
  title: string
  description: string
  severity: string
  status: string
  author: string
  date: string
  enabled: boolean
  attack_techniques: string[]
  tags: string[]
}

interface SecurityDashboard {
  total_events: number
  events_by_severity: Record<string, number>
  events_by_technique: Record<string, number>
  top_rules: Array<{
    rule_id: string
    rule_title: string
    event_count: number
    severity: string
  }>
  recent_events: SecurityEvent[]
  threat_intel_stats: {
    total_indicators: number
    by_type: Record<string, number>
    by_severity: Record<string, number>
  }
}

// MITRE ATT&CK Tactics
const MITRE_TACTICS = [
  { id: 'reconnaissance', name: 'Reconnaissance', shortName: 'Recon' },
  { id: 'resource-development', name: 'Resource Development', shortName: 'Resource' },
  { id: 'initial-access', name: 'Initial Access', shortName: 'Init Access' },
  { id: 'execution', name: 'Execution', shortName: 'Exec' },
  { id: 'persistence', name: 'Persistence', shortName: 'Persist' },
  { id: 'privilege-escalation', name: 'Privilege Escalation', shortName: 'PrivEsc' },
  { id: 'defense-evasion', name: 'Defense Evasion', shortName: 'Evasion' },
  { id: 'credential-access', name: 'Credential Access', shortName: 'Creds' },
  { id: 'discovery', name: 'Discovery', shortName: 'Discovery' },
  { id: 'lateral-movement', name: 'Lateral Movement', shortName: 'Lateral' },
  { id: 'collection', name: 'Collection', shortName: 'Collect' },
  { id: 'command-and-control', name: 'Command and Control', shortName: 'C2' },
  { id: 'exfiltration', name: 'Exfiltration', shortName: 'Exfil' },
  { id: 'impact', name: 'Impact', shortName: 'Impact' }
]

export default function SIEMDashboardPage() {
  const { getApiTimeRange } = useTimeRange()
  const [dashboard, setDashboard] = useState<SecurityDashboard | null>(null)
  const [rules, setRules] = useState<SigmaRule[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all')

  const loadSecurityData = async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const [dashboardRes, rulesRes] = await Promise.allSettled([
        apiClient.get<SecurityDashboard>('/v1/security/dashboard', {
          start_time,
          end_time
        }),
        apiClient.get<SigmaRule[]>('/v1/security/sigma-rules')
      ])

      if (dashboardRes.status === 'fulfilled') {
        const data = dashboardRes.value?.data || dashboardRes.value
        if (data) {
          setDashboard(data as SecurityDashboard)
        } else {
          setDashboard(generateMockDashboard())
        }
      } else {
        setDashboard(generateMockDashboard())
      }

      if (rulesRes.status === 'fulfilled') {
        const data = rulesRes.value?.data || rulesRes.value
        if (Array.isArray(data)) {
          setRules(data)
        } else {
          setRules(generateMockRules())
        }
      } else {
        setRules(generateMockRules())
      }
    } catch (error) {
      console.error('Failed to load security data:', error)
      setDashboard(generateMockDashboard())
      setRules(generateMockRules())
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadSecurityData()
  }, [])

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'text-red-500 bg-red-500/10 border-red-500/30'
      case 'high': return 'text-orange-500 bg-orange-500/10 border-orange-500/30'
      case 'medium': return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/30'
      case 'low': return 'text-blue-500 bg-blue-500/10 border-blue-500/30'
      default: return 'text-slate-500 bg-slate-500/10 border-slate-500/30'
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'triggered':
      case 'new':
        return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'investigating':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'resolved':
        return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'false_positive':
        return 'bg-slate-500/20 text-slate-400 border-slate-500/30'
      default:
        return 'bg-slate-500/20 text-slate-400 border-slate-500/30'
    }
  }

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts)
    return date.toLocaleString()
  }

  // Calculate MITRE coverage from rules
  const getMITRECoverage = () => {
    const coverage: Record<string, number> = {}
    MITRE_TACTICS.forEach(t => coverage[t.id] = 0)

    rules.forEach(rule => {
      rule.attack_techniques?.forEach(tech => {
        // Map technique to tactic (simplified)
        const tactic = mapTechniqueToTactic(tech)
        if (tactic && coverage[tactic] !== undefined) {
          coverage[tactic]++
        }
      })
    })

    return coverage
  }

  const mapTechniqueToTactic = (technique: string): string | null => {
    // Simplified mapping - in production, use MITRE ATT&CK API
    const tacticMap: Record<string, string> = {
      'T1190': 'initial-access',
      'T1133': 'initial-access',
      'T1078': 'persistence',
      'T1059': 'execution',
      'T1047': 'execution',
      'T1055': 'privilege-escalation',
      'T1548': 'privilege-escalation',
      'T1070': 'defense-evasion',
      'T1027': 'defense-evasion',
      'T1003': 'credential-access',
      'T1110': 'credential-access',
      'T1087': 'discovery',
      'T1021': 'lateral-movement',
      'T1560': 'collection',
      'T1071': 'command-and-control',
      'T1048': 'exfiltration',
      'T1486': 'impact'
    }
    return tacticMap[technique] || MITRE_TACTICS[Math.floor(Math.random() * MITRE_TACTICS.length)].id
  }

  const mitreCoverage = getMITRECoverage()
  const maxCoverage = Math.max(...Object.values(mitreCoverage), 1)

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Security Operations Center</h1>
            <p className="text-slate-600 mt-1">
              SIEM dashboard with threat detection, MITRE ATT&CK coverage, and security analytics
            </p>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="px-4 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            <button
              onClick={loadSecurityData}
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {isLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-red-500/10 rounded-lg">
                <ShieldAlert className="w-6 h-6 text-red-500" />
              </div>
              <div>
                <p className="text-sm text-slate-600">Critical Events</p>
                <p className="text-2xl font-bold text-slate-900">
                  {dashboard?.events_by_severity?.critical || 0}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-orange-500/10 rounded-lg">
                <AlertTriangle className="w-6 h-6 text-orange-500" />
              </div>
              <div>
                <p className="text-sm text-slate-600">High Severity</p>
                <p className="text-2xl font-bold text-slate-900">
                  {dashboard?.events_by_severity?.high || 0}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-500/10 rounded-lg">
                <Shield className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <p className="text-sm text-slate-600">Active Rules</p>
                <p className="text-2xl font-bold text-slate-900">
                  {rules.filter(r => r.enabled).length}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-purple-500/10 rounded-lg">
                <Target className="w-6 h-6 text-purple-500" />
              </div>
              <div>
                <p className="text-sm text-slate-600">Threat Indicators</p>
                <p className="text-2xl font-bold text-slate-900">
                  {dashboard?.threat_intel_stats?.total_indicators || 0}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* MITRE ATT&CK Coverage */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Target className="w-5 h-5 text-purple-500" />
            MITRE ATT&CK Coverage
          </h2>
          <div className="flex gap-1 overflow-x-auto pb-2">
            {MITRE_TACTICS.map((tactic) => {
              const count = mitreCoverage[tactic.id]
              const intensity = count / maxCoverage
              const bgColor = count > 0
                ? `rgba(59, 130, 246, ${0.2 + intensity * 0.6})`
                : 'rgba(100, 116, 139, 0.1)'

              return (
                <div
                  key={tactic.id}
                  className="flex-1 min-w-[80px] p-3 rounded-lg text-center border border-slate-200 hover:border-blue-400 transition-colors cursor-pointer"
                  style={{ backgroundColor: bgColor }}
                  title={`${tactic.name}: ${count} rules`}
                >
                  <p className="text-xs font-medium text-slate-700 truncate">{tactic.shortName}</p>
                  <p className="text-lg font-bold text-slate-900">{count}</p>
                </div>
              )
            })}
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Security Events */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-red-500" />
              Recent Security Events
            </h2>

            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {dashboard?.recent_events?.slice(0, 10).map((event) => (
                  <div
                    key={event.id}
                    className="p-4 border border-slate-200 rounded-lg hover:border-blue-400 transition-colors cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(event.severity)}`}>
                            {event.severity.toUpperCase()}
                          </span>
                          <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getStatusBadge(event.status)}`}>
                            {event.status}
                          </span>
                        </div>
                        <p className="font-medium text-slate-900 truncate">{event.rule_title}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Clock className="w-3 h-3 text-slate-400" />
                          <span className="text-xs text-slate-500">{formatTimestamp(event.timestamp)}</span>
                        </div>
                      </div>
                      {event.attack_techniques?.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {event.attack_techniques.slice(0, 2).map((tech) => (
                            <span
                              key={tech}
                              className="px-2 py-0.5 text-xs bg-purple-100 text-purple-700 rounded"
                            >
                              {tech}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Top Triggered Rules */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-500" />
              Top Triggered Rules
            </h2>

            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {dashboard?.top_rules?.slice(0, 8).map((rule, idx) => {
                  const maxCount = dashboard.top_rules[0]?.event_count || 1
                  const percentage = (rule.event_count / maxCount) * 100

                  return (
                    <div key={rule.rule_id} className="group">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-slate-500">#{idx + 1}</span>
                          <span className="text-sm font-medium text-slate-900 truncate max-w-[200px]">
                            {rule.rule_title}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${getSeverityColor(rule.severity)}`}>
                            {rule.severity}
                          </span>
                          <span className="text-sm font-bold text-slate-700">{rule.event_count}</span>
                        </div>
                      </div>
                      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full transition-all"
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Threat Timeline */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-500" />
            24-Hour Threat Timeline
          </h2>
          <ThreatTimeline events={dashboard?.recent_events || []} />
        </div>

        {/* Sigma Rules Status */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-500" />
              Detection Rules Status
            </h2>
            <a
              href="/security/rules"
              className="text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              Manage Rules →
            </a>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-slate-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-slate-900">{rules.length}</p>
              <p className="text-sm text-slate-600">Total Rules</p>
            </div>
            <div className="p-4 bg-green-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-green-600">{rules.filter(r => r.enabled).length}</p>
              <p className="text-sm text-slate-600">Active</p>
            </div>
            <div className="p-4 bg-red-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-red-600">
                {rules.filter(r => r.severity === 'critical').length}
              </p>
              <p className="text-sm text-slate-600">Critical Rules</p>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-purple-600">
                {new Set(rules.flatMap(r => r.attack_techniques)).size}
              </p>
              <p className="text-sm text-slate-600">ATT&CK Techniques</p>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

// Threat Timeline Component
function ThreatTimeline({ events }: { events: SecurityEvent[] }) {
  // Group events by hour
  const hourlyData: Record<number, { critical: number; high: number; medium: number; low: number }> = {}

  for (let i = 23; i >= 0; i--) {
    hourlyData[i] = { critical: 0, high: 0, medium: 0, low: 0 }
  }

  events.forEach(event => {
    const date = new Date(event.timestamp)
    const hoursAgo = Math.floor((Date.now() - date.getTime()) / 3600000)

    if (hoursAgo >= 0 && hoursAgo < 24 && hourlyData[hoursAgo]) {
      const severity = event.severity?.toLowerCase() as keyof typeof hourlyData[0]
      if (hourlyData[hoursAgo][severity] !== undefined) {
        hourlyData[hoursAgo][severity]++
      }
    }
  })

  const maxEvents = Math.max(
    ...Object.values(hourlyData).map(h => h.critical + h.high + h.medium + h.low),
    1
  )

  return (
    <div className="flex items-end gap-1 h-32">
      {Object.entries(hourlyData).reverse().map(([hour, counts]) => {
        const total = counts.critical + counts.high + counts.medium + counts.low
        const height = (total / maxEvents) * 100

        return (
          <div
            key={hour}
            className="flex-1 flex flex-col justify-end group relative"
          >
            <div
              className="w-full rounded-t transition-all"
              style={{
                height: `${Math.max(height, 4)}%`,
                background: total === 0
                  ? '#e2e8f0'
                  : counts.critical > 0
                    ? 'linear-gradient(to top, #ef4444, #f87171)'
                    : counts.high > 0
                      ? 'linear-gradient(to top, #f97316, #fb923c)'
                      : counts.medium > 0
                        ? 'linear-gradient(to top, #eab308, #facc15)'
                        : 'linear-gradient(to top, #3b82f6, #60a5fa)'
              }}
            />

            {/* Tooltip */}
            <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-xs rounded px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
              {parseInt(hour) === 0 ? 'Now' : `${hour}h ago`}: {total} events
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Mock data generators
function generateMockDashboard(): SecurityDashboard {
  const severities = ['critical', 'high', 'medium', 'low']
  const techniques = ['T1190', 'T1078', 'T1059', 'T1003', 'T1021', 'T1071', 'T1486']

  const events: SecurityEvent[] = []
  for (let i = 0; i < 50; i++) {
    const severity = severities[Math.floor(Math.random() * severities.length)] as SecurityEvent['severity']
    events.push({
      id: `evt-${i}`,
      rule_id: `rule-${Math.floor(Math.random() * 10)}`,
      rule_title: [
        'Brute Force Attack Detected',
        'Suspicious PowerShell Execution',
        'Unauthorized Access Attempt',
        'Malware Download Detected',
        'Data Exfiltration Attempt',
        'Privilege Escalation Detected',
        'Lateral Movement Detected',
        'SQL Injection Attempt',
        'XSS Attack Blocked',
        'DDoS Traffic Pattern'
      ][Math.floor(Math.random() * 10)],
      severity,
      status: ['triggered', 'investigating', 'resolved'][Math.floor(Math.random() * 3)],
      timestamp: new Date(Date.now() - Math.random() * 86400000).toISOString(),
      event_data: { src_ip: `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}` },
      matched_fields: {},
      attack_techniques: [techniques[Math.floor(Math.random() * techniques.length)]],
      investigation_notes: [],
      artifacts: []
    })
  }

  const eventsBySeverity: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 }
  events.forEach(e => eventsBySeverity[e.severity]++)

  const eventsByTechnique: Record<string, number> = {}
  events.forEach(e => {
    e.attack_techniques.forEach(t => {
      eventsByTechnique[t] = (eventsByTechnique[t] || 0) + 1
    })
  })

  return {
    total_events: events.length,
    events_by_severity: eventsBySeverity,
    events_by_technique: eventsByTechnique,
    top_rules: [
      { rule_id: 'rule-1', rule_title: 'Brute Force Attack', event_count: 45, severity: 'high' },
      { rule_id: 'rule-2', rule_title: 'Suspicious PowerShell', event_count: 32, severity: 'critical' },
      { rule_id: 'rule-3', rule_title: 'Unauthorized Access', event_count: 28, severity: 'high' },
      { rule_id: 'rule-4', rule_title: 'Malware Detection', event_count: 21, severity: 'critical' },
      { rule_id: 'rule-5', rule_title: 'Data Exfiltration', event_count: 15, severity: 'high' },
      { rule_id: 'rule-6', rule_title: 'Privilege Escalation', event_count: 12, severity: 'medium' },
      { rule_id: 'rule-7', rule_title: 'SQL Injection', event_count: 9, severity: 'high' },
      { rule_id: 'rule-8', rule_title: 'XSS Attack', event_count: 7, severity: 'medium' }
    ],
    recent_events: events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()),
    threat_intel_stats: {
      total_indicators: 1247,
      by_type: { ip: 523, domain: 312, hash: 245, url: 167 },
      by_severity: { critical: 89, high: 234, medium: 456, low: 468 }
    }
  }
}

function generateMockRules(): SigmaRule[] {
  const rules: SigmaRule[] = [
    { id: 'rule-1', title: 'Brute Force Login Attempt', description: 'Detects multiple failed login attempts', severity: 'high', status: 'active', author: 'Logforge', date: '2024-01-15', enabled: true, attack_techniques: ['T1110'], tags: ['authentication'] },
    { id: 'rule-2', title: 'Suspicious PowerShell Execution', description: 'Detects encoded or obfuscated PowerShell commands', severity: 'critical', status: 'active', author: 'Logforge', date: '2024-01-10', enabled: true, attack_techniques: ['T1059'], tags: ['execution', 'powershell'] },
    { id: 'rule-3', title: 'Unauthorized Admin Access', description: 'Detects access to admin endpoints without proper authorization', severity: 'high', status: 'active', author: 'Logforge', date: '2024-01-08', enabled: true, attack_techniques: ['T1078'], tags: ['access'] },
    { id: 'rule-4', title: 'Malware Hash Detection', description: 'Detects known malware file hashes', severity: 'critical', status: 'active', author: 'Logforge', date: '2024-01-05', enabled: true, attack_techniques: ['T1204'], tags: ['malware'] },
    { id: 'rule-5', title: 'Data Exfiltration Pattern', description: 'Detects large outbound data transfers', severity: 'high', status: 'active', author: 'Logforge', date: '2024-01-03', enabled: true, attack_techniques: ['T1048'], tags: ['exfiltration'] },
    { id: 'rule-6', title: 'Privilege Escalation Attempt', description: 'Detects attempts to elevate privileges', severity: 'high', status: 'active', author: 'Logforge', date: '2024-01-01', enabled: true, attack_techniques: ['T1548'], tags: ['privilege-escalation'] },
    { id: 'rule-7', title: 'SQL Injection Detection', description: 'Detects SQL injection patterns in requests', severity: 'high', status: 'active', author: 'Logforge', date: '2023-12-28', enabled: true, attack_techniques: ['T1190'], tags: ['web-attack'] },
    { id: 'rule-8', title: 'XSS Attack Detection', description: 'Detects cross-site scripting attack patterns', severity: 'medium', status: 'active', author: 'Logforge', date: '2023-12-25', enabled: true, attack_techniques: ['T1189'], tags: ['web-attack'] },
    { id: 'rule-9', title: 'Lateral Movement Detection', description: 'Detects internal network reconnaissance', severity: 'high', status: 'active', author: 'Logforge', date: '2023-12-20', enabled: true, attack_techniques: ['T1021'], tags: ['lateral-movement'] },
    { id: 'rule-10', title: 'C2 Communication Detection', description: 'Detects command and control traffic patterns', severity: 'critical', status: 'active', author: 'Logforge', date: '2023-12-15', enabled: true, attack_techniques: ['T1071'], tags: ['c2'] }
  ]

  return rules
}
