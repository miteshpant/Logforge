'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { Loader2, Search, Users } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { entityRisk, listEntities, type EntityRisk, type EntitySummary } from '@/lib/api/entities'
import { entityHref, entityLabel, riskTone } from '@/lib/entityFormat'

const TYPES = ['all', 'user', 'host', 'ip', 'service', 'cloud_account'] as const
const TONE: Record<string, string> = {
  high: 'bg-red-500/20 text-red-300 border-red-500/30', medium: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  low: 'bg-slate-500/20 text-slate-300 border-white/10', none: 'bg-slate-800 text-slate-500 border-white/5',
}

/** Entities (Phase 11): who and what is riskiest now, and every entity seen. */
export default function EntitiesPage() {
  const [type, setType] = useState<(typeof TYPES)[number]>('all')
  const [risk, setRisk] = useState<EntityRisk[] | null>(null)
  const [q, setQ] = useState('')
  const [found, setFound] = useState<EntitySummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const out = await entityRisk({ type: type === 'all' ? undefined : type, limit: 50 })
      setRisk(out.entities)
    } catch (e: any) {
      setError(e?.message || 'Failed to load entity risk')
      setRisk([])
    }
  }, [type])

  useEffect(() => { load() }, [load])

  const search = async () => {
    try {
      const out = await listEntities({ type: type === 'all' ? undefined : type, q: q.trim(), limit: 50 })
      setFound(out.entities)
    } catch (e: any) {
      setError(e?.message || 'Search failed')
    }
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Users className="w-6 h-6" /> Entities</h1>
          <p className="text-slate-400 mt-1">Users, hosts, addresses, services and cloud accounts, ranked by risk over the last 14 days.</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {TYPES.map(t => (
            <button key={t} onClick={() => setType(t)} data-testid={`entity-type-${t}`}
              className={`px-3 py-1.5 rounded-lg text-sm ${type === t ? 'bg-blue-600 text-white' : 'bg-slate-800/40 text-slate-300 hover:bg-white/5'}`}>
              {t === 'all' ? 'All' : entityLabel(t)}
            </button>
          ))}
          <form className="ml-auto flex items-center gap-2" onSubmit={e => { e.preventDefault(); search() }}>
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Find an entity" data-testid="entity-search"
              className="px-3 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-sm text-white" />
            <button type="submit" className="p-2 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5"><Search className="w-4 h-4" /></button>
          </form>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}

        {found && (
          <section className="space-y-2" data-testid="entity-found">
            <h2 className="text-sm font-semibold text-white">Found ({found.length})</h2>
            <ul className="grid gap-1 md:grid-cols-2">
              {found.map(e => (
                <li key={`${e.entity_type}:${e.value}`} className="text-sm">
                  <Link href={entityHref(e.entity_type, e.value)} className="text-blue-300 hover:underline">
                    {entityLabel(e.entity_type)} {e.value}</Link>
                  <span className="text-slate-500"> · {e.events.toLocaleString()} events · last seen {new Date(e.last_seen).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="rounded-xl border border-white/10 overflow-hidden">
          <table className="w-full text-sm" data-testid="entity-risk-table">
            <thead className="bg-slate-900/60 text-slate-400 text-xs uppercase">
              <tr><th className="text-left p-3 w-20">Risk</th><th className="text-left p-3">Entity</th><th className="text-left p-3">Why</th><th className="text-right p-3 w-24">Alerts</th></tr>
            </thead>
            <tbody>
              {risk === null && (
                <tr><td colSpan={4} className="p-6 text-center text-slate-400"><Loader2 className="w-4 h-4 animate-spin inline" /></td></tr>
              )}
              {risk?.length === 0 && (
                <tr><td colSpan={4} className="p-6 text-center text-slate-400">No entity has risk in the last 14 days.</td></tr>
              )}
              {risk?.map(r => (
                <tr key={`${r.entity_type}:${r.value}`} className="border-t border-white/5" data-testid="entity-risk-row">
                  <td className="p-3"><span className={`px-2 py-0.5 rounded border text-xs font-semibold ${TONE[riskTone(r.score)]}`}>{r.score}</span></td>
                  <td className="p-3">
                    <Link href={entityHref(r.entity_type, r.value)} className="text-blue-300 hover:underline">{r.value}</Link>
                    <span className="block text-xs text-slate-500">{entityLabel(r.entity_type)}</span>
                  </td>
                  <td className="p-3 text-slate-300 text-xs">{r.factors.slice(0, 2).map(f => f.label).join(' · ')}</td>
                  <td className="p-3 text-right text-slate-300">{r.alerts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </DashboardLayout>
  )
}
