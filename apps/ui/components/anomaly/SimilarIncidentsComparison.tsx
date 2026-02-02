'use client'

import { useState } from 'react'

interface SimilarIncident {
  incident_id: string
  occurred_at: string
  similarity_score: number
  resolution: string
  time_to_resolve: string
}

interface SimilarIncidentsComparisonProps {
  incidents: SimilarIncident[]
  currentAnomalyId: string
}

export default function SimilarIncidentsComparison({
  incidents,
  currentAnomalyId
}: SimilarIncidentsComparisonProps) {
  const [expandedIncident, setExpandedIncident] = useState<string | null>(null)

  if (!incidents || incidents.length === 0) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 text-center">
        <div className="text-slate-500 mb-2">🔍</div>
        <p className="text-slate-500">No similar incidents found in history</p>
        <p className="text-xs text-slate-600 mt-1">This appears to be a unique anomaly pattern</p>
      </div>
    )
  }

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

      if (diffDays === 0) return 'Today'
      if (diffDays === 1) return 'Yesterday'
      if (diffDays < 7) return `${diffDays} days ago`
      if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
      if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`
      return `${Math.floor(diffDays / 365)} years ago`
    } catch {
      return dateStr
    }
  }

  const getSimilarityColor = (score: number) => {
    if (score >= 0.9) return 'bg-red-500/20 text-red-400 border-red-500/30'
    if (score >= 0.7) return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
    if (score >= 0.5) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
    return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
  }

  const getSimilarityBarColor = (score: number) => {
    if (score >= 0.9) return 'bg-red-500'
    if (score >= 0.7) return 'bg-orange-500'
    if (score >= 0.5) return 'bg-yellow-500'
    return 'bg-blue-500'
  }

  const parseTimeToResolve = (timeStr: string) => {
    // Parse strings like "45m", "2h 30m", "1d 4h"
    const parts = timeStr.split(' ')
    let totalMinutes = 0

    parts.forEach(part => {
      if (part.includes('d')) totalMinutes += parseInt(part) * 24 * 60
      if (part.includes('h')) totalMinutes += parseInt(part) * 60
      if (part.includes('m')) totalMinutes += parseInt(part)
    })

    return totalMinutes
  }

  const averageResolutionTime = incidents.length > 0
    ? incidents.reduce((sum, inc) => sum + parseTimeToResolve(inc.time_to_resolve), 0) / incidents.length
    : 0

  const formatResolutionTime = (minutes: number) => {
    if (minutes < 60) return `${Math.round(minutes)}m`
    if (minutes < 1440) return `${Math.round(minutes / 60)}h ${Math.round(minutes % 60)}m`
    return `${Math.round(minutes / 1440)}d ${Math.round((minutes % 1440) / 60)}h`
  }

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-200">Similar Historical Incidents</h3>
          <p className="text-sm text-slate-500 mt-1">
            Found {incidents.length} incident{incidents.length !== 1 ? 's' : ''} with similar patterns
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">Avg. Resolution Time</p>
          <p className="text-lg font-semibold text-blue-400">{formatResolutionTime(averageResolutionTime)}</p>
        </div>
      </div>

      {/* Incidents List */}
      <div className="space-y-3">
        {incidents
          .sort((a, b) => b.similarity_score - a.similarity_score)
          .map((incident, index) => (
            <div
              key={incident.incident_id}
              className={`bg-slate-700/50 rounded-lg border transition-all ${
                expandedIncident === incident.incident_id
                  ? 'border-blue-500/50 shadow-lg shadow-blue-500/10'
                  : 'border-slate-600 hover:border-slate-500'
              }`}
            >
              {/* Incident Summary */}
              <button
                onClick={() => setExpandedIncident(
                  expandedIncident === incident.incident_id ? null : incident.incident_id
                )}
                className="w-full p-4 text-left"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 flex-1">
                    {/* Rank Badge */}
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                      index === 0 ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
                      index === 1 ? 'bg-slate-400/20 text-slate-400 border border-slate-400/30' :
                      index === 2 ? 'bg-orange-600/20 text-orange-400 border border-orange-600/30' :
                      'bg-slate-600/20 text-slate-500 border border-slate-600/30'
                    }`}>
                      #{index + 1}
                    </div>

                    {/* Incident Info */}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-mono text-slate-400">
                          {incident.incident_id.slice(0, 8)}...
                        </span>
                        <span className="text-xs text-slate-600">•</span>
                        <span className="text-xs text-slate-500">{formatDate(incident.occurred_at)}</span>
                      </div>

                      {/* Similarity Bar */}
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-slate-600 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${getSimilarityBarColor(incident.similarity_score)} transition-all duration-500`}
                            style={{ width: `${incident.similarity_score * 100}%` }}
                          />
                        </div>
                        <span className={`text-xs font-medium px-2 py-0.5 rounded border ${getSimilarityColor(incident.similarity_score)}`}>
                          {(incident.similarity_score * 100).toFixed(0)}% match
                        </span>
                      </div>
                    </div>

                    {/* Resolution Time Badge */}
                    <div className="text-right">
                      <p className="text-xs text-slate-500">Resolved in</p>
                      <p className="text-sm font-semibold text-green-400">{incident.time_to_resolve}</p>
                    </div>

                    {/* Expand Icon */}
                    <div className="text-slate-500">
                      {expandedIncident === incident.incident_id ? '▼' : '▶'}
                    </div>
                  </div>
                </div>
              </button>

              {/* Expanded Details */}
              {expandedIncident === incident.incident_id && (
                <div className="border-t border-slate-600 p-4 bg-slate-800/50">
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Resolution Strategy:</p>
                      <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                        <p className="text-sm text-green-300">{incident.resolution}</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="bg-slate-700/50 rounded p-2">
                        <p className="text-slate-500">Incident ID</p>
                        <p className="text-slate-300 font-mono mt-1">{incident.incident_id}</p>
                      </div>
                      <div className="bg-slate-700/50 rounded p-2">
                        <p className="text-slate-500">Occurred</p>
                        <p className="text-slate-300 mt-1">{new Date(incident.occurred_at).toLocaleString()}</p>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-2 rounded transition-colors">
                        Apply This Resolution
                      </button>
                      <button className="flex-1 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs px-3 py-2 rounded transition-colors">
                        View Full Details
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
      </div>

      {/* Best Match Highlight */}
      {incidents.length > 0 && incidents[0].similarity_score >= 0.8 && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <span className="text-2xl">💡</span>
            <div>
              <p className="text-sm font-semibold text-blue-400 mb-1">High Similarity Detected</p>
              <p className="text-xs text-blue-300">
                The most similar incident was resolved in <strong>{incidents[0].time_to_resolve}</strong> using:
                "{incidents[0].resolution}". Consider applying this resolution strategy.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Statistics */}
      <div className="border-t border-slate-700 pt-4">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs text-slate-500">Best Match</p>
            <p className="text-lg font-bold text-blue-400">
              {incidents.length > 0 ? `${(incidents[0].similarity_score * 100).toFixed(0)}%` : 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Avg. Similarity</p>
            <p className="text-lg font-bold text-slate-300">
              {incidents.length > 0
                ? `${((incidents.reduce((sum, inc) => sum + inc.similarity_score, 0) / incidents.length) * 100).toFixed(0)}%`
                : 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Total Found</p>
            <p className="text-lg font-bold text-slate-300">{incidents.length}</p>
          </div>
        </div>
      </div>
    </div>
  )
}