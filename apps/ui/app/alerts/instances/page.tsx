'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Bell,
  AlertTriangle,
  CheckCircle,
  Clock,
  Eye,
  MessageSquare,
  UserCheck,
  XCircle,
  ChevronRight,
  Filter,
  Search,
  RefreshCw,
  ExternalLink,
  Zap,
  TrendingUp
} from 'lucide-react'

interface AlertInstance {
  id: string
  rule_id: string
  rule_name: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  status: 'triggered' | 'acknowledged' | 'resolved' | 'suppressed'
  triggered_at: string
  acknowledged_at?: string
  resolved_at?: string
  acknowledged_by?: string
  resolved_by?: string
  trigger_data: {
    matched_count: number
    sample_values: any[]
    threshold?: number
    actual_value?: number
  }
  related_logs_count: number
  related_traces_count: number
  notes: string[]
}

// Mock data
const generateMockInstances = (): AlertInstance[] => {
  const now = Date.now()
  return [
    {
      id: 'alert-001',
      rule_id: 'rule-1',
      rule_name: 'High Error Rate',
      severity: 'critical',
      status: 'triggered',
      triggered_at: new Date(now - 300000).toISOString(),
      trigger_data: {
        matched_count: 156,
        sample_values: [{ error: 'Connection timeout', service: 'payment-service' }],
        threshold: 5,
        actual_value: 12.5
      },
      related_logs_count: 1250,
      related_traces_count: 45,
      notes: []
    },
    {
      id: 'alert-002',
      rule_id: 'rule-2',
      rule_name: 'API Latency Spike',
      severity: 'high',
      status: 'acknowledged',
      triggered_at: new Date(now - 1800000).toISOString(),
      acknowledged_at: new Date(now - 1200000).toISOString(),
      acknowledged_by: 'john@company.com',
      trigger_data: {
        matched_count: 89,
        sample_values: [{ endpoint: '/api/v1/checkout', latency: 3200 }],
        threshold: 2000,
        actual_value: 3200
      },
      related_logs_count: 890,
      related_traces_count: 89,
      notes: ['Investigating database connection pool issue']
    },
    {
      id: 'alert-003',
      rule_id: 'rule-3',
      rule_name: 'Anomalous Login Pattern',
      severity: 'high',
      status: 'resolved',
      triggered_at: new Date(now - 7200000).toISOString(),
      acknowledged_at: new Date(now - 6900000).toISOString(),
      resolved_at: new Date(now - 5400000).toISOString(),
      acknowledged_by: 'security@company.com',
      resolved_by: 'security@company.com',
      trigger_data: {
        matched_count: 23,
        sample_values: [{ user: 'user@example.com', locations: ['US', 'RU', 'CN'] }]
      },
      related_logs_count: 230,
      related_traces_count: 0,
      notes: ['False positive - user traveling', 'Updated baseline for this user']
    },
    {
      id: 'alert-004',
      rule_id: 'rule-4',
      rule_name: 'Database Connection Pool Exhaustion',
      severity: 'critical',
      status: 'resolved',
      triggered_at: new Date(now - 10800000).toISOString(),
      acknowledged_at: new Date(now - 10500000).toISOString(),
      resolved_at: new Date(now - 9000000).toISOString(),
      acknowledged_by: 'dba@company.com',
      resolved_by: 'dba@company.com',
      trigger_data: {
        matched_count: 1,
        sample_values: [{ pool: 'primary-db', available: 2, max: 100 }],
        threshold: 10,
        actual_value: 2
      },
      related_logs_count: 450,
      related_traces_count: 120,
      notes: ['Increased pool size from 100 to 200', 'Root cause: slow query in reports module']
    },
    {
      id: 'alert-005',
      rule_id: 'rule-1',
      rule_name: 'High Error Rate',
      severity: 'critical',
      status: 'suppressed',
      triggered_at: new Date(now - 600000).toISOString(),
      trigger_data: {
        matched_count: 45,
        sample_values: [{ error: 'Connection timeout', service: 'payment-service' }],
        threshold: 5,
        actual_value: 8.2
      },
      related_logs_count: 450,
      related_traces_count: 12,
      notes: ['Suppressed - related to alert-001']
    }
  ]
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  info: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
}

