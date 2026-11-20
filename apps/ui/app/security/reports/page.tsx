'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { CalendarClock, Download, FileBarChart, Loader2, Map, Send, ShieldCheck, Trash2 } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import {
  deleteSchedule, download, listIntegrations, listSchedules, saveSchedule, sendSchedule, socReport,
  type Integration, type ReportSchedule, type SocReport,
} from '@/lib/api/response'
import { scheduleSummary } from '@/lib/responseFormat'

const PERIODS = [7, 30, 90]
const BLANK = { name: 'Weekly SOC report', every: 'weekly' as const, hour: 7, format: 'pdf' as const, integration_id: '', recipients: '' }

/**
 * Security → Reports (Phase 13): the security operations report (on screen,
 * PDF, CSV), detection coverage as an ATT&CK Navigator layer, and reports
 * emailed on a schedule.
 */
export default function ReportsPage() {
  const [days, setDays] = useState(30)
  const [report, setReport] = useState<SocReport | null>(null)
  const [schedules, setSchedules] = useState<ReportSchedule[]>([])
  const [emails, setEmails] = useState<Integration[]>([])
  const [form, setForm] = useState<typeof BLANK | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadReport = useCallback(async () => {
    setReport(null)
    try {
      setReport(await socReport(days))
    } catch (e: any) {
      setError(e?.message || 'Failed to build the report')
    }
  }, [days])

  const loadSchedules = useCallback(async () => {
    try {
      const [s, i] = await Promise.all([listSchedules(), listIntegrations()])
      setSchedules(s.schedules)
      setEmails(i.integrations.filter(x => x.kind === 'email'))
    } catch (e: any) {
      setError(e?.message || 'Failed to load schedules')
    }
  }, [])

  useEffect(() => { loadReport() }, [loadReport])
  useEffect(() => { loadSchedules() }, [loadSchedules])

  const save = async (name: string, endpoint: string) => {
    setError(null); setMessage(null)
    try {
      setMessage(`Downloaded ${await download(endpoint, name)}.`)
    } catch (e: any) {
      setError(e?.message || 'Download failed')
    }
  }

  const create = async () => {
    if (!form) return
    setError(null); setMessage(null)
    try {
      const recipients = form.recipients.split(/[\s,;]+/).filter(Boolean)
      await saveSchedule({ name: form.name, every: form.every, hour: Number(form.hour), format: form.format,
        integration_id: form.integration_id, recipients, enabled: true })
      setMessage(`Scheduled ${form.name}.`)
      setForm(null)
      await loadSchedules()
    } catch (e: any) {
      setError(e?.message || 'Failed to save the schedule')
    }
  }

  const send = async (s: ReportSchedule) => {
    setError(null); setMessage(null)
    try {
      const { result } = await sendSchedule(s.id)
      if (result.ok) setMessage(`Sent ${s.name} to ${s.recipients.join(', ')}.`)
      else setError(`${s.name} wasn't sent: ${result.error}`)
      await loadSchedules()
    } catch (e: any) {
      setError(e?.message || 'Failed to send')
    }
  }

  const remove = async (s: ReportSchedule) => {
    if (!window.confirm(`Delete the schedule ${s.name}?`)) return
    try {
      await deleteSchedule(s.id)
      await loadSchedules()
    } catch (e: any) {
      setError(e?.message || 'Failed to delete')
    }
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-8">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2"><FileBarChart className="w-6 h-6" /> Reports</h1>
            <p className="text-slate-400 mt-1">Alerts, case response, detection coverage, retention and response automation for a period.</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <select data-testid="report-days" value={days} onChange={e => setDays(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm text-white">
              {PERIODS.map(d => <option key={d} value={d}>Last {d} days</option>)}
            </select>
            <button data-testid="download-pdf" onClick={() => save('logforge-soc-report.pdf', `/v1/reports/soc?days=${days}&format=pdf`)}
              className="px-3 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm inline-flex items-center gap-1"><Download className="w-4 h-4" /> PDF</button>
            <button data-testid="download-csv" onClick={() => save('logforge-soc-report.csv', `/v1/reports/soc?days=${days}&format=csv`)}
              className="px-3 py-2 rounded bg-slate-700 hover:bg-slate-600 text-white text-sm inline-flex items-center gap-1"><Download className="w-4 h-4" /> CSV</button>
            <button data-testid="download-navigator" onClick={() => save('logforge-coverage-layer.json', '/v1/reports/attack-navigator')}
              title="Open in the MITRE ATT&CK Navigator: Open Existing Layer → Upload from local"
              className="px-3 py-2 rounded bg-slate-700 hover:bg-slate-600 text-white text-sm inline-flex items-center gap-1"><Map className="w-4 h-4" /> ATT&CK Navigator layer</button>
            <button data-testid="download-compliance" onClick={() => save('logforge-compliance-report.pdf', `/v1/reports/compliance?days=${days}&format=pdf`)}
              title="SOC 2 and ISO 27001 evidence: access review, API keys, audit trail, retention, legal holds, incident response"
              className="px-3 py-2 rounded bg-slate-700 hover:bg-slate-600 text-white text-sm inline-flex items-center gap-1"><ShieldCheck className="w-4 h-4" /> Compliance evidence</button>
          </div>
        </div>
        {message && <p className="text-sm text-emerald-300" data-testid="reports-message">{message}</p>}
        {error && <p className="text-sm text-red-400" data-testid="reports-error">{error}</p>}

        {!report && !error && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}
        {report && (
          <div className="grid gap-4 lg:grid-cols-2" data-testid="report">
            <p className="text-sm text-slate-400 lg:col-span-2">{report.period.start} to {report.period.end} ({report.period.days} days)</p>
            {report.sections.map(section => (
              <section key={section.title} className="bg-slate-900 border border-slate-800 rounded-lg p-4" data-testid={`report-${section.title}`}>
                <h2 className="text-white font-semibold mb-2">{section.title}</h2>
                <table className="w-full text-sm">
                  {section.columns && (
                    <thead className="text-left text-slate-400"><tr>{section.columns.map(c => <th key={c} className="py-1 pr-2 font-normal">{c}</th>)}</tr></thead>
                  )}
                  <tbody>
                    {section.rows.map((row, i) => (
                      <tr key={i} className="border-t border-slate-800 text-slate-200">
                        {row.map((cell, j) => <td key={j} className={`py-1 pr-2 ${j === 0 && !section.columns ? 'text-slate-400' : ''}`}>{cell ?? '—'}</td>)}
                      </tr>
                    ))}
                    {section.rows.length === 0 && <tr><td className="py-1 text-slate-500">None in this period.</td></tr>}
                  </tbody>
                </table>
                {section.note && <p className="text-xs text-slate-500 mt-2">{section.note}</p>}
              </section>
            ))}
          </div>
        )}

        <section className="space-y-3" data-testid="schedules">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2"><CalendarClock className="w-5 h-5" /> Scheduled reports</h2>
            <button data-testid="new-schedule" onClick={() => setForm({ ...BLANK, integration_id: emails[0]?.id || '' })}
              className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-white text-sm">Schedule a report</button>
          </div>
          {form && (
            emails.length === 0 ? (
              <p className="text-sm text-amber-300" data-testid="schedule-needs-email">
                Reports are sent by email. <Link href="/settings/integrations" className="underline">Add an email integration</Link> first.
              </p>
            ) : (
              <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 grid gap-3 md:grid-cols-3" data-testid="schedule-form">
                <label className="text-sm text-slate-300">Name
                  <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white" />
                </label>
                <label className="text-sm text-slate-300">Every
                  <select value={form.every} onChange={e => setForm({ ...form, every: e.target.value as any })} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white">
                    <option value="daily">Day</option><option value="weekly">Week (Mondays)</option><option value="monthly">Month (the 1st)</option>
                  </select>
                </label>
                <label className="text-sm text-slate-300">Hour (UTC)
                  <input type="number" min={0} max={23} value={form.hour} onChange={e => setForm({ ...form, hour: Number(e.target.value) })} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white" />
                </label>
                <label className="text-sm text-slate-300">Format
                  <select value={form.format} onChange={e => setForm({ ...form, format: e.target.value as any })} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white">
                    <option value="pdf">PDF</option><option value="csv">CSV</option>
                  </select>
                </label>
                <label className="text-sm text-slate-300">Send with
                  <select value={form.integration_id} onChange={e => setForm({ ...form, integration_id: e.target.value })} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white">
                    {emails.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                  </select>
                </label>
                <label className="text-sm text-slate-300">Recipients
                  <input data-testid="schedule-recipients" value={form.recipients} placeholder="ciso@example.com, soc@example.com"
                    onChange={e => setForm({ ...form, recipients: e.target.value })} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white" />
                </label>
                <div className="md:col-span-3 flex gap-2">
                  <button data-testid="save-schedule" onClick={create} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm">Save</button>
                  <button onClick={() => setForm(null)} className="px-4 py-2 rounded bg-slate-800 text-white text-sm">Cancel</button>
                </div>
              </div>
            )
          )}
          {schedules.length === 0 && !form && <p className="text-slate-400 text-sm" data-testid="schedules-empty">No scheduled reports.</p>}
          {schedules.map(s => (
            <div key={s.id} className="flex items-center justify-between gap-3 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2" data-testid={`schedule-${s.name}`}>
              <div>
                <p className="text-slate-200">{s.name}</p>
                <p className="text-xs text-slate-400">{scheduleSummary(s)} · {s.recipients.join(', ')}
                  {s.last_sent && ` · last sent ${new Date(s.last_sent).toLocaleString()}`}
                  {s.last_error && <span className="text-red-300"> · last attempt failed: {s.last_error}</span>}
                </p>
              </div>
              <div className="flex gap-2 whitespace-nowrap">
                <button onClick={() => send(s)} className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-white text-xs inline-flex items-center gap-1"><Send className="w-3 h-3" /> Send now</button>
                <button aria-label={`Delete ${s.name}`} onClick={() => remove(s)} className="p-1 text-slate-400 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </section>
      </div>
    </DashboardLayout>
  )
}
