'use client'

import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Activity,
  AlertTriangle,
  TrendingDown,
  TrendingUp,
  CheckCircle,
  XCircle,
  ChevronRight,
  RefreshCw
} from 'lucide-react'

interface AnomalyStats {
  total_anomalies: number
  active_anomalies: number
  dismissed_anomalies: number
  resolved_anomalies: number
  by_severity: {
    critical: number
    high: number
    medium: number
    low: number
  }
  by_type: Record<string, number>
  trend: 'increasing' | 'decreasing' | 'stable'
  trend_percentage: number
}

interface AnomalyStatsWidgetProps {
  className?: string
}

export default function AnomalyStatsWidget({ className }: AnomalyStatsWidgetProps) {
  const { getApiTimeRange, currentTimeRange } = useTimeRange()
  const [stats, setStats] = useState<AnomalyStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadStats = useCallback(async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get('/v1/ai/anomalies/stats', {
        start_time,
        end_time
      })

      const data = response?.data || response
      if (data) {
        setStats(data)
      }
    } catch (err: any) {
      if (err.name !== 'AbortError' && err.name !== 'CanceledError') {
        console.error('Failed to load anomaly stats:', err)
      }
      setStats(null)
    } finally {
      setIsLoading(false)
    }
  }, [getApiTimeRange])

  useEffect(() => {
    loadStats()
  }, [loadStats, currentTimeRange.value])

  const getTrendIcon = () => {
    if (!stats) return null
    if (stats.trend === 'increasing') return <TrendingUp className="w-4 h-4 text-red-400" />
    if (stats.trend === 'decreasing') return <TrendingDown className="w-4 h-4 text-green-400" />
    return <Activity className="w-4 h-4 text-slate-400" />
  }

  const getTrendColor = () => {
    if (!stats) return 'text-slate-400'
    if (stats.trend === 'increasing') return 'text-red-400'
    if (stats.trend === 'decreasing') return 'text-green-400'
    return 'text-slate-400'
  }

  return (
    <div className={`relative overflow-hidden rounded-2xl p-5 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 ${className || ''}`}>
      {/* Background glow */}
      <div className="absolute top-0 left-0 w-48 h-48 -translate-y-16 -translate-x-8 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-40 h-40 translate-y-12 translate-x-6 bg-teal-500/8 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="relative z-10 flex items-start justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center shadow-md shadow-cyan-500/30">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white tracking-tight">Anomaly Detection</h2>
            <p className="text-xs text-slate-400 font-medium mt-0.5">
              ML-powered monitoring
            </p>
          </div>
        </div>

        <button
          onClick={loadStats}
          disabled={isLoading}
          className="p-1.5 rounded-lg hover:bg-white/5 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 text-slate-400 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Content */}
      <div className="relative z-10">
        {isLoading ? (
          <div className="space-y-3">
            <div className="h-20 bg-white/5 rounded-lg animate-pulse" />
            <div className="grid grid-cols-2 gap-2">
              <div className="h-16 bg-white/5 rounded-lg animate-pulse" />
              <div className="h-16 bg-white/5 rounded-lg animate-pulse" />
            </div>
          </div>
        ) : !stats ? (
          <div className="flex flex-col items-center justify-center py-8 text-slate-400">
            <Activity className="w-8 h-8 mb-2 opacity-40" />
            <p className="text-sm">No anomaly data available</p>
            <p className="text-xs text-slate-500 mt-1">ML models are training</p>
          </div>
        ) : (
          <>
            {/* Main metric */}
            <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] border border-white/5 mb-3">
              <div>
                <div className="text-3xl font-extrabold text-white leading-none">
                  {stats.active_anomalies}
                </div>
                <div className="text-xs text-slate-400 font-medium mt-1">Active Anomalies</div>
              </div>
              <div className="text-right">
                <div className={`flex items-center gap-1.5 ${getTrendColor()}`}>
                  {getTrendIcon()}
                  <span className="text-sm font-bold">
                    {stats.trend_percentage > 0 ? '+' : ''}{stats.trend_percentage}%
                  </span>
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5 capitalize">{stats.trend} trend</div>
              </div>
            </div>

            {/* Severity breakdown */}
            <div className="grid grid-cols-4 gap-2 mb-3">
              <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/15 text-center">
                <div className="text-lg font-bold text-red-400">{stats.by_severity?.critical || 0}</div>
                <div className="text-[9px] text-slate-400 font-semibold uppercase">Crit</div>
              </div>
              <div className="p-2.5 rounded-lg bg-orange-500/10 border border-orange-500/15 text-center">
                <div className="text-lg font-bold text-orange-400">{stats.by_severity?.high || 0}</div>
                <div className="text-[9px] text-slate-400 font-semibold uppercase">High</div>
              </div>
              <div className="p-2.5 rounded-lg bg-yellow-500/10 border border-yellow-500/15 text-center">
                <div className="text-lg font-bold text-yellow-400">{stats.by_severity?.medium || 0}</div>
                <div className="text-[9px] text-slate-400 font-semibold uppercase">Med</div>
              </div>
              <div className="p-2.5 rounded-lg bg-blue-500/10 border border-blue-500/15 text-center">
                <div className="text-lg font-bold text-blue-400">{stats.by_severity?.low || 0}</div>
                <div className="text-[9px] text-slate-400 font-semibold uppercase">Low</div>
              </div>
            </div>

            {/* Status summary */}
            <div className="grid grid-cols-3 gap-2">
              <div className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.03] border border-white/5">
                <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
                <div>
                  <div className="text-sm font-bold text-white">{stats.total_anomalies}</div>
                  <div className="text-[9px] text-slate-500">Total</div>
                </div>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.03] border border-white/5">
                <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                <div>
                  <div className="text-sm font-bold text-white">{stats.resolved_anomalies}</div>
                  <div className="text-[9px] text-slate-500">Resolved</div>
                </div>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.03] border border-white/5">
                <XCircle className="w-3.5 h-3.5 text-slate-400" />
                <div>
                  <div className="text-sm font-bold text-white">{stats.dismissed_anomalies}</div>
                  <div className="text-[9px] text-slate-500">Dismissed</div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="relative z-10 mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/3">
          <Activity className="w-3 h-3 text-cyan-400" />
          <span className="text-[10px] text-slate-400 font-medium">
            ML models active
          </span>
        </div>
        <a
          href="/anomaly-detection"
          className="text-[10px] text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1"
        >
          View Details <ChevronRight className="w-3 h-3" />
        </a>
      </div>
    </div>
  )
}
