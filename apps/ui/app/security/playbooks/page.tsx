'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { CheckCircle, ClipboardList, Loader2, Play, ShieldCheck, Trash2, Workflow, XCircle } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import {
  decide, deletePlaybook, listPlaybooks, listRuns, savePlaybook, validatePlaybook,
  type Playbook, type Run,
} from '@/lib/api/response'
import { runProgress, runTone, TONE_CLASS, triggerSummary, waitingApproval } from '@/lib/responseFormat'

const EXAMPLE = `name: Brute force response
trigger:
  on: alert                  # alert | case_created | case_updated
  when: alert.severity in ["high", "critical"] and alert.rule_id == "ssh_brute_force"
steps:
  - id: intel
    enrich: {indicator: "{{ alert.entities.src_ip.0 }}"}
  - id: notify
    action: {integration: SOC Slack, inputs: {text: "{{ alert.title }}: {{ steps.intel.output.verdict }}"}}
  - id: ticket
    action: {integration: Jira, inputs: {summary: "{{ alert.title }}"}}
    link_case: true          # the ticket follows the case, and closing it closes the case
  - id: approve
    approval: {prompt: "Block {{ alert.entities.src_ip.0 }} at the firewall?", timeout: 4h}
  - id: block
    action: {integration: Firewall, inputs: {action: block_ip, target: "{{ alert.entities.src_ip.0 }}"}}
`

/**
 * Security → Playbooks (Phase 13): what runs when alerts and cases arrive,
 * what ran, and the containment steps waiting for a person to approve.
 */
