'use client'

import { useCallback, useEffect, useState } from 'react'
import { LifeBuoy, Loader2, Plus, Send } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { closeTicket, listTickets, openTicket, replyTicket, type Ticket } from '@/lib/api/support'

const STATUS_STYLE: Record<string, string> = {
  open: 'bg-amber-500/15 text-amber-300', answered: 'bg-emerald-500/15 text-emerald-300', closed: 'bg-slate-600/30 text-slate-400',
}

/** Ask the platform's support; answers arrive here and under the bell. */
export default function SupportPage() {
  const [tickets, setTickets] = useState<Ticket[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [composing, setComposing] = useState(false)
  const [form, setForm] = useState({ subject: '', text: '', priority: 'normal' })
  const [reply, setReply] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try { setTickets(await listTickets()) } catch (e: any) { setError(e?.message || 'Could not load tickets'); setTickets([]) }
  }, [])
  useEffect(() => { load() }, [load])

  const ticket = tickets?.find(t => t.id === selected) || null
  const put = (t: Ticket) => setTickets(list => [t, ...(list || []).filter(x => x.id !== t.id)])

  const act = async (fn: () => Promise<Ticket>, after?: () => void) => {
    setBusy(true)
    setError(null)
    try { const t = await fn(); put(t); setSelected(t.id); after?.() } catch (e: any) { setError(e?.message || 'Something went wrong') } finally { setBusy(false) }
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2"><LifeBuoy className="w-6 h-6" /> Support</h1>
            <p className="text-slate-400 mt-1">Ask the Logforge team. You&apos;re notified when they answer.</p>
          </div>
          <button data-testid="ticket-new" onClick={() => { setComposing(true); setSelected(null) }}
            className="px-3 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm inline-flex items-center gap-1"><Plus className="w-4 h-4" /> New ticket</button>
        </div>
        {error && <p className="text-sm text-red-400" data-testid="support-error">{error}</p>}

        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <section className="rounded-lg border border-white/10 bg-slate-900/60 divide-y divide-white/5">
            {tickets === null && <div className="p-6"><Loader2 className="w-5 h-5 animate-spin text-slate-400" /></div>}
            {tickets?.length === 0 && <p className="p-6 text-sm text-slate-400">No tickets yet.</p>}
            {tickets?.map(t => (
              <button key={t.id} data-testid="ticket-row" onClick={() => { setSelected(t.id); setComposing(false) }}
                className={`w-full text-left p-4 hover:bg-white/5 ${selected === t.id ? 'bg-white/5' : ''}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-white truncate">{t.subject}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${STATUS_STYLE[t.status]}`} data-testid="ticket-status">{t.status}</span>
                </div>
                <p className="text-xs text-slate-500 mt-1">{t.created_by} · {t.priority} · updated {t.updated_at.slice(0, 16).replace('T', ' ')}</p>
              </button>
            ))}
          </section>

          <section className="rounded-lg border border-white/10 bg-slate-900/60 p-5 space-y-4">
            {composing ? (
              <form className="space-y-3" onSubmit={e => { e.preventDefault(); act(() => openTicket(form), () => { setComposing(false); setForm({ subject: '', text: '', priority: 'normal' }) }) }}>
                <input data-testid="ticket-subject" required minLength={3} maxLength={200} placeholder="Subject" value={form.subject}
                  onChange={e => setForm({ ...form, subject: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white" />
                <textarea data-testid="ticket-text" required rows={6} placeholder="What happened, and what did you expect?" value={form.text}
                  onChange={e => setForm({ ...form, text: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white" />
                <div className="flex items-center justify-between">
                  <label className="text-sm text-slate-400">Priority
                    <select value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}
                      className="ml-2 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white">
                      {['low', 'normal', 'high', 'urgent'].map(p => <option key={p}>{p}</option>)}
                    </select>
                  </label>
                  <button data-testid="ticket-submit" disabled={busy} className="px-3 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm disabled:opacity-50">Send</button>
                </div>
              </form>
            ) : !ticket ? <p className="text-sm text-slate-400">Choose a ticket, or open a new one.</p> : (
              <>
                <div className="flex items-start justify-between gap-2">
                  <h2 className="text-lg font-semibold text-white">{ticket.subject}</h2>
                  {ticket.status !== 'closed' && (
                    <button onClick={() => act(() => closeTicket(ticket.id))} data-testid="ticket-close"
                      className="text-sm px-3 py-1 rounded border border-slate-600 text-slate-300 hover:bg-white/5">Close</button>
                  )}
                </div>
                <ol className="space-y-3 max-h-[28rem] overflow-y-auto" data-testid="ticket-messages">
                  {ticket.messages.map((m, i) => (
                    <li key={i} className={`rounded p-3 text-sm ${m.from === 'support' ? 'bg-blue-500/10 mr-8' : 'bg-slate-800 ml-8'}`}>
                      <p className="text-xs text-slate-500 mb-1">{m.from === 'support' ? m.author : 'You'} · {m.at.slice(0, 16).replace('T', ' ')}</p>
                      <p className="whitespace-pre-wrap text-slate-200">{m.text}</p>
                    </li>
                  ))}
                </ol>
                {ticket.status === 'closed' ? <p className="text-sm text-slate-500">Closed. Open a new ticket for anything else.</p> : (
                  <div className="flex gap-2">
                    <textarea value={reply} onChange={e => setReply(e.target.value)} rows={2} placeholder="Reply"
                      data-testid="ticket-reply" className="flex-1 bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm" />
                    <button disabled={busy || !reply.trim()} onClick={() => act(() => replyTicket(ticket.id, reply), () => setReply(''))}
                      className="self-end px-3 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50 inline-flex items-center gap-1"><Send className="w-4 h-4" /> Send</button>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </DashboardLayout>
  )
}
