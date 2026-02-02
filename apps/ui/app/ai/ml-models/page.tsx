'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Brain,
  Activity,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  BarChart3,
  Shield,
  Gauge,
  Settings,
  Loader2,
  ChevronDown,
  ChevronRight,
  Zap,
  TrendingUp,
  Database,
  Sliders,
  RotateCcw,
  Eye,
  Layers
} from 'lucide-react'

interface ModelHealthItem {
  model_id: string
  name: string
  description: string
  status: string
  accuracy: number
  false_positive_rate: number
  false_negative_rate: number
  sample_count: number
  last_trained: string | null
  hours_since_training: number | null
  drift_score: number
  data_quality: string
  baseline_count: number
  needs_retraining: boolean
}

interface ModelHealthSummary {
  total_models: number
  healthy: number
  degraded: number
  stale: number
  needs_retraining: number
  overall_health: string
}

interface BaselineVisualization {
  model_id: string
  baseline_type: string
  statistics: {
    mean: number
    std_dev: number
    min: number
    max: number
    p50: number
    p95: number
    p99: number
    sample_count: number
  }
  bands: {
    normal: { lower: number; upper: number }
    warning: { lower: number; upper: number }
    critical: { lower: number; upper: number }
  }
  accuracy: number
  last_trained: string
  is_active: number
}

interface BaselineListItem {
  model_id: string
  service_name: string
  baseline_type: string
  baseline_data: Record<string, any>
  last_trained?: string
  accuracy_score?: number
  sample_count?: number
}

