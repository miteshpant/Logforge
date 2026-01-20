'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import { apiClient } from '@/lib/api'
import {
  Activity,
  Clock,
  AlertTriangle,
  Cpu,
  HardDrive,
  RefreshCw,
  Play,
  Pause,
  TrendingUp,
  TrendingDown,
  BarChart3
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts'

// Metric definitions - must match metric_name values in metrics_mt table
const METRIC_DEFINITIONS = {
  response_time: {
    name: 'Response Time',
    icon: Clock,
    unit: 'ms',
    color: '#3b82f6',
    description: 'Response time / latency'
  },
  throughput: {
    name: 'Throughput',
    icon: Activity,
    unit: 'req/s',
    color: '#10b981',
    description: 'Requests per second'
  },
  error_rate: {
    name: 'Error Rate',
    icon: AlertTriangle,
    unit: '%',
    color: '#ef4444',
    description: 'Percentage of failed requests'
  },
  cpu_usage: {
    name: 'CPU Usage',
    icon: Cpu,
    unit: '%',
    color: '#f59e0b',
    description: 'CPU utilization'
  },
  memory_usage: {
    name: 'Memory Usage',
    icon: HardDrive,
    unit: '%',
    color: '#8b5cf6',
    description: 'Memory utilization'
  }
}

type MetricType = keyof typeof METRIC_DEFINITIONS
type AggregationType = 'avg' | 'min' | 'max' | 'sum' | 'p50' | 'p95' | 'p99'

interface MetricDataPoint {
  timestamp: string
  value: number
  service?: string
}

export default function MetricsExplorerPage() {
  const { getApiTimeRange, currentTimeRange } = useTimeRange()

  // Selected metrics and options
  const [selectedMetrics, setSelectedMetrics] = useState<MetricType[]>(['response_time', 'throughput'])
  const [aggregation, setAggregation] = useState<AggregationType>('avg')
  const [selectedService, setSelectedService] = useState<string>('all')

  // Data state
  const [metricsData, setMetricsData] = useState<Record<string, MetricDataPoint[]>>({})
  const [services, setServices] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Real-time streaming state
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingData, setStreamingData] = useState<MetricDataPoint[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)

  // Auto-refresh
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(30000)
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Fetch available services
  useEffect(() => {
    const fetchServices = async () => {
      try {
        const response = await apiClient.get('/v1/observability/service-map')
        const data = response.data?.data || response.data
        if (data?.nodes) {
          const serviceNames = data.nodes.map((n: any) => n.service_name || n.id)
          setServices([...new Set(serviceNames)] as string[])
        }
      } catch (err) {
        console.error('Failed to fetch services:', err)
      }
    }
    fetchServices()
  }, [])

  // Calculate appropriate granularity based on time range
  // Goal: ~60-100 data points for any time range
  const calculateGranularity = (startTime: string, endTime: string): string => {
    const start = new Date(startTime).getTime()
    const end = new Date(endTime).getTime()
    const durationMs = end - start
    const durationSeconds = durationMs / 1000

    // Target ~60-100 data points
    if (durationSeconds <= 900) {          // <= 15 minutes
      return '10s'                          // 90 points for 15min
    } else if (durationSeconds <= 3600) {  // <= 1 hour
      return '30s'                          // 120 points for 1hr
    } else if (durationSeconds <= 21600) { // <= 6 hours
      return '5m'                           // 72 points for 6hr
    } else if (durationSeconds <= 86400) { // <= 24 hours
      return '15m'                          // 96 points for 24hr
    } else if (durationSeconds <= 604800) { // <= 7 days
      return '1h'                           // 168 points for 7d
    } else {
      return '4h'                           // ~180 points for 30d
    }
  }

  // Query metrics from API
  const queryMetrics = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const { start_time, end_time } = getApiTimeRange()
      const granularity = calculateGranularity(start_time, end_time)
      const results: Record<string, MetricDataPoint[]> = {}

      for (const metric of selectedMetrics) {
        try {
          const response = await apiClient.post('/v1/observability/metrics/query', {
            metric_name: metric,
            start_time,
            end_time,
            aggregation,
            service: selectedService !== 'all' ? selectedService : undefined,
            granularity
          })

          const data = response.data

          // Handle different response formats from API
          if (data?.metrics?.[metric]) {
            results[metric] = data.metrics[metric]
          } else if (data?.data) {
            results[metric] = data.data
          } else if (Array.isArray(data)) {
            results[metric] = data
          }
        } catch (err) {
          console.error(`Failed to query ${metric}:`, err)
        }
      }

      setMetricsData(results)
    } catch (err) {
      setError('Failed to query metrics')
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }, [selectedMetrics, aggregation, selectedService, getApiTimeRange])

  // Initial load and time range change
  useEffect(() => {
    queryMetrics()
  }, [currentTimeRange.value])

  // Auto-refresh effect
  useEffect(() => {
    if (autoRefresh && !isStreaming) {
      refreshTimerRef.current = setInterval(queryMetrics, refreshInterval)
    }
    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current)
      }
    }
  }, [autoRefresh, refreshInterval, isStreaming, queryMetrics])

  // Start real-time streaming
  const startStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setStreamingData([])
    setIsStreaming(true)

    try {
      const eventSource = new EventSource(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'}/v1/stream/metrics`
      )

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.metrics) {
            setStreamingData(prev => [...prev.slice(-100), ...data.metrics])
          }
        } catch (err) {
          console.error('Failed to parse SSE data:', err)
        }
      }

      eventSource.onerror = () => {
        eventSource.close()
        setIsStreaming(false)
        setError('Streaming connection failed')
      }

      eventSourceRef.current = eventSource
    } catch (err) {
      setIsStreaming(false)
      setError('Failed to start streaming')
    }
  }

  // Stop streaming
  const stopStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsStreaming(false)
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current)
      }
    }
  }, [])

  // Toggle metric selection
  const toggleMetric = (metric: MetricType) => {
    setSelectedMetrics(prev =>
      prev.includes(metric)
        ? prev.filter(m => m !== metric)
        : [...prev, metric]
    )
  }

  // Format chart data for Recharts
  const formatChartData = () => {
    if (isStreaming && streamingData.length > 0) {
      const grouped: Record<string, any> = {}
      streamingData.forEach(point => {
        const time = new Date(point.timestamp).toLocaleTimeString()
        if (!grouped[time]) {
          grouped[time] = { time }
        }
        selectedMetrics.forEach((metric) => {
          if (!grouped[time][metric]) {
            grouped[time][metric] = point.value
          }
        })
      })
      return Object.values(grouped).slice(-60)
    }

    const allTimestamps = new Set<string>()
    Object.values(metricsData).forEach(data => {
      data.forEach(point => allTimestamps.add(point.timestamp))
    })

    const sortedTimestamps = Array.from(allTimestamps).sort()

    return sortedTimestamps.map(timestamp => {
      const point: any = { time: new Date(timestamp).toLocaleTimeString() }

      Object.entries(metricsData).forEach(([metric, data]) => {
        const matchingPoint = data.find(d => d.timestamp === timestamp)
        if (matchingPoint) {
          point[metric] = Math.round(matchingPoint.value * 100) / 100
        }
      })

      return point
    })
  }

  // Calculate current stats
  const calculateStats = (metric: MetricType) => {
    const data = metricsData[metric] || []
    if (data.length === 0) return { current: 0, avg: 0, trend: 0, hasData: false }

    const values = data.map(d => d.value)
    const current = values[values.length - 1] || 0
    const avg = values.reduce((a, b) => a + b, 0) / values.length

    const tenPercent = Math.max(1, Math.floor(values.length * 0.1))
    const recentAvg = values.slice(-tenPercent).reduce((a, b) => a + b, 0) / tenPercent
    const earlyAvg = values.slice(0, tenPercent).reduce((a, b) => a + b, 0) / tenPercent
    const trend = earlyAvg > 0 ? ((recentAvg - earlyAvg) / earlyAvg) * 100 : 0

    return { current, avg, trend, hasData: true }
  }

  const chartData = formatChartData()
  const hasAnyData = Object.keys(metricsData).length > 0 && Object.values(metricsData).some(d => d.length > 0)

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Controls Bar */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4">
          <div className="flex flex-wrap items-center gap-4">
            {/* Metric Selector */}
            <div className="flex flex-wrap gap-2">
              {Object.entries(METRIC_DEFINITIONS).map(([key, def]) => {
                const Icon = def.icon
                const isSelected = selectedMetrics.includes(key as MetricType)
                return (
                  <button
                    key={key}
                    onClick={() => toggleMetric(key as MetricType)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      isSelected
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : 'bg-slate-700/50 text-slate-400 hover:bg-slate-600/50 border border-white/5'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {def.name}
                  </button>
                )
              })}
            </div>

            <div className="h-8 w-px bg-white/10" />

            {/* Aggregation */}
            <select
              value={aggregation}
              onChange={(e) => setAggregation(e.target.value as AggregationType)}
              className="px-3 py-2 bg-slate-700/50 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            >
              <option value="avg">Average</option>
              <option value="min">Minimum</option>
              <option value="max">Maximum</option>
              <option value="sum">Sum</option>
              <option value="p50">P50</option>
              <option value="p95">P95</option>
              <option value="p99">P99</option>
            </select>

            {/* Service Filter */}
            <select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              className="px-3 py-2 bg-slate-700/50 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            >
              <option value="all">All Services</option>
              {services.map(service => (
                <option key={service} value={service}>{service}</option>
              ))}
            </select>

            <div className="flex-1" />

            {/* Streaming Toggle */}
            {isStreaming ? (
              <button
                onClick={stopStreaming}
                className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 rounded-lg text-sm font-medium transition-all"
              >
                <Pause className="w-4 h-4" />
                Stop Live
              </button>
            ) : (
              <button
                onClick={startStreaming}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 rounded-lg text-sm font-medium transition-all"
              >
                <Play className="w-4 h-4" />
                Live Mode
              </button>
            )}

            {/* Refresh Button */}
            <button
              onClick={queryMetrics}
              disabled={isLoading || isStreaming}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 border border-blue-500/30 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {selectedMetrics.map(metric => {
            const def = METRIC_DEFINITIONS[metric]
            const Icon = def.icon
            const stats = calculateStats(metric)

            return (
              <div
                key={metric}
                className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${def.color}15` }}
                    >
                      <Icon className="w-4 h-4" style={{ color: def.color }} />
                    </div>
                    <span className="text-sm text-slate-400">{def.name}</span>
                  </div>
                  {stats.hasData && stats.trend !== 0 && (
                    <div className={`flex items-center gap-1 text-xs ${
                      stats.trend > 0
                        ? metric === 'error_rate' ? 'text-red-400' : 'text-emerald-400'
                        : metric === 'error_rate' ? 'text-emerald-400' : 'text-red-400'
                    }`}>
                      {stats.trend > 0 ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {Math.abs(stats.trend).toFixed(1)}%
                    </div>
                  )}
                </div>
                {isLoading ? (
                  <div className="animate-pulse">
                    <div className="h-8 bg-slate-700 rounded w-3/4 mb-2"></div>
                    <div className="h-4 bg-slate-700 rounded w-1/2"></div>
                  </div>
                ) : stats.hasData ? (
                  <>
                    <div className="text-2xl font-bold text-white">
                      {stats.current.toFixed(metric === 'error_rate' ? 2 : 0)}
                      <span className="text-sm font-normal text-slate-500 ml-1">
                        {def.unit}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      Avg: {stats.avg.toFixed(metric === 'error_rate' ? 2 : 0)} {def.unit}
                    </div>
                  </>
                ) : (
                  <div className="text-slate-500 text-sm">No data</div>
                )}
              </div>
            )
          })}
        </div>

        {/* Main Chart */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-400" />
              {isStreaming ? 'Live Metrics' : 'Time Series'}
            </h2>
            {isStreaming && (
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                <span className="text-sm text-emerald-400">Streaming</span>
              </div>
            )}
          </div>

          {error ? (
            <div className="flex items-center justify-center h-80 text-red-400">
              {error}
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center h-80">
              <div className="animate-pulse flex flex-col items-center gap-4">
                <RefreshCw className="w-8 h-8 text-slate-500 animate-spin" />
                <span className="text-slate-400">Loading metrics...</span>
              </div>
            </div>
          ) : !hasAnyData && chartData.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-80 text-slate-400">
              <BarChart3 className="w-12 h-12 text-slate-600 mb-4" />
              <p className="text-lg font-medium">No metrics data available</p>
              <p className="text-sm text-slate-500 mt-1">Try adjusting the time range or check your data sources</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={400}>
              <AreaChart data={chartData}>
                <defs>
                  {selectedMetrics.map(metric => (
                    <linearGradient key={metric} id={`gradient-${metric}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={METRIC_DEFINITIONS[metric].color} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={METRIC_DEFINITIONS[metric].color} stopOpacity={0} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis
                  dataKey="time"
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '12px',
                    color: '#fff',
                    backdropFilter: 'blur(8px)'
                  }}
                />
                <Legend />
                {selectedMetrics.map(metric => (
                  <Area
                    key={metric}
                    type="monotone"
                    dataKey={metric}
                    name={METRIC_DEFINITIONS[metric].name}
                    stroke={METRIC_DEFINITIONS[metric].color}
                    fill={`url(#gradient-${metric})`}
                    strokeWidth={2}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
            <h3 className="text-sm font-medium text-white mb-3">Auto Refresh</h3>
            <div className="flex items-center gap-3">
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  disabled={isStreaming}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-600 peer-focus:ring-2 peer-focus:ring-blue-500/50 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600" />
              </label>
              {autoRefresh && (
                <select
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(Number(e.target.value))}
                  className="px-2 py-1 bg-slate-700/50 border border-white/10 rounded text-sm text-white focus:outline-none"
                >
                  <option value={10000}>10s</option>
                  <option value={30000}>30s</option>
                  <option value={60000}>1m</option>
                  <option value={300000}>5m</option>
                </select>
              )}
            </div>
          </div>

          <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
            <h3 className="text-sm font-medium text-white mb-3">Data Points</h3>
            <div className="text-2xl font-bold text-white">
              {isStreaming ? streamingData.length : Object.values(metricsData).reduce((acc, d) => acc + d.length, 0)}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              {isStreaming ? 'Live data points' : 'Historical data points'}
            </div>
          </div>

          <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
            <h3 className="text-sm font-medium text-white mb-3">Selected Metrics</h3>
            <div className="flex flex-wrap gap-1">
              {selectedMetrics.map(metric => (
                <span
                  key={metric}
                  className="px-2 py-1 text-xs rounded-md border"
                  style={{
                    backgroundColor: `${METRIC_DEFINITIONS[metric].color}15`,
                    borderColor: `${METRIC_DEFINITIONS[metric].color}30`,
                    color: METRIC_DEFINITIONS[metric].color
                  }}
                >
                  {METRIC_DEFINITIONS[metric].name}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
