'use client'

import { useState, useEffect, useRef, memo } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import APMServiceOverview from '@/components/observability/APMServiceOverview'
import APMSlowestEndpoints from '@/components/observability/APMSlowestEndpoints'
import APMErrorRates from '@/components/observability/APMErrorRates'
import APMTransactions from '@/components/observability/APMTransactions'
import APMApdexScore from '@/components/observability/APMApdexScore'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import { GitCompare, RefreshCw, Pause, Play } from 'lucide-react'

// Comparison period options
export type ComparisonPeriod = 'none' | 'previous_period' | 'yesterday' | 'last_week'

// Auto-refresh interval options (in milliseconds)
export type RefreshInterval = 0 | 10000 | 30000 | 60000 | 300000

export interface ServicePerformance {
  service_name: string
  request_count: number
  avg_latency_ms: number
  p50_latency_ms: number
  p95_latency_ms: number
  p99_latency_ms: number
  error_rate: number
  throughput: number
  apdex_score: number
}

// Aggregated metrics for comparison
export interface AggregatedMetrics {
  total_requests: number
  avg_latency_ms: number
  error_rate: number
  throughput: number
}

export interface EndpointPerformance {
  endpoint: string
  service: string
  request_count: number
  avg_latency_ms: number
  p50_latency_ms: number
  p95_latency_ms: number
  p99_latency_ms: number
  error_rate: number
}

export interface ErrorRateMetric {
  timestamp: number
  service: string
  error_rate: number
  error_count: number
  total_requests: number
}

export interface Transaction {
  name: string
  service: string
  count: number
  avg_duration_ms: number
  percentage: number
}

// Memoized components to prevent unnecessary re-renders
const MemoizedServiceOverview = memo(APMServiceOverview)
const MemoizedApdexScore = memo(APMApdexScore)
const MemoizedSlowestEndpoints = memo(APMSlowestEndpoints)
const MemoizedErrorRates = memo(APMErrorRates)
const MemoizedTransactions = memo(APMTransactions)

// Helper to calculate comparison time range
function getComparisonTimeRange(
  startTime: string,
  endTime: string,
  period: ComparisonPeriod
): { start_time: string; end_time: string } | null {
  if (period === 'none') return null

  const start = new Date(startTime)
  const end = new Date(endTime)
  const duration = end.getTime() - start.getTime()

  let compStart: Date
  let compEnd: Date

  switch (period) {
    case 'previous_period':
      compEnd = new Date(start.getTime())
      compStart = new Date(start.getTime() - duration)
      break
    case 'yesterday':
      compStart = new Date(start.getTime() - 24 * 60 * 60 * 1000)
      compEnd = new Date(end.getTime() - 24 * 60 * 60 * 1000)
      break
    case 'last_week':
      compStart = new Date(start.getTime() - 7 * 24 * 60 * 60 * 1000)
      compEnd = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000)
      break
    default:
      return null
  }

  return {
    start_time: compStart.toISOString(),
    end_time: compEnd.toISOString()
  }
}

