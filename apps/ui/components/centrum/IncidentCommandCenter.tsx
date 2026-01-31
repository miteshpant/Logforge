'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import { apiClient } from '@/lib/api'
import {
  AlertTriangle,
  AlertCircle,
  Activity,
  Clock,
  ExternalLink,
  ChevronRight,
  Zap,
  DollarSign,
  FileText,
  GitBranch,
  Lightbulb,
  CheckCircle,
  RefreshCw
} from 'lucide-react'

interface Incident {
  id: string
  title: string
  description: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  status: 'triggered' | 'acknowledged' | 'investigating' | 'resolved'
  service: string
  triggered_at: string
  acknowledged_at?: string
  resolved_at?: string
  related_logs: number
  related_traces: number
  related_alerts: number
  ai_root_cause?: string
  ai_confidence?: number
  estimated_cost_impact?: number
  assignee?: string
  tags: string[]
}

interface IncidentCommandCenterProps {
  isLoading?: boolean
  timeRange?: string
}

const SEVERITY_CONFIG = {
  critical: {
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    icon: AlertCircle,
    pulse: true
  },
  high: {
    color: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/30',
    icon: AlertTriangle,
    pulse: false
  },
  medium: {
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    icon: AlertTriangle,
    pulse: false
  },
  low: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    icon: Activity,
    pulse: false
  }
}

const STATUS_CONFIG = {
  triggered: { color: 'text-red-400', bg: 'bg-red-500/20', label: 'Triggered' },
  acknowledged: { color: 'text-yellow-400', bg: 'bg-yellow-500/20', label: 'Acknowledged' },
  investigating: { color: 'text-blue-400', bg: 'bg-blue-500/20', label: 'Investigating' },
  resolved: { color: 'text-green-400', bg: 'bg-green-500/20', label: 'Resolved' }
}

