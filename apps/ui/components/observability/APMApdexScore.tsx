'use client'

import { TrendingUp, Award } from 'lucide-react'
import type { ServicePerformance } from '@/app/observability/apm/page'

interface APMApdexScoreProps {
  services: ServicePerformance[]
  isLoading: boolean
}

export default function APMApdexScore({ services, isLoading }: APMApdexScoreProps) {
  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 animate-pulse">
        <div className="h-6 bg-slate-700 rounded w-1/4 mb-4"></div>
        <div className="h-24 bg-slate-700 rounded"></div>
      </div>
    )
  }

  if (services.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
        <div className="text-center text-slate-400 py-8">
          <Award className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No Apdex data available</p>
        </div>
      </div>
    )
  }

  // Calculate overall Apdex score
  const overallApdex = services.reduce((sum, s) => sum + s.apdex_score, 0) / services.length

  const getApdexColor = (score: number) => {
    if (score >= 0.94) return 'text-emerald-400'
    if (score >= 0.85) return 'text-blue-400'
    if (score >= 0.70) return 'text-yellow-400'
    if (score >= 0.50) return 'text-orange-400'
    return 'text-red-400'
  }

  const getApdexBgColor = (score: number) => {
    if (score >= 0.94) return 'bg-emerald-500'
    if (score >= 0.85) return 'bg-blue-500'
    if (score >= 0.70) return 'bg-yellow-500'
    if (score >= 0.50) return 'bg-orange-500'
    return 'bg-red-500'
  }

  const getApdexRating = (score: number) => {
    if (score >= 0.94) return 'Excellent'
    if (score >= 0.85) return 'Good'
    if (score >= 0.70) return 'Fair'
    if (score >= 0.50) return 'Poor'
    return 'Unacceptable'
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-white">Apdex Score</h2>
            <p className="text-sm text-slate-400 mt-1">Application Performance Index</p>
          </div>
          <div className="text-right">
            <div className={`text-4xl font-bold ${getApdexColor(overallApdex)}`}>
              {overallApdex.toFixed(2)}
            </div>
            <div className="text-sm text-slate-400 mt-1">
              {getApdexRating(overallApdex)}
            </div>
          </div>
        </div>

        {/* Apdex Gauge (simplified visual) */}
        <div className="mb-6">
          <div className="h-3 bg-slate-700/30 rounded-full overflow-hidden">
            <div
              className={`h-full ${getApdexBgColor(overallApdex)} transition-all duration-500`}
              style={{ width: `${overallApdex * 100}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-slate-500 mt-2">
            <span>0.0</span>
            <span>0.5</span>
            <span>1.0</span>
          </div>
        </div>

        {/* Service Breakdown */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            By Service
          </h3>

          {services
            .sort((a, b) => b.apdex_score - a.apdex_score)
            .map(service => (
              <div
                key={service.service_name}
                className="flex items-center justify-between py-2 px-3 bg-slate-800/50 rounded-lg hover:bg-slate-700/50 transition-colors"
              >
                <span className="text-sm text-slate-300">{service.service_name}</span>
                <div className="flex items-center gap-3">
                  <div className="w-24 h-2 bg-slate-700/30 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${getApdexBgColor(service.apdex_score)}`}
                      style={{ width: `${service.apdex_score * 100}%` }}
                    />
                  </div>
                  <span className={`text-sm font-mono font-semibold ${getApdexColor(service.apdex_score)} w-12 text-right`}>
                    {service.apdex_score.toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
        </div>

        {/* Legend */}
        <div className="mt-6 pt-4 border-t border-slate-700">
          <div className="grid grid-cols-5 gap-2 text-xs">
            <div className="text-center">
              <div className="w-full h-2 bg-emerald-500 rounded mb-1"></div>
              <span className="text-slate-400">≥0.94</span>
            </div>
            <div className="text-center">
              <div className="w-full h-2 bg-blue-500 rounded mb-1"></div>
              <span className="text-slate-400">≥0.85</span>
            </div>
            <div className="text-center">
              <div className="w-full h-2 bg-yellow-500 rounded mb-1"></div>
              <span className="text-slate-400">≥0.70</span>
            </div>
            <div className="text-center">
              <div className="w-full h-2 bg-orange-500 rounded mb-1"></div>
              <span className="text-slate-400">≥0.50</span>
            </div>
            <div className="text-center">
              <div className="w-full h-2 bg-red-500 rounded mb-1"></div>
              <span className="text-slate-400">&lt;0.50</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
