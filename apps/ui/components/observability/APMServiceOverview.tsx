'use client'

import { Activity, Clock, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { ServicePerformance, ComparisonPeriod } from '@/app/observability/apm/page'

// Format latency values for display
const formatLatency = (ms: number): string => {
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

// Calculate percentage change
const calculateChange = (current: number, previous: number): number | null => {
  if (previous === 0) return current > 0 ? 100 : null
  return ((current - previous) / previous) * 100
}

// Format change for display
const formatChange = (change: number | null): string => {
  if (change === null) return 'N/A'
  const sign = change >= 0 ? '+' : ''
  return `${sign}${change.toFixed(1)}%`
}

interface APMServiceOverviewProps {
  services: ServicePerformance[]
  isLoading: boolean
  comparisonServices?: ServicePerformance[]
  comparisonPeriod?: ComparisonPeriod
  isLoadingComparison?: boolean
}

export default function APMServiceOverview({
  services,
  isLoading,
  comparisonServices = [],
  comparisonPeriod = 'none',
  isLoadingComparison = false
}: APMServiceOverviewProps) {
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

  // Calculate current aggregate metrics
  const totalRequests = services.reduce((sum, s) => sum + s.request_count, 0)
  const avgLatency = services.reduce((sum, s) => sum + s.avg_latency_ms, 0) / (services.length || 1)
  const avgErrorRate = services.reduce((sum, s) => sum + s.error_rate, 0) / (services.length || 1)
  const totalThroughput = services.reduce((sum, s) => sum + s.throughput, 0)

  // Calculate comparison aggregate metrics
  const hasComparison = comparisonPeriod !== 'none' && comparisonServices.length > 0
  const prevTotalRequests = comparisonServices.reduce((sum, s) => sum + s.request_count, 0)
  const prevAvgLatency = comparisonServices.reduce((sum, s) => sum + s.avg_latency_ms, 0) / (comparisonServices.length || 1)
  const prevAvgErrorRate = comparisonServices.reduce((sum, s) => sum + s.error_rate, 0) / (comparisonServices.length || 1)
  const prevTotalThroughput = comparisonServices.reduce((sum, s) => sum + s.throughput, 0)

  // Calculate changes
  const requestsChange = hasComparison ? calculateChange(totalRequests, prevTotalRequests) : null
  const latencyChange = hasComparison ? calculateChange(avgLatency, prevAvgLatency) : null
  const errorRateChange = hasComparison ? calculateChange(avgErrorRate, prevAvgErrorRate) : null
  const throughputChange = hasComparison ? calculateChange(totalThroughput, prevTotalThroughput) : null

  // Comparison period label
  const comparisonLabel = {
    'none': '',
    'previous_period': 'vs previous period',
    'yesterday': 'vs yesterday',
    'last_week': 'vs last week'
  }[comparisonPeriod]

  const stats = [
    {
      label: 'Total Requests',
      value: totalRequests.toLocaleString(),
      icon: Activity,
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/20',
      change: requestsChange,
      changeIsGood: (c: number | null) => c !== null && c >= 0 // More requests is good
    },
    {
      label: 'Avg Latency',
      value: formatLatency(avgLatency),
      icon: Clock,
      color: avgLatency > 1000 ? 'text-red-400' : avgLatency > 100 ? 'text-yellow-400' : 'text-emerald-400',
      bgColor: avgLatency > 1000 ? 'bg-red-500/20' : avgLatency > 100 ? 'bg-yellow-500/20' : 'bg-emerald-500/20',
      change: latencyChange,
      changeIsGood: (c: number | null) => c !== null && c <= 0 // Lower latency is good
    },
    {
      label: 'Error Rate',
      value: `${avgErrorRate.toFixed(2)}%`,
      icon: AlertCircle,
      color: avgErrorRate > 2 ? 'text-red-400' : 'text-emerald-400',
      bgColor: avgErrorRate > 2 ? 'bg-red-500/20' : 'bg-emerald-500/20',
      change: errorRateChange,
      changeIsGood: (c: number | null) => c !== null && c <= 0 // Lower error rate is good
    },
    {
      label: 'Throughput',
      value: `${totalThroughput.toLocaleString()}/s`,
      icon: TrendingUp,
      color: 'text-purple-400',
      bgColor: 'bg-purple-500/20',
      change: throughputChange,
      changeIsGood: (c: number | null) => c !== null && c >= 0 // Higher throughput is good
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat) => {
        const isGood = stat.changeIsGood(stat.change)
        const changeColor = stat.change === null ? 'text-slate-500' :
          isGood ? 'text-emerald-400' : 'text-red-400'

        return (
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

            {/* Comparison indicator */}
            {comparisonPeriod !== 'none' && (
              <div className="mt-3 pt-3 border-t border-slate-700/50">
                {isLoadingComparison ? (
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-4 bg-slate-700 rounded animate-pulse"></div>
                  </div>
                ) : hasComparison ? (
                  <div className="flex items-center gap-2">
                    {stat.change !== null && (
                      <>
                        {stat.change > 0 ? (
                          <TrendingUp className={`w-4 h-4 ${changeColor}`} />
                        ) : stat.change < 0 ? (
                          <TrendingDown className={`w-4 h-4 ${changeColor}`} />
                        ) : (
                          <Minus className="w-4 h-4 text-slate-500" />
                        )}
                      </>
                    )}
                    <span className={`text-sm font-medium ${changeColor}`}>
                      {formatChange(stat.change)}
                    </span>
                    <span className="text-xs text-slate-500">{comparisonLabel}</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">No comparison data</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