export default function MLModelsPage() {
  // Model health
  const [models, setModels] = useState<ModelHealthItem[]>([])
  const [healthSummary, setHealthSummary] = useState<ModelHealthSummary | null>(null)
  const [isLoadingHealth, setIsLoadingHealth] = useState(true)

  // Baselines
  const [baselines, setBaselines] = useState<BaselineVisualization[]>([])
  const [isLoadingBaselines, setIsLoadingBaselines] = useState(true)

  // Baseline list
  const [baselineList, setBaselineList] = useState<BaselineListItem[]>([])
  const [isLoadingBaselineList, setIsLoadingBaselineList] = useState(true)

  // UI state
  const [expandedModels, setExpandedModels] = useState<Record<string, boolean>>({})
  const [retrainingModel, setRetrainingModel] = useState<string | null>(null)
  const [retrainDays, setRetrainDays] = useState(30)
  const [showThresholdModal, setShowThresholdModal] = useState<string | null>(null)
  const [thresholdSigma, setThresholdSigma] = useState('3.0')
  const [thresholdMinConfidence, setThresholdMinConfidence] = useState('0.7')
  const [thresholdReason, setThresholdReason] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [actionResult, setActionResult] = useState<{ model: string; success: boolean; message: string } | null>(null)

  const loadModelHealth = useCallback(async () => {
    try {
      setIsLoadingHealth(true)
      const response = await apiClient.get<{ models: ModelHealthItem[]; summary: ModelHealthSummary }>('/v1/ai/models/health')
      const data = response?.data || response
      if (data?.models) {
        setModels(data.models)
      } else if (Array.isArray(data)) {
        setModels(data as ModelHealthItem[])
      } else {
        setModels([])
      }
      if (data?.summary) {
        setHealthSummary(data.summary)
      }
    } catch (error) {
      console.error('Failed to load model health:', error)
      setModels([])
      setHealthSummary(null)
    } finally {
      setIsLoadingHealth(false)
    }
  }, [])

  const loadBaselines = useCallback(async () => {
    try {
      setIsLoadingBaselines(true)
      const response = await apiClient.get<{ baselines: BaselineVisualization[]; total: number }>('/v1/ai/models/baselines/visualization')
      const data = response?.data || response
      if (data?.baselines) {
        setBaselines(data.baselines)
      } else if (Array.isArray(data)) {
        setBaselines(data as BaselineVisualization[])
      } else {
        setBaselines([])
      }
    } catch (error) {
      console.error('Failed to load baseline visualization:', error)
      setBaselines([])
    } finally {
      setIsLoadingBaselines(false)
    }
  }, [])

  const loadBaselineList = useCallback(async () => {
    try {
      setIsLoadingBaselineList(true)
      const response = await apiClient.get<{ baselines: BaselineListItem[]; total: number }>('/v1/ai/baselines')
      const data = response?.data || response
      if (data?.baselines) {
        setBaselineList(data.baselines)
      } else if (Array.isArray(data)) {
        setBaselineList(data as BaselineListItem[])
      } else {
        setBaselineList([])
      }
    } catch (error) {
      console.error('Failed to load baseline list:', error)
      setBaselineList([])
    } finally {
      setIsLoadingBaselineList(false)
    }
  }, [])

  useEffect(() => {
    loadModelHealth()
    loadBaselines()
    loadBaselineList()
  }, [loadModelHealth, loadBaselines, loadBaselineList])

  const handleRetrain = async (modelId: string) => {
    setActionLoading(modelId)
    setActionResult(null)
    try {
      const response = await apiClient.post<{ status: string }>('/v1/ai/models/retrain', {
        model_id: modelId,
        training_days: retrainDays,
        force: false
      })
      const data = response?.data || response
      setActionResult({
        model: modelId,
        success: true,
        message: `Model retrained with ${retrainDays} days of data`
      })
      setRetrainingModel(null)
      // Reload health after retraining
      loadModelHealth()
      loadBaselines()
      loadBaselineList()
    } catch (error) {
      console.error('Failed to retrain model:', error)
      setActionResult({
        model: modelId,
        success: false,
        message: 'Failed to retrain model. Please try again.'
      })
    } finally {
      setActionLoading(null)
    }
  }

  const handleUpdateThresholds = async (modelId: string) => {
    setActionLoading(modelId)
    setActionResult(null)
    try {
      await apiClient.put('/v1/ai/models/thresholds', {
        model_id: modelId,
        thresholds: {
          sigma_threshold: parseFloat(thresholdSigma),
          min_confidence: parseFloat(thresholdMinConfidence)
        },
        reason: thresholdReason
      })
      setActionResult({
        model: modelId,
        success: true,
        message: 'Thresholds updated successfully'
      })
      setShowThresholdModal(null)
      setThresholdReason('')
      loadBaselines()
    } catch (error) {
      console.error('Failed to update thresholds:', error)
      setActionResult({
        model: modelId,
        success: false,
        message: 'Failed to update thresholds. Please try again.'
      })
    } finally {
      setActionLoading(null)
    }
  }

  const toggleModel = (modelId: string) => {
    setExpandedModels(prev => ({
      ...prev,
      [modelId]: !prev[modelId]
    }))
  }

  const getStatusBadge = (status: string) => {
    const map: Record<string, { bg: string; text: string; icon: typeof CheckCircle }> = {
      healthy: { bg: 'bg-green-500/20 border-green-500/30', text: 'text-green-400', icon: CheckCircle },
      degraded: { bg: 'bg-orange-500/20 border-orange-500/30', text: 'text-orange-400', icon: AlertTriangle },
      stale: { bg: 'bg-yellow-500/20 border-yellow-500/30', text: 'text-yellow-400', icon: Clock },
      noisy: { bg: 'bg-purple-500/20 border-purple-500/30', text: 'text-purple-400', icon: Activity },
      no_baseline: { bg: 'bg-slate-800/30 border-white/5', text: 'text-slate-400', icon: XCircle }
    }
    return map[status] || map.no_baseline
  }

  const getQualityBadge = (quality: string) => {
    const map: Record<string, string> = {
      high: 'bg-green-500/20 text-green-400',
      medium: 'bg-yellow-500/20 text-yellow-400',
      low: 'bg-red-500/20 text-red-400',
      none: 'bg-slate-800/30 text-slate-400'
    }
    return map[quality] || map.none
  }

  const formatHours = (hours: number | null) => {
    if (hours == null) return 'Never'
    if (hours < 1) return `${Math.round(hours * 60)}m ago`
    if (hours < 24) return `${Math.round(hours)}h ago`
    return `${Math.round(hours / 24)}d ago`
  }

  const formatNumber = (n: number) => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
    return n.toString()
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Brain className="w-7 h-7 text-indigo-500" />
              ML Model Management
            </h1>
            <p className="text-slate-400 mt-1">
              Monitor model health, manage baselines, tune thresholds, and trigger retraining
            </p>
          </div>
          <button
            onClick={() => { loadModelHealth(); loadBaselines(); loadBaselineList() }}
            className="flex items-center gap-2 px-4 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh All
          </button>
        </div>

        {/* Action Result Toast */}
        {actionResult && (
          <div className={`flex items-center gap-3 p-4 rounded-lg border ${
            actionResult.success
              ? 'bg-green-500/10 border-green-500/30 text-green-400'
              : 'bg-red-500/10 border-red-500/30 text-red-400'
          }`}>
            {actionResult.success ? (
              <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
            ) : (
              <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            )}
            <span className="text-sm font-medium">{actionResult.message}</span>
            <button
              onClick={() => setActionResult(null)}
              className="ml-auto text-sm underline hover:no-underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Health Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {isLoadingHealth ? (
            [1, 2, 3, 4, 5].map(i => (
              <div key={i} className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5 h-24 animate-pulse">
                <div className="h-4 bg-slate-700 rounded w-24 mb-3" />
                <div className="h-7 bg-slate-700 rounded w-12" />
              </div>
            ))
          ) : healthSummary ? (
            <>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <Layers className="w-4 h-4 text-indigo-500" />
                  <span className="text-sm font-medium">Total Models</span>
                </div>
                <p className="text-3xl font-bold text-white">{healthSummary.total_models}</p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span className="text-sm font-medium">Healthy</span>
                </div>
                <p className="text-3xl font-bold text-green-400">{healthSummary.healthy}</p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <AlertTriangle className="w-4 h-4 text-orange-500" />
                  <span className="text-sm font-medium">Degraded</span>
                </div>
                <p className="text-3xl font-bold text-orange-400">{healthSummary.degraded}</p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <Clock className="w-4 h-4 text-yellow-500" />
                  <span className="text-sm font-medium">Stale</span>
                </div>
                <p className="text-3xl font-bold text-yellow-400">{healthSummary.stale}</p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <RotateCcw className="w-4 h-4 text-purple-500" />
                  <span className="text-sm font-medium">Needs Retraining</span>
                </div>
                <p className="text-3xl font-bold text-purple-400">{healthSummary.needs_retraining}</p>
              </div>
            </>
          ) : (
            <div className="col-span-5 text-center py-8 text-slate-400">
              No model health data available
            </div>
          )}
        </div>

        {/* Model Cards */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-indigo-500" />
            Model Health Details
          </h2>

          {isLoadingHealth ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-24 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl border border-white/5 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : models.length === 0 ? (
            <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-12 text-center">
              <Brain className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400">No ML models found</p>
              <p className="text-slate-400 text-sm mt-1">Models will appear here once baselines are created</p>
            </div>
          ) : (
            <div className="space-y-3">
              {models.map(model => {
                const statusStyle = getStatusBadge(model.status)
                const StatusIcon = statusStyle.icon
                const isExpanded = expandedModels[model.model_id]

                return (
                  <div key={model.model_id} className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 overflow-hidden">
                    {/* Model Header Row */}
                    <button
                      onClick={() => toggleModel(model.model_id)}
                      className="w-full flex items-center justify-between p-5 hover:bg-white/5 transition-colors text-left"
                    >
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        {isExpanded
                          ? <ChevronDown className="w-5 h-5 text-slate-400 flex-shrink-0" />
                          : <ChevronRight className="w-5 h-5 text-slate-400 flex-shrink-0" />
                        }
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3 flex-wrap">
                            <span className="font-semibold text-white">{model.name}</span>
                            <span className={`text-xs px-2.5 py-0.5 rounded-full border ${statusStyle.bg} ${statusStyle.text} flex items-center gap-1`}>
                              <StatusIcon className="w-3 h-3" />
                              {model.status}
                            </span>
                            {model.needs_retraining && (
                              <span className="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded-full border border-purple-500/30">
                                Needs Retraining
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-slate-400 mt-0.5">{model.description}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-6 flex-shrink-0 ml-4">
                        <div className="text-right">
                          <p className="text-xs text-slate-400">Accuracy</p>
                          <p className={`text-lg font-bold ${
                            model.accuracy >= 0.8 ? 'text-green-400' :
                            model.accuracy >= 0.6 ? 'text-yellow-400' :
                            'text-red-400'
                          }`}>
                            {model.accuracy > 0 ? `${(model.accuracy * 100).toFixed(1)}%` : '--'}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs text-slate-400">Last Trained</p>
                          <p className="text-sm font-medium text-slate-300">
                            {formatHours(model.hours_since_training)}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs text-slate-400">Quality</p>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getQualityBadge(model.data_quality)}`}>
                            {model.data_quality}
                          </span>
                        </div>
                      </div>
                    </button>

                    {/* Expanded Details */}
                    {isExpanded && (
                      <div className="border-t border-white/5 bg-slate-800/50 p-5 space-y-5">
                        {/* Metrics Grid */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl p-4 rounded-lg border border-white/5">
                            <div className="flex items-center gap-2 mb-1">
                              <Gauge className="w-4 h-4 text-blue-500" />
                              <span className="text-xs text-slate-400">Accuracy</span>
                            </div>
                            <p className="text-xl font-bold text-white">
                              {model.accuracy > 0 ? `${(model.accuracy * 100).toFixed(2)}%` : 'N/A'}
                            </p>
                          </div>
                          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl p-4 rounded-lg border border-white/5">
                            <div className="flex items-center gap-2 mb-1">
                              <AlertTriangle className="w-4 h-4 text-orange-500" />
                              <span className="text-xs text-slate-400">False Positive Rate</span>
                            </div>
                            <p className="text-xl font-bold text-white">
                              {model.false_positive_rate > 0 ? `${(model.false_positive_rate * 100).toFixed(2)}%` : 'N/A'}
                            </p>
                          </div>
                          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl p-4 rounded-lg border border-white/5">
                            <div className="flex items-center gap-2 mb-1">
                              <XCircle className="w-4 h-4 text-red-500" />
                              <span className="text-xs text-slate-400">False Negative Rate</span>
                            </div>
                            <p className="text-xl font-bold text-white">
                              {model.false_negative_rate > 0 ? `${(model.false_negative_rate * 100).toFixed(2)}%` : 'N/A'}
                            </p>
                          </div>
                          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl p-4 rounded-lg border border-white/5">
                            <div className="flex items-center gap-2 mb-1">
                              <TrendingUp className="w-4 h-4 text-purple-500" />
                              <span className="text-xs text-slate-400">Drift Score</span>
                            </div>
                            <p className={`text-xl font-bold ${
                              model.drift_score > 0.5 ? 'text-red-400' :
                              model.drift_score > 0.2 ? 'text-yellow-400' :
                              'text-green-400'
                            }`}>
                              {model.drift_score > 0 ? model.drift_score.toFixed(4) : 'N/A'}
                            </p>
                          </div>
                        </div>

                        {/* Additional Info */}
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                          <div className="flex items-center gap-3 p-3 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5">
                            <Database className="w-5 h-5 text-slate-400" />
                            <div>
                              <p className="text-xs text-slate-400">Sample Count</p>
                              <p className="text-sm font-semibold text-white">
                                {formatNumber(model.sample_count)}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5">
                            <BarChart3 className="w-5 h-5 text-slate-400" />
                            <div>
                              <p className="text-xs text-slate-400">Baselines</p>
                              <p className="text-sm font-semibold text-white">{model.baseline_count}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5">
                            <Clock className="w-5 h-5 text-slate-400" />
                            <div>
                              <p className="text-xs text-slate-400">Last Trained</p>
                              <p className="text-sm font-semibold text-white">
                                {model.last_trained
                                  ? new Date(model.last_trained).toLocaleString()
                                  : 'Never'}
                              </p>
                            </div>
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-3 pt-2">
                          {/* Retrain Button */}
                          {retrainingModel === model.model_id ? (
                            <div className="flex items-center gap-3 p-3 bg-slate-800/50 border border-indigo-500/20 rounded-lg">
                              <label className="text-sm text-slate-300">Training days:</label>
                              <select
                                value={retrainDays}
                                onChange={(e) => setRetrainDays(Number(e.target.value))}
                                className="px-2 py-1 border border-white/10 rounded text-sm"
                              >
                                <option value={7}>7 days</option>
                                <option value={14}>14 days</option>
                                <option value={30}>30 days</option>
                                <option value={60}>60 days</option>
                                <option value={90}>90 days</option>
                              </select>
                              <button
                                onClick={() => handleRetrain(model.model_id)}
                                disabled={actionLoading === model.model_id}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
                              >
                                {actionLoading === model.model_id ? (
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                  <Zap className="w-4 h-4" />
                                )}
                                Retrain
                              </button>
                              <button
                                onClick={() => setRetrainingModel(null)}
                                className="text-sm text-slate-400 hover:text-slate-300"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setRetrainingModel(model.model_id)}
                              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm rounded-lg transition-colors"
                            >
                              <RotateCcw className="w-4 h-4" />
                              Retrain Model
                            </button>
                          )}

                          {/* Threshold Button */}
                          <button
                            onClick={() => setShowThresholdModal(model.model_id)}
                            className="flex items-center gap-2 px-4 py-2 border border-white/10 text-slate-300 text-sm rounded-lg hover:bg-white/5 transition-colors"
                          >
                            <Sliders className="w-4 h-4" />
                            Tune Thresholds
                          </button>
                        </div>

                        {/* Threshold Modal */}
                        {showThresholdModal === model.model_id && (
                          <div className="p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl border border-white/5 rounded-lg space-y-4">
                            <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                              <Sliders className="w-4 h-4 text-indigo-500" />
                              Adjust Detection Thresholds
                            </h4>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div>
                                <label className="block text-xs font-medium text-slate-400 mb-1">
                                  Sigma Threshold (standard deviations)
                                </label>
                                <input
                                  type="number"
                                  value={thresholdSigma}
                                  onChange={(e) => setThresholdSigma(e.target.value)}
                                  step="0.5"
                                  min="1"
                                  max="5"
                                  className="w-full px-3 py-2 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                                />
                                <p className="text-xs text-slate-400 mt-1">Lower = more sensitive, Higher = fewer alerts</p>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-slate-400 mb-1">
                                  Minimum Confidence (0-1)
                                </label>
                                <input
                                  type="number"
                                  value={thresholdMinConfidence}
                                  onChange={(e) => setThresholdMinConfidence(e.target.value)}
                                  step="0.05"
                                  min="0"
                                  max="1"
                                  className="w-full px-3 py-2 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                                />
                                <p className="text-xs text-slate-400 mt-1">Only report anomalies above this confidence</p>
                              </div>
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-400 mb-1">
                                Reason for change (optional)
                              </label>
                              <input
                                type="text"
                                value={thresholdReason}
                                onChange={(e) => setThresholdReason(e.target.value)}
                                placeholder="e.g., Reducing false positives after deployment"
                                className="w-full px-3 py-2 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                              />
                            </div>
                            <div className="flex items-center gap-3">
                              <button
                                onClick={() => handleUpdateThresholds(model.model_id)}
                                disabled={actionLoading === model.model_id}
                                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
                              >
                                {actionLoading === model.model_id ? (
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                  <CheckCircle className="w-4 h-4" />
                                )}
                                Apply Thresholds
                              </button>
                              <button
                                onClick={() => { setShowThresholdModal(null); setThresholdReason('') }}
                                className="px-4 py-2 text-sm text-slate-400 hover:text-white"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Baseline Visualization */}
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-500" />
            Baseline Statistical Overview
          </h2>

          {isLoadingBaselines ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-20 bg-slate-800/30 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : baselines.length === 0 ? (
            <div className="text-center py-12">
              <BarChart3 className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400">No baselines available</p>
              <p className="text-slate-400 text-sm mt-1">Create baselines by saving ML model data</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left py-2.5 px-3 text-slate-400 font-medium">Model</th>
                    <th className="text-left py-2.5 px-3 text-slate-400 font-medium">Type</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">Mean</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">Std Dev</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">P50</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">P95</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">P99</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">Samples</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">Accuracy</th>
                    <th className="text-center py-2.5 px-3 text-slate-400 font-medium">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {baselines.map((baseline, idx) => (
                    <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                      <td className="py-2.5 px-3 font-medium text-white">{baseline.model_id}</td>
                      <td className="py-2.5 px-3">
                        <span className="text-xs px-2 py-0.5 bg-indigo-500/20 text-indigo-400 rounded-full">
                          {baseline.baseline_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                        {baseline.statistics.mean.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                        {baseline.statistics.std_dev.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                        {baseline.statistics.p50.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                        {baseline.statistics.p95.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                        {baseline.statistics.p99.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                        {formatNumber(baseline.statistics.sample_count)}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span className={`font-mono font-medium ${
                          baseline.accuracy >= 0.8 ? 'text-green-400' :
                          baseline.accuracy >= 0.5 ? 'text-yellow-400' :
                          'text-slate-400'
                        }`}>
                          {baseline.accuracy > 0 ? `${(baseline.accuracy * 100).toFixed(1)}%` : '--'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        {baseline.is_active ? (
                          <CheckCircle className="w-4 h-4 text-green-500 mx-auto" />
                        ) : (
                          <XCircle className="w-4 h-4 text-slate-300 mx-auto" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Detection Bands */}
        {baselines.length > 0 && (
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-green-500" />
              Anomaly Detection Bands
            </h2>
            <p className="text-sm text-slate-400 mb-4">
              These bands define the boundaries for normal, warning, and critical anomaly detection thresholds.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {baselines.map((baseline, idx) => (
                <div key={idx} className="border border-white/5 rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-white">{baseline.model_id}</span>
                    <span className="text-xs px-2 py-0.5 bg-indigo-500/20 text-indigo-400 rounded-full">
                      {baseline.baseline_type}
                    </span>
                  </div>

                  {/* Band Visualization */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between p-2 bg-green-500/10 border border-green-500/30 rounded">
                      <span className="text-xs font-medium text-green-400">Normal</span>
                      <span className="text-xs font-mono text-green-400">
                        {baseline.bands.normal.lower.toFixed(2)} &ndash; {baseline.bands.normal.upper.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-yellow-500/10 border border-yellow-500/30 rounded">
                      <span className="text-xs font-medium text-yellow-400">Warning</span>
                      <span className="text-xs font-mono text-yellow-400">
                        {baseline.bands.warning.lower.toFixed(2)} &ndash; {baseline.bands.warning.upper.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-red-500/10 border border-red-500/30 rounded">
                      <span className="text-xs font-medium text-red-400">Critical</span>
                      <span className="text-xs font-mono text-red-400">
                        {baseline.bands.critical.lower.toFixed(2)} &ndash; {baseline.bands.critical.upper.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Baseline Inventory */}
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Database className="w-5 h-5 text-slate-400" />
            Baseline Inventory
          </h2>

          {isLoadingBaselineList ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-14 bg-slate-800/30 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : baselineList.length === 0 ? (
            <div className="text-center py-12">
              <Database className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400">No baselines saved yet</p>
              <p className="text-slate-400 text-sm mt-1">Use the API to save ML baselines for anomaly detection</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left py-2.5 px-3 text-slate-400 font-medium">Model ID</th>
                    <th className="text-left py-2.5 px-3 text-slate-400 font-medium">Service</th>
                    <th className="text-left py-2.5 px-3 text-slate-400 font-medium">Type</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">Samples</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">Accuracy</th>
                    <th className="text-right py-2.5 px-3 text-slate-400 font-medium">Last Trained</th>
                  </tr>
                </thead>
                <tbody>
                  {baselineList.map((item, idx) => (
                    <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                      <td className="py-2.5 px-3 font-medium text-white font-mono text-xs">
                        {item.model_id}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">{item.service_name || '--'}</td>
                      <td className="py-2.5 px-3">
                        <span className="text-xs px-2 py-0.5 bg-slate-800/30 text-slate-400 rounded-full">
                          {item.baseline_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                        {item.sample_count != null ? formatNumber(item.sample_count) : '--'}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span className={`font-mono font-medium ${
                          (item.accuracy_score ?? 0) >= 0.8 ? 'text-green-400' :
                          (item.accuracy_score ?? 0) >= 0.5 ? 'text-yellow-400' :
                          'text-slate-400'
                        }`}>
                          {item.accuracy_score != null ? `${(item.accuracy_score * 100).toFixed(1)}%` : '--'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-400 text-xs">
                        {item.last_trained
                          ? new Date(item.last_trained).toLocaleString()
                          : 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
