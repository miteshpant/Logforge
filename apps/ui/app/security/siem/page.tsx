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
  Zap,
  CheckCircle,
  Search,
  XCircle,
  Eye,
  X
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

interface MitreCoverageTechnique {
  technique_id: string
  technique_name: string
  tactic: string
  tactics: string[]
  rule_count: number
  enabled_rule_count: number
  has_fixtures: boolean
  last_detection_at: string | null
}

interface MitreCoverage {
  techniques: MitreCoverageTechnique[]
  awaiting_content: string[]
  summary: {
    total_techniques: number
    covered_techniques: number
    awaiting_content: number
    total_rules: number
  }
}

interface TacticCoverage {
  covered: number
  total: number
  enabledRules: number
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
  const [coverage, setCoverage] = useState<MitreCoverage | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all')
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const handleEventAction = async (eventId: string, action: 'acknowledge' | 'investigate' | 'resolve' | 'false-positive') => {
    setActionLoading(`${eventId}-${action}`)
    try {
      const body = action === 'resolve' || action === 'false-positive'
        ? { resolution_notes: `Marked as ${action} from SIEM dashboard` }
        : { notes: `Action taken from SIEM dashboard` }

      await apiClient.post(`/v1/security/${eventId}/${action}`, body)

      // Update event status in local state
      const statusMap: Record<string, string> = {
        'acknowledge': 'investigating',
        'investigate': 'investigating',
        'resolve': 'resolved',
        'false-positive': 'false_positive'
      }
      if (dashboard) {
        const updatedEvents = dashboard.recent_events.map(e =>
          e.id === eventId ? { ...e, status: statusMap[action] } : e
        )
        setDashboard({ ...dashboard, recent_events: updatedEvents })
        if (selectedEvent?.id === eventId) {
          setSelectedEvent({ ...selectedEvent, status: statusMap[action] })
        }
      }
    } catch (err) {
      console.error(`Failed to ${action} event:`, err)
    } finally {
      setActionLoading(null)
    }
  }

  const loadSecurityData = async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const [dashboardRes, rulesRes, coverageRes] = await Promise.allSettled([
        apiClient.get<SecurityDashboard>('/v1/security/dashboard', {
          params: { start_time, end_time }
        }),
        // LF-016: paginated envelope {rules: [...], total, limit, offset}
        apiClient.get<{ rules: SigmaRule[]; total: number; limit: number; offset: number }>(
          '/v1/security/sigma-rules',
          { params: { limit: 500, offset: 0 } }
        ),
        // Server-side ATT&CK matrix: technique -> tactic mapping and
        // fixture-tested coverage come from the API, not the browser.
        apiClient.get<MitreCoverage>('/v1/security/mitre-coverage')
      ])

      if (coverageRes.status === 'fulfilled') {
        const data: any = coverageRes.value?.data || coverageRes.value
        setCoverage(Array.isArray(data?.techniques) ? (data as MitreCoverage) : null)
      } else {
        setCoverage(null)
      }

      if (dashboardRes.status === 'fulfilled') {
        const data = dashboardRes.value?.data || dashboardRes.value
        if (data) {
          setDashboard(data as SecurityDashboard)
        } else {
          setDashboard(null)
        }
      } else {
        setDashboard(null)
      }

