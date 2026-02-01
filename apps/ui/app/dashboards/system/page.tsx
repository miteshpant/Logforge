'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Clock,
  Cpu,
  Database,
  Gauge,
  RefreshCw,
  Search,
  Server,
  Shield,
  TrendingUp,
  Zap
} from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface ErrorByService {
  service: string
  error_count: number
  level?: string
}

interface TimeSeriesBucket {
  bucket: string
  avg_response_time?: number
  p95_response_time?: number
  count?: number
  error_count?: number
}

interface TopErrorMessage {
  msg: string
  error_count: number
  service?: string
}

interface ServiceHealthEntry {
  service: string
  level: string
  event_count: number
  unique_hosts?: number
}

interface SlowEndpoint {
  service: string
  avg_response_time: number
  p95_response_time: number
  max_response_time: number
  request_count: number
}

interface SecurityPattern {
  source_ip: string
  service: string
  security_events: number
}

interface InfraMetric {
  host: string
  metric_name: string
  avg_value: number
  peak_value: number
}

// ─── Query Definitions ────────────────────────────────────────────────────────

function buildErrorsByServiceQuery(startTime: string, endTime: string) {
  return {
    start_time: startTime,
    end_time: endTime,
    filters: [
      { field: 'level', operator: 'in', value: ['ERROR', 'CRITICAL'] }
    ],
    group_by: ['service'],
    aggregations: [
      { type: 'count', field: '*', alias: 'error_count' }
    ],
    order_by: [{ field: 'error_count', direction: 'desc' }],
    limit: 10
  }
}

function buildResponseTimeTrendsQuery(startTime: string, endTime: string) {
  return {
    start_time: startTime,
    end_time: endTime,
    interval: '5m',
    aggregations: [
      { type: 'avg', field: 'response_time', alias: 'avg_response_time' },
      { type: 'percentile', field: 'response_time', percentile: 95, alias: 'p95_response_time' }
    ]
  }
}

function buildLogVolumeQuery(startTime: string, endTime: string) {
  return {
    start_time: startTime,
    end_time: endTime,
    interval: '5m',
    aggregations: [
      { type: 'count', field: '*', alias: 'count' }
    ]
  }
}

function buildTopErrorMessagesQuery(startTime: string, endTime: string) {
  return {
    start_time: startTime,
    end_time: endTime,
    filters: [
      { field: 'level', operator: 'in', value: ['ERROR', 'CRITICAL'] }
    ],
    group_by: ['msg'],
    aggregations: [
      { type: 'count', field: '*', alias: 'error_count' }
    ],
    order_by: [{ field: 'error_count', direction: 'desc' }],
    limit: 8
  }
}

function buildServiceHealthQuery(startTime: string, endTime: string) {
  return {
    start_time: startTime,
    end_time: endTime,
    group_by: ['service', 'level'],
    aggregations: [
      { type: 'count', field: '*', alias: 'event_count' },
      { type: 'unique', field: 'host', alias: 'unique_hosts' }
    ]
  }
}

function buildSlowestEndpointsQuery(startTime: string, endTime: string) {
  return {
    start_time: startTime,
    end_time: endTime,
    filters: [
      { field: 'response_time', operator: 'gte', value: 100 }
    ],
    group_by: ['service'],
    aggregations: [
      { type: 'avg', field: 'response_time', alias: 'avg_response_time' },
      { type: 'percentile', field: 'response_time', percentile: 95, alias: 'p95_response_time' },
      { type: 'max', field: 'response_time', alias: 'max_response_time' },
      { type: 'count', field: '*', alias: 'request_count' }
    ],
    order_by: [{ field: 'p95_response_time', direction: 'desc' }],
    limit: 8
  }
}