export default function APMPage() {
  const { getApiTimeRange, currentTimeRange } = useTimeRange()

  // Separate state for each component
  const [services, setServices] = useState<ServicePerformance[]>([])
  const [isLoadingServices, setIsLoadingServices] = useState(true)

  const [endpoints, setEndpoints] = useState<EndpointPerformance[]>([])
  const [isLoadingEndpoints, setIsLoadingEndpoints] = useState(true)

  const [errorRates, setErrorRates] = useState<ErrorRateMetric[]>([])
  const [isLoadingErrorRates, setIsLoadingErrorRates] = useState(true)

  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoadingTransactions, setIsLoadingTransactions] = useState(true)

  const [selectedService, setSelectedService] = useState<string>('all')

  // Comparison mode state
  const [comparisonPeriod, setComparisonPeriod] = useState<ComparisonPeriod>('none')
  const [comparisonServices, setComparisonServices] = useState<ServicePerformance[]>([])
  const [isLoadingComparison, setIsLoadingComparison] = useState(false)

  // Auto-refresh state
  const [refreshInterval, setRefreshInterval] = useState<RefreshInterval>(0)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const autoRefreshRef = useRef<NodeJS.Timeout | null>(null)

  // Progressive loading flags
  const [enableServices, setEnableServices] = useState(false)
  const [enableEndpoints, setEnableEndpoints] = useState(false)
  const [enableErrorRates, setEnableErrorRates] = useState(false)
  const [enableTransactions, setEnableTransactions] = useState(false)

  // Abort controllers for request cancellation
  const servicesAbortRef = useRef<AbortController | null>(null)
  const endpointsAbortRef = useRef<AbortController | null>(null)
  const errorRatesAbortRef = useRef<AbortController | null>(null)
  const transactionsAbortRef = useRef<AbortController | null>(null)

  // Individual data loaders
  const loadServices = async () => {
    try {
      if (servicesAbortRef.current) servicesAbortRef.current.abort()
      servicesAbortRef.current = new AbortController()

      setIsLoadingServices(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<{ services: ServicePerformance[] }>('/v1/observability/apm/services', {
        start_time,
        end_time
      })

      const data = response?.data?.data || response?.data || response
      if (data && Array.isArray(data.services)) {
        setServices(data.services)
      } else if (Array.isArray(data)) {
        setServices(data)
      } else {
        setServices([])
      }
    } catch (error: any) {
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load services:', error)
      }
      setServices([])
    } finally {
      setIsLoadingServices(false)
    }
  }

  const loadEndpoints = async () => {
    try {
      if (endpointsAbortRef.current) endpointsAbortRef.current.abort()
      endpointsAbortRef.current = new AbortController()

      setIsLoadingEndpoints(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<{ endpoints: EndpointPerformance[] }>('/v1/observability/apm/slowest-endpoints', {
        start_time,
        end_time,
        limit: 10
      })

      const data = response?.data?.data || response?.data || response
      if (data && Array.isArray(data.endpoints)) {
        setEndpoints(data.endpoints)
      } else if (Array.isArray(data)) {
        setEndpoints(data)
      } else {
        setEndpoints([])
      }
    } catch (error: any) {
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load endpoints:', error)
      }
      setEndpoints([])
    } finally {
      setIsLoadingEndpoints(false)
    }
  }

  const loadErrorRates = async () => {
    try {
      if (errorRatesAbortRef.current) errorRatesAbortRef.current.abort()
      errorRatesAbortRef.current = new AbortController()

      setIsLoadingErrorRates(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<{ metrics: ErrorRateMetric[] }>('/v1/observability/apm/error-rates', {
        start_time,
        end_time,
        interval: '5m'
      })

      const data = response?.data?.data || response?.data || response
      if (data && Array.isArray(data.metrics)) {
        setErrorRates(data.metrics)
      } else if (Array.isArray(data)) {
        setErrorRates(data)
      } else {
        setErrorRates([])
      }
    } catch (error: any) {
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load error rates:', error)
      }
      setErrorRates([])
    } finally {
      setIsLoadingErrorRates(false)
    }
  }

  const loadTransactions = async () => {
    try {
      if (transactionsAbortRef.current) transactionsAbortRef.current.abort()
      transactionsAbortRef.current = new AbortController()

      setIsLoadingTransactions(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<{ transactions: Transaction[] }>('/v1/observability/apm/transactions', {
        start_time,
        end_time,
        limit: 10
      })

      const data = response?.data?.data || response?.data || response
      if (data && Array.isArray(data.transactions)) {
        setTransactions(data.transactions)
      } else if (Array.isArray(data)) {
        setTransactions(data)
      } else {
        setTransactions([])
      }
    } catch (error: any) {
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load transactions:', error)
      }
      setTransactions([])
    } finally {
      setIsLoadingTransactions(false)
    }
  }

  // Load comparison data
  const loadComparisonData = async () => {
    if (comparisonPeriod === 'none') {
      setComparisonServices([])
      return
    }

    try {
      setIsLoadingComparison(true)
      const { start_time, end_time } = getApiTimeRange()
      const compRange = getComparisonTimeRange(start_time, end_time, comparisonPeriod)

      if (!compRange) {
        setComparisonServices([])
        return
      }

      const response = await apiClient.get<{ services: ServicePerformance[] }>('/v1/observability/apm/services', {
        start_time: compRange.start_time,
        end_time: compRange.end_time
      })

      const data = response?.data?.data || response?.data || response
      if (data && Array.isArray(data.services)) {
        setComparisonServices(data.services)
      } else if (Array.isArray(data)) {
        setComparisonServices(data)
      } else {
        setComparisonServices([])
      }
    } catch (error: any) {
      console.error('Failed to load comparison data:', error)
      setComparisonServices([])
    } finally {
      setIsLoadingComparison(false)
    }
  }

  // Load comparison when period changes or time range changes
  useEffect(() => {
    if (comparisonPeriod !== 'none') {
      loadComparisonData()
    } else {
      setComparisonServices([])
    }
  }, [comparisonPeriod, currentTimeRange.value])

  // Progressive loading - Enable components one by one
  useEffect(() => {
    // Reset all flags
    setEnableServices(false)
    setEnableEndpoints(false)
    setEnableErrorRates(false)
    setEnableTransactions(false)

    // Priority 1: Services (immediate)
    setEnableServices(true)

    // Priority 2: Endpoints (200ms delay)
    const timer1 = setTimeout(() => setEnableEndpoints(true), 200)

    // Priority 3: Error Rates (400ms delay)
    const timer2 = setTimeout(() => setEnableErrorRates(true), 400)

    // Priority 4: Transactions (600ms delay)
    const timer3 = setTimeout(() => setEnableTransactions(true), 600)

    // Cleanup
    return () => {
      clearTimeout(timer1)
      clearTimeout(timer2)
      clearTimeout(timer3)

      if (servicesAbortRef.current) servicesAbortRef.current.abort()
      if (endpointsAbortRef.current) endpointsAbortRef.current.abort()
      if (errorRatesAbortRef.current) errorRatesAbortRef.current.abort()
      if (transactionsAbortRef.current) transactionsAbortRef.current.abort()
    }
  }, [currentTimeRange.value])

  // Load Services when enabled
  useEffect(() => {
    if (enableServices) loadServices()
  }, [enableServices, currentTimeRange.value])

  // Load Endpoints when enabled
  useEffect(() => {
    if (enableEndpoints) {
      const timer = setTimeout(() => loadEndpoints(), 100)
      return () => clearTimeout(timer)
    }
  }, [enableEndpoints, currentTimeRange.value])

  // Load Error Rates when enabled
  useEffect(() => {
    if (enableErrorRates) {
      const timer = setTimeout(() => loadErrorRates(), 200)
      return () => clearTimeout(timer)
    }
  }, [enableErrorRates, currentTimeRange.value])

  // Load Transactions when enabled
  useEffect(() => {
    if (enableTransactions) {
      const timer = setTimeout(() => loadTransactions(), 300)
      return () => clearTimeout(timer)
    }
  }, [enableTransactions, currentTimeRange.value])

  // Manual refresh
  const handleRefresh = () => {
    loadServices()
    setTimeout(() => loadEndpoints(), 100)
    setTimeout(() => loadErrorRates(), 200)
    setTimeout(() => loadTransactions(), 300)
    setLastRefresh(new Date())
  }

  // Auto-refresh effect
  useEffect(() => {
    // Clear existing interval
    if (autoRefreshRef.current) {
      clearInterval(autoRefreshRef.current)
      autoRefreshRef.current = null
    }

    // Set up new interval if enabled
    if (refreshInterval > 0) {
      autoRefreshRef.current = setInterval(() => {
        handleRefresh()
      }, refreshInterval)
    }

    // Cleanup on unmount or interval change
    return () => {
      if (autoRefreshRef.current) {
        clearInterval(autoRefreshRef.current)
        autoRefreshRef.current = null
      }
    }
  }, [refreshInterval])

  // Format time since last refresh
  const getTimeSinceRefresh = () => {
    const seconds = Math.floor((new Date().getTime() - lastRefresh.getTime()) / 1000)
    if (seconds < 60) return `${seconds}s ago`
    const minutes = Math.floor(seconds / 60)
    return `${minutes}m ago`
  }

  const isAnyLoading = isLoadingServices || isLoadingEndpoints || isLoadingErrorRates || isLoadingTransactions

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white">Application Performance Monitoring</h1>
            <p className="text-slate-400 mt-1">
              Monitor latency, throughput, errors, and service health
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Comparison Period Selector */}
            <div className="flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-slate-400" />
              <select
                value={comparisonPeriod}
                onChange={(e) => setComparisonPeriod(e.target.value as ComparisonPeriod)}
                className="px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:border-purple-500"
              >
                <option value="none">No Comparison</option>
                <option value="previous_period">Previous Period</option>
                <option value="yesterday">Yesterday</option>
                <option value="last_week">Last Week</option>
              </select>
            </div>

            {/* Service Filter */}
            <select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              className="px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Services</option>
              {services.map(s => (
                <option key={s.service_name} value={s.service_name}>
                  {s.service_name}
                </option>
              ))}
            </select>

            {/* Auto-Refresh Selector */}
            <div className="flex items-center gap-2">
              <RefreshCw className={`w-4 h-4 ${refreshInterval > 0 ? 'text-emerald-400 animate-spin' : 'text-slate-400'}`} style={{ animationDuration: '3s' }} />
              <select
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(Number(e.target.value) as RefreshInterval)}
                className={`px-3 py-2 bg-slate-800 border rounded-lg text-white text-sm focus:outline-none ${
                  refreshInterval > 0 ? 'border-emerald-500/50' : 'border-slate-600'
                }`}
              >
                <option value={0}>Auto-Refresh: Off</option>
                <option value={10000}>Every 10s</option>
                <option value={30000}>Every 30s</option>
                <option value={60000}>Every 1m</option>
                <option value={300000}>Every 5m</option>
              </select>
            </div>

            <button
              onClick={handleRefresh}
              disabled={isAnyLoading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isAnyLoading ? 'animate-spin' : ''}`} />
              {isAnyLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Service Overview Grid */}
        <MemoizedServiceOverview
          services={services}
          isLoading={isLoadingServices}
          comparisonServices={comparisonServices}
          comparisonPeriod={comparisonPeriod}
          isLoadingComparison={isLoadingComparison}
        />

        {/* Apdex Score */}
        <MemoizedApdexScore services={services} isLoading={isLoadingServices} />

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Slowest Endpoints */}
          <MemoizedSlowestEndpoints
            endpoints={
              selectedService === 'all'
                ? endpoints
                : endpoints.filter(e => e.service === selectedService)
            }
            isLoading={isLoadingEndpoints}
          />

          {/* Error Rates */}
          <MemoizedErrorRates
            metrics={
              selectedService === 'all'
                ? errorRates
                : errorRates.filter(m => m.service === selectedService)
            }
            isLoading={isLoadingErrorRates}
          />
        </div>

        {/* Transactions */}
        <MemoizedTransactions
          transactions={
            selectedService === 'all'
              ? transactions
              : transactions.filter(t => t.service === selectedService)
          }
          isLoading={isLoadingTransactions}
        />
      </div>
    </DashboardLayout>
  )
}
