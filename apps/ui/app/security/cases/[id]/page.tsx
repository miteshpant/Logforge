'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import DashboardLayout from '@/components/layout/DashboardLayout'
import TriagePanel from '@/components/ai/TriagePanel'
import CopilotPanel from '@/components/ai/CopilotPanel'
import CaseReportPanel from '@/components/ai/CaseReportPanel'
import CaseTickets from '@/components/response/CaseTickets'
import { ArrowLeft, Link2, Loader2, MessageSquare, Pin, ShieldAlert, Tag, User } from 'lucide-react'
import { caseAction, CaseDetail, Evidence, getCase, Severity, unpinEvidence, updateCase } from '@/lib/api/cases'
import { threatBadge } from '@/lib/intelFormat'
import { CaseStatus, currentEvidence, describeEvent, evidenceHref, nextStatuses, needsReason, statusLabel } from '@/lib/caseFormat'

const SEVERITY_STYLE: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-300 border-red-500/40',
  high: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  medium: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  low: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
}

const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString() : '—')

export default function CaseDetailPage() {
  const params = useParams()
  const id = String(params?.id || '')
  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [pendingStatus, setPendingStatus] = useState<CaseStatus | null>(null)
  const [reason, setReason] = useState('')
  const [assignee, setAssignee] = useState('')
  const [comment, setComment] = useState('')
  const [tag, setTag] = useState('')
  const [evidence, setEvidence] = useState<Evidence>({ kind: 'search', ref: '', title: '' })

  const load = useCallback(async () => {
    try {
      const data = await getCase(id)
      setDetail(data)
      setAssignee(data.case.assignee || '')
    } catch (e: any) {
      setError(e?.message || 'Failed to load the case')
    }
  }, [id])

  useEffect(() => { if (id) load() }, [id, load])

  const run = async (change: () => Promise<unknown>, after?: () => void) => {
    setBusy(true)
    setError(null)
    try {
      await change()
      after?.()
      await load()
    } catch (e: any) {
      setError(e?.message || 'The change was not saved')
    } finally {
      setBusy(false)
    }
  }

  const changeStatus = (status: CaseStatus) => {
    if (needsReason(status)) {
      setPendingStatus(status)
      return
    }
    run(() => caseAction(id, 'status', { status }))
  }

  if (!detail) {
    return (
      <DashboardLayout>
        <div className="p-6">
          {error ? (
            <div role="alert" data-testid="case-error" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</div>
          ) : (
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
          )}
        </div>
      </DashboardLayout>
    )
  }

  const c = detail.case
  const evidenceItems = currentEvidence(detail)

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <Link href="/security/cases" className="text-sm text-slate-400 hover:text-white flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" /> All cases
        </Link>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-0.5 text-xs rounded border ${SEVERITY_STYLE[c.severity] || ''}`}>{c.severity}</span>
              <span data-testid="case-status" className="px-2 py-0.5 text-xs rounded border border-white/20 text-slate-200 capitalize">
                {statusLabel(c.status)}
              </span>
              {c.merged_into && (
                <Link href={`/security/cases/${c.merged_into}`} className="text-xs text-blue-300">merged into {c.merged_into.slice(0, 8)}</Link>
              )}
            </div>
            <h1 data-testid="case-title" className="text-2xl font-bold text-white">{c.title}</h1>
            <p className="text-xs text-slate-500 mt-1">
              Opened {when(c.created_at)} by {c.created_by} · acknowledged {when(c.acknowledged_at)}
              {c.resolved_at && ` · closed ${when(c.resolved_at)}`}
            </p>
            {c.close_reason && <p data-testid="case-close-reason" className="text-sm text-slate-300 mt-2">Closed: {c.close_reason}</p>}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {nextStatuses(c.status).map(status => (
              <button key={status} data-testid={`status-${status}`} disabled={busy} onClick={() => changeStatus(status)}
                className="px-3 py-1.5 text-sm rounded-lg border border-white/10 text-slate-200 hover:bg-white/5 capitalize disabled:opacity-50">
                {c.status === 'resolved' || c.status === 'false_positive' ? 'Reopen' : statusLabel(status)}
              </button>
            ))}
            <select aria-label="Severity" value={c.severity} disabled={busy}
              onChange={e => run(() => updateCase(id, { severity: e.target.value as Severity }))}
              className="px-2 py-1.5 bg-slate-900 border border-white/10 rounded-lg text-sm text-white">
              {['low', 'medium', 'high', 'critical'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {pendingStatus && (
          <div className="flex gap-2 p-4 rounded-lg border border-white/10 bg-slate-800/50">
            <input data-testid="close-reason" autoFocus value={reason} onChange={e => setReason(e.target.value)}
              placeholder={`Why is this case ${statusLabel(pendingStatus)}? (set on its alerts too)`}
              className="flex-1 px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white" />
            <button data-testid="confirm-status" disabled={busy || !reason.trim()}
              onClick={() => run(() => caseAction(id, 'status', { status: pendingStatus, reason: reason.trim() }),
                () => { setPendingStatus(null); setReason('') })}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 capitalize">
              Mark {statusLabel(pendingStatus)}
            </button>
            <button onClick={() => setPendingStatus(null)} className="px-3 py-2 text-slate-400 hover:text-white">Cancel</button>
          </div>
        )}

        {error && (
          <div role="alert" data-testid="case-error" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Timeline */}
          <section className="xl:col-span-2 space-y-4">
            <TriagePanel kind="case" id={detail.case.id} />
            <CopilotPanel subject={{ kind: 'case', id: detail.case.id }} caseId={detail.case.id} onChanged={load} />
            <CaseReportPanel caseId={detail.case.id} />
            <h2 className="text-sm font-semibold text-white flex items-center gap-2"><MessageSquare className="w-4 h-4" /> Timeline</h2>
            <div className="space-y-2">
              <textarea data-testid="comment-input" value={comment} onChange={e => setComment(e.target.value)} rows={3}
                placeholder="Add a note. @name mentions are recorded."
                className="w-full px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white text-sm" />
              <button data-testid="comment-post" disabled={busy || !comment.trim()}
                onClick={() => run(() => caseAction(id, 'comments', { text: comment.trim() }), () => setComment(''))}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm disabled:opacity-50">Add note</button>
            </div>
            <ol className="space-y-2">
              {[...detail.timeline].reverse().map(event => {
                const href = event.kind === 'evidence_pinned' ? evidenceHref(event.data as any) : null
                return (
                  <li key={event.id} data-testid="timeline-item" data-kind={event.kind}
                    className="p-3 rounded-lg border border-white/5 bg-slate-800/40">
                    <div className="flex justify-between gap-4 text-sm">
                      <span className="text-slate-200">{describeEvent(event)}</span>
                      <span className="text-xs text-slate-500 whitespace-nowrap">{when(event.ts)}</span>
                    </div>
                    {event.kind === 'comment' && (
                      <p className="mt-2 text-sm text-slate-300 whitespace-pre-wrap">{event.data.text}</p>
                    )}
                    {href && (
                      <a href={href} target={href.startsWith('http') ? '_blank' : undefined} rel="noreferrer"
                        className="mt-1 inline-flex items-center gap-1 text-xs text-blue-300 hover:underline">
                        <Link2 className="w-3 h-3" /> {event.data.ref}
                      </a>
                    )}
                    {event.kind === 'evidence_pinned' && !href && (
                      <p className="mt-1 text-xs text-slate-400 font-mono break-all">{event.data.ref}</p>
                    )}
                  </li>
                )
              })}
            </ol>
          </section>

          {/* Side panel */}
          <aside className="space-y-6">
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2"><User className="w-4 h-4" /> Assignee</h2>
              <div className="flex gap-2">
                <input data-testid="assignee-input" value={assignee} onChange={e => setAssignee(e.target.value)} placeholder="user@example.com"
                  className="flex-1 px-3 py-1.5 bg-slate-900 border border-white/10 rounded-lg text-white text-sm" />
                <button data-testid="assign" disabled={busy || assignee === (c.assignee || '')}
                  onClick={() => run(() => caseAction(id, 'assign', { assignee: assignee.trim() || null }))}
                  className="px-3 py-1.5 border border-white/10 rounded-lg text-sm text-slate-200 hover:bg-white/5 disabled:opacity-50">Save</button>
              </div>
            </section>

            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" /> Alerts ({detail.alerts.length})
              </h2>
              {detail.alerts.length === 0 && <p className="text-xs text-slate-500">No alerts linked.</p>}
              {detail.alerts.map(alert => (
                <div key={alert.id} data-testid="case-alert" className="p-3 rounded-lg border border-white/5 bg-slate-800/40 text-sm">
                  {alert.missing ? (
                    <span className="text-slate-500">Alert {alert.id.slice(0, 8)} is no longer stored</span>
                  ) : (
                    <>
                      <div className="flex justify-between gap-2">
                        <span className="text-slate-200">{alert.title}</span>
                        <span className={`px-1.5 text-xs rounded border ${SEVERITY_STYLE[alert.severity || ''] || ''}`}>{alert.severity}</span>
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {when(alert.ts)} · {statusLabel(alert.status || '')}
                        {(alert.mitre_techniques || []).length > 0 && ` · ${alert.mitre_techniques!.join(', ')}`}
                      </div>
                      {threatBadge(alert.threat) && (
                        <div data-testid="intel-badge" className="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded border border-red-500/40 bg-red-500/10 text-xs text-red-300">
                          <ShieldAlert className="w-3 h-3" /> {threatBadge(alert.threat)}
                        </div>
                      )}
                      {alert.geo && Object.entries(alert.geo).map(([field, g]) => (
                        <span key={field} className="ml-2 text-xs text-slate-500">{field}: {[g.city, g.country].filter(Boolean).join(', ')}{g.as_org ? ` · ${g.as_org}` : ''}</span>
                      ))}
                    </>
                  )}
                </div>
              ))}
            </section>

            <CaseTickets caseId={c.id} refreshKey={c.status} />

            {Object.keys(c.entities).length > 0 && (
              <section className="space-y-2">
                <h2 className="text-sm font-semibold text-white">Entities</h2>
                <dl data-testid="case-entities" className="text-sm space-y-1">
                  {Object.entries(c.entities).map(([name, values]) => (
                    <div key={name} className="flex gap-2">
                      <dt className="text-slate-500 w-20">{name}</dt>
                      <dd className="text-slate-200 font-mono break-all">{values.join(', ')}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            )}

            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Pin className="w-4 h-4" /> Evidence ({evidenceItems.length})</h2>
              {evidenceItems.length > 0 && (
                <ul className="space-y-1" data-testid="evidence-list">
                  {evidenceItems.map(item => {
                    const href = evidenceHref(item.data as any)
                    const label = String((item.data as any).title || (item.data as any).ref)
                    return (
                      <li key={item.id} data-testid="evidence-item" className="flex items-start gap-2 text-xs">
                        {href ? <a href={href} className="flex-1 text-blue-300 hover:underline break-all">{label}</a>
                          : <span className="flex-1 text-slate-300 break-all">{label}</span>}
                        <button data-testid="evidence-unpin" disabled={busy} title="Take back this pin"
                          onClick={() => run(() => unpinEvidence(id, item.id))}
                          className="shrink-0 px-1.5 rounded text-slate-400 hover:bg-red-500/20 hover:text-red-300">Take back</button>
                      </li>
                    )
                  })}
                </ul>
              )}
              <div className="space-y-2 p-3 rounded-lg border border-white/5 bg-slate-800/40">
                <select data-testid="evidence-kind" value={evidence.kind}
                  onChange={e => setEvidence({ ...evidence, kind: e.target.value as Evidence['kind'] })}
                  className="w-full px-2 py-1.5 bg-slate-900 border border-white/10 rounded text-sm text-white">
                  <option value="search">Log search</option>
                  <option value="event">Event</option>
                  <option value="trace">Trace</option>
                  <option value="log">Log line</option>
                  <option value="link">Link</option>
                </select>
                <input data-testid="evidence-ref" value={evidence.ref} onChange={e => setEvidence({ ...evidence, ref: e.target.value })}
                  placeholder="Query, event or trace ID, or URL"
                  className="w-full px-2 py-1.5 bg-slate-900 border border-white/10 rounded text-sm text-white" />
                <input data-testid="evidence-title" value={evidence.title || ''} onChange={e => setEvidence({ ...evidence, title: e.target.value })}
                  placeholder="Title (optional)"
                  className="w-full px-2 py-1.5 bg-slate-900 border border-white/10 rounded text-sm text-white" />
                <button data-testid="evidence-pin" disabled={busy || !evidence.ref.trim()}
                  onClick={() => run(() => caseAction(id, 'evidence', { ...evidence, ref: evidence.ref.trim(), title: evidence.title || undefined }),
                    () => setEvidence({ kind: evidence.kind, ref: '', title: '' }))}
                  className="w-full px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm disabled:opacity-50">Pin evidence</button>
              </div>
            </section>

            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Tag className="w-4 h-4" /> Tags</h2>
              <div className="flex flex-wrap gap-1">
                {c.tags.map(t => (
                  <button key={t} title="Remove tag" disabled={busy} onClick={() => run(() => caseAction(id, 'tags', { remove: [t] }))}
                    className="px-2 py-0.5 text-xs rounded bg-slate-700 text-slate-200 hover:bg-red-500/30">{t} ×</button>
                ))}
              </div>
              <div className="flex gap-2">
                <input value={tag} onChange={e => setTag(e.target.value)} placeholder="Add tag"
                  onKeyDown={e => e.key === 'Enter' && tag.trim() && run(() => caseAction(id, 'tags', { add: [tag.trim()] }), () => setTag(''))}
                  className="flex-1 px-2 py-1.5 bg-slate-900 border border-white/10 rounded text-sm text-white" />
              </div>
            </section>
          </aside>
        </div>
      </div>
    </DashboardLayout>
  )
}
