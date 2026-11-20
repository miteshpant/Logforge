'use client'

import Link from 'next/link'
import { AlertTriangle, Bot, ExternalLink, ShieldCheck } from 'lucide-react'
import type { AICitation, CitedSummary } from '@/lib/api/ai'
import type { AIProviderInfo } from '@/lib/aiFormat'
import { fallbackLabel, flagMessages, providerNotice, splitCitations } from '@/lib/aiFormat'

/** Where an answer came from: the model (and whether it is external) or the fallback, and why. */
export function ModeNotice({ mode, provider, reason }: { mode: string; provider: AIProviderInfo | null; reason?: string }) {
  const fallback = fallbackLabel(mode)
  const notice = providerNotice(provider)
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs" data-testid="ai-mode">
      {fallback ? (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-white/10 text-slate-400"
          data-testid="ai-fallback">
          <Bot className="w-3 h-3" /> {fallback}
        </span>
      ) : (
        <span data-testid="ai-provider-notice"
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border ${notice.external
            ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : 'border-white/10 text-slate-400'}`}>
          {notice.external ? <ExternalLink className="w-3 h-3" /> : <Bot className="w-3 h-3" />} {notice.text}
        </span>
      )}
      {fallback && reason && <span className="text-slate-500">{reason}</span>}
    </div>
  )
}

export function CitedText({ text, citations }: { text: string; citations: AICitation[] }) {
  const cites = Object.fromEntries(citations.map(c => [c.id, c]))
  return (
    <>
      {splitCitations(text).map((seg, i) => 'cite' in seg ? (
        cites[seg.cite]
          ? (cites[seg.cite].link
            ? <Link key={i} href={cites[seg.cite].link} title={`${cites[seg.cite].kind}: ${cites[seg.cite].label}`}
                data-testid="ai-citation"
                className="mx-0.5 px-1 rounded bg-blue-500/20 text-blue-300 text-xs align-super hover:bg-blue-500/30">{seg.cite}</Link>
            : <span key={i} title={`${cites[seg.cite].kind}: ${cites[seg.cite].label}`} data-testid="ai-citation"
                className="mx-0.5 px-1 rounded bg-blue-500/20 text-blue-300 text-xs align-super">{seg.cite}</span>)
          : <span key={i} className="mx-0.5 px-1 rounded bg-red-500/20 text-red-300 text-xs align-super">{seg.cite}?</span>
      ) : <span key={i}>{seg.text}</span>)}
    </>
  )
}

/** A summary in sections, every sentence citing its evidence, with the evidence listed below. */
export default function CitedSections({ summary }: { summary: CitedSummary }) {
  const warnings = flagMessages(summary.flags || [])
  return (
    <div className="space-y-3" data-testid="ai-sections">
      <div className="flex flex-wrap items-center gap-2">
        <ModeNotice mode={summary.mode} provider={summary.provider} reason={summary.reason} />
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-green-500/30 bg-green-500/10 text-green-300 text-xs">
          <ShieldCheck className="w-3 h-3" /> Every sentence cites its evidence
        </span>
      </div>
      {summary.sections.filter(s => s.sentences.length > 0).map(section => (
        <div key={section.key} data-testid={`ai-section-${section.key}`}>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">{section.title}</h4>
          <ul className="space-y-1 text-sm text-slate-200 leading-relaxed">
            {section.sentences.map((sentence, i) => (
              <li key={i}><CitedText text={sentence} citations={summary.citations} /></li>
            ))}
          </ul>
        </div>
      ))}
      {summary.dropped?.length > 0 && (
        <p className="text-xs text-slate-500" data-testid="ai-dropped"
          title={summary.dropped.join('\n')}>
          {summary.dropped.length} uncited {summary.dropped.length === 1 ? 'sentence' : 'sentences'} from the model
          {summary.dropped.length === 1 ? ' was' : ' were'} removed.
        </p>
      )}
      {warnings.length > 0 && (
        <ul className="space-y-1" data-testid="ai-flags">
          {warnings.map(w => (
            <li key={w} className="flex items-start gap-1.5 text-xs text-amber-300"><AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />{w}</li>
          ))}
        </ul>
      )}
      <ol className="space-y-1 text-xs border-t border-white/5 pt-2" data-testid="ai-sources">
        {summary.citations.map(c => (
          <li key={c.id} className="flex gap-2 min-w-0">
            <span className="text-slate-500 w-8 shrink-0">{c.id}</span>
            <span className="text-slate-500 w-20 shrink-0">{c.kind}</span>
            {c.link
              ? <Link href={c.link} className="text-blue-300 hover:underline truncate">{c.label}</Link>
              : <span className="text-slate-300 truncate">{c.label}</span>}
          </li>
        ))}
      </ol>
    </div>
  )
}
