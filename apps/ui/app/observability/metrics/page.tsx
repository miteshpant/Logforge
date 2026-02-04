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
// Categories: apm, infrastructure, database, cache, queue
const METRIC_DEFINITIONS = {
  // APM Metrics
  response_time: {
    name: 'Response Time',
    icon: Clock,
    unit: 'ms',
    color: '#3b82f6',
    category: 'apm',
    description: 'HTTP response time / request latency'
  },
  throughput: {
    name: 'Throughput',
    icon: Activity,
    unit: 'req/s',
    color: '#10b981',
    category: 'apm',
    description: 'Request throughput / requests per second'
  },
  error_rate: {
    name: 'Error Rate',
    icon: AlertTriangle,
    unit: '%',
    color: '#ef4444',
    category: 'apm',
    description: 'Error rate percentage'
  },
  // Infrastructure Metrics
  cpu_usage: {
    name: 'CPU Usage',
    icon: Cpu,
    unit: '%',
    color: '#f59e0b',
    category: 'infrastructure',
    description: 'CPU utilization percentage'
  },
  memory_usage: {
    name: 'Memory Usage',
    icon: HardDrive,
    unit: '%',
    color: '#8b5cf6',
    category: 'infrastructure',
    description: 'Memory utilization percentage'
  },
  disk_usage: {
    name: 'Disk Usage',
    icon: HardDrive,
    unit: '%',
    color: '#6366f1',
    category: 'infrastructure',
    description: 'Disk utilization percentage'
  },
  network_in: {
    name: 'Network In',
    icon: Activity,
    unit: 'bytes',
    color: '#14b8a6',
    category: 'infrastructure',
    description: 'Network bytes received'
  },
  network_out: {
    name: 'Network Out',
    icon: Activity,
    unit: 'bytes',
    color: '#0ea5e9',
    category: 'infrastructure',
    description: 'Network bytes transmitted'
  },
  // Database Metrics
  db_connections: {
    name: 'DB Connections',
    icon: Activity,
    unit: 'count',
    color: '#a855f7',
    category: 'database',
    description: 'Database active connections'
  },
  db_query_time: {
    name: 'DB Query Time',
    icon: Clock,
    unit: 'ms',
    color: '#d946ef',
    category: 'database',
    description: 'Database query execution time'
  },
  // Cache Metrics
  cache_hit_rate: {
    name: 'Cache Hit Rate',
    icon: TrendingUp,
    unit: '%',
    color: '#22c55e',
    category: 'cache',
    description: 'Cache hit rate percentage'
  },
  cache_miss_rate: {
    name: 'Cache Miss Rate',
    icon: TrendingDown,
    unit: '%',
    color: '#f97316',
    category: 'cache',
    description: 'Cache miss rate percentage'
  },
  // Queue Metrics
  queue_depth: {
    name: 'Queue Depth',
    icon: BarChart3,
    unit: 'count',
    color: '#ec4899',
    category: 'queue',
    description: 'Queue message depth/backlog'
  },
  queue_latency: {
    name: 'Queue Latency',
    icon: Clock,
    unit: 'ms',
    color: '#f43f5e',
    category: 'queue',
    description: 'Queue message processing latency'
  }
}

type MetricType = keyof typeof METRIC_DEFINITIONS
type AggregationType = 'avg' | 'min' | 'max' | 'sum' | 'p50' | 'p95' | 'p99'

interface MetricDataPoint {
  timestamp: string
  value: number
  service?: string
}

