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

            <button
              onClick={handleRefresh}
              disabled={isAnyLoading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {isAnyLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Service Overview Grid */}
        <MemoizedServiceOverview services={services} isLoading={isLoadingServices} />

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