function buildSecurityPatternsQuery(startTime: string, endTime: string) {
  return {
    start_time: startTime,
    end_time: endTime,
    filters: [
      { field: 'msg', operator: 'regex', value: '(failed|denied|unauthorized|forbidden|rejected|blocked)' },
      { field: 'level', operator: 'in', value: ['WARN', 'ERROR'] }
    ],
    group_by: ['source_ip', 'service'],
    aggregations: [
      { type: 'count', field: '*', alias: 'security_events' }
    ],
    order_by: [{ field: 'security_events', direction: 'desc' }],
    limit: 10
  }
}

function buildInfraUtilizationQuery(startTime: string, endTime: string) {
  return {
    start_time: startTime,
    end_time: endTime,
    filters: [
      { field: 'metric_name', operator: 'in', value: ['cpu_usage', 'memory_usage', 'disk_usage'] }
    ],
    group_by: ['host', 'metric_name'],
    aggregations: [
      { type: 'avg', field: 'metric_value', alias: 'avg_value' },
      { type: 'max', field: 'metric_value', alias: 'peak_value' }
    ],
    order_by: [{ field: 'avg_value', direction: 'desc' }],
    limit: 15
  }
}

// ─── Helper Functions ─────────────────────────────────────────────────────────

function extractArrayData(response: any): any[] {
  const data = response?.data || response
  if (Array.isArray(data)) return data
  if (data?.logs && Array.isArray(data.logs)) return data.logs
  if (data?.results && Array.isArray(data.results)) return data.results
  if (data?.data && Array.isArray(data.data)) return data.data
  if (data?.buckets && Array.isArray(data.buckets)) return data.buckets
  if (data?.aggregations && typeof data.aggregations === 'object') {
    return Object.entries(data.aggregations).map(([key, value]) => ({
      key,
      ...(typeof value === 'object' && value !== null ? value as Record<string, unknown> : { value })
    }))
  }
  return []
}

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.round(ms)}ms`
}

function formatTimeBucket(bucket: string): string {
  const d = new Date(bucket)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// ─── Widget Components ────────────────────────────────────────────────────────

function WidgetShell({ title, icon: Icon, iconColor, isLoading, children }: {
  title: string
  icon: React.ElementType
  iconColor: string
  isLoading: boolean
  children: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <Icon className={`w-5 h-5 ${iconColor}`} />
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      </div>
      {isLoading ? (
        <div className="flex-1 flex items-center justify-center py-8">
          <RefreshCw className="w-5 h-5 text-slate-300 animate-spin" />
        </div>
      ) : (
        <div className="flex-1">{children}</div>
      )}
    </div>
  )
}

function ErrorsByServiceWidget({ data, isLoading }: { data: ErrorByService[]; isLoading: boolean }) {
  const maxCount = Math.max(...data.map(d => d.error_count), 1)
  return (
    <WidgetShell title="Error Rate by Service" icon={AlertTriangle} iconColor="text-red-500" isLoading={isLoading}>
      {data.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-4">No errors detected</p>
      ) : (
        <div className="space-y-3">
          {data.map((item, idx) => (
            <div key={idx}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-slate-700 font-medium truncate max-w-[180px]">{item.service || 'unknown'}</span>
                <span className="text-red-600 font-bold">{item.error_count.toLocaleString()}</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-red-400 to-red-600 rounded-full transition-all"
                  style={{ width: `${(item.error_count / maxCount) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </WidgetShell>
  )
}

