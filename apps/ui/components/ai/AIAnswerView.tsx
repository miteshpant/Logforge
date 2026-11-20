'use client'

import Link from 'next/link'
import { AlertTriangle, Bot, ExternalLink, ShieldCheck } from 'lucide-react'
import type { AIAnswer } from '@/lib/api/ai'
import { flagMessages, providerNotice, splitCitations } from '@/lib/aiFormat'

/** A grounded answer: text with citation links, the model used (and whether it is external), and any flags. */
export default function AIAnswerView({ answer }: { answer: AIAnswer }) {
  const cites = Object.fromEntries(answer.citations.map(c => [c.id, c]))
  const notice = providerNotice(answer.provider)
  const warnings = answer.mode === 'ai' ? flagMessages(answer.flags) : []
  return (
    <div className="space-y-3" data-testid="ai-answer">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span data-testid="ai-provider-notice"
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border ${notice.external
            ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : 'border-white/10 text-slate-400'}`}>
          {notice.external ? <ExternalLink className="w-3 h-3" /> : <Bot className="w-3 h-3" />} {notice.text}
        </span>
        {answer.mode === 'ai' && answer.grounded && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-green-500/30 bg-green-500/10 text-green-300">
            <ShieldCheck className="w-3 h-3" /> Every sentence cites its source
          </span>
        )}
        {answer.mode === 'rule_based' && answer.reason && (
          <span className="text-slate-500" data-testid="ai-fallback-reason">{answer.reason}</span>
        )}
      </div>

      <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed" data-testid="ai-answer-text">
        {splitCitations(answer.text).map((seg, i) => 'cite' in seg ? (
          cites[seg.cite]
            ? <Link key={i} href={cites[seg.cite].link} title={`${cites[seg.cite].kind}: ${cites[seg.cite].label}`}
                data-testid="ai-citation"
                className="mx-0.5 px-1 rounded bg-blue-500/20 text-blue-300 text-xs align-super hover:bg-blue-500/30">{seg.cite}</Link>
            : <span key={i} className="mx-0.5 px-1 rounded bg-red-500/20 text-red-300 text-xs align-super"
                title="Not a source any lookup returned">{seg.cite}?</span>
        ) : <span key={i}>{seg.text}</span>)}
      </p>

      {warnings.length > 0 && (
        <ul className="space-y-1" data-testid="ai-flags">
          {warnings.map(w => (
            <li key={w} className="flex items-start gap-1.5 text-xs text-amber-300"><AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />{w}</li>
          ))}
        </ul>
      )}

      {answer.citations.length > 0 && (
        <ol className="space-y-1 text-xs" data-testid="ai-sources">
          {answer.citations.map(c => (
            <li key={c.id} className="flex gap-2 min-w-0">
              <span className="text-slate-500 w-8 shrink-0">{c.id}</span>
              <span className="text-slate-500 w-16 shrink-0">{c.kind}</span>
              <Link href={c.link} className="text-blue-300 hover:underline truncate">{c.label}</Link>
            </li>
          ))}
        </ol>
      )}

      {answer.tool_calls && answer.tool_calls.length > 0 && (
        <details className="text-xs text-slate-500">
          <summary className="cursor-pointer">{answer.tool_calls.length} {answer.tool_calls.length === 1 ? "lookup" : "lookups"}</summary>
          <ul className="mt-1 space-y-0.5 font-mono">
            {answer.tool_calls.map((t, i) => (
              <li key={i} className={t.ok ? '' : 'text-red-300'}>
                {t.name}({Object.values(t.arguments).join(', ')}){t.error ? ` - ${t.error}` : ''}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
