'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import DashboardLayout from '@/components/layout/DashboardLayout'
import PipelineDraftPanel from '@/components/ai/PipelineDraftPanel'
import { ArrowLeft, FlaskConical, Loader2, RotateCcw, Save, Trash2 } from 'lucide-react'
import {
  createPipeline, DeadLetter, deadLetters, deletePipeline, discardDeadLetters, getPipeline, PipelineBody, PipelineDef,
  pipelineStats, replayDeadLetters, SimulationResult, simulatePipeline, updatePipeline, VersionStats,
} from '@/lib/api/pipelines'
import { diffFields, parseProcessors, sampleDocs } from '@/lib/pipelineFormat'

const CHANGE_STYLE: Record<string, string> = {
  added: 'text-green-300', changed: 'text-yellow-300', removed: 'text-red-300 line-through',
}
const STATUS_STYLE: Record<string, string> = {
  ok: 'bg-green-500/15 text-green-300 border-green-500/30',
  dropped: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  failed: 'bg-red-500/15 text-red-300 border-red-500/30',
}

function show(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value)
}

export default function PipelineEditorPage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const isNew = params.id === 'new'
  const [record, setRecord] = useState<PipelineDef | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [services, setServices] = useState('')
  const [condition, setCondition] = useState('')
  const [priority, setPriority] = useState(100)
  const [isDefault, setIsDefault] = useState(false)
  const [processorsText, setProcessorsText] = useState('[\n]')
  const [samples, setSamples] = useState('')
  const [draftOnFailure, setDraftOnFailure] = useState<any[] | null>(null)
  const [results, setResults] = useState<SimulationResult[] | null>(null)
  const [tab, setTab] = useState<'editor' | 'metrics' | 'dlq'>('editor')
  const [stats, setStats] = useState<VersionStats[]>([])
  const [letters, setLetters] = useState<DeadLetter[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fill = (p: PipelineDef, copy: boolean) => {
    setName(copy ? `${p.id}-copy` : p.name)
    setDescription(p.description || '')
    setEnabled(copy ? true : p.enabled)
    setServices((p.routing?.services || []).join(', '))
    setCondition(p.routing?.if || '')
    setPriority(p.routing?.priority ?? 100)
    setIsDefault(Boolean(p.routing?.default))
    setProcessorsText(JSON.stringify(p.processors, null, 2))
  }

  useEffect(() => {
    (async () => {
      try {
        if (isNew) {
          const from = new URLSearchParams(window.location.search).get('from')
          if (from) fill(await getPipeline(from), true)
        } else {
          const p = await getPipeline(params.id)
          setRecord(p)
          fill(p, false)
        }
      } catch (e: any) {
        setError(e?.message || 'Failed to load the pipeline')
      } finally {
        setLoading(false)
      }
    })()
  }, [isNew, params.id])

  const loadSide = useCallback(async () => {
    if (isNew || !record) return
    try {
      const [s, d] = await Promise.all([pipelineStats(record.id), deadLetters({ pipeline_id: record.id, limit: 100 })])
      setStats(s.versions)
      setLetters(d.entries)
    } catch (e: any) {
      setError(e?.message || 'Failed to load metrics')
    }
  }, [isNew, record])


  const parsed = useMemo(() => parseProcessors(processorsText), [processorsText])
  const readOnly = Boolean(record?.builtin)

  const body = (): PipelineBody => ({
    id: record?.id || '',
    name: name.trim(),
    description,
    enabled,
    routing: {
      services: services.split(',').map(s => s.trim()).filter(Boolean), if: condition.trim(), priority,
      default: isDefault,
    },
    processors: parsed.processors,
    on_failure: draftOnFailure ?? (record?.on_failure || []),
  })

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key)
    setError(null)
    setNotice(null)
    try {
      await fn()
    } catch (e: any) {
      setError(e?.message || 'Something went wrong')
    } finally {
      setBusy(null)
    }
  }

  const simulate = () => run('simulate', async () => {
    if (parsed.error) throw new Error(parsed.error)
    const docs = sampleDocs(samples)
    if (!docs.length) throw new Error('Paste one or more sample log lines first')
    const { id, ...definition } = body()
    setResults(await simulatePipeline({ ...definition, name: definition.name || 'draft' }, docs))
  })

  const save = () => run('save', async () => {
    if (parsed.error) throw new Error(parsed.error)
    if (!name.trim()) throw new Error('Give the pipeline a name')
    const payload = body()
    if (isNew) {
      const { id, ...rest } = payload
      const created = await createPipeline(rest as PipelineBody)
      router.replace(`/settings/pipelines/${encodeURIComponent(created.id)}`)
    } else {
      const saved = await updatePipeline(record!.id, payload)
      setRecord(saved)
      setNotice(`Saved version ${saved.version}. New events use it within seconds.`)
    }
  })

  const remove = () => run('delete', async () => {
    if (!record || !window.confirm(`Delete pipeline ${record.name}? Events will no longer be routed to it.`)) return
    await deletePipeline(record.id)
    router.replace('/settings/pipelines')
  })

  const latest = stats[0]

  return (
    <DashboardLayout>
      <div className="p-6 space-y-5">
        <Link href="/settings/pipelines" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" /> Ingest Pipelines
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 data-testid="pipeline-title" className="text-2xl font-bold text-white flex-1">
            {isNew ? 'New pipeline' : record?.name}
            {record && <span className="ml-2 text-sm text-slate-500 font-normal">v{record.version}{record.builtin ? ' · built-in' : ''}</span>}
          </h1>
          {!readOnly && (
            <button data-testid="pipeline-save" onClick={save} disabled={busy !== null}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50">
              {busy === 'save' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save
            </button>
          )}
          {record && !record.builtin && (
            <button onClick={remove} disabled={busy !== null} aria-label="Delete pipeline"
              className="p-2 border border-white/10 rounded-lg text-slate-400 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
          )}
        </div>
        {readOnly && <p className="text-sm text-slate-400">Built-in pipelines are read-only. <Link className="text-blue-300 hover:underline" href={`/settings/pipelines/new?from=${record?.id}`}>Copy it</Link> to change it.</p>}

        {error && <div role="alert" data-testid="pipeline-error" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</div>}
        {notice && <div data-testid="pipeline-notice" className="p-3 rounded-lg border border-green-500/30 bg-green-500/10 text-sm text-green-300">{notice}</div>}

        {!isNew && (
          <div className="flex rounded-lg border border-white/10 overflow-hidden w-fit">
            {(['editor', 'metrics', 'dlq'] as const).map(t => (
              <button key={t} data-testid={`pipeline-tab-${t}`}
                onClick={() => { setTab(t); if (t !== 'editor') loadSide() }}
                className={`px-4 py-2 text-sm ${tab === t ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-white/5'}`}>
                {t === 'editor' ? 'Definition' : t === 'metrics' ? 'Metrics' : 'Dead letters'}
              </button>
            ))}
          </div>
        )}

        {loading && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}

        {!loading && tab === 'editor' && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <section className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="text-sm text-slate-300">Name
                  <input data-testid="pipeline-name" value={name} onChange={e => setName(e.target.value)} disabled={readOnly || !isNew}
                    className="mt-1 w-full px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white disabled:opacity-60" />
                </label>
                <label className="text-sm text-slate-300">Description
                  <input value={description} onChange={e => setDescription(e.target.value)} disabled={readOnly}
                    className="mt-1 w-full px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white" />
                </label>
                <label className="text-sm text-slate-300">Run for services (comma-separated)
                  <input data-testid="pipeline-services" value={services} onChange={e => setServices(e.target.value)} disabled={readOnly}
                    placeholder="nginx, ingress-nginx" className="mt-1 w-full px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white" />
                </label>
                <label className="text-sm text-slate-300">…or when (condition)
                  <input value={condition} onChange={e => setCondition(e.target.value)} disabled={readOnly}
                    placeholder="startswith(msg, 'CEF:')" className="mt-1 w-full px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white font-mono text-xs" />
                </label>
                <label className="text-sm text-slate-300">Priority (lower runs first)
                  <input type="number" value={priority} onChange={e => setPriority(Number(e.target.value))} disabled={readOnly}
                    className="mt-1 w-full px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white" />
                </label>
                <div className="flex items-end gap-4 text-sm text-slate-300 pb-2">
                  <label className="flex items-center gap-2"><input type="checkbox" checked={enabled} onChange={() => setEnabled(!enabled)} disabled={readOnly} /> Enabled</label>
                  <label className="flex items-center gap-2"><input type="checkbox" checked={isDefault} onChange={() => setIsDefault(!isDefault)} disabled={readOnly} /> Default for unmatched events</label>
                </div>
              </div>
              <label className="block text-sm text-slate-300">Processors (JSON)
                <textarea data-testid="pipeline-processors" value={processorsText} onChange={e => setProcessorsText(e.target.value)}
                  readOnly={readOnly} spellCheck={false} rows={18}
                  className="mt-1 w-full px-3 py-2 bg-slate-950 border border-white/10 rounded-lg text-slate-100 font-mono text-xs" />
              </label>
              {parsed.error
                ? <p data-testid="pipeline-json-error" className="text-xs text-red-400">{parsed.error}</p>
                : <p className="text-xs text-slate-500">{parsed.processors.length} processors. Each step is {'{"<processor>": {options}, "if": "...", "ignore_failure": true}'}; see the guide for the processor list.</p>}
              {!readOnly && (
                <PipelineDraftPanel service={services.split(',')[0]?.trim() || undefined} onUse={draft => {
                  setProcessorsText(JSON.stringify(draft.processors, null, 2))
                  if (draft.on_failure?.length) setDraftOnFailure(draft.on_failure)
                  setNotice('Draft loaded into the editor: review it, simulate, then save.')
                }} />
              )}
            </section>

            <section className="space-y-4">
              <label className="block text-sm text-slate-300">Sample events (one log line, or JSON object, per line)
                <textarea data-testid="pipeline-samples" value={samples} onChange={e => setSamples(e.target.value)} rows={6} spellCheck={false}
                  className="mt-1 w-full px-3 py-2 bg-slate-950 border border-white/10 rounded-lg text-slate-100 font-mono text-xs" />
              </label>
              <button data-testid="pipeline-simulate" onClick={simulate} disabled={busy !== null}
                className="flex items-center gap-2 px-4 py-2 border border-blue-500/40 text-blue-200 rounded-lg hover:bg-blue-500/10 disabled:opacity-50">
                {busy === 'simulate' ? <Loader2 className="w-4 h-4 animate-spin" /> : <FlaskConical className="w-4 h-4" />} Test with samples
              </button>
              {results && results.map((result, i) => {
                const input = sampleDocs(samples)[i]
                const before = typeof input === 'string' ? { msg: input } : (input as Record<string, unknown>)
                const changes = result.doc ? diffFields(before, result.doc) : diffFields(before, null)
                return (
                  <div key={i} data-testid="pipeline-result" className="rounded-lg border border-white/10 bg-slate-800/40 p-3 space-y-2">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-slate-400">Sample {i + 1}</span>
                      <span data-testid="pipeline-result-status" className={`px-2 py-0.5 rounded border text-xs ${STATUS_STYLE[result.status]}`}>{result.status}</span>
                      {result.error && <span className="text-xs text-red-300">{result.error.processor}: {result.error.message}</span>}
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      <div>
                        <div className="text-xs text-slate-500 mb-1">Before</div>
                        <pre className="text-xs bg-slate-950 rounded p-2 overflow-auto max-h-64 text-slate-300">{JSON.stringify(before, null, 2)}</pre>
                      </div>
                      <div>
                        <div className="text-xs text-slate-500 mb-1">After</div>
                        <pre data-testid="pipeline-result-after" className="text-xs bg-slate-950 rounded p-2 overflow-auto max-h-64 text-slate-100">{result.doc ? JSON.stringify(result.doc, null, 2) : '(dropped)'}</pre>
                      </div>
                    </div>
                    {changes.length > 0 && (
                      <ul data-testid="pipeline-result-changes" className="text-xs font-mono space-y-0.5">
                        {changes.map(c => (
                          <li key={c.path} className={CHANGE_STYLE[c.change]}>
                            {c.change === 'added' ? '+' : c.change === 'removed' ? '−' : '~'} {c.path}
                            {c.change !== 'removed' && <span className="text-slate-400"> = {show(c.after)}</span>}
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="text-xs text-slate-500">
                      {result.steps.map(s => `${s.on_failure ? 'on_failure:' : ''}${s.processor} ${s.status}`).join(' → ')}
                    </div>
                  </div>
                )
              })}
            </section>
          </div>
        )}

        {tab === 'metrics' && (
          <section data-testid="pipeline-metrics" className="space-y-3">
            <div className="flex items-center gap-3">
              <p className="text-xs text-slate-500 flex-1">Counted by this API process since it started, per version.</p>
              <button data-testid="pipeline-refresh" onClick={loadSide} className="text-xs text-blue-300 hover:underline">Refresh</button>
            </div>
            {!latest && <p className="text-sm text-slate-400">No events have gone through this pipeline yet.</p>}
            {latest && (
              <>
                <div className="flex flex-wrap gap-6 text-sm">
                  <div><div className="text-slate-500 text-xs">Version</div><div className="text-white">v{latest.version}</div></div>
                  <div><div className="text-slate-500 text-xs">Events</div><div className="text-white">{latest.events.in}</div></div>
                  <div><div className="text-slate-500 text-xs">Failed</div><div className="text-red-300">{latest.events.failed}</div></div>
                  <div><div className="text-slate-500 text-xs">Dropped</div><div className="text-white">{latest.events.dropped}</div></div>
                  <div><div className="text-slate-500 text-xs">Events/s</div><div className="text-white">{latest.events_per_second}</div></div>
                  <div><div className="text-slate-500 text-xs">Avg time per event</div><div className="text-white">{latest.avg_us} µs</div></div>
                </div>
                <table className="w-full text-sm rounded-lg border border-white/10">
                  <thead className="bg-slate-800/80 text-slate-400 text-xs uppercase">
                    <tr><th className="p-2 text-left">#</th><th className="p-2 text-left">Processor</th><th className="p-2 text-right">Ran</th>
                      <th className="p-2 text-right">Skipped</th><th className="p-2 text-right">Failed</th><th className="p-2 text-right">Dropped</th>
                      <th className="p-2 text-right">Avg µs</th></tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {latest.processors.map(p => (
                      <tr key={p.index} data-testid="pipeline-metric-row">
                        <td className="p-2 text-slate-500">{p.index + 1}</td>
                        <td className="p-2 text-slate-200 font-mono">{p.type}{p.tag ? ` (${p.tag})` : ''}</td>
                        <td className="p-2 text-right text-slate-300">{p.count}</td>
                        <td className="p-2 text-right text-slate-400">{p.skipped}</td>
                        <td className={`p-2 text-right ${p.failed ? 'text-red-300' : 'text-slate-500'}`}>{p.failed}</td>
                        <td className="p-2 text-right text-slate-400">{p.dropped}</td>
                        <td className="p-2 text-right text-slate-300">{p.avg_us}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </section>
        )}

        {tab === 'dlq' && (
          <section data-testid="pipeline-dlq" className="space-y-3">
            <div className="flex items-center gap-3">
              <p className="text-sm text-slate-400 flex-1">{letters.length} events failed this pipeline and are waiting. Fix the pipeline, then replay them.</p>
              <button onClick={loadSide} className="text-xs text-blue-300 hover:underline">Refresh</button>
              <button data-testid="pipeline-replay" disabled={!letters.length || busy !== null}
                onClick={() => run('replay', async () => {
                  const r = await replayDeadLetters({ pipeline_id: record!.id })
                  setNotice(`Replayed ${r.replayed} events through version ${record!.version}.`)
                  await loadSide()
                })}
                className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm disabled:opacity-50">
                <RotateCcw className="w-4 h-4" /> Replay all
              </button>
            </div>
            {letters.map(l => (
              <div key={l.id} data-testid="pipeline-dead-letter" className="p-3 rounded-lg border border-white/10 bg-slate-800/40 text-sm flex gap-3">
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-xs text-slate-200 break-all">{String(l.event?.msg ?? JSON.stringify(l.event))}</div>
                  <div className="text-xs text-red-300 mt-1">v{l.pipeline_version} · {l.processor || 'routing'}: {l.error}</div>
                  <div className="text-xs text-slate-500">{new Date(l.failed_at).toLocaleString()}</div>
                </div>
                <button aria-label="Discard" disabled={busy !== null}
                  onClick={() => run('discard', async () => { await discardDeadLetters([l.id]); await loadSide() })}
                  className="text-slate-500 hover:text-red-400 self-start"><Trash2 className="w-4 h-4" /></button>
              </div>
            ))}
          </section>
        )}
      </div>
    </DashboardLayout>
  )
}
