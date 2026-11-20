'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Check, Loader2, MessageSquarePlus, Pin, Play, Sparkles, Target } from 'lucide-react'
import { copilotPlan, copilotRun, type CopilotResult, type CopilotStep, type CopilotSubject } from '@/lib/api/ai'
import { caseAction } from '@/lib/api/cases'
import { flagMessages, signalTone } from '@/lib/aiFormat'
import { CitedText, ModeNotice } from './CitedSections'

/**
 * Investigation copilot (Phase 10), under the analyst's control: it proposes
 * read-only searches, the analyst picks and edits them, runs them, and
 * decides what to pin and which conclusions to record in the case.
 */
export default function CopilotPanel({ subject, caseId, onChanged }: {
  subject: CopilotSubject
  caseId?: string
  onChanged?: () => void
}) {
  const [steps, setSteps] = useState<(CopilotStep & { on: boolean })[]>([])
  const [result, setResult] = useState<CopilotResult | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<Set<string>>(new Set())

  const act = async (label: string, work: () => Promise<void>) => {
    setBusy(label)
    setError(null)
    try {
      await work()
    } catch (e: any) {
      setError(e?.message || 'The copilot failed')
    } finally {
      setBusy(null)
    }
  }

  const plan = () => act('plan', async () => {
    const out = await copilotPlan(subject)
    setSteps(out.steps.map(s => ({ ...s, on: true })))
    setResult(null)
  })

  const run = (extra: CopilotStep[] = []) => act('run', async () => {
    const chosen: CopilotStep[] = [...steps.filter(s => s.on).map(({ on: _on, ...s }) => s), ...extra].slice(0, 8)
    setSteps([...steps, ...extra.map(s => ({ ...s, on: true }))].slice(0, 8))
    setResult(await copilotRun(subject, chosen))
  })

  const pin = (cid: string) => act(`pin-${cid}`, async () => {
    const event = result!.timeline.find(e => e.cid === cid)!
    await caseAction(caseId!, 'evidence', {
      kind: 'link', ref: event.link, title: `${event.service || 'event'} ${event.ts}: ${event.msg}`.slice(0, 300),
      data: { source: 'copilot' },
    })
    setDone(prev => new Set(prev).add(`pin-${cid}`))
    onChanged?.()
  })

  const record = (index: number) => act(`note-${index}`, async () => {
    await caseAction(caseId!, 'comments', { text: `Copilot conclusion, approved: ${result!.hypotheses[index]}` })
    setDone(prev => new Set(prev).add(`note-${index}`))
    onChanged?.()
  })

  const roots = new Set(result?.root_cause || [])

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 space-y-3" data-testid="copilot-panel">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-blue-300" /> Investigation copilot
        </h3>
        <button onClick={plan} disabled={!!busy} data-testid="copilot-plan"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50">
          {busy === 'plan' && <Loader2 className="w-3 h-3 animate-spin" />} {steps.length ? 'Plan again' : 'Plan searches'}
        </button>
      </div>
      {!steps.length && !error && (
        <p className="text-xs text-slate-400">
          Proposes read-only searches around the alert, runs the ones you keep, and builds a cited timeline with
          where it likely started. Nothing is pinned or recorded unless you do it.
        </p>
      )}
      {error && <p className="text-xs text-red-400" data-testid="copilot-error">{error}</p>}

      {steps.length > 0 && (
        <div className="space-y-2" data-testid="copilot-steps">
          {steps.map((step, i) => (
            <div key={i} className="rounded-lg border border-white/5 bg-slate-800/40 p-2 text-xs space-y-1" data-testid="copilot-step">
              <label className="flex items-center gap-2 text-slate-200">
                <input type="checkbox" checked={step.on} onChange={() => setSteps(steps.map((s, j) => j === i ? { ...s, on: !s.on } : s))} />
                <span className="font-medium">{step.title}</span>
              </label>
              {step.why && <p className="text-slate-500">{step.why}</p>}
              <textarea value={step.query} rows={2} spellCheck={false} data-testid="copilot-step-query"
                onChange={e => setSteps(steps.map((s, j) => j === i ? { ...s, query: e.target.value } : s))}
                className="w-full rounded border border-white/10 bg-slate-950/60 p-1.5 font-mono text-[11px] text-green-300" />
              <p className="text-slate-500">{new Date(step.start).toLocaleString()} → {new Date(step.end).toLocaleString()}</p>
            </div>
          ))}
          <button onClick={() => run()} disabled={!!busy || !steps.some(s => s.on)} data-testid="copilot-run"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs disabled:opacity-50">
            {busy === 'run' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} Run the selected searches
          </button>
        </div>
      )}

      {result && (
        <div className="space-y-3" data-testid="copilot-result">
          <ModeNotice mode={result.mode} provider={result.provider} reason={result.reason} />
          <ul className="flex flex-wrap gap-2 text-[11px] text-slate-400">
            {result.steps.map(s => (
              <li key={s.id} className={s.error ? 'text-red-300' : ''}>
                {s.link ? <Link href={s.link} className="hover:underline">{s.title}</Link> : s.title}: {s.error || `${s.events} events`}
              </li>
            ))}
          </ul>

          {result.hypotheses.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">Hypotheses</h4>
              <ul className="space-y-1" data-testid="copilot-hypotheses">
                {result.hypotheses.map((h, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-200">
                    <span className="flex-1"><CitedText text={h} citations={result.citations} /></span>
                    {caseId && (
                      <button onClick={() => record(i)} disabled={!!busy || done.has(`note-${i}`)} data-testid="copilot-record"
                        title="Record as a conclusion in the case"
                        className="shrink-0 p-1 rounded border border-white/10 text-slate-300 hover:bg-white/10 disabled:opacity-40">
                        {done.has(`note-${i}`) ? <Check className="w-3 h-3" /> : <MessageSquarePlus className="w-3 h-3" />}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
              {result.dropped.length > 0 && (
                <p className="text-xs text-slate-500 mt-1">{result.dropped.length} uncited sentence(s) from the model removed.</p>
              )}
            </div>
          )}
          {flagMessages(result.flags).map(f => <p key={f} className="text-xs text-amber-300">{f}</p>)}

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">
              Timeline ({result.timeline.length})
            </h4>
            <ol className="space-y-1 max-h-96 overflow-y-auto pr-1" data-testid="copilot-timeline">
              {result.timeline.map(e => {
                const tone = signalTone(e.score)
                return (
                  <li key={e.cid} data-testid="copilot-event" data-root={roots.has(e.cid) ? 'yes' : 'no'}
                    className={`rounded border p-1.5 text-xs ${roots.has(e.cid) ? 'border-red-500/50 bg-red-500/10'
                      : tone === 'strong' ? 'border-amber-500/40 bg-amber-500/5' : tone === 'weak' ? 'border-white/10' : 'border-white/5'}`}>
                    <div className="flex items-start gap-2">
                      <span className="text-slate-500 w-8 shrink-0">{e.cid}</span>
                      <span className="text-slate-400 whitespace-nowrap">{new Date(e.ts).toLocaleTimeString()}</span>
                      <span className="text-slate-300 shrink-0">{e.service}{e.host ? ` @ ${e.host}` : ''}</span>
                      <span className="flex-1 text-slate-200 break-all">{e.msg}</span>
                      {caseId && (
                        <button onClick={() => pin(e.cid)} disabled={!!busy || done.has(`pin-${e.cid}`)} data-testid="copilot-pin"
                          title="Pin to the case" className="shrink-0 p-1 rounded text-slate-400 hover:bg-white/10 disabled:opacity-40">
                          {done.has(`pin-${e.cid}`) ? <Check className="w-3 h-3" /> : <Pin className="w-3 h-3" />}
                        </button>
                      )}
                    </div>
                    {(e.signals.length > 0 || roots.has(e.cid)) && (
                      <p className="mt-0.5 pl-10 text-[11px] text-amber-300 flex items-center gap-1">
                        {roots.has(e.cid) && <Target className="w-3 h-3 text-red-300" />}
                        {roots.has(e.cid) ? 'Likely start: ' : ''}{e.signals.join('; ')}
                      </p>
                    )}
                  </li>
                )
              })}
            </ol>
          </div>

          {result.next_steps.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">Proposed next searches</h4>
              <ul className="space-y-1 text-xs text-slate-300" data-testid="copilot-next">
                {result.next_steps.map((s, i) => <li key={i}>{s.title} <code className="text-slate-500">{s.query}</code></li>)}
              </ul>
              <button onClick={() => run(result.next_steps)} disabled={!!busy} data-testid="copilot-run-next"
                className="mt-1 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs disabled:opacity-50">
                <Play className="w-3 h-3" /> Run these too
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
