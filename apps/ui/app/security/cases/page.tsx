'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Briefcase, Loader2, Plus, RefreshCw, Search } from 'lucide-react'
import { bulkCases, Case, caseMetrics, CaseMetrics, createCase, listCases, Severity } from '@/lib/api/cases'
import { formatMinutes, needsReason, statusLabel } from '@/lib/caseFormat'

const VIEWS: Record<string, string[] | undefined> = {
  open: ['new', 'investigating', 'contained'],
  closed: ['resolved', 'false_positive'],
  all: undefined,
}

const SEVERITY_STYLE: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-300 border-red-500/40',
  high: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  medium: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  low: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
}

function ago(iso: string | null) {
  if (!iso) return '—'
  const minutes = (Date.now() - new Date(iso).getTime()) / 60000
  return `${formatMinutes(Math.max(minutes, 0))} ago`
}

function Overview({ metrics }: { metrics: CaseMetrics | null }) {
  if (!metrics) return null
  const urgent = (['critical', 'high'] as Severity[])
  const mtta = urgent.map(s => metrics.by_severity[s]?.mtta_minutes.median).find(v => v !== null && v !== undefined)
  const mttr = urgent.map(s => metrics.by_severity[s]?.mttr_minutes.median).find(v => v !== null && v !== undefined)
  const breaches = Object.values(metrics.sla_breaches.acknowledge).reduce((a, b) => a + b, 0)
    + Object.values(metrics.sla_breaches.resolve).reduce((a, b) => a + b, 0)
  const cards = [
    { label: 'Open cases', value: String(metrics.open_total) },
    { label: 'Median time to acknowledge (critical/high)', value: formatMinutes(mtta) },
    { label: 'Median time to resolve (critical/high)', value: formatMinutes(mttr) },
    { label: 'SLA breaches', value: String(breaches) },
    { label: 'Alerts per case', value: metrics.alerts_per_case.toFixed(1) },
  ]
  return (
    <div data-testid="case-overview" className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {cards.map(card => (
        <div key={card.label} className="p-4 rounded-lg border border-white/10 bg-slate-800/50">
          <div className="text-2xl font-semibold text-white">{card.value}</div>
          <div className="text-xs text-slate-400 mt-1">{card.label}</div>
        </div>
      ))}
    </div>
  )
}