      if (rulesRes.status === 'fulfilled') {
        const data: any = rulesRes.value?.data || rulesRes.value
        if (Array.isArray(data?.rules)) {
          setRules(data.rules)
        } else if (Array.isArray(data)) {
          // Pre-LF-016 bare-array shape
          setRules(data)
        } else {
          setRules([])
        }
      } else {
        setRules([])
      }
    } catch (error) {
      console.error('Failed to load security data:', error)
      setDashboard(null)
      setRules([])
      setCoverage(null)
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

  // Per-tactic coverage from GET /v1/security/mitre-coverage. A technique
  // counts as covered only when an enabled, fixture-tested rule detects it.
  // Techniques in several tactics count toward each of them.
  const getMITRECoverage = (): Record<string, TacticCoverage> => {
    const byTactic: Record<string, TacticCoverage> = {}
    MITRE_TACTICS.forEach(t => { byTactic[t.id] = { covered: 0, total: 0, enabledRules: 0 } })
    coverage?.techniques.forEach(tech => {
      const covered = tech.has_fixtures && tech.enabled_rule_count > 0
      tech.tactics.forEach(tactic => {
        const entry = byTactic[tactic]
        if (!entry) return
        entry.total++
        entry.enabledRules += tech.enabled_rule_count
        if (covered) entry.covered++
      })
    })
    return byTactic
  }

  const mitreCoverage = getMITRECoverage()
  const maxCoverage = Math.max(
    ...MITRE_TACTICS.map(t => mitreCoverage[t.id].covered),
    1
  )
  // Techniques that rules reference but the ATT&CK catalogue has no tactic for
  const unmappedCount = coverage?.techniques.filter(t => t.rule_count > 0 && t.tactics.length === 0).length ?? 0
  const awaitingCount = coverage?.summary.awaiting_content ?? 0

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white">Security Operations Center</h1>
            <p className="text-slate-400 mt-1">
              SIEM dashboard with threat detection, MITRE ATT&CK coverage, and security analytics
            </p>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="px-4 py-2 bg-slate-800 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500"
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
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-red-500/10 rounded-lg">
                <ShieldAlert className="w-6 h-6 text-red-500" />
              </div>
              <div>
                <p className="text-sm text-slate-400">Critical Events</p>
                <p className="text-2xl font-bold text-white">
                  {dashboard?.events_by_severity?.critical || 0}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-orange-500/10 rounded-lg">
                <AlertTriangle className="w-6 h-6 text-orange-500" />
              </div>
              <div>
                <p className="text-sm text-slate-400">High Severity</p>
                <p className="text-2xl font-bold text-white">
                  {dashboard?.events_by_severity?.high || 0}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-500/10 rounded-lg">
                <Shield className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <p className="text-sm text-slate-400">Active Rules</p>
                <p className="text-2xl font-bold text-white">
                  {rules.filter(r => r.enabled).length}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-purple-500/10 rounded-lg">
                <Target className="w-6 h-6 text-purple-500" />
              </div>
              <div>
                <p className="text-sm text-slate-400">Threat Indicators</p>
                <p className="text-2xl font-bold text-white">
                  {dashboard?.threat_intel_stats?.total_indicators || 0}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* MITRE ATT&CK Coverage */}
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Target className="w-5 h-5 text-purple-500" />
            MITRE ATT&CK Coverage
          </h2>
          <div className="flex gap-1 overflow-x-auto pb-2">
            {MITRE_TACTICS.map((tactic) => {
              const { covered: count, total, enabledRules } = mitreCoverage[tactic.id]
              const intensity = count / maxCoverage
              const bgColor = count > 0
                ? `rgba(59, 130, 246, ${0.2 + intensity * 0.6})`
                : 'rgba(100, 116, 139, 0.1)'

              return (
                <div
                  key={tactic.id}
                  className="flex-1 min-w-[80px] p-3 rounded-lg text-center border border-white/5 hover:border-blue-400 transition-colors cursor-pointer"
                  style={{ backgroundColor: bgColor }}
                  title={`${tactic.name}: ${count} of ${total} techniques covered by fixture-tested rules (${enabledRules} enabled rule${enabledRules === 1 ? '' : 's'})`}
                >
                  <p className="text-xs font-medium text-slate-300 truncate">{tactic.shortName}</p>
                  <p className="text-lg font-bold text-white">{count}</p>
                </div>
              )
            })}
            {unmappedCount > 0 && (
              <div
                className="flex-1 min-w-[80px] p-3 rounded-lg text-center border border-dashed border-slate-500/40 bg-slate-500/5"
                title={`Unmapped: ${unmappedCount} technique${unmappedCount === 1 ? '' : 's'} referenced by rules but not in the ATT&CK catalogue — excluded from coverage`}
              >
                <p className="text-xs font-medium text-slate-500 truncate italic">Unmapped</p>
                <p className="text-lg font-bold text-slate-400">{unmappedCount}</p>
              </div>
            )}
          </div>
          {unmappedCount > 0 && (
            <p className="text-xs text-slate-500 mt-2">
              {unmappedCount} technique{unmappedCount === 1 ? '' : 's'} referenced by rules could not be mapped to a tactic and {unmappedCount === 1 ? 'is' : 'are'} excluded from coverage.
            </p>
          )}
          {coverage ? (
            <p className="text-xs text-slate-500 mt-2">
              {coverage.summary.covered_techniques} of {coverage.summary.total_techniques} techniques covered by enabled, fixture-tested rules
              {awaitingCount > 0 && ` · ${awaitingCount} awaiting content (rules without verified fixtures)`}
            </p>
          ) : (
            <p className="text-xs text-slate-500 mt-2">Coverage unavailable</p>
          )}
        </div>

        {/* Severity Distribution */}
        {dashboard?.events_by_severity && (
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-red-500" />
              Event Severity Distribution
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {['critical', 'high', 'medium', 'low'].map(sev => {
                const count = dashboard.events_by_severity[sev] || 0
                const total = Object.values(dashboard.events_by_severity).reduce((s, v) => s + v, 0) || 1
                const pct = ((count / total) * 100).toFixed(1)
                const colors: Record<string, { bg: string; bar: string; text: string }> = {
                  critical: { bg: 'bg-red-500/10', bar: 'bg-red-500', text: 'text-red-400' },
                  high: { bg: 'bg-orange-500/10', bar: 'bg-orange-500', text: 'text-orange-400' },
                  medium: { bg: 'bg-yellow-500/10', bar: 'bg-yellow-500', text: 'text-yellow-400' },
                  low: { bg: 'bg-blue-500/10', bar: 'bg-blue-500', text: 'text-blue-400' }
                }
                const c = colors[sev]
                return (
                  <div key={sev} className={`p-4 ${c.bg} rounded-lg`}>
                    <p className={`text-sm font-medium capitalize ${c.text}`}>{sev}</p>
                    <p className="text-2xl font-bold text-white mt-1">{count}</p>
                    <div className="mt-2 h-1.5 bg-white/60 rounded-full overflow-hidden">
                      <div className={`h-full ${c.bar} rounded-full`} style={{ width: `${pct}%` }} />
                    </div>
                    <p className="text-xs text-slate-500 mt-1">{pct}% of total</p>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Security Events */}
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-red-500" />
              Recent Security Events
            </h2>

            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="h-16 bg-slate-700 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : !dashboard?.recent_events?.length ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <ShieldAlert className="w-10 h-10 text-slate-300 mb-3" />
                <p className="text-sm font-medium text-slate-500">No security events found</p>
                <p className="text-xs text-slate-400 mt-1">Events will appear here when detected by your rules</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {dashboard.recent_events.slice(0, 10).map((event) => (
                  <div
                    key={event.id}
                    className={`p-4 border rounded-lg transition-colors cursor-pointer ${
                      selectedEvent?.id === event.id ? 'border-blue-500 bg-blue-500/10' : 'border-white/5 hover:border-blue-400'
                    }`}
                    onClick={() => setSelectedEvent(event)}
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
                        <p className="font-medium text-white truncate">{event.rule_title}</p>
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
                              className="px-2 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded"
                            >
                              {tech}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Quick Action Buttons */}
                    {event.status !== 'resolved' && event.status !== 'false_positive' && (
                      <div className="flex items-center gap-2 mt-3 pt-2 border-t border-white/5">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleEventAction(event.id, 'acknowledge') }}
                          disabled={actionLoading === `${event.id}-acknowledge`}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 rounded transition-colors disabled:opacity-50"
                        >
                          <Eye className="w-3 h-3" />
                          Ack
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleEventAction(event.id, 'investigate') }}
                          disabled={actionLoading === `${event.id}-investigate`}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 rounded transition-colors disabled:opacity-50"
                        >
                          <Search className="w-3 h-3" />
                          Investigate
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleEventAction(event.id, 'resolve') }}
                          disabled={actionLoading === `${event.id}-resolve`}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-green-500/10 text-green-400 hover:bg-green-500/20 rounded transition-colors disabled:opacity-50"
                        >
                          <CheckCircle className="w-3 h-3" />
                          Resolve
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleEventAction(event.id, 'false-positive') }}
                          disabled={actionLoading === `${event.id}-false-positive`}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-slate-500/10 text-slate-400 hover:bg-slate-700 rounded transition-colors disabled:opacity-50"
                        >
                          <XCircle className="w-3 h-3" />
                          False +
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Top Triggered Rules */}
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-500" />
              Top Triggered Rules
            </h2>

            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="h-12 bg-slate-700 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : !dashboard?.top_rules?.length ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Zap className="w-10 h-10 text-slate-300 mb-3" />
                <p className="text-sm font-medium text-slate-500">No triggered rules</p>
                <p className="text-xs text-slate-400 mt-1">Rule triggers will appear here once detection rules match incoming events</p>
              </div>
            ) : (
              <div className="space-y-3">
                {dashboard.top_rules.slice(0, 8).map((rule, idx) => {
                  const maxCount = dashboard.top_rules[0]?.event_count || 1
                  const percentage = (rule.event_count / maxCount) * 100

                  return (
                    <div key={rule.rule_id} className="group">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-slate-500">#{idx + 1}</span>
                          <span className="text-sm font-medium text-white truncate max-w-[200px]">
                            {rule.rule_title}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${getSeverityColor(rule.severity)}`}>
                            {rule.severity}
                          </span>
                          <span className="text-sm font-bold text-slate-300">{rule.event_count}</span>
                        </div>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
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
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-500" />
            24-Hour Threat Timeline
          </h2>
          <ThreatTimeline events={dashboard?.recent_events || []} />
        </div>

        {/* Sigma Rules Status */}
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-500" />
              Detection Rules Status
            </h2>
            <a
              href="/security/rules"
              className="text-sm text-blue-400 hover:text-blue-300 font-medium"
            >
              Manage Rules →
            </a>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-slate-500/10 rounded-lg text-center">
              <p className="text-2xl font-bold text-white">{rules.length}</p>
              <p className="text-sm text-slate-400">Total Rules</p>
            </div>
            <div className="p-4 bg-green-500/10 rounded-lg text-center">
              <p className="text-2xl font-bold text-green-400">{rules.filter(r => r.enabled).length}</p>
              <p className="text-sm text-slate-400">Active</p>
            </div>
            <div className="p-4 bg-red-500/10 rounded-lg text-center">
              <p className="text-2xl font-bold text-red-400">
                {rules.filter(r => r.severity === 'critical').length}
              </p>
              <p className="text-sm text-slate-400">Critical Rules</p>
            </div>
            <div className="p-4 bg-purple-500/10 rounded-lg text-center">
              <p className="text-2xl font-bold text-purple-400">
                {new Set(rules.flatMap(r => r.attack_techniques)).size}
              </p>
              <p className="text-sm text-slate-400">ATT&CK Techniques</p>
            </div>
          </div>
        </div>
        {/* Event Detail Panel */}
        {selectedEvent && (
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Eye className="w-5 h-5 text-blue-500" />
                Event Detail
              </h2>
              <button
                onClick={() => setSelectedEvent(null)}
                className="p-1 hover:bg-slate-700 rounded-lg"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Rule</span>
                  <span className="text-sm font-medium text-white">{selectedEvent.rule_title}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Event ID</span>
                  <code className="text-xs bg-slate-700 px-2 py-1 rounded font-mono">{selectedEvent.id}</code>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Severity</span>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(selectedEvent.severity)}`}>
                    {selectedEvent.severity.toUpperCase()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Status</span>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getStatusBadge(selectedEvent.status)}`}>
                    {selectedEvent.status}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Timestamp</span>
                  <span className="text-sm text-white">{formatTimestamp(selectedEvent.timestamp)}</span>
                </div>
                {selectedEvent.kill_chain_phase && (
                  <div className="flex justify-between">
                    <span className="text-sm text-slate-500">Kill Chain Phase</span>
                    <span className="text-sm text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">{selectedEvent.kill_chain_phase}</span>
                  </div>
                )}
                {selectedEvent.assigned_to && (
                  <div className="flex justify-between">
                    <span className="text-sm text-slate-500">Assigned To</span>
                    <span className="text-sm text-white">{selectedEvent.assigned_to}</span>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                {selectedEvent.attack_techniques?.length > 0 && (
                  <div>
                    <p className="text-sm text-slate-500 mb-2">MITRE ATT&CK Techniques</p>
                    <div className="flex flex-wrap gap-2">
                      {selectedEvent.attack_techniques.map(tech => (
                        <span key={tech} className="px-2 py-1 text-xs bg-purple-500/20 text-purple-400 rounded font-mono">
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedEvent.matched_fields && Object.keys(selectedEvent.matched_fields).length > 0 && (
                  <div>
                    <p className="text-sm text-slate-500 mb-2">Matched Fields</p>
                    <div className="bg-slate-500/10 rounded-lg p-3 max-h-32 overflow-y-auto">
                      <pre className="text-xs text-slate-300 whitespace-pre-wrap">
                        {JSON.stringify(selectedEvent.matched_fields, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}

                {selectedEvent.investigation_notes?.length > 0 && (
                  <div>
                    <p className="text-sm text-slate-500 mb-2">Investigation Notes</p>
                    <div className="space-y-1">
                      {selectedEvent.investigation_notes.map((note, idx) => (
                        <p key={idx} className="text-xs text-slate-300 bg-slate-500/10 px-3 py-2 rounded">{note}</p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
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
                  ? '#334155'
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

