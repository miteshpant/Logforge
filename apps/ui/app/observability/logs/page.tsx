'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Search,
  Filter,
  Download,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Info,
  AlertTriangle,
  Bug,
  FileText,
  Clock,
  Server,
  Tag,
  X,
  Copy,
  ExternalLink,
  Columns,
  BarChart3
} from 'lucide-react'

interface LogEntry {
  id: string
  timestamp: string
  level: 'debug' | 'info' | 'warning' | 'error' | 'critical'
  service: string
  message: string
  trace_id?: string
  span_id?: string
  metadata: Record<string, unknown>
}

interface LogStats {
  total: number
  by_level: Record<string, number>
  by_service: Record<string, number>
}

const LOG_LEVEL_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  debug: { bg: 'bg-slate-100', text: 'text-slate-600', icon: <Bug className="w-3 h-3" /> },
  info: { bg: 'bg-blue-100', text: 'text-blue-600', icon: <Info className="w-3 h-3" /> },
  warning: { bg: 'bg-yellow-100', text: 'text-yellow-600', icon: <AlertTriangle className="w-3 h-3" /> },
  error: { bg: 'bg-red-100', text: 'text-red-600', icon: <AlertCircle className="w-3 h-3" /> },
  critical: { bg: 'bg-red-200', text: 'text-red-700', icon: <AlertCircle className="w-3 h-3" /> }
}

