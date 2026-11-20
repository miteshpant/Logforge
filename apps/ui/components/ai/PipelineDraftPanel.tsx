'use client'

import { useState } from 'react'
import { CheckCircle2, Loader2, Sparkles, XCircle } from 'lucide-react'
import { draftPipeline, type PipelineDraft } from '@/lib/api/ai'
import { draftSummary, flagMessages } from '@/lib/aiFormat'
import { ModeNotice } from './CitedSections'

/**
 * Draft a pipeline from sample lines (Phase 9). The draft is simulated on
 * the samples before it is offered; "Use this draft" only fills the editor,
 * nothing is saved.
 */
export default function PipelineDraftPanel({ service, onUse }: {
  service?: string
  onUse: (draft: PipelineDraft['pipeline']) => void
}) {
  const [samples, setSamples] = useState('')
  const [draft, setDraft] = useState<PipelineDraft | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lines = samples.split('\n').filter(l => l.trim()).slice(0, 50)

  const run = async () => {
    if (!lines.length || loading) return
    setLoading(true)
    setError(null)
    try {
      setDraft(await draftPipeline(lines, service || 'sample'))
    } catch (e: any) {
      setError(e?.message || 'Drafting failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 space-y-3" data-testid="pipeline-draft">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-blue-300" /> Draft from samples
      </h3>
      <textarea value={samples} onChange={e => setSamples(e.target.value)} rows={5} data-testid="pipeline-draft-samples"
        placeholder="Paste up to 50 raw log lines, one per line"
        className="w-full rounded-lg border border-white/10 bg-slate-950/60 p-2 text-xs font-mono text-slate-200" />
      <div className="flex items-center gap-2">
        <button onClick={run} disabled={loading || !lines.length} data-testid="pipeline-draft-run"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50">
          {loading && <Loader2 className="w-3 h-3 animate-spin" />} Draft pipeline
        </button>
        <span className="text-xs text-slate-500">{lines.length} {lines.length === 1 ? 'line' : 'lines'}</span>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      {draft && (
        <div className="space-y-2" data-testid="pipeline-draft-result">
          <ModeNotice mode={draft.mode} provider={draft.provider} reason={draft.reason} />
          <p className="flex items-center gap-1.5 text-sm" data-testid="pipeline-draft-summary">
            {draft.report.valid && draft.report.parsed === draft.report.total
              ? <CheckCircle2 className="w-4 h-4 text-green-400" /> : <XCircle className="w-4 h-4 text-amber-400" />}
            <span className="text-slate-200">{draftSummary(draft.report)}</span>
          </p>
          <p className="text-xs text-slate-400">{draft.explanation}</p>
          {flagMessages(draft.flags).map(f => <p key={f} className="text-xs text-amber-300">{f}</p>)}
          {Object.keys(draft.report.fields).length > 0 && (
            <div className="flex flex-wrap gap-1" data-testid="pipeline-draft-fields">
              {Object.entries(draft.report.fields).slice(0, 30).map(([name, value]) => (
                <span key={name} title={String(value)}
                  className="px-1.5 py-0.5 rounded bg-white/5 text-[11px] font-mono text-slate-300">{name}</span>
              ))}
            </div>
          )}
          {draft.report.failures.length > 0 && (
            <ul className="text-xs text-amber-300 space-y-0.5">
              {draft.report.failures.map((f, i) => <li key={i} className="font-mono truncate" title={f.sample}>{f.error}: {f.sample}</li>)}
            </ul>
          )}
          <details className="text-xs">
            <summary className="cursor-pointer text-slate-400">Processors</summary>
            <pre className="mt-1 p-2 rounded bg-slate-950/60 text-green-300 overflow-x-auto">{JSON.stringify(draft.pipeline.processors, null, 2)}</pre>
          </details>
          <button onClick={() => onUse(draft.pipeline)} disabled={!draft.report.valid} data-testid="pipeline-draft-use"
            className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white hover:bg-white/5 disabled:opacity-50">
            Use this draft
          </button>
        </div>
      )}
    </div>
  )
}
