'use client'

import { useEffect, useState } from 'react'
import { Loader2, Play, Sparkles } from 'lucide-react'
import { explainEvent, type Explanation } from '@/lib/api/ai'
import { eventForExplain } from '@/lib/aiFormat'
import type { NormalizedLog } from '@/components/query/logsApi'
import CitedSections from './CitedSections'

/** "Explain this event" in the Log Explorer's detail panel (Phase 9). */
export default function ExplainPanel({ log, onUseQuery }: { log: NormalizedLog; onUseQuery: (query: string) => void }) {
  const [explanation, setExplanation] = useState<Explanation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { setExplanation(null); setError(null) }, [log.id])

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setExplanation(await explainEvent(eventForExplain(log)))
    } catch (e: any) {
      setError(e?.message || 'Explanation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 space-y-3" data-testid="explain-panel">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-white flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-blue-300" /> Explain this event
        </h4>
        <button onClick={load} disabled={loading} data-testid="explain-run"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50">
          {loading && <Loader2 className="w-3 h-3 animate-spin" />}
          {explanation ? 'Refresh' : 'Explain'}
        </button>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      {explanation && (
        <>
          <CitedSections summary={explanation} />
          {explanation.fields.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">Fields</h5>
              <table className="w-full text-xs" data-testid="explain-fields">
                <tbody>
                  {explanation.fields.map(f => (
                    <tr key={f.field} className="border-t border-white/5 align-top">
                      <td className="py-1 pr-2 font-mono text-slate-300 whitespace-nowrap">{f.field}</td>
                      <td className="py-1 pr-2 font-mono text-slate-400 break-all">{String(f.value)}</td>
                      <td className="py-1 text-slate-400">{f.meaning}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {explanation.queries.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">Follow-up queries</h5>
              <ul className="space-y-1" data-testid="explain-queries">
                {explanation.queries.map(q => (
                  <li key={q.query} className="flex items-start gap-2">
                    <button onClick={() => onUseQuery(q.query)} title={q.query} data-testid="explain-query"
                      className="flex items-center gap-1 px-2 py-0.5 rounded border border-white/10 text-xs text-blue-300 hover:bg-white/5 shrink-0">
                      <Play className="w-3 h-3" /> Run
                    </button>
                    <span className="text-xs text-slate-300">{q.label}
                      <code className="block text-slate-500 break-all">{q.query}</code></span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}