export default function CasesPage() {
  const router = useRouter()
  const [view, setView] = useState<keyof typeof VIEWS>('open')
  const [query, setQuery] = useState('')
  const [cases, setCases] = useState<Case[]>([])
  const [total, setTotal] = useState(0)
  const [metrics, setMetrics] = useState<CaseMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [newTitle, setNewTitle] = useState('')
  const [newSeverity, setNewSeverity] = useState<Severity>('medium')
  const [showNew, setShowNew] = useState(false)
  const [bulkAssignee, setBulkAssignee] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [page, overview] = await Promise.all([
        listCases({ status: VIEWS[view], q: query || undefined, limit: 200 }),
        caseMetrics(30),
      ])
      setCases(page.cases)
      setTotal(page.total)
      setMetrics(overview)
    } catch (e: any) {
      setError(e?.message || 'Failed to load cases')
    } finally {
      setIsLoading(false)
    }
  }, [view, query])

  useEffect(() => {
    const timer = setTimeout(load, query ? 300 : 0)
    return () => clearTimeout(timer)
  }, [load, query])

  const create = async () => {
    if (!newTitle.trim()) return
    setBusy(true)
    try {
      const created = await createCase({ title: newTitle.trim(), severity: newSeverity })
      router.push(`/security/cases/${created.id}`)
    } catch (e: any) {
      setError(e?.message || 'Failed to create the case')
      setBusy(false)
    }
  }

  const bulk = async (body: Parameters<typeof bulkCases>[0]) => {
    setBusy(true)
    setError(null)
    try {
      const result = await bulkCases(body)
      const failed = Object.entries(result?.errors || {})
      if (failed.length) setError(failed.map(([id, reason]) => `${id.slice(0, 8)}: ${reason}`).join('; '))
      setSelected(new Set())
      await load()
    } catch (e: any) {
      setError(e?.message || 'Bulk update failed')
    } finally {
      setBusy(false)
    }
  }

  const bulkStatus = (status: string) => {
    const reason = needsReason(status) ? window.prompt(`Reason for closing ${selected.size} case(s) as ${statusLabel(status)}`) : ''
    if (needsReason(status) && !reason) return
    bulk({ case_ids: Array.from(selected), action: 'set_status', status, reason: reason || '' })
  }

  const toggle = (id: string) => {
    const next = new Set(selected)
    next.has(id) ? next.delete(id) : next.add(id)
    setSelected(next)
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Briefcase className="w-6 h-6 text-blue-400" /> Cases
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Investigations built from alerts. Alerts for the same source, host or user within 24 hours join one case.
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={load} className="flex items-center gap-2 px-3 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5">
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} /> Refresh
            </button>
            <button data-testid="new-case" onClick={() => setShowNew(!showNew)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium">
              <Plus className="w-4 h-4" /> New case
            </button>
          </div>
        </div>

        {showNew && (
          <div className="flex gap-2 p-4 rounded-lg border border-white/10 bg-slate-800/50">
            <input data-testid="new-case-title" value={newTitle} onChange={e => setNewTitle(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && create()} placeholder="Case title"
              className="flex-1 px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white" />
            <select value={newSeverity} onChange={e => setNewSeverity(e.target.value as Severity)}
              className="px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white">
              {['low', 'medium', 'high', 'critical'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button data-testid="new-case-create" onClick={create} disabled={busy || !newTitle.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50">Create</button>
          </div>
        )}

        <Overview metrics={metrics} />

        {error && (
          <div role="alert" data-testid="cases-error" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex rounded-lg border border-white/10 overflow-hidden">
            {Object.keys(VIEWS).map(name => (
              <button key={name} data-testid={`cases-view-${name}`} onClick={() => setView(name as keyof typeof VIEWS)}
                className={`px-4 py-2 text-sm capitalize ${view === name ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-white/5'}`}>
                {name}
              </button>
            ))}
          </div>
          <div className="relative flex-1 min-w-[240px]">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input data-testid="cases-search" value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Search case titles (rule, source IP, host...)"
              className="w-full pl-9 pr-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white" />
          </div>
          {selected.size > 0 && (
            <div data-testid="cases-bulk" className="flex items-center gap-2 text-sm">
              <span className="text-slate-400">{selected.size} selected</span>
              <input value={bulkAssignee} onChange={e => setBulkAssignee(e.target.value)} placeholder="Assignee"
                className="px-2 py-1.5 bg-slate-900 border border-white/10 rounded text-white w-40" />
              <button disabled={busy || !bulkAssignee.trim()}
                onClick={() => bulk({ case_ids: Array.from(selected), action: 'assign', assignee: bulkAssignee.trim() })}
                className="px-3 py-1.5 border border-white/10 rounded text-slate-200 hover:bg-white/5 disabled:opacity-50">Assign</button>
              <select defaultValue="" onChange={e => { if (e.target.value) bulkStatus(e.target.value); e.target.value = '' }}
                className="px-2 py-1.5 bg-slate-900 border border-white/10 rounded text-white">
                <option value="">Set status…</option>
                {['investigating', 'contained', 'resolved', 'false_positive'].map(s => <option key={s} value={s}>{statusLabel(s)}</option>)}
              </select>
            </div>
          )}
        </div>

        <div className="rounded-lg border border-white/10 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-800/80 text-slate-400 text-xs uppercase">
              <tr>
                <th className="w-10 p-3" />
                <th className="p-3 text-left">Severity</th>
                <th className="p-3 text-left">Case</th>
                <th className="p-3 text-left">Status</th>
                <th className="p-3 text-left">Assignee</th>
                <th className="p-3 text-right">Alerts</th>
                <th className="p-3 text-right">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {isLoading && cases.length === 0 && (
                <tr><td colSpan={7} className="p-8 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></td></tr>
              )}
              {!isLoading && cases.length === 0 && (
                <tr><td colSpan={7} className="p-8 text-center text-slate-400" data-testid="cases-empty">No cases.</td></tr>
              )}
              {cases.map(c => (
                <tr key={c.id} data-testid="case-row" className="hover:bg-white/5">
                  <td className="p-3 text-center">
                    <input type="checkbox" aria-label={`Select ${c.title}`} checked={selected.has(c.id)} onChange={() => toggle(c.id)} />
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 text-xs rounded border ${SEVERITY_STYLE[c.severity] || ''}`}>{c.severity}</span>
                  </td>
                  <td className="p-3">
                    <Link href={`/security/cases/${c.id}`} className="text-white hover:text-blue-300 font-medium">{c.title}</Link>
                    {c.tags.length > 0 && <div className="text-xs text-slate-500 mt-0.5">{c.tags.join(' · ')}</div>}
                  </td>
                  <td className="p-3 text-slate-300 capitalize" data-testid="case-status">{statusLabel(c.status)}</td>
                  <td className="p-3 text-slate-300">{c.assignee || <span className="text-slate-500">unassigned</span>}</td>
                  <td className="p-3 text-right text-slate-300">{c.alert_ids.length}</td>
                  <td className="p-3 text-right text-slate-400">{ago(c.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="text-xs text-slate-500">{total} case{total === 1 ? '' : 's'}</div>
      </div>
    </DashboardLayout>
  )
}
