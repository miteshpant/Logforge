'use client'

import { Activity, Clock, AlertCircle, TrendingUp } from 'lucide-react'
import type { ServicePerformance } from '@/app/observability/apm/page'

interface APMServiceOverviewProps {
  services: ServicePerformance[]
  isLoading: boolean
}

export default function APMServiceOverview({ services, isLoading }: APMServiceOverviewProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 animate-pulse">
            <div className="h-4 bg-slate-700 rounded w-3/4 mb-4"></div>
            <div className="h-8 bg-slate-700 rounded w-1/2"></div>
          </div>
        ))}
      </div>
    )
  }

  // Calculate aggregate metrics
  const totalRequests = services.reduce((sum, s) => sum + s.request_count, 0)
  const avgLatency = services.reduce((sum, s) => sum + s.avg_latency_ms, 0) / (services.length || 1)
  const avgErrorRate = services.reduce((sum, s) => sum + s.error_rate, 0) / (services.length || 1)
  const totalThroughput = services.reduce((sum, s) => sum + s.throughput, 0)

  const stats = [
    {
      label: 'Total Requests',
      value: totalRequests.toLocaleString(),
      icon: Activity,
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/20'
    },
    {
      label: 'Avg Latency',
      value: `${avgLatency.toFixed(0)}ms`,
      icon: Clock,
      color: avgLatency > 100 ? 'text-yellow-400' : 'text-emerald-400',
      bgColor: avgLatency > 100 ? 'bg-yellow-500/20' : 'bg-emerald-500/20'
    },
    {
      label: 'Error Rate',
      value: `${avgErrorRate.toFixed(2)}%`,
      icon: AlertCircle,
      color: avgErrorRate > 2 ? 'text-red-400' : 'text-emerald-400',
      bgColor: avgErrorRate > 2 ? 'bg-red-500/20' : 'bg-emerald-500/20'
    },
    {
      label: 'Throughput',
      value: `${totalThroughput.toLocaleString()}/s`,
      icon: TrendingUp,
      color: 'text-purple-400',
      bgColor: 'bg-purple-500/20'
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 hover:border-white/10 transition-colors"
        >
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm text-slate-400">{stat.label}</span>
            <div className={`p-2 rounded-lg ${stat.bgColor}`}>
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
            </div>
          </div>
          <div className={`text-3xl font-bold ${stat.color}`}>
            {stat.value}
          </div>
        </div>
      ))}
    </div>
  )
}
