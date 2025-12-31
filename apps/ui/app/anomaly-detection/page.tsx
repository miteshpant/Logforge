'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { useTimeRange } from '@/contexts/TimeRangeContext'

interface Anomaly {
  id: string
  anomaly_type: string
  severity: string
  detected_at: string
  service?: string
  metrics?: any[]
}

interface AnomalyStats {
  total: number
  critical: number
  liveStream: number
  accuracy: number
}

export default function AnomalyDetectionPage() {
  const { currentTimeRange } = useTimeRange()
  const [anomalies, setAnomalies] = useState<Anomaly[]>([])
  const [stats, setStats] = useState<AnomalyStats>({
    total: 0,
    critical: 0,
    liveStream: 0,
    accuracy: 95
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchAnomalies = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/ai/anomalies/detect/multi-metric', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          metrics: [
            { type: 'cpu_usage', service: 'payment-service', weight: 1.0 },
            { type: 'memory_usage', service: 'payment-service', weight: 0.9 },
            { type: 'error_rate', service: 'payment-service', weight: 0.8 }
          ],
          time_range: currentTimeRange.value,
          correlation_threshold: 0.6,
          algorithms: ['z_score']
        })
      })

      if (!response.ok) {
        throw new Error(`Detection failed: ${response.status}`)
      }

      const data = await response.json()
      const detectedAnomalies = data.anomalies || []

      setAnomalies(detectedAnomalies)

      // Calculate stats
      const criticalCount = detectedAnomalies.filter(
        (a: Anomaly) => a.severity === 'critical'
      ).length

      setStats({
        total: detectedAnomalies.length,
        critical: criticalCount,
        liveStream: 0, // Will be updated when live streaming is implemented
        accuracy: 95 // Default accuracy
      })
    } catch (err: any) {
      setError(err.message || 'Failed to fetch anomalies')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAnomalies()
  }, [currentTimeRange.value])

  return (
    <DashboardLayout>
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <span className="text-4xl">🤖</span>
              Intelligent Anomaly Detection
            </h1>
            <p className="text-slate-400 mt-2">
              AI-powered multi-metric correlation and anomaly detection
            </p>
          </div>

          {/* Refresh Button */}
          <button
            onClick={fetchAnomalies}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded-lg flex items-center gap-2 transition-colors"
          >
            <svg
              className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            {loading ? 'Detecting...' : 'Refresh'}
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 bg-red-900/20 border border-red-800 rounded-lg p-4">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {/* Total Anomalies */}
          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-slate-400 text-sm font-medium">Total Anomalies</h3>
              <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
            </div>
            <p className="text-3xl font-bold text-white">{stats.total}</p>
            <p className="text-xs text-slate-500 mt-1">Detected in time range</p>
          </div>

          {/* Critical Anomalies */}
          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-slate-400 text-sm font-medium">Critical</h3>
              <div className="w-10 h-10 bg-red-500/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
            </div>
            <p className="text-3xl font-bold text-white">{stats.critical}</p>
            <p className="text-xs text-slate-500 mt-1">Require immediate attention</p>
          </div>

          {/* Live Stream */}
          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-slate-400 text-sm font-medium">Live Stream</h3>
              <div className="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              </div>
            </div>
            <p className="text-3xl font-bold text-white">{stats.liveStream}</p>
            <p className="text-xs text-slate-500 mt-1">Real-time monitoring</p>
          </div>

          {/* Detection Accuracy */}
          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-slate-400 text-sm font-medium">Accuracy</h3>
              <div className="w-10 h-10 bg-purple-500/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <p className="text-3xl font-bold text-white">{stats.accuracy}%</p>
            <p className="text-xs text-slate-500 mt-1">ML model confidence</p>
          </div>
        </div>

        {/* Placeholder for next widgets */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-12 text-center">
          <p className="text-slate-300 text-xl mb-2">Ready for next widget</p>
          <p className="text-slate-500 text-sm">
            Recent Anomalies Table will be added next
          </p>
        </div>
      </div>
    </DashboardLayout>
  )
}