export default function IncidentCommandCenter({ isLoading: externalLoading, timeRange }: IncidentCommandCenterProps) {
  const router = useRouter()
  const { getApiTimeRange, currentTimeRange } = useTimeRange()
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [filter, setFilter] = useState<'all' | 'active' | 'critical'>('active')

  useEffect(() => {
    loadIncidents()
  }, [currentTimeRange.value])

  const loadIncidents = async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()
      const response = await apiClient.get('/v1/alerts', {
        status: 'triggered',
        limit: 20,
        start_time,
        end_time
      })

      if (response?.data?.alerts && response.data.alerts.length > 0) {
        setIncidents(response.data.alerts.map((alert: any) => ({
          id: alert.alert_id || alert.id,
          title: alert.rule_name || alert.title || alert.name || 'Unnamed Alert',
          description: alert.message || alert.description || '',
          severity: alert.severity || 'medium',
          status: alert.status === 'active' ? 'triggered' : (alert.status || 'triggered'),
          service: alert.details?.service || alert.service || 'unknown',
          triggered_at: alert.triggered_at || alert.created_at,
          acknowledged_at: alert.acknowledged_at,
          resolved_at: alert.resolved_at,
          related_logs: alert.details?.related_logs || 0,
          related_traces: alert.details?.related_traces || 0,
          related_alerts: alert.details?.related_alerts || 0,
          ai_root_cause: alert.details?.ai_root_cause,
          ai_confidence: alert.details?.ai_confidence,
          estimated_cost_impact: alert.details?.cost_impact,
          assignee: alert.details?.assignee || alert.assignee,
          tags: alert.details?.tags || alert.tags || []
        })))
      } else {
        setIncidents([])
      }
    } catch (error) {
      console.error('Failed to load incidents:', error)
      setIncidents([])
    } finally {
      setIsLoading(false)
    }
  }

  const filteredIncidents = incidents.filter(inc => {
    if (filter === 'active') return inc.status !== 'resolved'
    if (filter === 'critical') return inc.severity === 'critical' && inc.status !== 'resolved'
    return true
  })

  const formatTimeAgo = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    if (hours > 0) return `${hours}h ${minutes % 60}m ago`
    return `${minutes}m ago`
  }

  const formatCurrency = (amount: number) => {
    if (amount >= 1000) return `$${(amount / 1000).toFixed(1)}k`
    return `$${amount}`
  }

  const navigateToLogs = (service: string, timestamp: string) => {
    const startTime = new Date(new Date(timestamp).getTime() - 3600000).toISOString()
    router.push(`/logs?service=${service}&start_time=${startTime}`)
  }

  const navigateToTraces = (service: string, timestamp: string) => {
    const startTime = new Date(new Date(timestamp).getTime() - 3600000).toISOString()
    router.push(`/apm/traces?service=${service}&start_time=${startTime}`)
  }

  const navigateToAlert = (incidentId: string) => {
    router.push(`/alerts/instances?id=${incidentId}`)
  }

  const stats = {
    total: incidents.length,
    critical: incidents.filter(i => i.severity === 'critical' && i.status !== 'resolved').length,
    active: incidents.filter(i => i.status !== 'resolved').length,
    totalCostImpact: incidents
      .filter(i => i.status !== 'resolved')
      .reduce((sum, i) => sum + (i.estimated_cost_impact || 0), 0)
  }

  if (isLoading || externalLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
        <div className="flex items-center justify-center h-48">
          <div className="text-slate-400 text-sm animate-pulse">Loading incidents...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Header */}
      <div className="relative z-10 p-4 border-b border-white/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-red-500 to-orange-600 flex items-center justify-center shadow-md shadow-red-500/30">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Incident Command Center</h2>
              <p className="text-xs text-slate-400">
                {stats.active > 0
                  ? `${stats.active} active incident${stats.active !== 1 ? 's' : ''}`
                  : 'No active incidents'
                }
                {stats.totalCostImpact > 0 && ` • ${formatCurrency(stats.totalCostImpact)} estimated impact`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex bg-slate-800/50 rounded-lg p-0.5">
              {(['active', 'critical', 'all'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    filter === f
                      ? 'bg-blue-500/20 text-blue-400'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
            <button
              onClick={loadIncidents}
              className="p-2 rounded-lg bg-slate-800/50 hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Summary Stats - only show if there are incidents */}
        {incidents.length > 0 && (
          <div className="flex gap-4 mt-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20">
              <AlertCircle className="w-4 h-4 text-red-400" />
              <span className="text-sm font-semibold text-red-400">{stats.critical}</span>
              <span className="text-xs text-slate-400">Critical</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-orange-500/10 border border-orange-500/20">
              <Activity className="w-4 h-4 text-orange-400" />
              <span className="text-sm font-semibold text-orange-400">{stats.active}</span>
              <span className="text-xs text-slate-400">Active</span>
            </div>
            {stats.totalCostImpact > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-500/10 border border-green-500/20">
                <DollarSign className="w-4 h-4 text-green-400" />
                <span className="text-sm font-semibold text-green-400">{formatCurrency(stats.totalCostImpact)}</span>
                <span className="text-xs text-slate-400">Est. Impact</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Incident List */}
      <div className="relative z-10 divide-y divide-white/5 max-h-[400px] overflow-y-auto">
        {filteredIncidents.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-slate-400">
            <div className="text-center">
              <CheckCircle className="w-10 h-10 mx-auto mb-2 text-green-400" />
              <p className="text-sm">No active incidents</p>
              <p className="text-xs text-slate-500">All systems operational</p>
            </div>
          </div>
        ) : (
          filteredIncidents.map((incident) => {
            const severityConfig = SEVERITY_CONFIG[incident.severity]
            const statusConfig = STATUS_CONFIG[incident.status]
            const SeverityIcon = severityConfig.icon

            return (
              <div
                key={incident.id}
                className={`p-4 hover:bg-white/[0.02] cursor-pointer transition-colors ${
                  selectedIncident?.id === incident.id ? 'bg-white/[0.03]' : ''
                }`}
                onClick={() => setSelectedIncident(selectedIncident?.id === incident.id ? null : incident)}
              >
                {/* Incident Header */}
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg ${severityConfig.bg} ${severityConfig.border} border`}>
                    <SeverityIcon className={`w-5 h-5 ${severityConfig.color} ${severityConfig.pulse ? 'animate-pulse' : ''}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-sm font-semibold text-white truncate">{incident.title}</h3>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusConfig.bg} ${statusConfig.color}`}>
                        {statusConfig.label}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityConfig.bg} ${severityConfig.color}`}>
                        {incident.severity.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1 truncate">{incident.description}</p>
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatTimeAgo(incident.triggered_at)}
                      </span>
                      <span className="px-2 py-0.5 bg-slate-800 rounded text-slate-400">
                        {incident.service}
                      </span>
                      {incident.assignee && (
                        <span className="text-slate-400">→ {incident.assignee}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-right">
                    {incident.estimated_cost_impact && incident.estimated_cost_impact > 0 && (
                      <div>
                        <p className="text-sm font-bold text-red-400">{formatCurrency(incident.estimated_cost_impact)}</p>
                        <p className="text-[10px] text-slate-500">Est. Impact</p>
                      </div>
                    )}
                    <ChevronRight className={`w-5 h-5 text-slate-500 transition-transform ${
                      selectedIncident?.id === incident.id ? 'rotate-90' : ''
                    }`} />
                  </div>
                </div>

                {/* Expanded Details */}
                {selectedIncident?.id === incident.id && (
                  <div className="mt-4 pt-4 border-t border-white/5 space-y-4">
                    {/* AI Root Cause Analysis */}
                    {incident.ai_root_cause && (
                      <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
                        <div className="flex items-center gap-2 mb-2">
                          <Lightbulb className="w-4 h-4 text-purple-400" />
                          <span className="text-sm font-semibold text-purple-400">AI Root Cause Analysis</span>
                          {incident.ai_confidence && (
                            <span className="ml-auto text-xs text-purple-300 bg-purple-500/20 px-2 py-0.5 rounded">
                              {incident.ai_confidence}% confidence
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-slate-300">{incident.ai_root_cause}</p>
                      </div>
                    )}

                    {/* Quick Actions - Drill Down */}
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500 mr-2">Drill Down:</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          navigateToLogs(incident.service, incident.triggered_at)
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:bg-blue-500/20 transition-colors text-xs"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        Logs ({incident.related_logs.toLocaleString()})
                        <ExternalLink className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          navigateToTraces(incident.service, incident.triggered_at)
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/20 transition-colors text-xs"
                      >
                        <GitBranch className="w-3.5 h-3.5" />
                        Traces ({incident.related_traces})
                        <ExternalLink className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          navigateToAlert(incident.id)
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-500/10 border border-orange-500/20 text-orange-400 hover:bg-orange-500/20 transition-colors text-xs"
                      >
                        <AlertTriangle className="w-3.5 h-3.5" />
                        Related Alerts ({incident.related_alerts})
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>

                    {/* Tags */}
                    {incident.tags.length > 0 && (
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs text-slate-500">Tags:</span>
                        {incident.tags.map((tag, idx) => (
                          <span key={idx} className="px-2 py-0.5 bg-slate-800 rounded text-xs text-slate-400">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2 pt-2">
                      {incident.status === 'triggered' && (
                        <button className="px-4 py-2 rounded-lg bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 text-sm font-medium transition-colors">
                          Acknowledge
                        </button>
                      )}
                      {incident.status !== 'resolved' && (
                        <button className="px-4 py-2 rounded-lg bg-green-500/20 text-green-400 hover:bg-green-500/30 text-sm font-medium transition-colors">
                          Resolve
                        </button>
                      )}
                      <button className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 text-sm font-medium transition-colors">
                        View Full Details
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Footer */}
      <div className="relative z-10 p-3 border-t border-white/5 flex items-center justify-between bg-slate-900/50">
        <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/3">
          <Clock className="w-3 h-3 text-slate-400" />
          <span className="text-[10px] text-slate-400 font-mono">
            Updated {new Date().toLocaleTimeString()}
          </span>
        </div>
        <button
          onClick={() => router.push('/alerts/instances')}
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          View All Incidents
          <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}
