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
        const data = servicesRes.value?.data || servicesRes.value
        if (data && 'services' in data) {
          setServices(data.services)
        } else {
          setServices(generateMockServices())
        }
      } else {
        setServices(generateMockServices())
      }

      // Process endpoints
      if (endpointsRes.status === 'fulfilled') {
        const data = endpointsRes.value?.data || endpointsRes.value
        if (data && 'endpoints' in data) {
          setEndpoints(data.endpoints)
        } else {
          setEndpoints(generateMockEndpoints())
        }
      } else {
        setEndpoints(generateMockEndpoints())
      }

      // Process error rates
      if (errorRatesRes.status === 'fulfilled') {
        const data = errorRatesRes.value?.data || errorRatesRes.value
        if (data && 'metrics' in data) {
          setErrorRates(data.metrics)
        } else {
          setErrorRates(generateMockErrorRates())
        }
      } else {
        setErrorRates(generateMockErrorRates())
      }

      // Process transactions
      if (transactionsRes.status === 'fulfilled') {
        const data = transactionsRes.value?.data || transactionsRes.value
        if (data && 'transactions' in data) {
          setTransactions(data.transactions)
        } else {
          setTransactions(generateMockTransactions())
        }
      } else {
        setTransactions(generateMockTransactions())
      }
    } catch (error) {
      console.error('Failed to load APM data:', error)
      // Set mock data
      setServices(generateMockServices())
      setEndpoints(generateMockEndpoints())
      setErrorRates(generateMockErrorRates())
      setTransactions(generateMockTransactions())
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

// Mock data generators
function generateMockServices(): ServicePerformance[] {
  const services = ['api-gateway', 'auth-service', 'user-service', 'order-service', 'payment-service']

  return services.map(name => {
    const baseLatency = Math.random() * 150 + 20
    const errorRate = Math.random() * 3

    return {
      service_name: name,
      request_count: Math.floor(Math.random() * 50000) + 10000,
      avg_latency_ms: baseLatency,
      p50_latency_ms: baseLatency * 0.8,
      p95_latency_ms: baseLatency * 2.5,
      p99_latency_ms: baseLatency * 4,
      error_rate: errorRate,
      throughput: Math.floor(Math.random() * 1000) + 100,
      apdex_score: errorRate < 1 ? 0.95 : errorRate < 2 ? 0.75 : 0.5
    }
  })
}

function generateMockEndpoints(): EndpointPerformance[] {
  const endpoints = [
    { endpoint: 'POST /api/orders', service: 'order-service' },
    { endpoint: 'GET /api/users/:id', service: 'user-service' },
    { endpoint: 'POST /api/payments', service: 'payment-service' },
    { endpoint: 'GET /api/products/search', service: 'api-gateway' },
    { endpoint: 'PUT /api/users/:id', service: 'user-service' },
    { endpoint: 'GET /api/orders/:id/history', service: 'order-service' },
    { endpoint: 'POST /api/auth/login', service: 'auth-service' },
    { endpoint: 'GET /api/recommendations', service: 'api-gateway' },
    { endpoint: 'DELETE /api/cart/items/:id', service: 'order-service' },
    { endpoint: 'POST /api/reviews', service: 'user-service' }
  ]

  return endpoints.map(({ endpoint, service }) => {
    const baseLatency = Math.random() * 300 + 100

    return {
      endpoint,
      service,
      request_count: Math.floor(Math.random() * 10000) + 1000,
      avg_latency_ms: baseLatency,
      p50_latency_ms: baseLatency * 0.8,
      p95_latency_ms: baseLatency * 2,
      p99_latency_ms: baseLatency * 3,
      error_rate: Math.random() * 5
    }
  }).sort((a, b) => b.p99_latency_ms - a.p99_latency_ms)
}

function generateMockErrorRates(): ErrorRateMetric[] {
  const services = ['api-gateway', 'auth-service', 'user-service', 'order-service', 'payment-service']
  const now = Date.now()
  const metrics: ErrorRateMetric[] = []

  // Generate hourly data points for last 24 hours
  for (let i = 24; i >= 0; i--) {
    const timestamp = now - (i * 3600000)

    services.forEach(service => {
      const totalRequests = Math.floor(Math.random() * 5000) + 1000
      const errorCount = Math.floor(totalRequests * (Math.random() * 0.05))

      metrics.push({
        timestamp,
        service,
        error_rate: (errorCount / totalRequests) * 100,
        error_count: errorCount,
        total_requests: totalRequests
      })
    })
  }

  return metrics
}

function generateMockTransactions(): Transaction[] {
  const transactions = [
    { name: 'checkout.process', service: 'order-service' },
    { name: 'user.registration', service: 'user-service' },
    { name: 'payment.authorize', service: 'payment-service' },
    { name: 'search.products', service: 'api-gateway' },
    { name: 'auth.login', service: 'auth-service' },
    { name: 'cart.update', service: 'order-service' },
    { name: 'user.profile.update', service: 'user-service' },
    { name: 'recommendation.generate', service: 'api-gateway' },
    { name: 'payment.refund', service: 'payment-service' },
    { name: 'order.history', service: 'order-service' }
  ]

  const total = transactions.reduce((sum) => sum + Math.random() * 1000, 0)

  return transactions.map(({ name, service }) => {
    const count = Math.floor(Math.random() * 10000) + 500

    return {
      name,
      service,
      count,
      avg_duration_ms: Math.floor(Math.random() * 200) + 50,
      percentage: (count / total) * 100
    }
  }).sort((a, b) => b.count - a.count)
}
