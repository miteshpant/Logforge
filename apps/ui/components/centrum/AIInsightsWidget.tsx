'use client'

import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Brain,
  Lightbulb,
  TrendingUp,
  AlertTriangle,
  Zap,
  ChevronRight,
  RefreshCw,
  Sparkles
} from 'lucide-react'

interface Insight {
  id: string
  type: 'optimization' | 'anomaly' | 'prediction' | 'correlation' | 'recommendation'
  severity: 'info' | 'warning' | 'critical'
  title: string
  description: string
  confidence: number
  created_at: string
  metadata?: Record<string, unknown>
}

interface AIInsightsWidgetProps {
  className?: string
}

const INSIGHT_ICONS: Record<string, React.ReactNode> = {
  optimization: <Zap className="w-4 h-4" />,
  anomaly: <AlertTriangle className="w-4 h-4" />,
  prediction: <TrendingUp className="w-4 h-4" />,
  correlation: <Sparkles className="w-4 h-4" />,
  recommendation: <Lightbulb className="w-4 h-4" />,
}

const INSIGHT_COLORS: Record<string, string> = {
  info: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  warning: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  critical: 'text-red-400 bg-red-500/10 border-red-500/20',
}

export default function AIInsightsWidget({ className }: AIInsightsWidgetProps) {
  const { getApiTimeRange, currentTimeRange } = useTimeRange()
  const [insights, setInsights] = useState<Insight[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadInsights = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get('/v1/ai/insights', {
        start_time,
        end_time,
        limit: 5
      })

      const data = response?.data || response
      if (Array.isArray(data)) {
        setInsights(data)
      } else if (data?.insights) {
        // Backend returns { insights: { critical: [...], warnings: [...], informational: [...] } }
        if (Array.isArray(data.insights)) {
          setInsights(data.insights)
        } else if (typeof data.insights === 'object') {
          const flattened: Insight[] = []
          const insightsObj = data.insights as Record<string, any[]>
          const severityMap: Record<string, string> = {
            critical: 'critical',
            warnings: 'warning',
            informational: 'info'
          }
          for (const [category, items] of Object.entries(insightsObj)) {
            if (Array.isArray(items)) {
              items.forEach((item: any, idx: number) => {
                flattened.push({
                  id: item.id || `${category}-${idx}`,
                  type: item.type || 'recommendation',
                  severity: (severityMap[category] || item.severity || 'info') as Insight['severity'],
                  title: item.title || `${category} insight`,
                  description: item.description || '',
                  confidence: item.confidence || 0.7,
                  created_at: item.created_at || new Date().toISOString(),
                  metadata: item
                })
              })
            }
          }
          setInsights(flattened.slice(0, 5))
        } else {
          setInsights([])
        }
      } else {
        setInsights([])
      }
    } catch (err: any) {
      if (err.name !== 'AbortError' && err.name !== 'CanceledError') {
        console.error('Failed to load AI insights:', err)
        setError('Failed to load insights')
      }
      setInsights([])
    } finally {
      setIsLoading(false)
    }
  }, [getApiTimeRange])

  useEffect(() => {
    loadInsights()
  }, [loadInsights, currentTimeRange.value])

  const formatTimeAgo = (ts: string) => {
    const diff = Date.now() - new Date(ts).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return 'just now'
  }

  return (
    <div className={`relative overflow-hidden rounded-2xl p-5 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 ${className || ''}`}>
      {/* Background glow */}
      <div className="absolute top-0 right-0 w-48 h-48 -translate-y-16 translate-x-8 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-40 h-40 translate-y-12 -translate-x-6 bg-blue-500/8 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="relative z-10 flex items-start justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center shadow-md shadow-purple-500/30">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white tracking-tight">AI Insights</h2>
            <p className="text-xs text-slate-400 font-medium mt-0.5">
              Powered by ML analysis
            </p>
          </div>
        </div>

        <button
          onClick={loadInsights}
          disabled={isLoading}
          className="p-1.5 rounded-lg hover:bg-white/5 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 text-slate-400 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Content */}
      <div className="relative z-10 space-y-2">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-white/5 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-8 text-slate-400">
            <Brain className="w-8 h-8 mb-2 opacity-40" />
            <p className="text-sm">{error}</p>
          </div>
        ) : insights.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-slate-400">
            <Lightbulb className="w-8 h-8 mb-2 opacity-40" />
            <p className="text-sm">No active insights</p>
            <p className="text-xs text-slate-500 mt-1">AI is analyzing your data</p>
          </div>
        ) : (
          insights.map((insight) => (
            <div
              key={insight.id}
              className={`p-3 rounded-lg border cursor-pointer transition-all hover:scale-[1.01] ${INSIGHT_COLORS[insight.severity] || INSIGHT_COLORS.info}`}
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex-shrink-0">
                  {INSIGHT_ICONS[insight.type] || INSIGHT_ICONS.recommendation}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-white truncate">{insight.title}</p>
                    {insight.confidence > 0.8 && (
                      <span className="text-[9px] font-bold text-purple-400 bg-purple-500/15 px-1.5 py-0.5 rounded-full">
                        HIGH CONF
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{insight.description}</p>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className="text-[10px] text-slate-500 capitalize">{insight.type}</span>
                    {insight.created_at && (
                      <span className="text-[10px] text-slate-500">{formatTimeAgo(insight.created_at)}</span>
                    )}
                    <span className="text-[10px] text-slate-500">
                      {Math.round(insight.confidence * 100)}% confidence
                    </span>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-500 flex-shrink-0 mt-1" />
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="relative z-10 mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/3">
          <Sparkles className="w-3 h-3 text-purple-400" />
          <span className="text-[10px] text-slate-400 font-medium">
            {insights.length} active insight{insights.length !== 1 ? 's' : ''}
          </span>
        </div>
        <a
          href="/anomaly-detection"
          className="text-[10px] text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1"
        >
          View All <ChevronRight className="w-3 h-3" />
        </a>
      </div>
    </div>
  )
}