// Format large numbers with K/M/G suffixes
const formatValue = (value: number, unit: string): { value: string; unit: string } => {
  // For percentages, just format with appropriate decimals
  if (unit === '%') {
    return { value: value.toFixed(value < 10 ? 2 : 1), unit: '%' }
  }

  // For bytes, convert to KB/MB/GB
  if (unit === 'bytes') {
    if (value >= 1e9) {
      return { value: (value / 1e9).toFixed(2), unit: 'GB' }
    } else if (value >= 1e6) {
      return { value: (value / 1e6).toFixed(2), unit: 'MB' }
    } else if (value >= 1e3) {
      return { value: (value / 1e3).toFixed(2), unit: 'KB' }
    }
    return { value: value.toFixed(0), unit: 'B' }
  }

  // For counts, convert to K/M
  if (unit === 'count' || unit === 'req/s') {
    if (value >= 1e6) {
      return { value: (value / 1e6).toFixed(2), unit: unit === 'req/s' ? 'M/s' : 'M' }
    } else if (value >= 1e3) {
      return { value: (value / 1e3).toFixed(2), unit: unit === 'req/s' ? 'K/s' : 'K' }
    }
    return { value: value.toFixed(value < 10 ? 1 : 0), unit }
  }

  // For ms, convert to seconds if large
  if (unit === 'ms') {
    if (value >= 1000) {
      return { value: (value / 1000).toFixed(2), unit: 's' }
    }
    return { value: value.toFixed(value < 10 ? 1 : 0), unit: 'ms' }
  }

  // Default formatting
  if (value >= 1e6) {
    return { value: (value / 1e6).toFixed(2), unit: `M ${unit}` }
  } else if (value >= 1e3) {
    return { value: (value / 1e3).toFixed(2), unit: `K ${unit}` }
  }

  return { value: value.toFixed(value < 10 ? 2 : 0), unit }
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

  // Fetch available services that have metrics data
  useEffect(() => {
    const fetchServices = async () => {
      try {
        const response = await apiClient.get('/v1/observability/metrics/services')
        const data = response.data
        if (data?.services) {
          setServices(data.services)
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

  // Fetch a single metric - used when toggling individual metrics
  const fetchSingleMetric = useCallback(async (metric: MetricType) => {
    try {
      const { start_time, end_time } = getApiTimeRange()
      const granularity = calculateGranularity(start_time, end_time)

      const response = await apiClient.post('/v1/observability/metrics/query', {
        metric_name: metric,
        start_time,
        end_time,
        aggregation,
        service_name: selectedService !== 'all' ? selectedService : undefined,
        granularity
      })

      const data = response.data
      let metricData: MetricDataPoint[] = []

      if (data?.metrics?.[metric]) {
        metricData = data.metrics[metric]
      } else if (data?.data) {
        metricData = data.data
      } else if (Array.isArray(data)) {
        metricData = data
      }

      // Add to existing data without replacing everything
      setMetricsData(prev => ({ ...prev, [metric]: metricData }))
    } catch (err) {
      console.error(`Failed to fetch metric ${metric}:`, err)
    }
  }, [aggregation, selectedService, getApiTimeRange])

  // Query all selected metrics - used for full refresh
  const queryMetrics = useCallback(async (metricsToFetch?: MetricType[]) => {
    const metrics = metricsToFetch || selectedMetrics
    if (metrics.length === 0) {
      setMetricsData({})
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const { start_time, end_time } = getApiTimeRange()
      const granularity = calculateGranularity(start_time, end_time)

      // Fetch all metrics in parallel using Promise.allSettled
      const metricPromises = metrics.map(metric =>
        apiClient.post('/v1/observability/metrics/query', {
          metric_name: metric,
          start_time,
          end_time,
          aggregation,
          service_name: selectedService !== 'all' ? selectedService : undefined,
          granularity
        }).then(response => ({ metric, response }))
      )

      const settledResults = await Promise.allSettled(metricPromises)

      const results: Record<string, MetricDataPoint[]> = {}

      settledResults.forEach((result) => {
        if (result.status === 'fulfilled') {
          const { metric, response } = result.value
          const data = response.data

          // Handle different response formats from API
          if (data?.metrics?.[metric]) {
            results[metric] = data.metrics[metric]
          } else if (data?.data) {
            results[metric] = data.data
          } else if (Array.isArray(data)) {
            results[metric] = data
          }
        } else {
          console.error('Failed to query metric:', result.reason)
        }
      })

      setMetricsData(results)
    } catch (err) {
      setError('Failed to query metrics')
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }, [selectedMetrics, aggregation, selectedService, getApiTimeRange])

  // Fetch all data when aggregation, service filter, or time range changes (full refresh needed)
  useEffect(() => {
    if (selectedMetrics.length > 0) {
      queryMetrics()
    }
  }, [aggregation, selectedService, currentTimeRange.value])

  // Initial load
  useEffect(() => {
    queryMetrics()
  }, [])

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
      // SSE doesn't support custom headers, pass customer_id as query param
      const customerId = localStorage.getItem('customer_id') || 'default'
      const eventSource = new EventSource(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'}/v1/stream/metrics?customer_id=${encodeURIComponent(customerId)}`
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

  // Toggle metric selection - only fetch new metric, don't refresh everything
  const toggleMetric = (metric: MetricType) => {
    const isCurrentlySelected = selectedMetrics.includes(metric)

    if (isCurrentlySelected) {
      // Deselecting: remove from selection and data (no API call needed)
      setSelectedMetrics(prev => prev.filter(m => m !== metric))
      setMetricsData(prev => {
        const newData = { ...prev }
        delete newData[metric]
        return newData
      })
    } else {
      // Selecting: add to selection and fetch only this metric
      setSelectedMetrics(prev => [...prev, metric])
      fetchSingleMetric(metric)
    }
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

  // Get metrics grouped by category
  const getMetricsByCategory = (category: string) => {
    return selectedMetrics.filter(m => METRIC_DEFINITIONS[m].category === category)
  }

  // Get chart data for a specific category
  const getCategoryChartData = (categoryMetrics: MetricType[]) => {
    if (categoryMetrics.length === 0) return []

    const allTimestamps = new Set<string>()
    categoryMetrics.forEach(metric => {
      const data = metricsData[metric] || []
      data.forEach(point => allTimestamps.add(point.timestamp))
    })

    const sortedTimestamps = Array.from(allTimestamps).sort()

    return sortedTimestamps.map(timestamp => {
      const point: any = { time: new Date(timestamp).toLocaleTimeString() }
      categoryMetrics.forEach(metric => {
        const data = metricsData[metric] || []
        const matchingPoint = data.find(d => d.timestamp === timestamp)
        if (matchingPoint) {
          point[metric] = Math.round(matchingPoint.value * 100) / 100
        }
      })
      return point
    })
  }

  // Category labels and icons
  const categoryConfig: Record<string, { label: string; color: string }> = {
    apm: { label: 'APM Metrics', color: '#3b82f6' },
    infrastructure: { label: 'Infrastructure Metrics', color: '#f59e0b' },
    database: { label: 'Database Metrics', color: '#a855f7' },
    cache: { label: 'Cache Metrics', color: '#22c55e' },
    queue: { label: 'Queue Metrics', color: '#ec4899' }
  }

  // Get categories with selected metrics
  const activeCategories = (['apm', 'infrastructure', 'database', 'cache', 'queue'] as const)
    .filter(cat => getMetricsByCategory(cat).length > 0)

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Global Controls Bar */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4">
          <div className="flex flex-wrap items-center gap-4">
            <h1 className="text-lg font-semibold text-white">Metrics Explorer</h1>

            <div className="h-6 w-px bg-white/10" />

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

            {/* Auto Refresh Toggle */}
            <div className="flex items-center gap-2">
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  disabled={isStreaming}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-slate-600 peer-focus:ring-2 peer-focus:ring-blue-500/50 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" />
              </label>
              <span className="text-xs text-slate-400">Auto</span>
              {autoRefresh && (
                <select
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(Number(e.target.value))}
                  className="px-2 py-1 bg-slate-700/50 border border-white/10 rounded text-xs text-white focus:outline-none"
                >
                  <option value={10000}>10s</option>
                  <option value={30000}>30s</option>
                  <option value={60000}>1m</option>
                </select>
              )}
            </div>

            <div className="flex-1" />

            {/* Streaming Toggle */}
            {isStreaming ? (
              <button
                onClick={stopStreaming}
                className="flex items-center gap-2 px-3 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 rounded-lg text-sm font-medium transition-all"
              >
                <Pause className="w-4 h-4" />
                Stop Live
              </button>
            ) : (
              <button
                onClick={startStreaming}
                className="flex items-center gap-2 px-3 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 rounded-lg text-sm font-medium transition-all"
              >
                <Play className="w-4 h-4" />
                Live Mode
              </button>
            )}

            {/* Refresh Button */}
            <button
              onClick={queryMetrics}
              disabled={isLoading || isStreaming}
              className="flex items-center gap-2 px-3 py-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 border border-blue-500/30 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="relative overflow-hidden rounded-2xl bg-red-500/10 border border-red-500/20 p-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Category Sections */}
        {(['apm', 'infrastructure', 'database', 'cache', 'queue'] as const).map(category => {
          const categoryMetrics = Object.entries(METRIC_DEFINITIONS).filter(([, def]) => def.category === category)
          const selectedCategoryMetrics = getMetricsByCategory(category)
          const categoryData = getCategoryChartData(selectedCategoryMetrics)
          const config = categoryConfig[category]
          const hasCategoryData = categoryData.length > 0

          return (
            <div
              key={category}
              className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5"
            >
              {/* Category Header */}
              <div className="px-5 py-4 border-b border-white/5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: config.color }}
                    />
                    <h2 className="text-lg font-semibold text-white">{config.label}</h2>
                    {isStreaming && selectedCategoryMetrics.length > 0 && (
                      <div className="flex items-center gap-1 ml-2">
                        <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                        <span className="text-xs text-emerald-400">Live</span>
                      </div>
                    )}
                  </div>

                  {/* Metric Toggles */}
                  <div className="flex flex-wrap gap-2">
                    {categoryMetrics.map(([key, def]) => {
                      const Icon = def.icon
                      const isSelected = selectedMetrics.includes(key as MetricType)
                      return (
                        <button
                          key={key}
                          onClick={() => toggleMetric(key as MetricType)}
                          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                            isSelected
                              ? 'text-white border'
                              : 'bg-slate-700/50 text-slate-400 hover:bg-slate-600/50 border border-white/5'
                          }`}
                          style={isSelected ? {
                            backgroundColor: `${def.color}20`,
                            borderColor: `${def.color}50`,
                            color: def.color
                          } : undefined}
                        >
                          <Icon className="w-3.5 h-3.5" />
                          {def.name}
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* Category Content */}
              {selectedCategoryMetrics.length === 0 ? (
                <div className="px-5 py-8 text-center text-slate-500">
                  <p className="text-sm">Select metrics above to view data</p>
                </div>
              ) : (
                <div className="p-5 space-y-4">
                  {/* Stats Cards */}
                  <div className={`grid gap-3 ${
                    selectedCategoryMetrics.length === 1 ? 'grid-cols-1 max-w-xs' :
                    selectedCategoryMetrics.length === 2 ? 'grid-cols-2 max-w-lg' :
                    selectedCategoryMetrics.length <= 4 ? 'grid-cols-2 md:grid-cols-4' :
                    'grid-cols-2 md:grid-cols-3 lg:grid-cols-5'
                  }`}>
                    {selectedCategoryMetrics.map(metric => {
                      const def = METRIC_DEFINITIONS[metric]
                      const Icon = def.icon
                      const stats = calculateStats(metric)

                      return (
                        <div
                          key={metric}
                          className="rounded-xl p-3 bg-slate-800/50 border border-white/5"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <div
                                className="w-7 h-7 rounded-lg flex items-center justify-center"
                                style={{ backgroundColor: `${def.color}15` }}
                              >
                                <Icon className="w-3.5 h-3.5" style={{ color: def.color }} />
                              </div>
                              <span className="text-xs text-slate-400">{def.name}</span>
                            </div>
                            {stats.hasData && stats.trend !== 0 && (
                              <div className={`flex items-center gap-0.5 text-xs ${
                                stats.trend > 0
                                  ? metric === 'error_rate' || metric === 'cache_miss_rate' ? 'text-red-400' : 'text-emerald-400'
                                  : metric === 'error_rate' || metric === 'cache_miss_rate' ? 'text-emerald-400' : 'text-red-400'
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
                              <div className="h-6 bg-slate-700 rounded w-3/4 mb-1"></div>
                              <div className="h-3 bg-slate-700 rounded w-1/2"></div>
                            </div>
                          ) : stats.hasData ? (
                            (() => {
                              const formatted = formatValue(stats.current, def.unit)
                              const formattedAvg = formatValue(stats.avg, def.unit)
                              return (
                                <>
                                  <div className="text-xl font-bold text-white">
                                    {formatted.value}
                                    <span className="text-xs font-normal text-slate-500 ml-1">{formatted.unit}</span>
                                  </div>
                                  <div className="text-xs text-slate-500">
                                    Avg: {formattedAvg.value} {formattedAvg.unit}
                                  </div>
                                </>
                              )
                            })()
                          ) : (
                            <div className="text-slate-500 text-sm">No data</div>
                          )}
                        </div>
                      )
                    })}
                  </div>

                  {/* Chart */}
                  {isLoading ? (
                    <div className="flex items-center justify-center h-48">
                      <RefreshCw className="w-6 h-6 text-slate-500 animate-spin" />
                    </div>
                  ) : !hasCategoryData ? (
                    <div className="flex flex-col items-center justify-center h-48 text-slate-500">
                      <BarChart3 className="w-8 h-8 text-slate-600 mb-2" />
                      <p className="text-sm">No data available for selected time range</p>
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height={200}>
                      <AreaChart data={categoryData}>
                        <defs>
                          {selectedCategoryMetrics.map(metric => (
                            <linearGradient key={metric} id={`gradient-${category}-${metric}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor={METRIC_DEFINITIONS[metric].color} stopOpacity={0.3} />
                              <stop offset="95%" stopColor={METRIC_DEFINITIONS[metric].color} stopOpacity={0} />
                            </linearGradient>
                          ))}
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                        <XAxis
                          dataKey="time"
                          stroke="#64748b"
                          fontSize={10}
                          tickLine={false}
                          axisLine={false}
                        />
                        <YAxis
                          stroke="#64748b"
                          fontSize={10}
                          tickLine={false}
                          axisLine={false}
                          width={45}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: 'rgba(15, 23, 42, 0.95)',
                            border: '1px solid rgba(255, 255, 255, 0.1)',
                            borderRadius: '8px',
                            color: '#fff',
                            fontSize: '12px'
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: '11px' }} />
                        {selectedCategoryMetrics.map(metric => (
                          <Area
                            key={metric}
                            type="monotone"
                            dataKey={metric}
                            name={METRIC_DEFINITIONS[metric].name}
                            stroke={METRIC_DEFINITIONS[metric].color}
                            fill={`url(#gradient-${category}-${metric})`}
                            strokeWidth={2}
                          />
                        ))}
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </div>
              )}
            </div>
          )
        })}

        {/* Summary Footer */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
            <div className="text-xs text-slate-500 mb-1">Total Data Points</div>
            <div className="text-xl font-bold text-white">
              {isStreaming ? streamingData.length : Object.values(metricsData).reduce((acc, d) => acc + d.length, 0)}
            </div>
          </div>
          <div className="rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
            <div className="text-xs text-slate-500 mb-1">Selected Metrics</div>
            <div className="text-xl font-bold text-white">{selectedMetrics.length}</div>
          </div>
          <div className="rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
            <div className="text-xs text-slate-500 mb-1">Active Categories</div>
            <div className="text-xl font-bold text-white">{activeCategories.length}</div>
          </div>
          <div className="rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
            <div className="text-xs text-slate-500 mb-1">Status</div>
            <div className={`text-xl font-bold ${isStreaming ? 'text-emerald-400' : isLoading ? 'text-yellow-400' : 'text-white'}`}>
              {isStreaming ? 'Streaming' : isLoading ? 'Loading' : 'Ready'}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