export default function PlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[] | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [editing, setEditing] = useState<{ id?: string; definition: string; enabled: boolean } | null>(null)
  const [check, setCheck] = useState<string | null>(null)
  const [openRun, setOpenRun] = useState<string | null>(null)
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([listPlaybooks(), listRuns()])
      setPlaybooks(p.playbooks)
      setRuns(r.runs)
    } catch (e: any) {
      setError(e?.message || 'Failed to load playbooks')
    }
  }, [])

  useEffect(() => { load() }, [load])

  const validate = async () => {
    if (!editing) return
    try {
      const out = await validatePlaybook(editing.definition)
      setCheck(out.valid
        ? `Valid: ${out.name}, ${triggerSummary({ trigger: out.trigger, when: out.when })}, ${out.steps!.length} steps` +
          (out.steps!.some(s => s.containment) ? ' (containment behind an approval)' : '')
        : `Invalid: ${out.error}`)
    } catch (e: any) {
      setCheck(`Invalid: ${e?.message}`)
    }
  }

  const save = async () => {
    if (!editing) return
    setError(null); setMessage(null)
    try {
      const { playbook } = await savePlaybook(editing.definition, editing.enabled, editing.id)
      setMessage(`Saved ${playbook.name}.`)
      setEditing(null); setCheck(null)
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to save')
    }
  }

  const toggle = async (p: Playbook) => {
    try {
      await savePlaybook(p.definition, !p.enabled, p.id)
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to update')
    }
  }

  const remove = async (p: Playbook) => {
    if (!window.confirm(`Delete ${p.name}? Runs already started keep their history.`)) return
    try {
      await deletePlaybook(p.id)
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to delete')
    }
  }

  const decision = async (run: Run, step: string, choice: 'approve' | 'reject') => {
    setError(null); setMessage(null)
    try {
      const out = await decide(run.id, step, choice, notes[run.id] || '')
      setMessage(`${choice === 'approve' ? 'Approved' : 'Rejected'}: ${run.playbook_name} is now ${out.run.status.replace('_', ' ')}.`)
      await load()
    } catch (e: any) {
      setError(e?.message || 'The decision was not recorded')
    }
  }

  const waiting = runs.filter(r => r.status === 'waiting_approval')

  return (
    <DashboardLayout>
      <div className="p-6 space-y-8">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Workflow className="w-6 h-6" /> Playbooks</h1>
            <p className="text-slate-400 mt-1">
              Automatic response to alerts and cases, through your <Link href="/settings/integrations" className="text-blue-400 hover:underline">integrations</Link>.
              Containment always waits for a person.
            </p>
          </div>
          <button data-testid="new-playbook" onClick={() => { setEditing({ definition: EXAMPLE, enabled: false }); setCheck(null) }}
            className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm">New playbook</button>
        </div>
        {message && <p className="text-sm text-emerald-300" data-testid="playbooks-message">{message}</p>}
        {error && <p className="text-sm text-red-400" data-testid="playbooks-error">{error}</p>}

        {waiting.length > 0 && (
          <section className="space-y-3" data-testid="approvals">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-amber-300" /> Waiting for approval</h2>
            {waiting.map(run => {
              const step = waitingApproval(run)!
              return (
                <div key={run.id} className="bg-amber-500/5 border border-amber-500/30 rounded-lg p-4 space-y-2" data-testid={`approval-${run.id}`}>
                  <p className="text-white font-medium">{step.prompt}</p>
                  <p className="text-xs text-slate-400">
                    {run.playbook_name} · {run.trigger_ref} · approvers: {(step.approvers || []).join(', ')}
                    {step.deadline && ` · expires ${new Date(step.deadline).toLocaleString()}`}
                  </p>
                  <div className="flex gap-2 items-center flex-wrap">
                    <input placeholder="Note (optional)" value={notes[run.id] || ''} onChange={e => setNotes({ ...notes, [run.id]: e.target.value })}
                      className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white flex-1 min-w-[12rem]" />
                    <button data-testid={`approve-${run.id}`} onClick={() => decision(run, step.id, 'approve')}
                      className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-sm">Approve</button>
                    <button data-testid={`reject-${run.id}`} onClick={() => decision(run, step.id, 'reject')}
                      className="px-3 py-1 rounded bg-red-600 hover:bg-red-500 text-white text-sm">Reject</button>
                  </div>
                </div>
              )
            })}
          </section>
        )}

        {editing && (
          <section className="bg-slate-900 border border-slate-700 rounded-lg p-5 space-y-3" data-testid="playbook-editor">
            <h2 className="text-lg font-semibold text-white">{editing.id ? 'Edit playbook' : 'New playbook'}</h2>
            <textarea data-testid="playbook-definition" spellCheck={false} rows={20} value={editing.definition}
              onChange={e => { setEditing({ ...editing, definition: e.target.value }); setCheck(null) }}
              className="w-full font-mono text-xs bg-slate-950 border border-slate-700 rounded p-3 text-slate-100" />
            <label className="text-sm text-slate-300 flex items-center gap-2">
              <input type="checkbox" checked={editing.enabled} onChange={e => setEditing({ ...editing, enabled: e.target.checked })} /> Enabled
            </label>
            {check && <p data-testid="playbook-check" className={`text-sm ${check.startsWith('Valid') ? 'text-emerald-300' : 'text-red-400'}`}>{check}</p>}
            <div className="flex gap-2">
              <button data-testid="validate-playbook" onClick={validate} className="px-4 py-2 rounded bg-slate-700 hover:bg-slate-600 text-white text-sm">Validate</button>
              <button data-testid="save-playbook" onClick={save} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm">Save</button>
              <button onClick={() => { setEditing(null); setCheck(null) }} className="px-4 py-2 rounded bg-slate-800 text-white text-sm">Cancel</button>
            </div>
          </section>
        )}

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2"><ClipboardList className="w-5 h-5" /> Definitions</h2>
          {!playbooks && !error && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}
          {playbooks?.length === 0 && <p className="text-slate-400" data-testid="playbooks-empty">No playbooks yet.</p>}
          {playbooks && playbooks.length > 0 && (
            <table className="w-full text-sm" data-testid="playbooks-table">
              <thead className="text-left text-slate-400 border-b border-slate-700">
                <tr><th className="py-2">Name</th><th>Trigger</th><th>Steps</th><th>Enabled</th><th /></tr>
              </thead>
              <tbody>
                {playbooks.map(p => (
                  <tr key={p.id} className="border-b border-slate-800 text-slate-200" data-testid={`playbook-${p.name}`}>
                    <td className="py-2 font-medium">{p.name}</td>
                    <td className={p.error ? 'text-red-400' : 'text-slate-400'}>{triggerSummary(p)}</td>
                    <td className="text-slate-400">{p.steps.map(s => s.id).join(' → ')}</td>
                    <td>
                      <button onClick={() => toggle(p)} data-testid={`toggle-${p.name}`}
                        className={`px-2 py-0.5 rounded text-xs border ${p.enabled ? TONE_CLASS.good : TONE_CLASS.neutral}`}>
                        {p.enabled ? 'on' : 'off'}
                      </button>
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <button onClick={() => { setEditing({ id: p.id, definition: p.definition, enabled: p.enabled }); setCheck(null) }}
                        className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-white text-xs mr-2">Edit</button>
                      <button aria-label={`Delete ${p.name}`} onClick={() => remove(p)} className="p-1 text-slate-400 hover:text-red-400">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2"><Play className="w-5 h-5" /> Recent runs</h2>
          {runs.length === 0 && <p className="text-slate-400" data-testid="runs-empty">No runs yet.</p>}
          {runs.length > 0 && (
            <ul className="space-y-2" data-testid="runs">
              {runs.map(run => (
                <li key={run.id} className="bg-slate-900 border border-slate-800 rounded-lg">
                  <button className="w-full flex items-center justify-between gap-3 px-4 py-2 text-left" onClick={() => setOpenRun(openRun === run.id ? null : run.id)}>
                    <span className="text-slate-200">{run.playbook_name} <span className="text-slate-500 text-xs">· {run.trigger_ref} · {new Date(run.created_at).toLocaleString()}</span></span>
                    <span className="flex items-center gap-3">
                      <span className="text-xs text-slate-400">{runProgress(run)}</span>
                      <span className={`px-2 py-0.5 rounded text-xs border ${TONE_CLASS[runTone(run.status)]}`} data-testid={`run-status-${run.id}`}>{run.status.replace('_', ' ')}</span>
                    </span>
                  </button>
                  {openRun === run.id && (
                    <ol className="px-4 pb-3 space-y-1 text-sm">
                      {run.steps.map(s => (
                        <li key={s.id} className="flex items-start gap-2 text-slate-300">
                          {s.status === 'done' ? <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5" />
                            : ['failed', 'rejected', 'expired'].includes(s.status) ? <XCircle className="w-4 h-4 text-red-400 mt-0.5" />
                              : <span className="w-4 h-4 rounded-full border border-slate-600 mt-0.5" />}
                          <span><b>{s.id}</b> ({s.type}) {s.status}
                            {s.error && <span className="text-red-300"> — {s.error}</span>}
                            {s.output?.ticket && <> — <a className="text-blue-400 hover:underline" href={s.output.url} target="_blank" rel="noreferrer">{s.output.ticket}</a></>}
                            {s.decision && <span className="text-slate-400"> — {s.decision.approved ? 'approved' : 'rejected'} by {s.decision.by}{s.decision.note ? `: ${s.decision.note}` : ''}</span>}
                          </span>
                        </li>
                      ))}
                    </ol>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </DashboardLayout>
  )
}
