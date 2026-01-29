'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api'
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Activity,
  TrendingUp,
  TrendingDown,
  Clock,
  ArrowRight
} from 'lucide-react'

interface ServiceHealth {
  name: string
  status: 'healthy' | 'degraded' | 'critical' | 'unknown'
  latency_p99: number
  latency_trend: 'up' | 'down' | 'stable'
  error_rate: number
  request_rate: number
  last_incident?: string
  dependencies: string[]
}

interface ServiceHealthMapProps {
  isLoading?: boolean
}

const STATUS_CONFIG = {
  healthy: {
    color: 'text-green-400',
    bg: 'bg-green-500/20',
    border: 'border-green-500/30',
    icon: CheckCircle,
    label: 'Healthy'
  },
  degraded: {
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/20',
    border: 'border-yellow-500/30',
    icon: AlertTriangle,
    label: 'Degraded'
  },
  critical: {
    color: 'text-red-400',
    bg: 'bg-red-500/20',
    border: 'border-red-500/30',
    icon: XCircle,
    label: 'Critical'
  },
  unknown: {
    color: 'text-slate-400',
    bg: 'bg-slate-500/20',
    border: 'border-slate-500/30',
    icon: Activity,
    label: 'Unknown'
  }
}

const generateMockServices = (): ServiceHealth[] => [
  {
    name: 'api-gateway',
    status: 'healthy',
    latency_p99: 45,
    latency_trend: 'stable',
    error_rate: 0.1,
    request_rate: 1250,
    dependencies: ['auth-service', 'payment-service', 'order-service']
  },
  {
    name: 'auth-service',
    status: 'degraded',
    latency_p99: 850,
    latency_trend: 'up',
    error_rate: 2.3,
    request_rate: 890,
    last_incident: '5m ago',
    dependencies: ['redis-cache', 'postgresql']
  },
  {
    name: 'payment-service',
    status: 'critical',
    latency_p99: 2100,
    latency_trend: 'up',
    error_rate: 15.2,
    request_rate: 450,
    last_incident: '3m ago',
    dependencies: ['postgresql', 'stripe-api']
  },
  {
    name: 'order-service',
    status: 'healthy',
    latency_p99: 120,
    latency_trend: 'down',
    error_rate: 0.05,
    request_rate: 780,
    dependencies: ['postgresql', 'kafka']
  },
  {
    name: 'inventory-service',
    status: 'healthy',
    latency_p99: 85,
    latency_trend: 'stable',
    error_rate: 0.2,
    request_rate: 340,
    dependencies: ['postgresql', 'redis-cache']
  },
  {
    name: 'notification-service',
    status: 'healthy',
    latency_p99: 200,
    latency_trend: 'stable',
    error_rate: 0.8,
    request_rate: 560,
    dependencies: ['kafka', 'sendgrid-api']
  },
  {
    name: 'analytics-service',
    status: 'degraded',
    latency_p99: 450,
    latency_trend: 'up',
    error_rate: 1.5,
    request_rate: 120,
    last_incident: '15m ago',
    dependencies: ['clickhouse', 'kafka']
  },
  {
    name: 'search-service',
    status: 'healthy',
    latency_p99: 35,
    latency_trend: 'down',
    error_rate: 0.02,
    request_rate: 920,
    dependencies: ['elasticsearch']
  }
]

export default function ServiceHealthMap({ isLoading: externalLoading }: ServiceHealthMapProps) {
  const router = useRouter()
  const [services, setServices] = useState<ServiceHealth[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

  useEffect(() => {
    loadServices()
  }, [])

  const loadServices = async () => {
    try {
      setIsLoading(true)
      const response = await apiClient.get('/v1/observability/services/health')

      if (response?.data?.services) {
        setServices(response.data.services)
      } else {
        setServices(generateMockServices())
      }
    } catch (error) {
      console.error('Failed to load service health:', error)
      setServices(generateMockServices())
    } finally {
      setIsLoading(false)
    }
  }

  const stats = {
    total: services.length,
    healthy: services.filter(s => s.status === 'healthy').length,
    degraded: services.filter(s => s.status === 'degraded').length,
    critical: services.filter(s => s.status === 'critical').length
  }

  const formatLatency = (ms: number) => {
    if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
    return `${ms}ms`
  }

  if (isLoading || externalLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-5">
        <div className="flex items-center justify-center h-48">
          <div className="text-slate-400 text-sm animate-pulse">Loading service health...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-5">
      {/* Background glow */}
      <div className="absolute top-0 right-0 w-32 h-32 -translate-y-16 translate-x-8 bg-green-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-md shadow-green-500/30">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Service Health</h2>
            <p className="text-xs text-slate-400">{stats.total} services monitored</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {stats.critical > 0 && (
            <div className="flex items-center gap-1 px-2 py-1 rounded bg-red-500/20 border border-red-500/30">
              <XCircle className="w-3 h-3 text-red-400" />
              <span className="text-xs font-medium text-red-400">{stats.critical} Critical</span>
            </div>
          )}
          {stats.degraded > 0 && (
            <div className="flex items-center gap-1 px-2 py-1 rounded bg-yellow-500/20 border border-yellow-500/30">
              <AlertTriangle className="w-3 h-3 text-yellow-400" />
              <span className="text-xs font-medium text-yellow-400">{stats.degraded} Degraded</span>
            </div>
          )}
        </div>
      </div>

      {/* Service Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {services.map((service) => {
          const statusConfig = STATUS_CONFIG[service.status]
          const StatusIcon = statusConfig.icon

          return (
            <div
              key={service.name}
              onClick={() => router.push(`/apm/services?service=${service.name}`)}
              className={`p-3 rounded-lg border ${statusConfig.border} ${statusConfig.bg} cursor-pointer hover:bg-opacity-30 transition-all group`}
            >
              <div className="flex items-center justify-between mb-2">
                <StatusIcon className={`w-4 h-4 ${statusConfig.color}`} />
                {service.latency_trend === 'up' && (
                  <TrendingUp className="w-3 h-3 text-red-400" />
                )}
                {service.latency_trend === 'down' && (
                  <TrendingDown className="w-3 h-3 text-green-400" />
                )}
              </div>
              <h3 className="text-xs font-semibold text-white truncate mb-1">
                {service.name}
              </h3>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-slate-400">P99</span>
                <span className={service.latency_p99 > 500 ? 'text-orange-400' : 'text-slate-300'}>
                  {formatLatency(service.latency_p99)}
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-slate-400">Err</span>
                <span className={service.error_rate > 1 ? 'text-red-400' : 'text-slate-300'}>
                  {service.error_rate.toFixed(1)}%
                </span>
              </div>
              {service.last_incident && (
                <div className="mt-1 pt-1 border-t border-white/5">
                  <span className="text-[9px] text-orange-400 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" />
                    Incident {service.last_incident}
                  </span>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-3 text-[10px] text-slate-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            Healthy: {stats.healthy}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
            Degraded: {stats.degraded}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500"></span>
            Critical: {stats.critical}
          </span>
        </div>
        <button
          onClick={() => router.push('/apm/services')}
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          View All
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}
