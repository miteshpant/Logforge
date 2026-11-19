'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { AlertTriangle, GitBranch, Loader2, Plus } from 'lucide-react'
import { deadLetters, listPipelines, PipelineDef, tenantStats } from '@/lib/api/pipelines'
import { routingSummary } from '@/lib/pipelineFormat'

export default function PipelinesPage() {
  const [pipelines, setPipelines] = useState<PipelineDef[]>([])
  const [builtins, setBuiltins] = useState<PipelineDef[]>([])
  const [stats, setStats] = useState<Record<string, { events: { in: number; ok: number; dropped: number; failed: number } }>>({})
  const [pending, setPending] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    (async () => {
      try {
        const [list, s, dlq] = await Promise.all([listPipelines(), tenantStats(), deadLetters({ limit: 1 })])
        setPipelines(list.pipelines)
        setBuiltins(list.builtins)
        setStats(s.pipelines)
        setPending(Object.fromEntries(Object.entries(dlq.counts).map(([id, c]) => [id, c.pending || 0])))
      } catch (e: any) {
        setError(e?.message || 'Failed to load pipelines')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2"><GitBranch className="w-6 h-6 text-blue-400" /> Ingest Pipelines</h1>
            <p className="text-sm text-slate-400 mt-1 max-w-3xl">
              Shape logs on the way in: parse, rename, mask, enrich or drop fields before they are stored and searched.
              Events that a pipeline cannot process wait in its dead-letter queue until you fix the pipeline and replay them.
            </p>
          </div>
          <Link href="/settings/pipelines/new" data-testid="pipeline-new"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg">
            <Plus className="w-4 h-4" /> New pipeline
          </Link>
        </div>

        {error && <div role="alert" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</div>}
        {loading && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}

        {!loading && (
          <section className="rounded-lg border border-white/10 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-800/80 text-slate-400 text-xs uppercase">
                <tr>
                  <th className="p-3 text-left">Pipeline</th>
                  <th className="p-3 text-left">Runs for</th>
                  <th className="p-3 text-right">Processors</th>
                  <th className="p-3 text-right" title="Since this API process started">Events</th>
                  <th className="p-3 text-right">Failed</th>
                  <th className="p-3 text-right">Dropped</th>
                  <th className="p-3 text-right">Dead letters</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {pipelines.length === 0 && (
                  <tr><td colSpan={7} className="p-6 text-center text-slate-400">No pipelines yet. Create one, or copy a built-in below.</td></tr>
                )}
                {pipelines.map(p => {
                  const s = stats[p.id]?.events
                  return (
                    <tr key={p.id} data-testid="pipeline-row" className="hover:bg-white/5">
                      <td className="p-3">
                        <Link href={`/settings/pipelines/${encodeURIComponent(p.id)}`} className="text-blue-300 hover:underline font-medium">{p.name}</Link>
                        <span className="ml-2 text-xs text-slate-500">v{p.version}{p.enabled ? '' : ' · disabled'}</span>
                        {p.description && <div className="text-xs text-slate-500">{p.description}</div>}
                      </td>
                      <td className="p-3 text-slate-300">{routingSummary(p.routing)}</td>
                      <td className="p-3 text-right text-slate-300">{p.processors.length}</td>
                      <td className="p-3 text-right text-slate-300">{s?.in ?? 0}</td>
                      <td className={`p-3 text-right ${s?.failed ? 'text-red-300' : 'text-slate-500'}`}>{s?.failed ?? 0}</td>
                      <td className="p-3 text-right text-slate-400">{s?.dropped ?? 0}</td>
                      <td className="p-3 text-right">
                        {pending[p.id] ? <span className="inline-flex items-center gap-1 text-yellow-300"><AlertTriangle className="w-3 h-3" />{pending[p.id]}</span>
                          : <span className="text-slate-500">0</span>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </section>
        )}

        {!loading && builtins.length > 0 && (
          <section className="space-y-2">
            <h2 className="text-sm font-semibold text-white">Built-in pipelines</h2>
            <p className="text-xs text-slate-500">These parse the formats of the /v1/ingest/nginx, /syslog, /cef and /text endpoints. Send any log through one with the X-Logforge-Pipeline header, or copy one to adapt it.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {builtins.map(b => (
                <div key={b.id} data-testid="pipeline-builtin" className="p-4 rounded-lg border border-white/10 bg-slate-800/40 flex items-center gap-3">
                  <div className="flex-1">
                    <div className="text-white text-sm font-mono">{b.id}</div>
                    <div className="text-xs text-slate-500">{b.description} · {b.processors.length} processors</div>
                  </div>
                  <Link href={`/settings/pipelines/new?from=${encodeURIComponent(b.id)}`}
                    className="px-3 py-1.5 border border-white/10 rounded-lg text-sm text-slate-200 hover:bg-white/5">Copy</Link>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </DashboardLayout>
  )
}
