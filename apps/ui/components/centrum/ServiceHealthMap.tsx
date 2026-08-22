'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api'
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Activity,
  Clock,
  ArrowRight,
  RefreshCw
} from 'lucide-react'

interface ServiceHealth {
  name: string
  status: 'healthy' | 'degraded' | 'critical' | 'unknown'
  // Metrics are only present when the APM endpoint reported them
  latency_p99?: number
  error_rate?: number
  request_count?: number
  throughput?: number
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

// Health thresholds applied to REAL error-rate / latency values.
//   critical: error rate > 5%  or p99 latency > 2000ms
//   degraded: error rate > 1%  or p99 latency > 500ms
//   healthy:  metrics present and below both thresholds
//   unknown:  the APM endpoint reported no metrics for the service
const deriveStatus = (errorRate?: number, p99?: number): ServiceHealth['status'] => {
  if (errorRate === undefined && p99 === undefined) return 'unknown'
  if ((errorRate ?? 0) > 5 || (p99 ?? 0) > 2000) return 'critical'
  if ((errorRate ?? 0) > 1 || (p99 ?? 0) > 500) return 'degraded'
  return 'healthy'
}

export default function ServiceHealthMap({ isLoading: externalLoading }: ServiceHealthMapProps) {
  const router = useRouter()
  const [services, setServices] = useState<ServiceHealth[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    loadServices()
  }, [])

  const loadServices = async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      // Topology (service names + dependencies) and APM metrics (requests,
      // errors, latency), joined by service name. No fallback data — if both
      // fail, an error state is rendered instead.
      const [topologyRes, apmRes] = await Promise.allSettled([
        apiClient.get('/v1/observability/service-map'),
        apiClient.get('/v1/observability/apm/services')
      ])

      if (topologyRes.status === 'rejected' && apmRes.status === 'rejected') {
        const topoErr: any = topologyRes.reason
        const apmErr: any = apmRes.reason
        setServices([])
        setLoadError(
          `GET /v1/observability/service-map returned ${topoErr?.status ?? 'a network error'}; ` +
          `GET /v1/observability/apm/services returned ${apmErr?.status ?? 'a network error'}`
        )
        return
      }

      const topologyServices: any[] =
        topologyRes.status === 'fulfilled'
          ? (topologyRes.value?.data?.services ?? [])
          : []
      const apmServices: any[] =
        apmRes.status === 'fulfilled'
          ? (apmRes.value?.data?.services ?? [])
          : []

      const apmByName = new Map<string, any>()
      apmServices.forEach(s => {
        if (s?.service_name) apmByName.set(s.service_name, s)
      })

      const names = new Set<string>()
      topologyServices.forEach(s => { if (s?.service_name) names.add(s.service_name) })
      apmServices.forEach(s => { if (s?.service_name) names.add(s.service_name) })

      const merged: ServiceHealth[] = Array.from(names).sort().map(name => {
        const topo = topologyServices.find(s => s?.service_name === name)
        const apm = apmByName.get(name)
        const errorRate = apm?.error_rate !== undefined ? Number(apm.error_rate) : undefined
        const p99 = apm?.p99_latency_ms !== undefined ? Number(apm.p99_latency_ms) : undefined
        return {
          name,
          status: deriveStatus(errorRate, p99),
          latency_p99: p99,
          error_rate: errorRate,
          request_count: apm?.request_count !== undefined ? Number(apm.request_count) : undefined,
          throughput: apm?.throughput !== undefined ? Number(apm.throughput) : undefined,
          dependencies: Array.isArray(topo?.dependencies) ? topo.dependencies : []
        }
      })

      setServices(merged)

      // A partial failure is still surfaced — never silently ignored
      if (topologyRes.status === 'rejected') {
        const err: any = topologyRes.reason
        setLoadError(`Service topology unavailable: GET /v1/observability/service-map returned ${err?.status ?? 'a network error'}`)
      } else if (apmRes.status === 'rejected') {
        const err: any = apmRes.reason
        setLoadError(`APM metrics unavailable: GET /v1/observability/apm/services returned ${err?.status ?? 'a network error'}`)
      }
    } catch (error: any) {
      console.error('Failed to load service health:', error)
      setServices([])
      setLoadError(`Failed to load service health: ${error?.message || 'network error'}`)
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
    return `${Math.round(ms)}ms`
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

      {/* Error state — the map never shows substitute data */}
      {loadError && (
        <div className="mb-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <XCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <p className="text-xs text-red-400">{loadError}</p>
          </div>
          <button
            onClick={loadServices}
            className="flex items-center gap-1 text-xs text-red-300 hover:text-red-200 shrink-0"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {services.length === 0 && !loadError && (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <Activity className="w-8 h-8 text-slate-500 mb-2" />
          <p className="text-sm text-slate-400">No services reported</p>
          <p className="text-xs text-slate-500 mt-1">
            Services appear here once traces are ingested for this tenant
          </p>
        </div>
      )}

      {/* Service Grid */}
      {services.length > 0 && (
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
                  <span className={`text-[9px] uppercase tracking-wide ${statusConfig.color}`}>
                    {statusConfig.label}
                  </span>
                </div>
                <h3 className="text-xs font-semibold text-white truncate mb-1">
                  {service.name}
                </h3>
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-slate-400">P99</span>
                  <span className={service.latency_p99 !== undefined && service.latency_p99 > 500 ? 'text-orange-400' : 'text-slate-300'}>
                    {service.latency_p99 !== undefined ? formatLatency(service.latency_p99) : '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-slate-400">Err</span>
                  <span className={service.error_rate !== undefined && service.error_rate > 1 ? 'text-red-400' : 'text-slate-300'}>
                    {service.error_rate !== undefined ? `${service.error_rate.toFixed(1)}%` : '—'}
                  </span>
                </div>
                {service.request_count !== undefined && (
                  <div className="mt-1 pt-1 border-t border-white/5">
                    <span className="text-[9px] text-slate-400 flex items-center gap-1">
                      <Clock className="w-2.5 h-2.5" />
                      {service.request_count.toLocaleString()} requests
                    </span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

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
