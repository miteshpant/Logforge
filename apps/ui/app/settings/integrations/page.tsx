'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { CheckCircle, Loader2, Plus, Puzzle, ShieldAlert, Trash2, XCircle, Zap } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import {
  deleteIntegration, listIntegrations, listKinds, saveIntegration, testIntegration,
  type ActionResult, type Integration,
} from '@/lib/api/response'
import { fieldLabel, kindFields, type KindInfo } from '@/lib/responseFormat'

interface Draft { id?: string; name: string; kind: string; config: Record<string, string>; secrets: Record<string, string> }

/**
 * Settings → Integrations (Phase 13): the connections playbooks use to notify
 * (Slack, Teams, PagerDuty, Opsgenie, email, webhooks), open tickets (Jira,
 * GitHub) and contain (through the customer's own automation). Secrets are
 * write-only: the page shows which are set, never their values.
 */
export default function IntegrationsPage() {
  const [kinds, setKinds] = useState<KindInfo[]>([])
  const [items, setItems] = useState<Integration[] | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [tests, setTests] = useState<Record<string, ActionResult>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [k, i] = await Promise.all([listKinds(), listIntegrations()])
      setKinds(k.kinds)
      setItems(i.integrations)
    } catch (e: any) {
      setError(e?.message || 'Failed to load integrations')
    }
  }, [])

  useEffect(() => { load() }, [load])

  const kindOf = useMemo(() => Object.fromEntries(kinds.map(k => [k.kind, k])), [kinds])
  const current = draft ? kindOf[draft.kind] : undefined

  const startNew = (kind: string) => { setMessage(null); setError(null); setDraft({ name: '', kind, config: {}, secrets: {} }) }
  const startEdit = (i: Integration) => {
    setMessage(null); setError(null)
    setDraft({ id: i.id, name: i.name, kind: i.kind, config: Object.fromEntries(Object.entries(i.config).map(([k, v]) => [k, String(v)])), secrets: {} })
  }

  const save = async () => {
    if (!draft) return
    setBusy('save'); setError(null); setMessage(null)
    try {
      const secrets = Object.fromEntries(Object.entries(draft.secrets).filter(([, v]) => v))
      await saveIntegration({ name: draft.name, kind: draft.kind, config: draft.config, secrets }, draft.id)
      setMessage(`Saved ${draft.name}.`)
      setDraft(null)
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to save')
    } finally {
      setBusy(null)
    }
  }

  const test = async (i: Integration) => {
    setBusy(`test-${i.id}`); setError(null)
    try {
      const { result } = await testIntegration(i.id)
      setTests(t => ({ ...t, [i.id]: result }))
    } catch (e: any) {
      setTests(t => ({ ...t, [i.id]: { ok: false, status: null, output: {}, error: e?.message || 'failed' } }))
    } finally {
      setBusy(null)
    }
  }

  const remove = async (i: Integration) => {
    if (!window.confirm(`Delete ${i.name}? Playbooks that use it will fail at that step.`)) return
    try {
      await deleteIntegration(i.id)
      setMessage(`Deleted ${i.name}.`)
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to delete')
    }
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Puzzle className="w-6 h-6" /> Integrations</h1>
            <p className="text-slate-400 mt-1">
              Where <Link href="/security/playbooks" className="text-blue-400 hover:underline">playbooks</Link> send
              notifications, open tickets and ask for containment.
            </p>
          </div>
          <select data-testid="add-integration" className="bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm text-white"
            value="" onChange={e => e.target.value && startNew(e.target.value)}>
            <option value="">+ Add an integration…</option>
            {kinds.map(k => <option key={k.kind} value={k.kind}>{k.label}</option>)}
          </select>
        </div>
        {message && <p className="text-sm text-emerald-300" data-testid="integrations-message">{message}</p>}
        {error && <p className="text-sm text-red-400" data-testid="integrations-error">{error}</p>}

        {draft && current && (
          <section className="bg-slate-900 border border-slate-700 rounded-lg p-5 space-y-4" data-testid="integration-form">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Plus className="w-4 h-4" /> {draft.id ? `Edit ${draft.name}` : `New ${current.label} integration`}
            </h2>
            {current.containment && (
              <p className="text-sm text-amber-300 flex items-center gap-2"><ShieldAlert className="w-4 h-4" />
                Containment: playbooks can only call this after a person approves the step.</p>
            )}
            <label className="block text-sm text-slate-300">Name
              <input data-testid="integration-name" className="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
                value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} placeholder="SOC Slack" />
              <span className="text-xs text-slate-500">Playbooks refer to the integration by this name.</span>
            </label>
            {kindFields(current).map(f => (
              <label key={f.name} className="block text-sm text-slate-300">
                {f.label}{f.required ? '' : ' (optional)'}
                <input data-testid={`field-${f.name}`} type={f.secret ? 'password' : 'text'} autoComplete="off"
                  className="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
                  value={(f.secret ? draft.secrets[f.name] : draft.config[f.name]) ?? ''}
                  placeholder={f.secret && draft.id && items?.find(i => i.id === draft.id)?.secrets_set.includes(f.name) ? 'set (leave empty to keep)' : ''}
                  onChange={e => setDraft(f.secret ? { ...draft, secrets: { ...draft.secrets, [f.name]: e.target.value } }
                    : { ...draft, config: { ...draft.config, [f.name]: e.target.value } })} />
                {f.help && <span className="text-xs text-slate-500">{f.help}</span>}
              </label>
            ))}
            <p className="text-xs text-slate-500">Inputs playbook steps can set: {current.inputs.join(', ')}.</p>
            <div className="flex gap-2">
              <button data-testid="save-integration" onClick={save} disabled={busy === 'save' || !draft.name}
                className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm disabled:opacity-50">
                {busy === 'save' ? 'Saving…' : 'Save'}
              </button>
              <button onClick={() => setDraft(null)} className="px-4 py-2 rounded bg-slate-700 text-white text-sm">Cancel</button>
            </div>
          </section>
        )}

        {!items && !error && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}
        {items && items.length === 0 && (
          <p className="text-slate-400" data-testid="integrations-empty">No integrations yet. Add one to let playbooks act.</p>
        )}
        {items && items.length > 0 && (
          <table className="w-full text-sm" data-testid="integrations-table">
            <thead className="text-left text-slate-400 border-b border-slate-700">
              <tr><th className="py-2">Name</th><th>Kind</th><th>Settings</th><th>Secrets</th><th>Last test</th><th /></tr>
            </thead>
            <tbody>
              {items.map(i => {
                const result = tests[i.id]
                return (
                  <tr key={i.id} className="border-b border-slate-800 text-slate-200" data-testid={`integration-${i.name}`}>
                    <td className="py-2 font-medium">{i.name}</td>
                    <td>{kindOf[i.kind]?.label || i.kind}{kindOf[i.kind]?.containment && <span className="ml-2 text-xs text-amber-300">containment</span>}</td>
                    <td className="text-slate-400">{Object.entries(i.config).map(([k, v]) => `${fieldLabel(k)}: ${v}`).join(' · ') || '—'}</td>
                    <td className="text-slate-400">{i.secrets_set.length ? i.secrets_set.map(fieldLabel).join(', ') : 'none'}</td>
                    <td data-testid={`test-result-${i.name}`}>
                      {result && (result.ok
                        ? <span className="text-emerald-300 flex items-center gap-1"><CheckCircle className="w-4 h-4" /> OK{result.status ? ` (${result.status})` : ''}</span>
                        : <span className="text-red-300 flex items-center gap-1"><XCircle className="w-4 h-4" /> {result.error}</span>)}
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <button data-testid={`test-${i.name}`} onClick={() => test(i)} disabled={busy === `test-${i.id}`}
                        title={kindOf[i.kind]?.containment ? 'Sends a dry-run request (dry_run: true)' : 'Sends a test message'}
                        className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-white text-xs mr-2 inline-flex items-center gap-1">
                        <Zap className="w-3 h-3" /> {busy === `test-${i.id}` ? 'Testing…' : 'Test'}
                      </button>
                      <button onClick={() => startEdit(i)} className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-white text-xs mr-2">Edit</button>
                      <button aria-label={`Delete ${i.name}`} onClick={() => remove(i)} className="p-1 text-slate-400 hover:text-red-400">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </DashboardLayout>
  )
}
