'use client'

// Phase 6: turn the current LogforgeQL query into a dashboard panel.

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Loader2, X } from 'lucide-react'
import { apiClient } from '@/lib/api'
import { panelTypeFor, type QueryResultShape } from '@/lib/dashboardPanels'

const TYPES: { value: string; label: string }[] = [
  { value: 'line_chart', label: 'Line chart' },
  { value: 'area_chart', label: 'Area chart' },
  { value: 'bar_chart', label: 'Bar chart' },
  { value: 'pie_chart', label: 'Pie chart' },
  { value: 'metric', label: 'Single value' },
  { value: 'table', label: 'Table' },
]

export default function AddToDashboard({ query, result, onClose }: {
  query: string
  result: QueryResultShape | null
  onClose: () => void
}) {
  const [dashboards, setDashboards] = useState<{ id: string; name: string }[]>([])
  const [dashboardId, setDashboardId] = useState('')
  const [newName, setNewName] = useState('')
  const [name, setName] = useState('')
  const [type, setType] = useState(result ? panelTypeFor(result) : 'table')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<string | null>(null)

  useEffect(() => {
    apiClient.get('/v1/dashboards')
      .then((response: any) => {
        const data = response?.data?.dashboards || response?.data || []
        const list = Array.isArray(data) ? data.map((d: any) => ({ id: d.id || d.dashboard_id, name: d.name })) : []
        setDashboards(list.filter((d: any) => d.id))
        setDashboardId(list[0]?.id || 'new')
      })
      .catch(() => setDashboardId('new'))
  }, [])

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      let target = dashboardId
      if (target === 'new') {
        const response: any = await apiClient.post('/v1/dashboards', { name: newName.trim(), widgets: [] })
        target = response?.data?.dashboard_id
      }
      const wide = type !== 'metric'
      await apiClient.post(`/v1/dashboards/${target}/widgets`, {
        name: name.trim(),
        type,
        query_definition: { logql: query },
        position: { x: 0, y: 0 },
        size: { w: wide ? 2 : 1, h: wide ? 2 : 1 },
        refresh_interval: 300,
      })
      setCreated(target)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err?.message || 'Could not add the panel')
    } finally {
      setSaving(false)
    }
  }

  const canSave = name.trim() && query.trim() && (dashboardId !== 'new' || newName.trim()) && !saving

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog"
      aria-label="Add to dashboard">
      <div className="w-[28rem] bg-slate-900 border border-white/10 rounded-2xl shadow-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-white font-semibold">Add to dashboard</h3>
          <button onClick={onClose} aria-label="Close" className="text-slate-400 hover:text-white"><X className="w-4 h-4" /></button>
        </div>
        <pre className="text-xs text-slate-300 bg-slate-800/60 rounded-lg p-2 whitespace-pre-wrap break-all max-h-24 overflow-auto">{query}</pre>
        {created ? (
          <div className="space-y-3">
            <p className="text-sm text-emerald-400">Panel added.</p>
            <Link data-testid="open-dashboard" href={`/dashboards/${created}`} className="text-sm text-blue-400 hover:text-blue-300">
              Open the dashboard
            </Link>
          </div>
        ) : (
          <>
            <label className="block text-xs text-slate-400">
              Dashboard
              <select data-testid="panel-dashboard" value={dashboardId} onChange={e => setDashboardId(e.target.value)}
                className="mt-1 w-full px-2 py-1.5 bg-slate-800 border border-white/10 rounded-md text-sm text-white">
                {dashboards.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                <option value="new">New dashboard…</option>
              </select>
            </label>
            {dashboardId === 'new' && (
              <input data-testid="panel-new-dashboard" placeholder="New dashboard name" value={newName}
                onChange={e => setNewName(e.target.value)}
                className="w-full px-2 py-1.5 bg-slate-800 border border-white/10 rounded-md text-sm text-white" />
            )}
            <label className="block text-xs text-slate-400">
              Panel title
              <input data-testid="panel-name" value={name} onChange={e => setName(e.target.value)}
                className="mt-1 w-full px-2 py-1.5 bg-slate-800 border border-white/10 rounded-md text-sm text-white" />
            </label>
            <label className="block text-xs text-slate-400">
              Visualization
              <select data-testid="panel-type" value={type} onChange={e => setType(e.target.value)}
                className="mt-1 w-full px-2 py-1.5 bg-slate-800 border border-white/10 rounded-md text-sm text-white">
                {TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
            {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
            <div className="flex justify-end gap-2">
              <button onClick={onClose} className="px-3 py-1.5 text-sm text-slate-400 hover:bg-white/5 rounded">Cancel</button>
              <button data-testid="panel-save" onClick={save} disabled={!canSave}
                className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add panel'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