const STATUS_COLORS: Record<string, string> = {
  triggered: 'bg-red-500/20 text-red-400',
  acknowledged: 'bg-yellow-500/20 text-yellow-400',
  resolved: 'bg-green-500/20 text-green-400',
  suppressed: 'bg-gray-500/20 text-gray-400'
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  triggered: <AlertTriangle className="w-4 h-4" />,
  acknowledged: <Eye className="w-4 h-4" />,
  resolved: <CheckCircle className="w-4 h-4" />,
  suppressed: <XCircle className="w-4 h-4" />
}

export default function AlertInstancesPage() {
  const { getApiTimeRange } = useTimeRange()
  const [instances, setInstances] = useState<AlertInstance[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedInstance, setSelectedInstance] = useState<AlertInstance | null>(null)
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterSeverity, setFilterSeverity] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)

  const loadInstances = useCallback(async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<{ instances: AlertInstance[] }>('/v1/alerts/instances', {
        start_time,
        end_time,
        status: filterStatus !== 'all' ? filterStatus : undefined,
        severity: filterSeverity !== 'all' ? filterSeverity : undefined
      })

      if (response?.data?.instances) {
        setInstances(response.data.instances)
      } else {
        setInstances(generateMockInstances())
      }
    } catch (error) {
      console.error('Failed to load alert instances:', error)
      setInstances(generateMockInstances())
    } finally {
      setIsLoading(false)
    }
  }, [getApiTimeRange, filterStatus, filterSeverity])

  useEffect(() => {
    loadInstances()
  }, [loadInstances])

  const handleRefresh = async () => {
    setIsRefreshing(true)
    await loadInstances()
    setIsRefreshing(false)
  }

  const acknowledgeAlert = async (instanceId: string) => {
    try {
      await apiClient.post(`/v1/alerts/instances/${instanceId}/acknowledge`)
      setInstances(instances.map(i =>
        i.id === instanceId
          ? { ...i, status: 'acknowledged' as const, acknowledged_at: new Date().toISOString(), acknowledged_by: 'current-user' }
          : i
      ))
    } catch (error) {
      console.error('Failed to acknowledge alert:', error)
      // Still update UI for demo
      setInstances(instances.map(i =>
        i.id === instanceId
          ? { ...i, status: 'acknowledged' as const, acknowledged_at: new Date().toISOString(), acknowledged_by: 'current-user' }
          : i
      ))
    }
  }

  const resolveAlert = async (instanceId: string) => {
    try {
      await apiClient.post(`/v1/alerts/instances/${instanceId}/resolve`)
      setInstances(instances.map(i =>
        i.id === instanceId
          ? { ...i, status: 'resolved' as const, resolved_at: new Date().toISOString(), resolved_by: 'current-user' }
          : i
      ))
    } catch (error) {
      console.error('Failed to resolve alert:', error)
      setInstances(instances.map(i =>
        i.id === instanceId
          ? { ...i, status: 'resolved' as const, resolved_at: new Date().toISOString(), resolved_by: 'current-user' }
          : i
      ))
    }
  }

  const filteredInstances = instances.filter(instance => {
    if (searchQuery && !instance.rule_name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false
    }
    if (filterStatus !== 'all' && instance.status !== filterStatus) return false
    if (filterSeverity !== 'all' && instance.severity !== filterSeverity) return false
    return true
  })

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  }

  const formatTimeAgo = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    if (hours > 0) return `${hours}h ${minutes % 60}m ago`
    return `${minutes}m ago`
  }

  const stats = {
    triggered: instances.filter(i => i.status === 'triggered').length,
    acknowledged: instances.filter(i => i.status === 'acknowledged').length,
    resolved: instances.filter(i => i.status === 'resolved').length,
    critical: instances.filter(i => i.severity === 'critical' && i.status !== 'resolved').length
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Alert Instances</h1>
            <p className="text-gray-400 mt-1">View and manage triggered alerts</p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="text-red-400 text-sm">Active Alerts</p>
                <p className="text-2xl font-bold text-white">{stats.triggered}</p>
              </div>
            </div>
          </div>
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-500/20 rounded-lg">
                <Eye className="w-5 h-5 text-yellow-400" />
              </div>
              <div>
                <p className="text-yellow-400 text-sm">Acknowledged</p>
                <p className="text-2xl font-bold text-white">{stats.acknowledged}</p>
              </div>
            </div>
          </div>
          <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-500/20 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <p className="text-green-400 text-sm">Resolved</p>
                <p className="text-2xl font-bold text-white">{stats.resolved}</p>
              </div>
            </div>
          </div>
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <Zap className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="text-red-400 text-sm">Critical (Active)</p>
                <p className="text-2xl font-bold text-white">{stats.critical}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 items-center">
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search alerts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Status</option>
            <option value="triggered">Triggered</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
            <option value="suppressed">Suppressed</option>
          </select>

          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Alert List */}
        <div className="space-y-3">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : filteredInstances.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400 bg-gray-800/50 rounded-lg border border-gray-700">
              <Bell className="w-12 h-12 mb-4 opacity-50" />
              <p>No alerts found</p>
            </div>
          ) : (
            filteredInstances.map((instance) => (
              <div
                key={instance.id}
                className={`bg-gray-800/50 border rounded-lg p-4 hover:bg-gray-800/70 transition-colors cursor-pointer ${
                  instance.status === 'triggered' ? 'border-red-500/50' :
                  instance.status === 'acknowledged' ? 'border-yellow-500/50' :
                  'border-gray-700'
                }`}
                onClick={() => setSelectedInstance(instance)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className={`p-2 rounded-lg ${STATUS_COLORS[instance.status]}`}>
                      {STATUS_ICONS[instance.status]}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-white font-medium">{instance.rule_name}</h3>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${SEVERITY_COLORS[instance.severity]}`}>
                          {instance.severity.toUpperCase()}
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[instance.status]}`}>
                          {instance.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-sm text-gray-400">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatTimeAgo(instance.triggered_at)}
                        </span>
                        {instance.trigger_data.threshold && (
                          <span className="flex items-center gap-1">
                            <TrendingUp className="w-3 h-3" />
                            {instance.trigger_data.actual_value} / {instance.trigger_data.threshold} threshold
                          </span>
                        )}
                        <span>{instance.related_logs_count} logs</span>
                        {instance.related_traces_count > 0 && (
                          <span>{instance.related_traces_count} traces</span>
                        )}
                      </div>
                      {instance.acknowledged_by && (
                        <p className="text-sm text-gray-500 mt-1">
                          Acknowledged by {instance.acknowledged_by}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {instance.status === 'triggered' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); acknowledgeAlert(instance.id) }}
                        className="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-sm hover:bg-yellow-500/30 transition-colors"
                      >
                        Acknowledge
                      </button>
                    )}
                    {(instance.status === 'triggered' || instance.status === 'acknowledged') && (
                      <button
                        onClick={(e) => { e.stopPropagation(); resolveAlert(instance.id) }}
                        className="px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-sm hover:bg-green-500/30 transition-colors"
                      >
                        Resolve
                      </button>
                    )}
                    <ChevronRight className="w-5 h-5 text-gray-500" />
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail Drawer */}
        {selectedInstance && (
          <div className="fixed inset-0 bg-black/50 z-50" onClick={() => setSelectedInstance(null)}>
            <div
              className="fixed right-0 top-0 h-full w-full max-w-xl bg-gray-900 border-l border-gray-700 overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="p-6 space-y-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-white">{selectedInstance.rule_name}</h2>
                    <div className="flex items-center gap-2 mt-2">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium border ${SEVERITY_COLORS[selectedInstance.severity]}`}>
                        {selectedInstance.severity.toUpperCase()}
                      </span>
                      <span className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[selectedInstance.status]}`}>
                        {selectedInstance.status}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedInstance(null)}
                    className="text-gray-400 hover:text-white"
                  >
                    <XCircle className="w-6 h-6" />
                  </button>
                </div>

                {/* Timeline */}
                <div className="border border-gray-700 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">Timeline</h3>
                  <div className="space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="p-1 bg-red-500/20 rounded">
                        <AlertTriangle className="w-4 h-4 text-red-400" />
                      </div>
                      <div>
                        <p className="text-white text-sm">Triggered</p>
                        <p className="text-gray-400 text-xs">{new Date(selectedInstance.triggered_at).toLocaleString()}</p>
                      </div>
                    </div>
                    {selectedInstance.acknowledged_at && (
                      <div className="flex items-start gap-3">
                        <div className="p-1 bg-yellow-500/20 rounded">
                          <Eye className="w-4 h-4 text-yellow-400" />
                        </div>
                        <div>
                          <p className="text-white text-sm">Acknowledged by {selectedInstance.acknowledged_by}</p>
                          <p className="text-gray-400 text-xs">{new Date(selectedInstance.acknowledged_at).toLocaleString()}</p>
                        </div>
                      </div>
                    )}
                    {selectedInstance.resolved_at && (
                      <div className="flex items-start gap-3">
                        <div className="p-1 bg-green-500/20 rounded">
                          <CheckCircle className="w-4 h-4 text-green-400" />
                        </div>
                        <div>
                          <p className="text-white text-sm">Resolved by {selectedInstance.resolved_by}</p>
                          <p className="text-gray-400 text-xs">{new Date(selectedInstance.resolved_at).toLocaleString()}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Trigger Data */}
                <div className="border border-gray-700 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">Trigger Details</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-800 p-3 rounded-lg">
                      <p className="text-gray-400 text-sm">Matched Events</p>
                      <p className="text-xl font-bold text-white">{selectedInstance.trigger_data.matched_count}</p>
                    </div>
                    {selectedInstance.trigger_data.threshold && (
                      <>
                        <div className="bg-gray-800 p-3 rounded-lg">
                          <p className="text-gray-400 text-sm">Threshold</p>
                          <p className="text-xl font-bold text-white">{selectedInstance.trigger_data.threshold}</p>
                        </div>
                        <div className="bg-gray-800 p-3 rounded-lg">
                          <p className="text-gray-400 text-sm">Actual Value</p>
                          <p className="text-xl font-bold text-red-400">{selectedInstance.trigger_data.actual_value}</p>
                        </div>
                      </>
                    )}
                    <div className="bg-gray-800 p-3 rounded-lg">
                      <p className="text-gray-400 text-sm">Related Logs</p>
                      <p className="text-xl font-bold text-white">{selectedInstance.related_logs_count}</p>
                    </div>
                  </div>
                </div>

                {/* Sample Values */}
                {selectedInstance.trigger_data.sample_values.length > 0 && (
                  <div className="border border-gray-700 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Sample Data</h3>
                    <pre className="bg-gray-800 p-3 rounded-lg text-sm text-gray-300 overflow-x-auto">
                      {JSON.stringify(selectedInstance.trigger_data.sample_values, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Notes */}
                <div className="border border-gray-700 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">Investigation Notes</h3>
                  {selectedInstance.notes.length > 0 ? (
                    <div className="space-y-2">
                      {selectedInstance.notes.map((note, idx) => (
                        <div key={idx} className="bg-gray-800 p-3 rounded-lg text-sm text-gray-300">
                          {note}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-sm">No notes yet</p>
                  )}
                  <div className="mt-3">
                    <textarea
                      placeholder="Add a note..."
                      rows={2}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500"
                    />
                    <button className="mt-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm transition-colors">
                      Add Note
                    </button>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-3">
                  <button className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
                    <ExternalLink className="w-4 h-4" />
                    View Logs
                  </button>
                  <button className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
                    <ExternalLink className="w-4 h-4" />
                    View Traces
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
