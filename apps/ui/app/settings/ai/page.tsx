'use client'

import { useCallback, useEffect, useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import AIAnswerView from '@/components/ai/AIAnswerView'
import { Bot, Loader2, Send } from 'lucide-react'
import {
  AIAnswer, AIAuditEntry, AISettings, AISettingsResponse, AIStatus, AIUsage, askAI, getAIAudit, getAISettings,
  getAIStatus, getAIUsage, saveAISettings,
} from '@/lib/api/ai'
import { providerNotice } from '@/lib/aiFormat'

const EMPTY: AISettings = { enabled: false, provider: null, redact_fields: [], monthly_token_budget: null, requests_per_minute: null }

export default function AISettingsPage() {
  const [status, setStatus] = useState<AIStatus | null>(null)
  const [admin, setAdmin] = useState<AISettingsResponse | null>(null)
  const [form, setForm] = useState<AISettings>(EMPTY)
  const [redactText, setRedactText] = useState('')
  const [usage, setUsage] = useState<AIUsage | null>(null)
  const [audit, setAudit] = useState<AIAuditEntry[]>([])
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<AIAnswer | null>(null)
  const [busy, setBusy] = useState<'load' | 'save' | 'ask' | null>('load')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setStatus(await getAIStatus())
      setUsage(await getAIUsage())
    } catch (e: any) {
      setError(e?.message || 'Failed to load AI status')
    }
    try {  // tenant admins only; others just don't see the settings
      const s = await getAISettings()
      const entries = (await getAIAudit({ limit: 100 })).entries
      setAudit(entries)  // before the section shows, so it never shows an empty log first
      setAdmin(s)
      setForm(s.settings)
      setRedactText(s.settings.redact_fields.join('\n'))
    } catch {
      setAdmin(null)
    }
    setBusy(null)
  }, [])

  useEffect(() => { load() }, [load])

  async function onSave() {
    setBusy('save'); setError(null); setNotice(null)
    try {
      const saved = await saveAISettings({
        ...form, redact_fields: redactText.split(/[\n,]/).map(s => s.trim()).filter(Boolean),
      })
      setAdmin(saved); setForm(saved.settings); setStatus(saved.status)
      setNotice(saved.status.active ? 'Saved: AI answers are on.' : `Saved. ${saved.status.reason || ''}`)
    } catch (e: any) {
      setError(e?.message || 'Save failed')
    } finally {
      setBusy(null)
    }
  }

  async function onAsk() {
    if (!question.trim()) return
    setBusy('ask'); setError(null); setAnswer(null)
    try {
      setAnswer(await askAI(question.trim()))
      setUsage(await getAIUsage())
      if (admin) setAudit((await getAIAudit({ limit: 100 })).entries)
    } catch (e: any) {
      setError(e?.message || 'The question failed')
    } finally {
      setBusy(null)
    }
  }

  const requests = Array.from(new Set(audit.map(a => a.request_id))).reverse().slice(0, 10)
  const providers = status?.providers || []
  const chosen = providers.find(p => p.name === form.provider)

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6 max-w-5xl">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Bot className="w-6 h-6 text-blue-400" /> AI</h1>
          <p className="text-sm text-slate-400 mt-1 max-w-3xl">
            Answers from your own logs, alerts, cases and threat intelligence. The model looks things up with read-only
            tools that run with your permissions, and cites every source. Configured fields and anything that looks
            like a secret are removed before data is sent, and every request is logged.
          </p>
        </div>

        {error && <div role="alert" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</div>}
        {notice && <div data-testid="ai-notice" className="p-3 rounded-lg border border-green-500/30 bg-green-500/10 text-sm text-green-300">{notice}</div>}
        {busy === 'load' && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}

        {status && (
          <section className="rounded-lg border border-white/10 bg-slate-800/40 p-4 text-sm space-y-1" data-testid="ai-status">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${status.active ? 'bg-green-400' : 'bg-slate-500'}`} />
              <span className="text-white font-medium" data-testid="ai-status-text">
                {status.active ? 'AI answers are on' : 'AI answers are off'}
              </span>
              {status.active && status.provider && (
                <span className="text-xs text-slate-400">· {providerNotice(status.provider).text}</span>
              )}
            </div>
            {!status.active && <p className="text-slate-400" data-testid="ai-status-reason">
              {status.reason}. Questions get the rule-based answer instead.</p>}
            {usage && (
              <p className="text-xs text-slate-500" data-testid="ai-usage">
                {usage.tokens.toLocaleString()} of {usage.monthly_token_budget.toLocaleString()} tokens used this month
                · {usage.requests} requests · limit {usage.requests_per_minute} per minute
              </p>
            )}
          </section>
        )}

        {admin && (
          <section className="rounded-lg border border-white/10 p-4 space-y-4" data-testid="ai-settings">
            <h2 className="text-sm font-semibold text-white">Settings for this tenant</h2>
            {!status?.global_enabled && (
              <p className="text-xs text-slate-400">AI is switched off for this deployment (config/ai.yml), so these
                settings take effect only once an administrator enables it.</p>
            )}
            <label className="flex items-center gap-2 text-sm text-slate-200">
              <input type="checkbox" data-testid="ai-enabled" checked={form.enabled}
                onChange={e => setForm({ ...form, enabled: e.target.checked })} disabled={!providers.length} />
              Use AI for this tenant
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <label className="space-y-1">
                <span className="text-xs text-slate-400">Provider</span>
                <select data-testid="ai-provider" value={form.provider || ''} disabled={!providers.length}
                  onChange={e => setForm({ ...form, provider: e.target.value || null })}
                  className="w-full bg-slate-900 border border-white/10 rounded px-2 py-1.5 text-slate-200">
                  <option value="">{providers.length ? 'Choose a provider' : 'None offered by this deployment'}</option>
                  {providers.map(p => <option key={p.name} value={p.name}>{p.label} ({p.model}){p.external ? ', external' : ''}</option>)}
                </select>
                {chosen?.external && <span className="block text-xs text-amber-300">Questions and the data the model looks
                  up (after redaction) are sent to this provider, outside your deployment.</span>}
              </label>
              <label className="space-y-1">
                <span className="text-xs text-slate-400">Also redact these fields (one per line)</span>
                <textarea data-testid="ai-redact" value={redactText} onChange={e => setRedactText(e.target.value)} rows={3}
                  placeholder="attrs.customer_email"
                  className="w-full bg-slate-900 border border-white/10 rounded px-2 py-1.5 text-slate-200 font-mono text-xs" />
                <span className="block text-xs text-slate-500">Always redacted: {admin.effective.redact_fields.filter(f =>
                  !form.redact_fields.includes(f)).join(', ')}, and secret-looking values.</span>
              </label>
              <label className="space-y-1">
                <span className="text-xs text-slate-400">Monthly token budget (empty: {admin.effective.monthly_token_budget.toLocaleString()})</span>
                <input type="number" min={0} value={form.monthly_token_budget ?? ''} data-testid="ai-budget"
                  onChange={e => setForm({ ...form, monthly_token_budget: e.target.value === '' ? null : Number(e.target.value) })}
                  className="w-full bg-slate-900 border border-white/10 rounded px-2 py-1.5 text-slate-200" />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-slate-400">Requests per minute (empty: {admin.effective.requests_per_minute})</span>
                <input type="number" min={0} value={form.requests_per_minute ?? ''}
                  onChange={e => setForm({ ...form, requests_per_minute: e.target.value === '' ? null : Number(e.target.value) })}
                  className="w-full bg-slate-900 border border-white/10 rounded px-2 py-1.5 text-slate-200" />
              </label>
            </div>
            <button data-testid="ai-save" onClick={onSave} disabled={!!busy}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm">
              {busy === 'save' && <Loader2 className="w-4 h-4 animate-spin" />} Save
            </button>
          </section>
        )}

        <section className="rounded-lg border border-white/10 p-4 space-y-3">
          <h2 className="text-sm font-semibold text-white">Ask</h2>
          <div className="flex gap-2">
            <input data-testid="ai-question" value={question} onChange={e => setQuestion(e.target.value)} maxLength={4000}
              onKeyDown={e => { if (e.key === 'Enter') onAsk() }}
              placeholder="Which source addresses failed to log in most in the last 24 hours?"
              className="flex-1 min-w-0 bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200" />
            <button data-testid="ai-ask" onClick={onAsk} disabled={!!busy || !question.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm">
              {busy === 'ask' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Ask
            </button>
          </div>
          {answer && <AIAnswerView answer={answer} />}
        </section>

        {admin && (
          <section className="space-y-2" data-testid="ai-audit">
            <h2 className="text-sm font-semibold text-white">Recent requests (audit log)</h2>
            {requests.length === 0 && <p className="text-xs text-slate-500">No AI requests yet.</p>}
            {requests.map(id => {
              const rows = audit.filter(a => a.request_id === id)
              const first = rows[0]
              const tokens = rows.reduce((n, r) => n + r.input_tokens + r.output_tokens, 0)
              const prompt = rows.find(r => r.kind === 'prompt')?.content
              return (
                <details key={id} className="rounded border border-white/5 p-2 text-xs">
                  <summary className="cursor-pointer text-slate-300">
                    {new Date(first.ts).toLocaleString()} · {first.provider} ({first.model}){first.external ? ' · external' : ''}
                    {' '}· {rows.length} entries · {tokens} tokens
                    <span className="text-slate-500"> · {String(prompt?.user || '').split('\n').slice(-1)[0].slice(0, 80)}</span>
                  </summary>
                  <ul className="mt-2 space-y-1 font-mono text-slate-400">
                    {rows.map(r => (
                      <li key={r.seq} className="break-all"><span className="text-slate-500">{r.kind}</span>{' '}
                        {JSON.stringify(r.content).slice(0, 400)}</li>
                    ))}
                  </ul>
                </details>
              )
            })}
          </section>
        )}
      </div>
    </DashboardLayout>
  )
}
