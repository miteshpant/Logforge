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

interface PredictionSummary {
  total_predictions?: number
  services_at_risk?: number
  capacity_trend?: string
  avg_confidence?: number
  high_risk_count?: number
}

interface ForecastDataPoint {
  timestamp: string
  value: number
  predicted?: boolean
  lower_bound?: number
  upper_bound?: number
}

interface ForecastResponse {
  metric: string
  data_points?: ForecastDataPoint[]
  forecast?: ForecastDataPoint[]
  historical?: ForecastDataPoint[]
  trend_direction?: string
  trend_percentage?: number
  current_value?: number
  predicted_value?: number
}

interface SLABreachPrediction {
  service_name: string
  current_error_rate?: number
  predicted_breach_time?: string
  confidence?: number
  trend?: string
  risk_level?: string
  sla_target?: number
  metric?: string
}

interface CapacityPrediction {
  growth_rate?: number
  days_until_limit?: number
  current_usage_pct?: number
  top_growing_services?: Array<{
    service: string
    growth_rate: number
    current_usage: number
    projected_limit_date?: string
  }>
}

interface WhatIfResult {
  scenario_type: string
  baseline?: Record<string, number>
  projected?: Record<string, number>
  impact_summary?: string
  risk_change?: string
  details?: string[]
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
  const [whatIfScenario, setWhatIfScenario] = useState('traffic_spike')
  const [whatIfParams, setWhatIfParams] = useState<Record<string, string>>({
    multiplier: '2',
    duration: '1h'
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
      const response = await apiClient.get<{ predictions: SLABreachPrediction[]; services: SLABreachPrediction[] }>('/v1/ai/predictions/sla-breach')
      const data = response?.data || response
      if (data?.predictions) {
        setSlaBreaches(data.predictions)
      } else if (data?.services) {
        setSlaBreaches(data.services)
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
      case 'critical': return 'bg-red-100 text-red-700 border-red-200'
      case 'high': return 'bg-orange-100 text-orange-700 border-orange-200'
      case 'medium': return 'bg-yellow-100 text-yellow-700 border-yellow-200'
      case 'low': return 'bg-green-100 text-green-700 border-green-200'
      default: return 'bg-slate-100 text-slate-700 border-slate-200'
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
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <Brain className="w-7 h-7 text-blue-500" />
              Predictive Analytics
            </h1>
            <p className="text-slate-600 mt-1">
              AI-powered forecasting, SLA breach predictions, and capacity planning
            </p>
          </div>
          <button
            onClick={() => { loadSummary(); loadForecast(); loadSLABreaches(); loadCapacity() }}
            className="flex items-center gap-2 px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh All
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {isLoadingSummary ? (
            [1, 2, 3, 4].map(i => (
              <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 h-28 animate-pulse">
                <div className="h-4 bg-slate-200 rounded w-24 mb-3" />
                <div className="h-8 bg-slate-200 rounded w-16" />
              </div>
            ))
          ) : (
            <>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-center gap-2 text-slate-600 mb-2">
                  <BarChart3 className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-medium">Total Predictions</span>
                </div>
                <p className="text-3xl font-bold text-slate-900">{summary?.total_predictions ?? 0}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-center gap-2 text-slate-600 mb-2">
                  <AlertTriangle className="w-4 h-4 text-orange-500" />
                  <span className="text-sm font-medium">Services at Risk</span>
                </div>
                <p className="text-3xl font-bold text-orange-600">{summary?.services_at_risk ?? 0}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-center gap-2 text-slate-600 mb-2">
                  <TrendingUp className="w-4 h-4 text-purple-500" />
                  <span className="text-sm font-medium">Capacity Trend</span>
                </div>
                <p className="text-xl font-bold text-slate-900 capitalize">{summary?.capacity_trend || 'Stable'}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-center gap-2 text-slate-600 mb-2">
                  <Target className="w-4 h-4 text-green-500" />
                  <span className="text-sm font-medium">Avg Confidence</span>
                </div>
                <p className="text-3xl font-bold text-slate-900">
                  {summary?.avg_confidence != null ? `${Math.round(summary.avg_confidence * 100)}%` : '--'}
                </p>
              </div>
            </>
          )}
        </div>

        {/* Trend Forecast */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-500" />
              Trend Forecast
            </h2>
            <select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value)}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-700 focus:outline-none focus:border-blue-500"
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
              {/* Trend Summary */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-sm text-slate-500 mb-1">Current Value</p>
                  <p className="text-2xl font-bold text-slate-900">
                    {forecast.current_value != null ? forecast.current_value.toFixed(2) : '--'}
                  </p>
                </div>
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-sm text-slate-500 mb-1">Predicted Value (7d)</p>
                  <div className="flex items-center gap-2">
                    <p className="text-2xl font-bold text-slate-900">
                      {forecast.predicted_value != null ? forecast.predicted_value.toFixed(2) : '--'}
                    </p>
                    {getTrendIcon(forecast.trend_direction)}
                  </div>
                </div>
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-sm text-slate-500 mb-1">Trend</p>
                  <div className="flex items-center gap-2">
                    <p className="text-2xl font-bold text-slate-900 capitalize">
                      {forecast.trend_direction || 'Stable'}
                    </p>
                    {forecast.trend_percentage != null && (
                      <span className={`text-sm font-medium ${
                        forecast.trend_percentage > 0 ? 'text-red-500' : 'text-green-500'
                      }`}>
                        {forecast.trend_percentage > 0 ? '+' : ''}{forecast.trend_percentage.toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Data Points Table */}
              {(forecast.data_points || forecast.forecast || forecast.historical) && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200">
                        <th className="text-left py-2 px-3 text-slate-500 font-medium">Timestamp</th>
                        <th className="text-right py-2 px-3 text-slate-500 font-medium">Value</th>
                        <th className="text-right py-2 px-3 text-slate-500 font-medium">Lower Bound</th>
                        <th className="text-right py-2 px-3 text-slate-500 font-medium">Upper Bound</th>
                        <th className="text-center py-2 px-3 text-slate-500 font-medium">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(forecast.data_points || forecast.forecast || forecast.historical || []).slice(0, 14).map((point, idx) => (
                        <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
                          <td className="py-2 px-3 text-slate-700">{formatTimestamp(point.timestamp)}</td>
                          <td className="py-2 px-3 text-right font-mono text-slate-900">{point.value.toFixed(3)}</td>
                          <td className="py-2 px-3 text-right font-mono text-slate-500">
                            {point.lower_bound != null ? point.lower_bound.toFixed(3) : '--'}
                          </td>
                          <td className="py-2 px-3 text-right font-mono text-slate-500">
                            {point.upper_bound != null ? point.upper_bound.toFixed(3) : '--'}
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                              point.predicted
                                ? 'bg-purple-100 text-purple-700'
                                : 'bg-blue-100 text-blue-700'
                            }`}>
                              {point.predicted ? 'Forecast' : 'Historical'}
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
              <p className="text-slate-500">No forecast data available</p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* SLA Breach Predictions */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-red-500" />
              SLA Breach Predictions
            </h2>

            {isLoadingSLA ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : slaBreaches.length === 0 ? (
              <div className="text-center py-10">
                <Shield className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 text-sm">No SLA breach risks detected</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      <th className="text-left py-2 px-2 text-slate-500 font-medium">Service</th>
                      <th className="text-right py-2 px-2 text-slate-500 font-medium">Error Rate</th>
                      <th className="text-right py-2 px-2 text-slate-500 font-medium">Breach In</th>
                      <th className="text-center py-2 px-2 text-slate-500 font-medium">Confidence</th>
                      <th className="text-center py-2 px-2 text-slate-500 font-medium">Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slaBreaches.map((item, idx) => (
                      <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="py-2.5 px-2">
                          <div className="flex items-center gap-2">
                            <Server className="w-4 h-4 text-slate-400" />
                            <span className="font-medium text-slate-900">{item.service_name}</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-slate-700">
                          {item.current_error_rate != null ? `${(item.current_error_rate * 100).toFixed(2)}%` : '--'}
                        </td>
                        <td className="py-2.5 px-2 text-right text-slate-700">
                          {item.predicted_breach_time || '--'}
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          {item.confidence != null && (
                            <span className="text-xs font-medium text-slate-600">
                              {Math.round(item.confidence * 100)}%
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${getRiskColor(item.risk_level)}`}>
                            {item.risk_level || item.trend || 'unknown'}
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
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
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
                  <div className="bg-slate-50 rounded-lg p-3">
                    <p className="text-xs text-slate-500 mb-1">Growth Rate</p>
                    <p className="text-xl font-bold text-slate-900">
                      {capacity.growth_rate != null ? `${capacity.growth_rate.toFixed(1)}%` : '--'}
                    </p>
                    <p className="text-xs text-slate-400">per day</p>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3">
                    <p className="text-xs text-slate-500 mb-1">Days Until Limit</p>
                    <p className={`text-xl font-bold ${
                      capacity.days_until_limit != null && capacity.days_until_limit < 30
                        ? 'text-red-600'
                        : 'text-slate-900'
                    }`}>
                      {capacity.days_until_limit ?? '--'}
                    </p>
                    <p className="text-xs text-slate-400">estimated</p>
                  </div>
                </div>

                {capacity.current_usage_pct != null && (
                  <div>
                    <div className="flex justify-between text-xs text-slate-500 mb-1">
                      <span>Current Usage</span>
                      <span>{capacity.current_usage_pct.toFixed(1)}%</span>
                    </div>
                    <div className="h-2.5 bg-slate-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          capacity.current_usage_pct > 80 ? 'bg-red-500' :
                          capacity.current_usage_pct > 60 ? 'bg-yellow-500' :
                          'bg-green-500'
                        }`}
                        style={{ width: `${Math.min(capacity.current_usage_pct, 100)}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Top Growing Services */}
                {capacity.top_growing_services && capacity.top_growing_services.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-slate-700 mb-2">Top Growing Services</h3>
                    <div className="space-y-2">
                      {capacity.top_growing_services.map((svc, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg">
                          <div className="flex items-center gap-2">
                            <Server className="w-4 h-4 text-slate-400" />
                            <span className="text-sm font-medium text-slate-800">{svc.service}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-xs text-slate-500">{svc.current_usage.toFixed(1)}% used</span>
                            <span className="text-xs font-medium text-red-600 flex items-center gap-0.5">
                              <ArrowUpRight className="w-3 h-3" />
                              {svc.growth_rate.toFixed(1)}%/d
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
                <p className="text-slate-500 text-sm">No capacity data available</p>
              </div>
            )}
          </div>
        </div>

        {/* What-If Scenario */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-500" />
            What-If Scenario Analysis
          </h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Input Form */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Scenario Type</label>
                <select
                  value={whatIfScenario}
                  onChange={(e) => setWhatIfScenario(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-700 focus:outline-none focus:border-blue-500"
                >
                  <option value="traffic_spike">Traffic Spike</option>
                  <option value="service_failure">Service Failure</option>
                  <option value="capacity_increase">Capacity Increase</option>
                  <option value="deployment_rollback">Deployment Rollback</option>
                  <option value="load_redistribution">Load Redistribution</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Multiplier</label>
                <input
                  type="text"
                  value={whatIfParams.multiplier || ''}
                  onChange={(e) => setWhatIfParams({ ...whatIfParams, multiplier: e.target.value })}
                  placeholder="e.g., 2"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-700 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Duration</label>
                <input
                  type="text"
                  value={whatIfParams.duration || ''}
                  onChange={(e) => setWhatIfParams({ ...whatIfParams, duration: e.target.value })}
                  placeholder="e.g., 1h, 30m, 2d"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-700 focus:outline-none focus:border-blue-500"
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
                    <p className="text-slate-600 text-sm">Simulating scenario...</p>
                  </div>
                </div>
              ) : whatIfResult ? (
                <div className="space-y-4">
                  {/* Impact Summary */}
                  {whatIfResult.impact_summary && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-amber-800 mb-1">Impact Summary</h4>
                      <p className="text-sm text-amber-700">{whatIfResult.impact_summary}</p>
                    </div>
                  )}

                  {/* Baseline vs Projected Comparison */}
                  {whatIfResult.baseline && whatIfResult.projected && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-slate-200">
                            <th className="text-left py-2 px-2 text-slate-500 font-medium">Metric</th>
                            <th className="text-right py-2 px-2 text-slate-500 font-medium">Baseline</th>
                            <th className="text-right py-2 px-2 text-slate-500 font-medium">Projected</th>
                            <th className="text-right py-2 px-2 text-slate-500 font-medium">Change</th>
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
                              <tr key={key} className="border-b border-slate-100">
                                <td className="py-2 px-2 text-slate-700 capitalize">
                                  {key.replace(/_/g, ' ')}
                                </td>
                                <td className="py-2 px-2 text-right font-mono text-slate-600">
                                  {typeof baseline === 'number' ? baseline.toFixed(2) : baseline}
                                </td>
                                <td className="py-2 px-2 text-right font-mono text-slate-900 font-medium">
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

                  {/* Risk Change */}
                  {whatIfResult.risk_change && (
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500 mb-0.5">Risk Level Change</p>
                      <p className="text-sm font-medium text-slate-800">{whatIfResult.risk_change}</p>
                    </div>
                  )}

                  {/* Details */}
                  {whatIfResult.details && whatIfResult.details.length > 0 && (
                    <div className="space-y-1">
                      {whatIfResult.details.map((detail, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-sm text-slate-600">
                          <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
                          <span>{detail}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center py-8">
                    <Zap className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500 text-sm">Configure a scenario and click Run</p>
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
