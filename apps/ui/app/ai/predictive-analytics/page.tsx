'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Activity,
  BarChart3,
  Clock,
  Target,
  Zap,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Server,
  HardDrive,
  Brain,
  Loader2,
  ChevronRight,
  Shield,
  Gauge,
  Calendar,
  Play
} from 'lucide-react'

// Matches backend prediction summary response (nested structure)
interface PredictionSummary {
  overall_risk_score?: number
  risk_level?: string
  risk_factors?: string[]
  forecast_summary?: {
    metric?: string
    data_points?: number
    trend_direction?: string
    slope?: number
    r_squared?: number
  }
  capacity_summary?: {
    current_daily_volume?: number
    growth_rate_percent?: number
    top_services_count?: number
    projections?: Array<{
      threshold?: string
      limit?: number
      estimated_days_until?: number | null
      estimated_date?: string
    }>
  }
  sla_summary?: {
    total_services_analysed?: number
    services_at_risk?: number
    at_risk_services?: Array<{
      service?: string
      risk_level?: string
      hours_to_breach?: number
    }>
  }
}

interface ForecastDataPoint {
  timestamp: string
  value: number
  predicted_value?: number
  predicted?: boolean
  lower_bound?: number
  upper_bound?: number
}

interface ForecastResponse {
  metric: string
  data_points?: number
  historical?: ForecastDataPoint[]
  projected?: ForecastDataPoint[]
  forecast?: ForecastDataPoint[]
  regression?: { slope: number; intercept: number; r_squared: number }
  trend_direction?: string
  trend_percentage?: number
  current_value?: number
  predicted_value?: number
}

// Matches backend at_risk_services items
interface SLABreachPrediction {
  service: string
  current_error_rate?: number
  predicted_breach_time?: string
  confidence?: number
  hours_to_breach?: number
  risk_level?: string
  sla_threshold_pct?: number
  trend_slope_per_hour?: number
  projected_rate_72h?: number
  r_squared?: number
}

// Matches backend CapacityResponse
interface CapacityPrediction {
  growth_rate_percent?: number
  growth_rate_per_day?: number
  current_daily_volume?: number
  average_daily_volume?: number
  r_squared?: number
  capacity_projections?: Array<{
    threshold?: string
    limit?: number
    estimated_days_until?: number | null
    estimated_date?: string
  }>
  top_services?: Array<{
    service: string
    total_volume: number
    daily_average: number
    active_days: number
  }>
}

// Matches backend what-if response
interface WhatIfResult {
  scenario_type: string
  parameters?: Record<string, any>
  baseline?: Record<string, number>
  projected?: Record<string, number>
  impact?: {
    log_volume_change?: number
    log_volume_change_pct?: number
    error_rate_change?: number
    service_count_change?: number
    sla_risk?: boolean
    capacity_risk?: boolean
    notes?: string[]
  }
}

