'use client'

import { useState } from 'react'
import { AlertTriangle, Loader2, Play, Sparkles } from 'lucide-react'
import { draftQuery, type QueryDraft } from '@/lib/api/ai'
import { ModeNotice } from './CitedSections'

/**
 * Ask in plain English (Phase 9): a LogforgeQL query is drafted from the
 * question and the tenant's fields, shown and explained; the user runs or
 * edits it. The query, not the model, produces the answer.
 */
export default function AskQueryBox({ onUse }: { onUse: (query: string) => void }) {
  const [question, setQuestion] = useState('')
  const [draft, setDraft] = useState<QueryDraft | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ask = async () => {
    if (!question.trim() || loading) return
    setLoading(true)
    setError(null)
    try {
      setDraft(await draftQuery(question.trim()))
    } catch (e: any) {
      setError(e?.message || 'Drafting failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mb-3 space-y-2" data-testid="ask-query">
      <form className="flex items-center gap-2" onSubmit={e => { e.preventDefault(); ask() }}>
        <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 bg-slate-800/30">
          <Sparkles className="w-4 h-4 text-blue-300 shrink-0" />
          <input value={question} onChange={e => setQuestion(e.target.value)} maxLength={2000}
            data-testid="ask-query-input"
            placeholder="Ask in plain English: which hosts logged the most errors in the last hour?"
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 outline-none" />
        </div>
        <button type="submit" disabled={loading || !question.trim()} data-testid="ask-query-run"
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm disabled:opacity-50">
          {loading && <Loader2 className="w-3 h-3 animate-spin" />} Draft query
        </button>
      </form>
      {error && <p className="text-xs text-red-400">{error}</p>}
      {draft && (
        <div className="rounded-lg border border-white/10 bg-slate-900/40 p-3 space-y-2" data-testid="ask-query-draft">
          <ModeNotice mode={draft.mode} provider={draft.provider} reason={draft.reason} />
          {draft.query ? (
            <div className="flex items-start gap-2">
              <code className="flex-1 text-xs text-green-300 font-mono break-all" data-testid="ask-query-text">{draft.query}</code>
              <button onClick={() => onUse(draft.query as string)} data-testid="ask-query-use"
                className="flex items-center gap-1 px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs shrink-0">
                <Play className="w-3 h-3" /> Use and run
              </button>
            </div>
          ) : null}
          <p className="text-xs text-slate-300" data-testid="ask-query-explanation">{draft.explanation}</p>
          {draft.unknown_fields?.length > 0 && (
            <p className="flex items-center gap-1.5 text-xs text-amber-300">
              <AlertTriangle className="w-3 h-3" /> Not seen in your logs recently: {draft.unknown_fields.join(', ')}
            </p>
          )}
          {!draft.valid && draft.error && <p className="text-xs text-red-400">{draft.error}</p>}
        </div>
      )}
    </div>
  )
}