function ResponseTimeTrendsWidget({ data, isLoading }: { data: TimeSeriesBucket[]; isLoading: boolean }) {
  const maxValue = Math.max(...data.map(d => d.p95_response_time || d.avg_response_time || 0), 1)
  return (
    <WidgetShell title="Response Time Trends" icon={TrendingUp} iconColor="text-blue-500" isLoading={isLoading}>
      {data.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-4">No response time data</p>
      ) : (
        <>
          <div className="flex items-end gap-0.5 h-32 mb-3">
            {data.slice(-30).map((bucket, idx) => {
              const p95 = bucket.p95_response_time || 0
              const avg = bucket.avg_response_time || 0
              const p95Height = (p95 / maxValue) * 100
              const avgHeight = (avg / maxValue) * 100
              return (
                <div key={idx} className="flex-1 flex flex-col items-center justify-end group relative h-full">
                  {/* P95 bar (background) */}
                  <div
                    className="w-full bg-blue-200 rounded-t absolute bottom-0"
                    style={{ height: `${Math.max(p95Height, 2)}%` }}
                  />
                  {/* Avg bar (foreground) */}
                  <div
                    className="w-full bg-blue-500 rounded-t relative z-10"
                    style={{ height: `${Math.max(avgHeight, 2)}%` }}
                  />
                  <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] rounded px-1.5 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-20">
                    avg: {formatMs(avg)} | p95: {formatMs(p95)}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex items-center gap-4 text-[10px] text-slate-500">
            <div className="flex items-center gap-1">
              <div className="w-3 h-2 bg-blue-500 rounded" />
              <span>Avg</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-2 bg-blue-200 rounded" />
              <span>P95</span>
            </div>
          </div>
        </>
      )}
    </WidgetShell>
  )
}

function LogVolumeWidget({ data, isLoading }: { data: TimeSeriesBucket[]; isLoading: boolean }) {
  const maxCount = Math.max(...data.map(d => d.count || 0), 1)
  const totalLogs = data.reduce((sum, d) => sum + (d.count || 0), 0)
  return (
    <WidgetShell title="Log Volume Timeline" icon={BarChart3} iconColor="text-green-500" isLoading={isLoading}>
      {data.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-4">No log data</p>
      ) : (
        <>
          <p className="text-2xl font-bold text-slate-900 mb-3">{totalLogs.toLocaleString()} <span className="text-sm font-normal text-slate-500">total logs</span></p>
          <div className="flex items-end gap-0.5 h-24">
            {data.slice(-40).map((bucket, idx) => {
              const count = bucket.count || 0
              const height = (count / maxCount) * 100
              return (
                <div key={idx} className="flex-1 group relative flex items-end h-full">
                  <div
                    className="w-full bg-gradient-to-t from-green-500 to-green-400 rounded-t transition-all hover:from-green-600 hover:to-green-500"
                    style={{ height: `${Math.max(height, 2)}%` }}
                  />
                  <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] rounded px-1.5 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                    {bucket.bucket ? formatTimeBucket(bucket.bucket) : ''}: {count.toLocaleString()}
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </WidgetShell>
  )
}

function TopErrorMessagesWidget({ data, isLoading }: { data: TopErrorMessage[]; isLoading: boolean }) {
  return (
    <WidgetShell title="Top Error Messages" icon={Zap} iconColor="text-orange-500" isLoading={isLoading}>
      {data.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-4">No error messages</p>
      ) : (
        <div className="space-y-2 max-h-[220px] overflow-y-auto">
          {data.map((item, idx) => (
            <div key={idx} className="flex items-start gap-2 p-2 bg-slate-50 rounded-lg">
              <span className="text-xs font-mono text-red-500 bg-red-50 px-1.5 py-0.5 rounded shrink-0">
                {item.error_count}x
              </span>
              <p className="text-xs text-slate-700 line-clamp-2 break-all">{item.msg || 'Unknown error'}</p>
            </div>
          ))}
        </div>
      )}
    </WidgetShell>
  )
}

function ServiceHealthMatrixWidget({ data, isLoading }: { data: ServiceHealthEntry[]; isLoading: boolean }) {
  // Pivot: group by service, then show counts per level
  const serviceMap: Record<string, Record<string, number>> = {}
  data.forEach(entry => {
    const svc = entry.service || 'unknown'
    if (!serviceMap[svc]) serviceMap[svc] = {}
    serviceMap[svc][entry.level?.toUpperCase() || 'INFO'] = entry.event_count
  })

  const services = Object.entries(serviceMap).slice(0, 8)
  const levels = ['ERROR', 'WARN', 'INFO', 'DEBUG']
  const levelColors: Record<string, string> = {
    ERROR: 'bg-red-500',
    WARN: 'bg-yellow-500',
    INFO: 'bg-blue-500',
    DEBUG: 'bg-slate-400'
  }

  return (
    <WidgetShell title="Service Health Matrix" icon={Server} iconColor="text-purple-500" isLoading={isLoading}>
      {services.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-4">No service data</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-1.5 text-slate-500 font-medium">Service</th>
                {levels.map(l => (
                  <th key={l} className="text-right py-1.5 text-slate-500 font-medium px-2">{l}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {services.map(([svc, counts]) => (
                <tr key={svc} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-1.5 text-slate-700 font-medium truncate max-w-[120px]">{svc}</td>
                  {levels.map(l => {
                    const count = counts[l] || 0
                    return (
                      <td key={l} className="text-right py-1.5 px-2">
                        {count > 0 ? (
                          <span className={`inline-block px-1.5 py-0.5 rounded text-white text-[10px] font-bold ${levelColors[l]}`}>
                            {count.toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-slate-300">-</span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </WidgetShell>
  )
}

function SlowestEndpointsWidget({ data, isLoading }: { data: SlowEndpoint[]; isLoading: boolean }) {
  return (
    <WidgetShell title="Slowest Services (P95)" icon={Gauge} iconColor="text-amber-500" isLoading={isLoading}>
      {data.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-4">No latency data</p>
      ) : (
        <div className="space-y-2">
          {data.map((item, idx) => (
            <div key={idx} className="flex items-center gap-3 p-2 bg-slate-50 rounded-lg">
              <span className="text-xs font-mono text-slate-500 w-5">#{idx + 1}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-700 font-medium truncate">{item.service || 'unknown'}</p>
                <div className="flex items-center gap-3 text-[10px] text-slate-500 mt-0.5">
                  <span>avg: {formatMs(item.avg_response_time)}</span>
                  <span>max: {formatMs(item.max_response_time)}</span>
                  <span>{item.request_count.toLocaleString()} req</span>
                </div>
              </div>
              <span className={`text-sm font-bold ${
                item.p95_response_time > 2000 ? 'text-red-600' :
                item.p95_response_time > 500 ? 'text-orange-600' :
                'text-green-600'
              }`}>
                {formatMs(item.p95_response_time)}
              </span>
            </div>
          ))}
        </div>
      )}
    </WidgetShell>
  )
}

function SecurityPatternsWidget({ data, isLoading }: { data: SecurityPattern[]; isLoading: boolean }) {
  const totalEvents = data.reduce((s, d) => s + d.security_events, 0)
  return (
    <WidgetShell title="Security Events (Regex)" icon={Shield} iconColor="text-red-600" isLoading={isLoading}>
      {data.length === 0 ? (
        <div className="text-center py-4">
          <Shield className="w-8 h-8 text-green-400 mx-auto mb-2" />
          <p className="text-sm text-green-600 font-medium">No suspicious patterns</p>
        </div>
      ) : (
        <>
          <p className="text-lg font-bold text-red-600 mb-3">{totalEvents.toLocaleString()} <span className="text-sm font-normal text-slate-500">security events</span></p>
          <div className="space-y-2 max-h-[180px] overflow-y-auto">
            {data.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 bg-red-50 rounded-lg">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-mono text-slate-700">{item.source_ip || 'unknown'}</p>
                  <p className="text-[10px] text-slate-500">{item.service}</p>
                </div>
                <span className="text-xs font-bold text-red-600 bg-red-100 px-2 py-0.5 rounded">
                  {item.security_events}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </WidgetShell>
  )
}

function InfraUtilizationWidget({ data, isLoading }: { data: InfraMetric[]; isLoading: boolean }) {
  // Group by host
  const hostMap: Record<string, InfraMetric[]> = {}
  data.forEach(m => {
    const host = m.host || 'unknown'
    if (!hostMap[host]) hostMap[host] = []
    hostMap[host].push(m)
  })

  const hosts = Object.entries(hostMap).slice(0, 5)
  const metricColors: Record<string, string> = {
    cpu_usage: 'bg-blue-500',
    memory_usage: 'bg-purple-500',
    disk_usage: 'bg-orange-500'
  }

  return (
    <WidgetShell title="Infrastructure Utilization" icon={Cpu} iconColor="text-cyan-500" isLoading={isLoading}>
      {hosts.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-4">No infrastructure metrics</p>
      ) : (
        <div className="space-y-3">
          {hosts.map(([host, metrics]) => (
            <div key={host}>
              <p className="text-xs font-medium text-slate-700 mb-1 truncate">{host}</p>
              <div className="flex gap-2">
                {metrics.map((m, idx) => {
                  const pct = Math.min(m.avg_value, 100)
                  const color = metricColors[m.metric_name] || 'bg-slate-400'
                  return (
                    <div key={idx} className="flex-1">
                      <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${color} rounded-full transition-all`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <p className="text-[9px] text-slate-500 mt-0.5 text-center">
                        {m.metric_name?.replace('_', ' ')} {pct.toFixed(0)}%
                      </p>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
          <div className="flex items-center gap-3 pt-2 border-t border-slate-100 text-[10px] text-slate-500">
            <div className="flex items-center gap-1"><div className="w-2 h-2 bg-blue-500 rounded" /> CPU</div>
            <div className="flex items-center gap-1"><div className="w-2 h-2 bg-purple-500 rounded" /> Memory</div>
            <div className="flex items-center gap-1"><div className="w-2 h-2 bg-orange-500 rounded" /> Disk</div>
          </div>
        </div>
      )}
    </WidgetShell>
  )
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function SystemIntelligenceDashboard() {
  const { getApiTimeRange, currentTimeRange } = useTimeRange()

  // Widget state
  const [errorsByService, setErrorsByService] = useState<ErrorByService[]>([])
  const [responseTimeTrends, setResponseTimeTrends] = useState<TimeSeriesBucket[]>([])
  const [logVolume, setLogVolume] = useState<TimeSeriesBucket[]>([])
  const [topErrors, setTopErrors] = useState<TopErrorMessage[]>([])
  const [serviceHealth, setServiceHealth] = useState<ServiceHealthEntry[]>([])
  const [slowEndpoints, setSlowEndpoints] = useState<SlowEndpoint[]>([])
  const [securityPatterns, setSecurityPatterns] = useState<SecurityPattern[]>([])
  const [infraMetrics, setInfraMetrics] = useState<InfraMetric[]>([])

  // Loading state per widget group
  const [loadingAdvanced, setLoadingAdvanced] = useState(true)
  const [loadingTimeSeries, setLoadingTimeSeries] = useState(true)
  const [loadingAggregate, setLoadingAggregate] = useState(true)
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null)

  const loadAllWidgets = useCallback(async () => {
    const { start_time, end_time } = getApiTimeRange()

    // Group 1: Advanced queries (errors, top messages, slowest, security)
    setLoadingAdvanced(true)
    const advancedQueries = Promise.allSettled([
      apiClient.post('/v1/query/advanced', buildErrorsByServiceQuery(start_time, end_time)),
      apiClient.post('/v1/query/advanced', buildTopErrorMessagesQuery(start_time, end_time)),
      apiClient.post('/v1/query/advanced', buildSlowestEndpointsQuery(start_time, end_time)),
      apiClient.post('/v1/query/advanced', buildSecurityPatternsQuery(start_time, end_time))
    ]).then(([errRes, msgRes, slowRes, secRes]) => {
      if (errRes.status === 'fulfilled') setErrorsByService(extractArrayData(errRes.value))
      if (msgRes.status === 'fulfilled') setTopErrors(extractArrayData(msgRes.value))
      if (slowRes.status === 'fulfilled') setSlowEndpoints(extractArrayData(slowRes.value))
      if (secRes.status === 'fulfilled') setSecurityPatterns(extractArrayData(secRes.value))
      setLoadingAdvanced(false)
    })

    // Group 2: Time series queries (response time, log volume)
    setLoadingTimeSeries(true)
    const timeSeriesQueries = Promise.allSettled([
      apiClient.post('/v1/query/timeseries', buildResponseTimeTrendsQuery(start_time, end_time)),
      apiClient.post('/v1/query/timeseries', buildLogVolumeQuery(start_time, end_time))
    ]).then(([rtRes, volRes]) => {
      if (rtRes.status === 'fulfilled') setResponseTimeTrends(extractArrayData(rtRes.value))
      if (volRes.status === 'fulfilled') setLogVolume(extractArrayData(volRes.value))
      setLoadingTimeSeries(false)
    })

    // Group 3: Aggregate queries (service health, infra)
    setLoadingAggregate(true)
    const aggregateQueries = Promise.allSettled([
      apiClient.post('/v1/query/aggregate', buildServiceHealthQuery(start_time, end_time)),
      apiClient.post('/v1/query/advanced', buildInfraUtilizationQuery(start_time, end_time))
    ]).then(([healthRes, infraRes]) => {
      if (healthRes.status === 'fulfilled') setServiceHealth(extractArrayData(healthRes.value))
      if (infraRes.status === 'fulfilled') setInfraMetrics(extractArrayData(infraRes.value))
      setLoadingAggregate(false)
    })

    await Promise.all([advancedQueries, timeSeriesQueries, aggregateQueries])
    setLastRefreshed(new Date())
  }, [getApiTimeRange])

  useEffect(() => {
    loadAllWidgets()
  }, [loadAllWidgets, currentTimeRange.value])

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
              <Database className="w-8 h-8 text-blue-600" />
              System Intelligence
            </h1>
            <p className="text-slate-600 mt-1">
              Auto-generated dashboard powered by the Advanced Query Engine
            </p>
          </div>
          <div className="flex items-center gap-3">
            {lastRefreshed && (
              <span className="text-xs text-slate-500 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Updated {lastRefreshed.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={loadAllWidgets}
              disabled={loadingAdvanced && loadingTimeSeries && loadingAggregate}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loadingAdvanced || loadingTimeSeries || loadingAggregate ? 'animate-spin' : ''}`} />
              Refresh All
            </button>
          </div>
        </div>

        {/* Query Engine Badges */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500">Powered by:</span>
          <span className="px-2 py-1 text-[10px] font-medium bg-blue-50 text-blue-700 rounded-full border border-blue-200">
            POST /v1/query/advanced
          </span>
          <span className="px-2 py-1 text-[10px] font-medium bg-green-50 text-green-700 rounded-full border border-green-200">
            POST /v1/query/timeseries
          </span>
          <span className="px-2 py-1 text-[10px] font-medium bg-purple-50 text-purple-700 rounded-full border border-purple-200">
            POST /v1/query/aggregate
          </span>
          <span className="px-2 py-1 text-[10px] font-medium bg-slate-50 text-slate-600 rounded-full border border-slate-200">
            8 query types: count, sum, avg, min, max, percentile, unique, cardinality
          </span>
        </div>

        {/* Row 1: Overview charts */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <ErrorsByServiceWidget data={errorsByService} isLoading={loadingAdvanced} />
          <ResponseTimeTrendsWidget data={responseTimeTrends} isLoading={loadingTimeSeries} />
          <LogVolumeWidget data={logVolume} isLoading={loadingTimeSeries} />
        </div>

        {/* Row 2: Detail tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <TopErrorMessagesWidget data={topErrors} isLoading={loadingAdvanced} />
          <ServiceHealthMatrixWidget data={serviceHealth} isLoading={loadingAggregate} />
        </div>

        {/* Row 3: Performance & Security */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <SlowestEndpointsWidget data={slowEndpoints} isLoading={loadingAdvanced} />
          <SecurityPatternsWidget data={securityPatterns} isLoading={loadingAdvanced} />
          <InfraUtilizationWidget data={infraMetrics} isLoading={loadingAggregate} />
        </div>
      </div>
    </DashboardLayout>
  )
}