export default function LogExplorerPage() {
  const { getApiTimeRange } = useTimeRange()
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [stats, setStats] = useState<LogStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [levelFilter, setLevelFilter] = useState<string[]>([])
  const [serviceFilter, setServiceFilter] = useState<string>('all')
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set())
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)
  const [isLiveMode, setIsLiveMode] = useState(false)
  const [services, setServices] = useState<string[]>([])

  const loadLogs = useCallback(async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<{ logs: LogEntry[]; stats: LogStats }>('/v1/query/logs', {
        start_time,
        end_time,
        search: searchQuery || undefined,
        level: levelFilter.length > 0 ? levelFilter.join(',') : undefined,
        service: serviceFilter !== 'all' ? serviceFilter : undefined,
        limit: 500
      })

      const data = response?.data || response
      if (data?.logs) {
        setLogs(data.logs)
        if (data.stats) setStats(data.stats)
      } else {
        const mockLogs = generateMockLogs()
        setLogs(mockLogs)
        setStats(calculateStats(mockLogs))
      }

      // Extract unique services
      const uniqueServices = new Set<string>()
      logs.forEach(log => uniqueServices.add(log.service))
      setServices(Array.from(uniqueServices))
    } catch (error) {
      console.error('Failed to load logs:', error)
      const mockLogs = generateMockLogs()
      setLogs(mockLogs)
      setStats(calculateStats(mockLogs))
    } finally {
      setIsLoading(false)
    }
  }, [getApiTimeRange, searchQuery, levelFilter, serviceFilter])

  useEffect(() => {
    loadLogs()
  }, [loadLogs])

  // Live mode polling
  useEffect(() => {
    if (!isLiveMode) return

    const interval = setInterval(() => {
      loadLogs()
    }, 5000)

    return () => clearInterval(interval)
  }, [isLiveMode, loadLogs])

  const toggleLogExpansion = (logId: string) => {
    setExpandedLogs(prev => {
      const next = new Set(prev)
      if (next.has(logId)) {
        next.delete(logId)
      } else {
        next.add(logId)
      }
      return next
    })
  }

  const toggleLevelFilter = (level: string) => {
    setLevelFilter(prev => {
      if (prev.includes(level)) {
        return prev.filter(l => l !== level)
      }
      return [...prev, level]
    })
  }

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts)
    return date.toLocaleString()
  }

  const formatRelativeTime = (ts: string) => {
    const diff = Date.now() - new Date(ts).getTime()
    if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return `${Math.floor(diff / 86400000)}d ago`
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const exportLogs = () => {
    const csvContent = [
      ['Timestamp', 'Level', 'Service', 'Message', 'Trace ID'].join(','),
      ...logs.map(log => [
        log.timestamp,
        log.level,
        log.service,
        `"${log.message.replace(/"/g, '""')}"`,
        log.trace_id || ''
      ].join(','))
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${new Date().toISOString()}.csv`
    a.click()
  }

  const filteredLogs = logs.filter(log => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        log.message.toLowerCase().includes(query) ||
        log.service.toLowerCase().includes(query) ||
        log.trace_id?.toLowerCase().includes(query) ||
        JSON.stringify(log.metadata).toLowerCase().includes(query)
      )
    }
    return true
  })

  return (
    <DashboardLayout>
      <div className="h-[calc(100vh-120px)] flex flex-col">
        {/* Controls Bar */}
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => setIsLiveMode(!isLiveMode)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              isLiveMode
                ? 'bg-green-500 text-white'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${isLiveMode ? 'bg-white animate-pulse' : 'bg-slate-400'}`} />
            {isLiveMode ? 'Live' : 'Live Mode'}
          </button>
          <button
            onClick={exportLogs}
            className="flex items-center gap-2 px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={loadLogs}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50 ml-auto"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Stats Bar */}
        {stats && (
          <div className="flex gap-4 mb-4">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-100 rounded-lg">
              <FileText className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-medium text-slate-700">{stats.total.toLocaleString()} logs</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-red-100 rounded-lg">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <span className="text-sm font-medium text-red-700">{(stats.by_level.error || 0) + (stats.by_level.critical || 0)} errors</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-100 rounded-lg">
              <AlertTriangle className="w-4 h-4 text-yellow-600" />
              <span className="text-sm font-medium text-yellow-700">{stats.by_level.warning || 0} warnings</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-100 rounded-lg">
              <Server className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-medium text-blue-700">{Object.keys(stats.by_service).length} services</span>
            </div>
          </div>
        )}

        {/* Search and Filters */}
        <div className="flex gap-4 mb-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search logs by message, service, trace ID, or metadata..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Level Filter */}
          <div className="flex items-center gap-1 px-2 py-1 bg-slate-100 rounded-lg">
            {Object.entries(LOG_LEVEL_STYLES).map(([level, style]) => (
              <button
                key={level}
                onClick={() => toggleLevelFilter(level)}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                  levelFilter.length === 0 || levelFilter.includes(level)
                    ? `${style.bg} ${style.text}`
                    : 'bg-transparent text-slate-400'
                }`}
              >
                {style.icon}
                {level}
              </button>
            ))}
          </div>

          {/* Service Filter */}
          <select
            value={serviceFilter}
            onChange={(e) => setServiceFilter(e.target.value)}
            className="px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Services</option>
            {services.map(service => (
              <option key={service} value={service}>{service}</option>
            ))}
          </select>
        </div>

        {/* Log List */}
        <div className="flex-1 bg-white rounded-xl border border-slate-200 overflow-hidden flex flex-col">
          {/* Table Header */}
          <div className="flex items-center gap-4 px-4 py-2 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase">
            <div className="w-8" />
            <div className="w-40">Timestamp</div>
            <div className="w-20">Level</div>
            <div className="w-32">Service</div>
            <div className="flex-1">Message</div>
            <div className="w-24">Trace</div>
          </div>

          {/* Log Entries */}
          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="p-8 text-center">
                <RefreshCw className="w-8 h-8 text-slate-300 animate-spin mx-auto mb-3" />
                <p className="text-slate-500">Loading logs...</p>
              </div>
            ) : filteredLogs.length === 0 ? (
              <div className="p-8 text-center">
                <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500">No logs found</p>
                <p className="text-sm text-slate-400 mt-1">Try adjusting your filters</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {filteredLogs.map(log => {
                  const isExpanded = expandedLogs.has(log.id)
                  const levelStyle = LOG_LEVEL_STYLES[log.level] || LOG_LEVEL_STYLES.info

                  return (
                    <div key={log.id} className="hover:bg-slate-50">
                      {/* Log Row */}
                      <div
                        className="flex items-center gap-4 px-4 py-2 cursor-pointer"
                        onClick={() => toggleLogExpansion(log.id)}
                      >
                        <div className="w-8">
                          {Object.keys(log.metadata).length > 0 && (
                            isExpanded
                              ? <ChevronDown className="w-4 h-4 text-slate-400" />
                              : <ChevronRight className="w-4 h-4 text-slate-400" />
                          )}
                        </div>
                        <div className="w-40 text-xs text-slate-500 font-mono">
                          <div>{formatTimestamp(log.timestamp)}</div>
                          <div className="text-slate-400">{formatRelativeTime(log.timestamp)}</div>
                        </div>
                        <div className="w-20">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${levelStyle.bg} ${levelStyle.text}`}>
                            {levelStyle.icon}
                            {log.level}
                          </span>
                        </div>
                        <div className="w-32">
                          <span className="text-sm text-slate-700 truncate block">{log.service}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm truncate ${log.level === 'error' || log.level === 'critical' ? 'text-red-700' : 'text-slate-700'}`}>
                            {log.message}
                          </p>
                        </div>
                        <div className="w-24">
                          {log.trace_id && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                copyToClipboard(log.trace_id!)
                              }}
                              className="text-xs font-mono text-blue-600 hover:text-blue-700 flex items-center gap-1"
                            >
                              {log.trace_id.slice(0, 8)}...
                              <Copy className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {isExpanded && Object.keys(log.metadata).length > 0 && (
                        <div className="px-4 pb-4 pl-12">
                          <div className="p-4 bg-slate-900 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs text-slate-400">Metadata</span>
                              <button
                                onClick={() => copyToClipboard(JSON.stringify(log.metadata, null, 2))}
                                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                              >
                                <Copy className="w-3 h-3" />
                                Copy
                              </button>
                            </div>
                            <pre className="text-xs text-green-400 overflow-x-auto">
                              {JSON.stringify(log.metadata, null, 2)}
                            </pre>
                          </div>

                          {/* Quick Actions */}
                          <div className="flex gap-2 mt-3">
                            {log.trace_id && (
                              <a
                                href={`/observability/traces?trace_id=${log.trace_id}`}
                                className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-100 text-purple-700 rounded-lg text-xs font-medium hover:bg-purple-200"
                              >
                                <ExternalLink className="w-3 h-3" />
                                View Trace
                              </a>
                            )}
                            <button
                              onClick={() => setSearchQuery(`service:${log.service}`)}
                              className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg text-xs font-medium hover:bg-slate-200"
                            >
                              <Filter className="w-3 h-3" />
                              Filter by Service
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Log Detail Panel */}
        {selectedLog && (
          <div className="fixed inset-y-0 right-0 w-1/2 bg-white shadow-xl border-l border-slate-200 z-50 overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-slate-900">Log Details</h3>
                <button
                  onClick={() => setSelectedLog(null)}
                  className="p-2 hover:bg-slate-100 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Details */}
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500">Timestamp</label>
                  <p className="text-sm text-slate-900 font-mono">{selectedLog.timestamp}</p>
                </div>
                <div>
                  <label className="text-xs text-slate-500">Level</label>
                  <p className={`text-sm font-medium ${LOG_LEVEL_STYLES[selectedLog.level]?.text}`}>
                    {selectedLog.level.toUpperCase()}
                  </p>
                </div>
                <div>
                  <label className="text-xs text-slate-500">Service</label>
                  <p className="text-sm text-slate-900">{selectedLog.service}</p>
                </div>
                <div>
                  <label className="text-xs text-slate-500">Message</label>
                  <p className="text-sm text-slate-900">{selectedLog.message}</p>
                </div>
                {selectedLog.trace_id && (
                  <div>
                    <label className="text-xs text-slate-500">Trace ID</label>
                    <p className="text-sm text-slate-900 font-mono">{selectedLog.trace_id}</p>
                  </div>
                )}
                <div>
                  <label className="text-xs text-slate-500">Metadata</label>
                  <pre className="mt-2 p-4 bg-slate-900 text-green-400 rounded-lg text-xs overflow-x-auto">
                    {JSON.stringify(selectedLog.metadata, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}

// Mock data generators
function generateMockLogs(): LogEntry[] {
  const services = ['api-gateway', 'auth-service', 'user-service', 'order-service', 'payment-service', 'notification-service']
  const levels: LogEntry['level'][] = ['debug', 'info', 'warning', 'error', 'critical']
  const messages = {
    debug: ['Cache hit for key user_123', 'Database query executed in 45ms', 'Request context initialized'],
    info: ['User login successful', 'Order created successfully', 'Payment processed', 'Email notification sent', 'API request completed'],
    warning: ['Rate limit approaching for IP 192.168.1.100', 'Slow database query detected', 'Cache miss, fetching from database', 'Retry attempt 2/3 for external API'],
    error: ['Failed to connect to database', 'Invalid authentication token', 'Payment gateway timeout', 'Failed to send email notification'],
    critical: ['Database connection pool exhausted', 'Payment service unavailable', 'Memory usage critical', 'Disk space low on primary volume']
  }

  const logs: LogEntry[] = []

  for (let i = 0; i < 200; i++) {
    const level = levels[Math.random() < 0.6 ? 1 : Math.floor(Math.random() * levels.length)]
    const service = services[Math.floor(Math.random() * services.length)]
    const messageList = messages[level]
    const message = messageList[Math.floor(Math.random() * messageList.length)]

    logs.push({
      id: `log-${i}`,
      timestamp: new Date(Date.now() - Math.random() * 3600000).toISOString(),
      level,
      service,
      message,
      trace_id: Math.random() > 0.3 ? `trace-${Math.random().toString(36).slice(2, 18)}` : undefined,
      span_id: Math.random() > 0.5 ? `span-${Math.random().toString(36).slice(2, 10)}` : undefined,
      metadata: level !== 'debug' ? {
        request_id: `req-${Math.random().toString(36).slice(2, 10)}`,
        user_id: Math.random() > 0.5 ? `user-${Math.floor(Math.random() * 1000)}` : undefined,
        duration_ms: Math.floor(Math.random() * 500),
        status_code: level === 'error' ? [400, 401, 403, 404, 500, 502, 503][Math.floor(Math.random() * 7)] : 200,
        ...(level === 'error' && {
          error_type: ['ValidationError', 'AuthenticationError', 'TimeoutError', 'DatabaseError'][Math.floor(Math.random() * 4)],
          stack_trace: 'Error: Something went wrong\n    at handleRequest (/app/src/handlers.ts:42)\n    at processRequest (/app/src/server.ts:128)'
        })
      } : {}
    })
  }

  return logs.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
}

function calculateStats(logs: LogEntry[]): LogStats {
  const stats: LogStats = {
    total: logs.length,
    by_level: {},
    by_service: {}
  }

  logs.forEach(log => {
    stats.by_level[log.level] = (stats.by_level[log.level] || 0) + 1
    stats.by_service[log.service] = (stats.by_service[log.service] || 0) + 1
  })

  return stats
}