export default function PredictiveAnalyticsPage() {
  const { getApiTimeRange } = useTimeRange()

  // Summary state
  const [summary, setSummary] = useState<PredictionSummary | null>(null)
  const [isLoadingSummary, setIsLoadingSummary] = useState(true)

  // Forecast state
  const [forecast, setForecast] = useState<ForecastResponse | null>(null)
  const [isLoadingForecast, setIsLoadingForecast] = useState(true)
  const [selectedMetric, setSelectedMetric] = useState('error_rate')

  // SLA state
  const [slaBreaches, setSlaBreaches] = useState<SLABreachPrediction[]>([])
  const [isLoadingSLA, setIsLoadingSLA] = useState(true)

  // Capacity state
  const [capacity, setCapacity] = useState<CapacityPrediction | null>(null)
  const [isLoadingCapacity, setIsLoadingCapacity] = useState(true)

  // What-If state
  const [whatIfScenario, setWhatIfScenario] = useState('traffic_increase')
  const [whatIfParams, setWhatIfParams] = useState<Record<string, string>>({
    factor: '2'
  })
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResult | null>(null)
  const [isRunningWhatIf, setIsRunningWhatIf] = useState(false)

  const loadSummary = useCallback(async () => {
    try {
      setIsLoadingSummary(true)
      const response = await apiClient.get<PredictionSummary>('/v1/ai/predictions/summary')
      const data = response?.data || response
      if (data) {
        setSummary(data as PredictionSummary)
      }
    } catch (error) {
      console.error('Failed to load predictions summary:', error)
      setSummary(null)
    } finally {
      setIsLoadingSummary(false)
    }
  }, [])

  const loadForecast = useCallback(async () => {
    try {
      setIsLoadingForecast(true)
      const response = await apiClient.get<ForecastResponse>('/v1/ai/predictions/forecast', {
        metric: selectedMetric,
        time_range: '7d',
        forecast_horizon: '7d'
      })
      const data = response?.data || response
      if (data) {
        setForecast(data as ForecastResponse)
      }
    } catch (error) {
      console.error('Failed to load forecast:', error)
      setForecast(null)
    } finally {
      setIsLoadingForecast(false)
    }
  }, [selectedMetric])

  const loadSLABreaches = useCallback(async () => {
    try {
      setIsLoadingSLA(true)
      const response = await apiClient.get<{ at_risk_services: SLABreachPrediction[] }>('/v1/ai/predictions/sla-breach')
      const data = response?.data || response
      if (data?.at_risk_services) {
        setSlaBreaches(data.at_risk_services)
      } else if (Array.isArray(data)) {
        setSlaBreaches(data)
      } else {
        setSlaBreaches([])
      }
    } catch (error) {
      console.error('Failed to load SLA breach predictions:', error)
      setSlaBreaches([])
    } finally {
      setIsLoadingSLA(false)
    }
  }, [])

  const loadCapacity = useCallback(async () => {
    try {
      setIsLoadingCapacity(true)
      const response = await apiClient.get<CapacityPrediction>('/v1/ai/predictions/capacity')
      const data = response?.data || response
      if (data) {
        setCapacity(data as CapacityPrediction)
      }
    } catch (error) {
      console.error('Failed to load capacity predictions:', error)
      setCapacity(null)
    } finally {
      setIsLoadingCapacity(false)
    }
  }, [])

  useEffect(() => {
    loadSummary()
    loadSLABreaches()
    loadCapacity()
  }, [loadSummary, loadSLABreaches, loadCapacity])

  useEffect(() => {
    loadForecast()
  }, [loadForecast])

  const runWhatIf = async () => {
    setIsRunningWhatIf(true)
    setWhatIfResult(null)
    try {
      const response = await apiClient.post<WhatIfResult>('/v1/ai/predictions/what-if', {
        scenario_type: whatIfScenario,
        parameters: whatIfParams
      })
      const data = response?.data || response
      if (data) {
        setWhatIfResult(data as WhatIfResult)
      }
    } catch (error) {
      console.error('Failed to run what-if scenario:', error)
    } finally {
      setIsRunningWhatIf(false)
    }
  }

  const getTrendIcon = (direction?: string) => {
    if (direction === 'up' || direction === 'increasing') return <ArrowUpRight className="w-4 h-4 text-red-500" />
    if (direction === 'down' || direction === 'decreasing') return <ArrowDownRight className="w-4 h-4 text-green-500" />
    return <Minus className="w-4 h-4 text-slate-400" />
  }

  const getRiskColor = (level?: string) => {
    switch (level) {
      case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      case 'medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'low': return 'bg-green-500/20 text-green-400 border-green-500/30'
      default: return 'bg-slate-800/30 text-slate-300 border-white/5'
    }
  }

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString()
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Brain className="w-7 h-7 text-blue-500" />
              Predictive Analytics
            </h1>
            <p className="text-slate-400 mt-1">
              AI-powered forecasting, SLA breach predictions, and capacity planning
            </p>
          </div>
          <button
            onClick={() => { loadSummary(); loadForecast(); loadSLABreaches(); loadCapacity() }}
            className="flex items-center gap-2 px-4 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-slate-800/50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh All
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {isLoadingSummary ? (
            [1, 2, 3, 4].map(i => (
              <div key={i} className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5 h-28 animate-pulse">
                <div className="h-4 bg-slate-700 rounded w-24 mb-3" />
                <div className="h-8 bg-slate-700 rounded w-16" />
              </div>
            ))
          ) : (
            <>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <Gauge className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-medium">Risk Score</span>
                </div>
                <p className={`text-3xl font-bold ${
                  (summary?.overall_risk_score ?? 0) >= 70 ? 'text-red-600' :
                  (summary?.overall_risk_score ?? 0) >= 40 ? 'text-yellow-600' :
                  'text-green-600'
                }`}>{summary?.overall_risk_score ?? 0}</p>
                <p className="text-xs text-slate-400 capitalize">{summary?.risk_level || 'unknown'}</p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <AlertTriangle className="w-4 h-4 text-orange-500" />
                  <span className="text-sm font-medium">Services at Risk</span>
                </div>
                <p className="text-3xl font-bold text-orange-600">{summary?.sla_summary?.services_at_risk ?? 0}</p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <TrendingUp className="w-4 h-4 text-purple-500" />
                  <span className="text-sm font-medium">Forecast Trend</span>
                </div>
                <p className="text-xl font-bold text-white capitalize">{summary?.forecast_summary?.trend_direction || 'Stable'}</p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <BarChart3 className="w-4 h-4 text-green-500" />
                  <span className="text-sm font-medium">Growth Rate</span>
                </div>
                <p className="text-3xl font-bold text-white">
                  {summary?.capacity_summary?.growth_rate_percent != null ? `${summary.capacity_summary.growth_rate_percent.toFixed(1)}%` : '--'}
                </p>
                <p className="text-xs text-slate-400">per day</p>
              </div>
            </>
          )}
        </div>

        {/* Trend Forecast */}
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-500" />
              Trend Forecast
            </h2>
            <select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value)}
              className="px-3 py-2 bg-slate-800/50 border border-white/10 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
            >
              <option value="error_rate">Error Rate</option>
              <option value="log_volume">Log Volume</option>
              <option value="warn_rate">Warning Rate</option>
            </select>
          </div>

          {isLoadingForecast ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            </div>
          ) : forecast ? (
            <div className="space-y-4">
              {/* Trend Summary - derived from response data */}
              {(() => {
                const lastHistorical = forecast.historical && forecast.historical.length > 0
                  ? forecast.historical[forecast.historical.length - 1]?.value
                  : null
                const lastProjected = forecast.projected && forecast.projected.length > 0
                  ? forecast.projected[forecast.projected.length - 1]?.value
                  : null
                const trendDir = forecast.regression?.slope != null
                  ? (forecast.regression.slope > 0 ? 'increasing' : forecast.regression.slope < 0 ? 'decreasing' : 'stable')
                  : null
                return (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-sm text-slate-400 mb-1">Current Value</p>
                      <p className="text-2xl font-bold text-white">
                        {lastHistorical != null ? lastHistorical.toFixed(2) : '--'}
                      </p>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-sm text-slate-400 mb-1">Predicted Value (7d)</p>
                      <div className="flex items-center gap-2">
                        <p className="text-2xl font-bold text-white">
                          {lastProjected != null ? lastProjected.toFixed(2) : '--'}
                        </p>
                        {getTrendIcon(trendDir ?? undefined)}
                      </div>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-sm text-slate-400 mb-1">Trend</p>
                      <div className="flex items-center gap-2">
                        <p className="text-2xl font-bold text-white capitalize">
                          {trendDir || 'Stable'}
                        </p>
                        {forecast.regression?.r_squared != null && (
                          <span className="text-xs text-slate-400">
                            R²={forecast.regression.r_squared.toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })()}

              {/* Data Points Table */}
              {(Array.isArray(forecast.historical) || Array.isArray(forecast.projected) || Array.isArray(forecast.forecast)) && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/5">
                        <th className="text-left py-2 px-3 text-slate-400 font-medium">Timestamp</th>
                        <th className="text-right py-2 px-3 text-slate-400 font-medium">Value</th>
                        <th className="text-right py-2 px-3 text-slate-400 font-medium">Lower Bound</th>
                        <th className="text-right py-2 px-3 text-slate-400 font-medium">Upper Bound</th>
                        <th className="text-center py-2 px-3 text-slate-400 font-medium">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ...(Array.isArray(forecast.historical) ? forecast.historical : []).slice(-7).map(p => ({ ...p, _type: 'historical' as const })),
                        ...(Array.isArray(forecast.projected) ? forecast.projected : Array.isArray(forecast.forecast) ? forecast.forecast : []).slice(0, 7).map(p => ({ ...p, _type: 'forecast' as const })),
                      ].map((point, idx) => (
                        <tr key={idx} className="border-b border-white/5 hover:bg-slate-800/50">
                          <td className="py-2 px-3 text-slate-300">{formatTimestamp(point.timestamp)}</td>
                          <td className="py-2 px-3 text-right font-mono text-white">
                            {(point.value ?? point.predicted_value ?? 0).toFixed(3)}
                          </td>
                          <td className="py-2 px-3 text-right font-mono text-slate-400">
                            {point.lower_bound != null ? point.lower_bound.toFixed(3) : '--'}
                          </td>
                          <td className="py-2 px-3 text-right font-mono text-slate-400">
                            {point.upper_bound != null ? point.upper_bound.toFixed(3) : '--'}
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                              point._type === 'forecast'
                                ? 'bg-purple-500/20 text-purple-400'
                                : 'bg-blue-500/20 text-blue-400'
                            }`}>
                              {point._type === 'forecast' ? 'Forecast' : 'Historical'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <Activity className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400">No forecast data available</p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* SLA Breach Predictions */}
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-red-500" />
              SLA Breach Predictions
            </h2>

            {isLoadingSLA ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-16 bg-slate-800/30 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : slaBreaches.length === 0 ? (
              <div className="text-center py-10">
                <Shield className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">No SLA breach risks detected</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/5">
                      <th className="text-left py-2 px-2 text-slate-400 font-medium">Service</th>
                      <th className="text-right py-2 px-2 text-slate-400 font-medium">Error Rate</th>
                      <th className="text-right py-2 px-2 text-slate-400 font-medium">Breach In</th>
                      <th className="text-center py-2 px-2 text-slate-400 font-medium">Confidence</th>
                      <th className="text-center py-2 px-2 text-slate-400 font-medium">Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slaBreaches.map((item, idx) => (
                      <tr key={idx} className="border-b border-white/5 hover:bg-slate-800/50">
                        <td className="py-2.5 px-2">
                          <div className="flex items-center gap-2">
                            <Server className="w-4 h-4 text-slate-400" />
                            <span className="font-medium text-white">{item.service}</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-slate-300">
                          {item.current_error_rate != null ? `${item.current_error_rate.toFixed(2)}%` : '--'}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-300">
                          {item.hours_to_breach != null ? `${item.hours_to_breach.toFixed(1)}h` : item.predicted_breach_time || '--'}
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          {item.confidence != null && (
                            <span className="text-xs font-medium text-slate-400">
                              {Math.round(item.confidence * 100)}%
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${getRiskColor(item.risk_level)}`}>
                            {item.risk_level || 'unknown'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Capacity Planning */}
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <HardDrive className="w-5 h-5 text-purple-500" />
              Capacity Planning
            </h2>

            {isLoadingCapacity ? (
              <div className="flex items-center justify-center h-48">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
              </div>
            ) : capacity ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-xs text-slate-400 mb-1">Growth Rate</p>
                    <p className="text-xl font-bold text-white">
                      {capacity.growth_rate_percent != null ? `${capacity.growth_rate_percent.toFixed(1)}%` : '--'}
                    </p>
                    <p className="text-xs text-slate-400">per day</p>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-xs text-slate-400 mb-1">Days Until Limit</p>
                    {(() => {
                      const firstProjection = capacity.capacity_projections?.[0]
                      const daysUntil = firstProjection?.estimated_days_until
                      return (
                        <>
                          <p className={`text-xl font-bold ${
                            daysUntil != null && daysUntil < 30
                              ? 'text-red-600'
                              : 'text-white'
                          }`}>
                            {daysUntil ?? '--'}
                          </p>
                          {firstProjection?.threshold && (
                            <p className="text-xs text-slate-400">{firstProjection.threshold}</p>
                          )}
                        </>
                      )
                    })()}
                  </div>
                </div>

                {capacity.current_daily_volume != null && (
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-xs text-slate-400 mb-1">Current Daily Volume</p>
                    <p className="text-lg font-bold text-white">
                      {capacity.current_daily_volume.toLocaleString()} logs/day
                    </p>
                    {capacity.average_daily_volume != null && (
                      <p className="text-xs text-slate-400">
                        Avg: {capacity.average_daily_volume.toLocaleString()} logs/day
                      </p>
                    )}
                  </div>
                )}

                {/* Top Services by Volume */}
                {capacity.top_services && capacity.top_services.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-slate-300 mb-2">Top Services by Volume</h3>
                    <div className="space-y-2">
                      {capacity.top_services.slice(0, 5).map((svc, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2.5 bg-slate-800/50 rounded-lg">
                          <div className="flex items-center gap-2">
                            <Server className="w-4 h-4 text-slate-400" />
                            <span className="text-sm font-medium text-white">{svc.service}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-xs text-slate-400">{svc.daily_average.toLocaleString()}/day</span>
                            <span className="text-xs font-medium text-slate-300">
                              {svc.total_volume.toLocaleString()} total
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-10">
                <HardDrive className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">No capacity data available</p>
              </div>
            )}
          </div>
        </div>

        {/* What-If Scenario */}
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-500" />
            What-If Scenario Analysis
          </h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Input Form */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Scenario Type</label>
                <select
                  value={whatIfScenario}
                  onChange={(e) => setWhatIfScenario(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800/50 border border-white/10 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
                >
                  <option value="traffic_increase">Traffic Increase</option>
                  <option value="error_rate_change">Error Rate Change</option>
                  <option value="add_services">Add Services</option>
                  <option value="combined">Combined Scenario</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  {whatIfScenario === 'add_services' ? 'Service Count' : 'Factor'}
                </label>
                <input
                  type="text"
                  value={whatIfScenario === 'add_services' ? (whatIfParams.count || '') : (whatIfParams.factor || '')}
                  onChange={(e) => {
                    if (whatIfScenario === 'add_services') {
                      setWhatIfParams({ ...whatIfParams, count: e.target.value })
                    } else {
                      setWhatIfParams({ ...whatIfParams, factor: e.target.value })
                    }
                  }}
                  placeholder={whatIfScenario === 'add_services' ? 'e.g., 5' : 'e.g., 2.0'}
                  className="w-full px-3 py-2 bg-slate-800/50 border border-white/10 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
                />
              </div>

              <button
                onClick={runWhatIf}
                disabled={isRunningWhatIf}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {isRunningWhatIf ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Running Scenario...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Run Scenario
                  </>
                )}
              </button>
            </div>

            {/* Results */}
            <div>
              {isRunningWhatIf ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Loader2 className="w-8 h-8 text-amber-500 animate-spin mx-auto mb-3" />
                    <p className="text-slate-400 text-sm">Simulating scenario...</p>
                  </div>
                </div>
              ) : whatIfResult ? (
                <div className="space-y-4">
                  {/* Impact Notes */}
                  {whatIfResult.impact?.notes && whatIfResult.impact.notes.length > 0 && (
                    <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-amber-400 mb-1">Impact Summary</h4>
                      <div className="space-y-1">
                        {whatIfResult.impact.notes.map((note, idx) => (
                          <p key={idx} className="text-sm text-amber-300">{note}</p>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Baseline vs Projected Comparison */}
                  {whatIfResult.baseline && whatIfResult.projected && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-white/5">
                            <th className="text-left py-2 px-2 text-slate-400 font-medium">Metric</th>
                            <th className="text-right py-2 px-2 text-slate-400 font-medium">Baseline</th>
                            <th className="text-right py-2 px-2 text-slate-400 font-medium">Projected</th>
                            <th className="text-right py-2 px-2 text-slate-400 font-medium">Change</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.keys(whatIfResult.baseline).map(key => {
                            const baseline = whatIfResult.baseline![key]
                            const projected = whatIfResult.projected![key]
                            const change = projected != null && baseline != null && baseline !== 0
                              ? ((projected - baseline) / baseline) * 100
                              : null
                            return (
                              <tr key={key} className="border-b border-white/5">
                                <td className="py-2 px-2 text-slate-300 capitalize">
                                  {key.replace(/_/g, ' ')}
                                </td>
                                <td className="py-2 px-2 text-right font-mono text-slate-400">
                                  {typeof baseline === 'number' ? baseline.toFixed(2) : baseline}
                                </td>
                                <td className="py-2 px-2 text-right font-mono text-white font-medium">
                                  {typeof projected === 'number' ? projected.toFixed(2) : projected}
                                </td>
                                <td className="py-2 px-2 text-right">
                                  {change != null && (
                                    <span className={`text-xs font-medium ${change > 0 ? 'text-red-600' : 'text-green-600'}`}>
                                      {change > 0 ? '+' : ''}{change.toFixed(1)}%
                                    </span>
                                  )}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Risk Indicators */}
                  {whatIfResult.impact && (whatIfResult.impact.sla_risk || whatIfResult.impact.capacity_risk) && (
                    <div className="flex gap-2">
                      {whatIfResult.impact.sla_risk && (
                        <span className="text-xs px-2.5 py-1 bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg font-medium">
                          SLA Risk
                        </span>
                      )}
                      {whatIfResult.impact.capacity_risk && (
                        <span className="text-xs px-2.5 py-1 bg-orange-500/20 text-orange-400 border border-orange-500/30 rounded-lg font-medium">
                          Capacity Risk
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center py-8">
                    <Zap className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-400 text-sm">Configure a scenario and click Run</p>
                    <p className="text-slate-400 text-xs mt-1">See how changes would impact your system</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
