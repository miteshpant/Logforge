'use client'

import { useState } from 'react'
import { CheckCircle2, Loader2, ShieldCheck, Sparkles, XCircle } from 'lucide-react'
import { draftRule, enableRule, type RuleDraft, type RuleEnabled } from '@/lib/api/ai'
import { flagMessages, parseSamples } from '@/lib/aiFormat'
import { ModeNotice } from './CitedSections'

/**
 * Draft a detection rule (Phase 10): "AI drafts, the gate verifies". A draft
 * is offered for enabling only when it passed the fixture gate, fires on the
 * samples and not on the known-good event; enabling checks it all again and
 * backtests it.
 */
export default function RuleDraftPanel({ onEnabled }: { onEnabled?: (ruleId: string) => void }) {
  const [description, setDescription] = useState('')
  const [technique, setTechnique] = useState('')
  const [samples, setSamples] = useState('')
  const [knownGood, setKnownGood] = useState('')
  const [draft, setDraft] = useState<RuleDraft | null>(null)
  const [enabled, setEnabled] = useState<RuleEnabled | null>(null)
  const [busy, setBusy] = useState<'draft' | 'enable' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const attack = parseSamples(samples)
  const good = parseSamples(knownGood)[0]

  const make = async () => {
    setBusy('draft')
    setError(null)
    setEnabled(null)
    try {
      setDraft(await draftRule({ description, samples: attack, technique: technique || undefined, known_good: good }))
    } catch (e: any) {
      setError(e?.message || 'Drafting failed')
    } finally {
      setBusy(null)
    }
  }

  const enable = async () => {
    if (!draft) return
    setBusy('enable')
    setError(null)
    try {
      const out = await enableRule({ yaml: draft.yaml, samples: attack, known_good: good })
      setEnabled(out)
      onEnabled?.(out.rule_id)
    } catch (e: any) {
      setError(e?.message || 'The rule was not enabled')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 space-y-3" data-testid="rule-draft">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2"><Sparkles className="w-4 h-4 text-blue-300" /> Draft a rule</h3>
      <div className="grid gap-2 md:grid-cols-[1fr_10rem]">
        <input value={description} onChange={e => setDescription(e.target.value)} data-testid="rule-draft-description"
          placeholder="The behaviour, e.g. Volume shadow copies deleted, as ransomware does"
          className="px-2 py-1.5 rounded bg-slate-950/60 border border-white/10 text-sm text-white" />
        <input value={technique} onChange={e => setTechnique(e.target.value)} data-testid="rule-draft-technique"
          placeholder="ATT&CK, e.g. T1490" className="px-2 py-1.5 rounded bg-slate-950/60 border border-white/10 text-sm text-white" />
      </div>
      <textarea value={samples} onChange={e => setSamples(e.target.value)} rows={4} data-testid="rule-draft-samples"
        placeholder="Attack events, one per line: a JSON object or a raw log line"
        className="w-full rounded-lg border border-white/10 bg-slate-950/60 p-2 text-xs font-mono text-slate-200" />
      <input value={knownGood} onChange={e => setKnownGood(e.target.value)} data-testid="rule-draft-known-good"
        placeholder="Optional: one similar event that is fine (the rule must not fire on it)"
        className="w-full px-2 py-1.5 rounded bg-slate-950/60 border border-white/10 text-xs font-mono text-white" />
      <button onClick={make} disabled={!!busy || description.trim().length < 3 || !attack.length} data-testid="rule-draft-run"
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50">
        {busy === 'draft' && <Loader2 className="w-3 h-3 animate-spin" />} Draft and test
      </button>
      {error && <p className="text-xs text-red-400" data-testid="rule-draft-error">{error}</p>}
      {draft && (
        <div className="space-y-2" data-testid="rule-draft-result">
          <ModeNotice mode={draft.mode} provider={draft.provider} reason={draft.reason} />
          <ul className="space-y-0.5 text-xs" data-testid="rule-draft-attempts">
            {draft.attempts.map(a => (
              <li key={a.attempt} className={`flex items-center gap-1.5 ${a.passed ? 'text-green-300' : 'text-amber-300'}`}>
                {a.passed ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                Attempt {a.attempt} ({a.by}): {a.passed ? 'passed the gate, fires on the samples' : a.reason}
              </li>
            ))}
          </ul>
          {flagMessages(draft.flags).map(f => <p key={f} className="text-xs text-amber-300">{f}</p>)}
          <pre className="max-h-72 overflow-auto rounded bg-slate-950/60 p-2 text-[11px] text-green-300" data-testid="rule-draft-yaml">{draft.yaml}</pre>
          <button onClick={enable} disabled={!draft.passed || !!busy || !!enabled} data-testid="rule-draft-enable"
            title={draft.passed ? 'Checks it again, backtests it on your logs, then enables it' : 'Only a draft that passed can be enabled'}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white hover:bg-white/5 disabled:opacity-40">
            {busy === 'enable' ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldCheck className="w-3 h-3" />} Backtest and enable
          </button>
          {enabled && (
            <p className="text-xs text-green-300" data-testid="rule-draft-enabled">
              Enabled {enabled.rule_id}: {enabled.backtest[enabled.rule_id]?.alerts_total ?? 0} alert(s) in the backtest.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
