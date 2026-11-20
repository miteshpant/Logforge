'use client'

import { useState } from 'react'
import { Loader2, Sparkles } from 'lucide-react'
import { triage, type CitedSummary } from '@/lib/api/ai'
import CitedSections from './CitedSections'

/** "Triage summary" for an alert or case (Phase 9): cited, with or without AI. */
export default function TriagePanel({ kind, id }: { kind: 'alert' | 'case'; id: string }) {
  const [summary, setSummary] = useState<CitedSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setSummary(await triage(kind, id))
    } catch (e: any) {
      setError(e?.message || 'Triage failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 space-y-3" data-testid="triage-panel">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-blue-300" /> Triage summary
        </h3>
        <button onClick={load} disabled={loading} data-testid="triage-run"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50">
          {loading && <Loader2 className="w-3 h-3 animate-spin" />}
          {summary ? 'Refresh' : 'Summarise'}
        </button>
      </div>
      {!summary && !loading && !error && (
        <p className="text-xs text-slate-400">
          What happened, the ATT&amp;CK context, the entities, their related activity and next steps, each
          sentence citing its evidence.
        </p>
      )}
      {error && <p className="text-xs text-red-400" data-testid="triage-error">{error}</p>}
      {summary && <CitedSections summary={summary} />}
    </div>
  )
}
