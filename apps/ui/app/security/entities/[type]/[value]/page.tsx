'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Activity, AlertTriangle, ArrowLeft, Briefcase, Network, ShieldAlert } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import CopilotPanel from '@/components/ai/CopilotPanel'
import { getEntity, type EntityDetail } from '@/lib/api/entities'
import { runLogQL, type NormalizedLog } from '@/components/query/logsApi'
import { copilotType, entityHref, entityLabel, riskTone } from '@/lib/entityFormat'

const TONE: Record<string, string> = {
  high: 'text-red-300 border-red-500/40 bg-red-500/10', medium: 'text-amber-300 border-amber-500/40 bg-amber-500/10',
  low: 'text-slate-300 border-white/10 bg-slate-800/40', none: 'text-slate-500 border-white/5 bg-slate-800/40',
}

/** One entity (Phase 11): its risk and why, anomalies, events, alerts, cases and related entities. */
export default function EntityPage() {
  const params = useParams()
  const type = decodeURIComponent(String(params?.type || ''))
  const value = decodeURIComponent(String(params?.value || ''))
  const [detail, setDetail] = useState<EntityDetail | null>(null)
  const [events, setEvents] = useState<NormalizedLog[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const out = await getEntity(type, value)
      setDetail(out)
      const end = new Date()
      const start = new Date(end.getTime() - 7 * 86400_000)
      const result = await runLogQL(`${out.query} | sort ts desc | head 25`,
        { start_time: start.toISOString(), end_time: end.toISOString() })
      setEvents(result.logs)
    } catch (e: any) {
      setError(e?.message || 'Failed to load the entity')
    }
  }, [type, value])

  useEffect(() => { if (type && value) load() }, [type, value, load])

  if (error) {
    return <DashboardLayout><div className="p-6"><p className="text-red-400" data-testid="entity-error">{error}</p></div></DashboardLayout>
  }
  if (!detail) {
    return <DashboardLayout><div className="p-6 text-slate-400">Loading…</div></DashboardLayout>
  }
  const { entity, risk } = detail
  const tone = riskTone(risk?.score)
  const copilot = copilotType(type)

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <Link href="/security/entities" className="text-sm text-slate-400 hover:text-white flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" /> All entities
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase text-slate-500">{entityLabel(entity.entity_type)}</p>
            <h1 className="text-2xl font-bold text-white break-all" data-testid="entity-value">{entity.value}</h1>
            <p className="text-sm text-slate-400 mt-1">
              {entity.events.toLocaleString()} events · first seen {new Date(entity.first_seen).toLocaleString()} ·
              last seen {new Date(entity.last_seen).toLocaleString()}
            </p>
          </div>
          <div className={`rounded-xl border px-4 py-3 text-center ${TONE[tone]}`} data-testid="entity-risk">
            <p className="text-3xl font-bold">{risk?.score ?? 0}</p>
            <p className="text-xs">risk{detail.rank ? ` · #${detail.rank} in the tenant` : ''}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2 space-y-6">
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2"><ShieldAlert className="w-4 h-4" /> Why this score</h2>
              {risk && risk.factors.length > 0 ? (
                <ul className="space-y-1" data-testid="entity-factors">
                  {risk.factors.map((f, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm">
                      <span className="w-12 shrink-0 text-right font-mono text-slate-300">+{f.points}</span>
                      <span className="text-xs uppercase w-20 shrink-0 text-slate-500 pt-0.5">{f.kind}</span>
                      <span className="text-slate-200">{f.label}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-slate-400">No alerts, intel hits or anomalies in the last 14 days.</p>}
            </section>

            {detail.anomalies.length > 0 && (
              <section className="space-y-2">
                <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Activity className="w-4 h-4" /> Unusual in the last day</h2>
                <ul className="space-y-1" data-testid="entity-anomalies">
                  {detail.anomalies.map((a, i) => (
                    <li key={i} className="text-sm text-amber-200"><span className="text-xs uppercase text-slate-500 mr-2">{a.kind}</span>{a.label}</li>
                  ))}
                </ul>
              </section>
            )}

            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">Recent events</h2>
                <Link href={`/observability/logs?logql=${encodeURIComponent(detail.query)}&since=7d`} className="text-xs text-blue-300 hover:underline">
                  Open in Log Explorer
                </Link>
              </div>
              <ol className="space-y-1 text-xs" data-testid="entity-events">
                {(events || []).map(e => (
                  <li key={e.id} className="flex gap-2 rounded border border-white/5 p-1.5">
                    <span className="text-slate-500 whitespace-nowrap">{new Date(e.timestamp).toLocaleString()}</span>
                    <span className="text-slate-300 shrink-0">{e.service}</span>
                    <span className="text-slate-200 break-all">{e.message}</span>
                  </li>
                ))}
                {events?.length === 0 && <li className="text-slate-400">No events in the last 7 days.</li>}
              </ol>
            </section>

            {copilot && (
              <CopilotPanel subject={{ kind: 'entity', type: copilot, value: entity.value, at: entity.last_seen }} />
            )}
          </div>

          <aside className="space-y-6">
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> Alerts ({detail.alerts.length})</h2>
              <ul className="space-y-1" data-testid="entity-alerts">
                {detail.alerts.slice(0, 15).map(a => (
                  <li key={a.id} className="text-sm">
                    <Link href={`/security/events?alert=${a.id}`} className="text-blue-300 hover:underline">{a.title}</Link>
                    <span className="block text-xs text-slate-500">{a.severity} · {new Date(a.ts).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Briefcase className="w-4 h-4" /> Cases ({detail.cases.length})</h2>
              <ul className="space-y-1" data-testid="entity-cases">
                {detail.cases.map(c => (
                  <li key={c.id} className="text-sm">
                    <Link href={`/security/cases/${c.id}`} className="text-blue-300 hover:underline">{c.title}</Link>
                    <span className="block text-xs text-slate-500">{c.status} · {c.severity}</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Network className="w-4 h-4" /> Seen with ({detail.related.length})</h2>
              <ul className="space-y-1" data-testid="entity-related">
                {detail.related.slice(0, 20).map(r => (
                  <li key={`${r.entity_type}:${r.value}`} className="text-sm">
                    <Link href={entityHref(r.entity_type, r.value)} className="text-blue-300 hover:underline">{r.value}</Link>
                    <span className="text-xs text-slate-500"> · {entityLabel(r.entity_type)} · {r.events.toLocaleString()} events</span>
                  </li>
                ))}
              </ul>
            </section>
          </aside>
        </div>
      </div>
    </DashboardLayout>
  )
}
