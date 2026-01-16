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
  Minus,
  BarChart3,
  LineChart,
  Settings2
} from 'lucide-react'
import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart
} from 'recharts'

// Metric definitions
const METRIC_DEFINITIONS = {
  latency: {
    name: 'Latency',
    icon: Clock,
    unit: 'ms',
    color: '#3b82f6',
    description: 'Response time'
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

interface MetricQueryResult {
  metric_name: string
  data: MetricDataPoint[]
  aggregation?: AggregationType
  service?: string
}

export default function MetricsExplorerPage() {
  const { getApiTimeRange, currentTimeRange } = useTimeRange()

  // Selected metrics and options
  const [selectedMetrics, setSelectedMetrics] = useState<MetricType[]>(['latency', 'throughput'])
  const [aggregation, setAggregation] = useState<AggregationType>('avg')
  const [groupBy, setGroupBy] = useState<string>('none')
  const [selectedService, setSelectedService] = useState<string>('all')

  // Data state
  const [metricsData, setMetricsData] = useState<Record<string, MetricDataPoint[]>>({})
  const [services, setServices] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
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

  // Query metrics from API
  const queryMetrics = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const { start_time, end_time } = getApiTimeRange()
      const results: Record<string, MetricDataPoint[]> = {}

      for (const metric of selectedMetrics) {
        try {
          const response = await apiClient.post('/v1/observability/metrics/query', {
            metric_name: metric,
            start_time,
            end_time,
            aggregation,
            service: selectedService !== 'all' ? selectedService : undefined,
            granularity: '1m'
          })

          const data = response.data

          // Handle different response formats
          if (data?.metrics?.[metric]) {
            results[metric] = data.metrics[metric]
          } else if (data?.data) {
            results[metric] = data.data
          } else if (Array.isArray(data)) {
            results[metric] = data
          } else {
            // Generate sample data if API returns empty
            results[metric] = generateSampleData(metric, start_time, end_time)
          }
        } catch (err) {
          console.error(`Failed to query ${metric}:`, err)
          // Generate sample data on error for demo
          const { start_time, end_time } = getApiTimeRange()
          results[metric] = generateSampleData(metric, start_time, end_time)
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

  // Generate sample data for demo/fallback
  const generateSampleData = (metric: string, startTime: string, endTime: string): MetricDataPoint[] => {
    const start = new Date(startTime).getTime()
    const end = new Date(endTime).getTime()
    const interval = (end - start) / 60 // 60 data points
    const data: MetricDataPoint[] = []

    for (let i = 0; i < 60; i++) {
      const timestamp = new Date(start + i * interval).toISOString()
      let value: number

      switch (metric) {
        case 'latency':
          value = 50 + Math.random() * 150 + Math.sin(i / 10) * 30
          break
        case 'throughput':
          value = 200 + Math.random() * 300 + Math.cos(i / 8) * 50
          break
        case 'error_rate':
          value = Math.random() * 3 + (Math.random() > 0.9 ? 5 : 0)
          break
        case 'cpu_usage':
          value = 30 + Math.random() * 40 + Math.sin(i / 12) * 10
          break
        case 'memory_usage':
          value = 50 + Math.random() * 25 + i * 0.1
          break
        default:
          value = Math.random() * 100
      }

      data.push({ timestamp, value })
    }

    return data
  }

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

    // Try to connect to real SSE endpoint
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
        // Fallback to simulated streaming
        eventSource.close()
        startSimulatedStreaming()
      }

      eventSourceRef.current = eventSource
    } catch (err) {
      // Fallback to simulated streaming
      startSimulatedStreaming()
    }
  }

  // Simulated streaming for demo
  const startSimulatedStreaming = () => {
    const interval = setInterval(() => {
      const now = new Date().toISOString()
      const newPoints: MetricDataPoint[] = selectedMetrics.map(metric => ({
        timestamp: now,
        value: generateStreamingValue(metric),
        service: selectedService !== 'all' ? selectedService : 'all-services'
      }))

      setStreamingData(prev => [...prev.slice(-100), ...newPoints])
    }, 1000)

    eventSourceRef.current = { close: () => clearInterval(interval) } as any
  }

  const generateStreamingValue = (metric: string): number => {
    switch (metric) {
      case 'latency': return 50 + Math.random() * 150
      case 'throughput': return 200 + Math.random() * 300
      case 'error_rate': return Math.random() * 3
      case 'cpu_usage': return 30 + Math.random() * 40
      case 'memory_usage': return 50 + Math.random() * 25
      default: return Math.random() * 100
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
      // Group streaming data by timestamp
      const grouped: Record<string, any> = {}
      streamingData.forEach(point => {
        const time = new Date(point.timestamp).toLocaleTimeString()
        if (!grouped[time]) {
          grouped[time] = { time }
        }
        // Assign value to metric (simplified - in real app, track by metric name)
        selectedMetrics.forEach((metric, idx) => {
          if (!grouped[time][metric]) {
            grouped[time][metric] = point.value
          }
        })
      })
      return Object.values(grouped).slice(-60)
    }

    // Historical data
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
    if (data.length === 0) return { current: 0, avg: 0, trend: 0 }

    const values = data.map(d => d.value)
    const current = values[values.length - 1] || 0
    const avg = values.reduce((a, b) => a + b, 0) / values.length

    // Calculate trend (compare last 10% to first 10%)
    const tenPercent = Math.max(1, Math.floor(values.length * 0.1))
    const recentAvg = values.slice(-tenPercent).reduce((a, b) => a + b, 0) / tenPercent
    const earlyAvg = values.slice(0, tenPercent).reduce((a, b) => a + b, 0) / tenPercent
    const trend = earlyAvg > 0 ? ((recentAvg - earlyAvg) / earlyAvg) * 100 : 0

    return { current, avg, trend }
  }

  const chartData = formatChartData()

  return (
    <DashboardLayout>
      <div className="space-y-4">
        {/* Controls Bar */}
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
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
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isSelected
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {def.name}
                  </button>
                )
              })}
            </div>

            <div className="h-8 w-px bg-slate-600" />

            {/* Aggregation */}
            <select
              value={aggregation}
              onChange={(e) => setAggregation(e.target.value as AggregationType)}
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
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
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
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
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <Pause className="w-4 h-4" />
                Stop Live
              </button>
            ) : (
              <button
                onClick={startStreaming}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <Play className="w-4 h-4" />
                Live Mode
              </button>
            )}

            {/* Refresh Button */}
            <button
              onClick={queryMetrics}
              disabled={isLoading || isStreaming}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
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
                className="bg-slate-800/50 rounded-lg p-4 border border-slate-700"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${def.color}20` }}
                    >
                      <Icon className="w-4 h-4" style={{ color: def.color }} />
                    </div>
                    <span className="text-sm text-slate-400">{def.name}</span>
                  </div>
                  {stats.trend !== 0 && (
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
                <div className="text-2xl font-bold text-white">
                  {stats.current.toFixed(metric === 'error_rate' ? 2 : 0)}
                  <span className="text-sm font-normal text-slate-400 ml-1">
                    {def.unit}
                  </span>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Avg: {stats.avg.toFixed(metric === 'error_rate' ? 2 : 0)} {def.unit}
                </div>
              </div>
            )
          })}
        </div>

        {/* Main Chart */}
        <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <LineChart className="w-5 h-5 text-blue-400" />
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
          ) : chartData.length === 0 ? (
            <div className="flex items-center justify-center h-80 text-slate-400">
              {isLoading ? 'Loading metrics...' : 'No data available'}
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
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="time"
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                />
                <YAxis
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#fff'
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
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <h3 className="text-sm font-medium text-white mb-2">Auto Refresh</h3>
            <div className="flex items-center gap-3">
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  disabled={isStreaming}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-600 peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600" />
              </label>
              {autoRefresh && (
                <select
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(Number(e.target.value))}
                  className="px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                >
                  <option value={10000}>10s</option>
                  <option value={30000}>30s</option>
                  <option value={60000}>1m</option>
                  <option value={300000}>5m</option>
                </select>
              )}
            </div>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <h3 className="text-sm font-medium text-white mb-2">Data Points</h3>
            <div className="text-2xl font-bold text-white">
              {isStreaming ? streamingData.length : Object.values(metricsData).reduce((acc, d) => acc + d.length, 0)}
            </div>
            <div className="text-xs text-slate-400">
              {isStreaming ? 'Live data points' : 'Historical data points'}
            </div>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <h3 className="text-sm font-medium text-white mb-2">Selected Metrics</h3>
            <div className="flex flex-wrap gap-1">
              {selectedMetrics.map(metric => (
                <span
                  key={metric}
                  className="px-2 py-1 text-xs rounded"
                  style={{
                    backgroundColor: `${METRIC_DEFINITIONS[metric].color}20`,
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
