'use client'

import { useCallback, useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Sparkles } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'

interface MetricName {
  name: string
  points: number
  last_seen: string
  standard: boolean
}

interface Point {
  timestamp: string
  value: number
}

/**
 * Metrics the tenant sends under non-standard names (e.g. "cpu.utilization").
 *
 * They are stored and queryable, but the explorer above only charts the
 * standard names from metric_name_mappings.yml, so they used to be invisible.
 * Listed from GET /v1/observability/metrics/names; click one to chart it.
 */
export default function CustomMetricsPanel({ aggregation = 'avg' }: { aggregation?: string }) {
  const { getApiTimeRange, refreshTrigger } = useTimeRange()
  const [names, setNames] = useState<MetricName[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [points, setPoints] = useState<Point[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    apiClient.get<{ metrics: MetricName[] }>('/v1/observability/metrics/names').then(res => {
      const custom = (res.success && res.data?.metrics ? res.data.metrics : []).filter(m => !m.standard)
      setNames(custom)
      setSelected(prev => prev ?? custom[0]?.name ?? null)
    })
  }, [refreshTrigger])

  const load = useCallback(async (metric: string) => {
    setLoading(true)
    const { start_time, end_time } = getApiTimeRange()
    const res = await apiClient.post('/v1/observability/metrics/query', {
      metric_name: metric, start_time, end_time, aggregation, granularity: '15m',
    })
    setPoints(res.success ? (res.data?.metrics?.[metric] || []) : [])
    setLoading(false)
  }, [getApiTimeRange, aggregation])

  useEffect(() => {
    if (selected) load(selected)
  }, [selected, load, refreshTrigger])

  if (names.length === 0) return null

  return (
    <div className="rounded-xl p-6 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5" data-testid="custom-metrics">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="w-4 h-4 text-amber-400" />
        <h2 className="text-lg font-semibold text-white">Custom Metrics</h2>
      </div>
      <p className="text-xs text-slate-400 mb-4">
        Metrics sent under names that aren&apos;t standard Logforge metrics. Rename them (see
        /v1/observability/metrics/standard) to chart them in the sections above.
      </p>
      <div className="flex flex-wrap gap-2 mb-4">
        {names.map(m => (
          <button
            key={m.name}
            onClick={() => setSelected(m.name)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono border transition-colors ${
              selected === m.name
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                : 'bg-slate-800/50 text-slate-300 border-white/5 hover:border-amber-500/30'
            }`}
          >
            {m.name} <span className="text-slate-500">· {m.points}</span>
          </button>
        ))}
      </div>
      <div className="h-56">
        {loading ? (
          <div className="h-full flex items-center justify-center text-sm text-slate-400">Loading…</div>
        ) : points.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-slate-400">No data in the selected time range</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points.map(p => ({ t: new Date(p.timestamp + 'Z').toLocaleTimeString(), v: p.value }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="t" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)' }} />
              <Line type="monotone" dataKey="v" name={selected ?? ''} stroke="#f59e0b" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
