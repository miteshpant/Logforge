'use client'

import { useState, useEffect } from 'react'
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

export default function APMPage() {
  const { getApiTimeRange } = useTimeRange()
  const [services, setServices] = useState<ServicePerformance[]>([])
  const [endpoints, setEndpoints] = useState<EndpointPerformance[]>([])
  const [errorRates, setErrorRates] = useState<ErrorRateMetric[]>([])
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedService, setSelectedService] = useState<string>('all')

  const loadAPMData = async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      // Load all APM data in parallel
      const [servicesRes, endpointsRes, errorRatesRes, transactionsRes] = await Promise.allSettled([
        apiClient.get<{ services: ServicePerformance[] }>('/v1/observability/apm/services', {
          start_time,
          end_time
        }),
        apiClient.get<{ endpoints: EndpointPerformance[] }>('/v1/observability/apm/slowest-endpoints', {
          start_time,
          end_time,
          limit: 10
        }),
        apiClient.get<{ metrics: ErrorRateMetric[] }>('/v1/observability/apm/error-rates', {
          start_time,
          end_time,
          interval: '5m'
        }),
        apiClient.get<{ transactions: Transaction[] }>('/v1/observability/apm/transactions', {
          start_time,
          end_time,
          limit: 10
        })
      ])

      // Process services
      if (servicesRes.status === 'fulfilled') {
        const data = servicesRes.value?.data?.data || servicesRes.value?.data || servicesRes.value
        if (data && Array.isArray(data.services)) {
          setServices(data.services)
        } else if (Array.isArray(data)) {
          setServices(data)
        } else {
          setServices([])
        }
      } else {
        console.error('Failed to load services:', servicesRes.reason)
        setServices([])
      }

      // Process endpoints
      if (endpointsRes.status === 'fulfilled') {
        const data = endpointsRes.value?.data?.data || endpointsRes.value?.data || endpointsRes.value
        if (data && Array.isArray(data.endpoints)) {
          setEndpoints(data.endpoints)
        } else if (Array.isArray(data)) {
          setEndpoints(data)
        } else {
          setEndpoints([])
        }
      } else {
        console.error('Failed to load endpoints:', endpointsRes.reason)
        setEndpoints([])
      }

      // Process error rates
      if (errorRatesRes.status === 'fulfilled') {
        const data = errorRatesRes.value?.data?.data || errorRatesRes.value?.data || errorRatesRes.value
        if (data && Array.isArray(data.metrics)) {
          setErrorRates(data.metrics)
        } else if (Array.isArray(data)) {
          setErrorRates(data)
        } else {
          setErrorRates([])
        }
      } else {
        console.error('Failed to load error rates:', errorRatesRes.reason)
        setErrorRates([])
      }

      // Process transactions
      if (transactionsRes.status === 'fulfilled') {
        const data = transactionsRes.value?.data?.data || transactionsRes.value?.data || transactionsRes.value
        if (data && Array.isArray(data.transactions)) {
          setTransactions(data.transactions)
        } else if (Array.isArray(data)) {
          setTransactions(data)
        } else {
          setTransactions([])
        }
      } else {
        console.error('Failed to load transactions:', transactionsRes.reason)
        setTransactions([])
      }
    } catch (error) {
      console.error('Failed to load APM data:', error)
      // Set empty arrays on error - no mock data
      setServices([])
      setEndpoints([])
      setErrorRates([])
      setTransactions([])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadAPMData()
  }, [])

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
              onClick={loadAPMData}
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {isLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Service Overview Grid */}
        <APMServiceOverview services={services} isLoading={isLoading} />

        {/* Apdex Score */}
        <APMApdexScore services={services} isLoading={isLoading} />

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Slowest Endpoints */}
          <APMSlowestEndpoints
            endpoints={
              selectedService === 'all'
                ? endpoints
                : endpoints.filter(e => e.service === selectedService)
            }
            isLoading={isLoading}
          />

          {/* Error Rates */}
          <APMErrorRates
            metrics={
              selectedService === 'all'
                ? errorRates
                : errorRates.filter(m => m.service === selectedService)
            }
            isLoading={isLoading}
          />
        </div>

        {/* Transactions */}
        <APMTransactions
          transactions={
            selectedService === 'all'
              ? transactions
              : transactions.filter(t => t.service === selectedService)
          }
          isLoading={isLoading}
        />
      </div>
    </DashboardLayout>
  )
}
