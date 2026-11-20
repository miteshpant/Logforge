'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Send } from 'lucide-react'
import { fetchTickets, replyTicket, updateTicket, type SupportTicket } from '@/lib/api'

const STATUSES = ['open', 'answered', 'closed'] as const
const PRIORITY_STYLE: Record<string, string> = {
  urgent: 'bg-red-100 text-red-800', high: 'bg-orange-100 text-orange-800',
  normal: 'bg-gray-100 text-gray-700', low: 'bg-gray-50 text-gray-500',
}

/** Tickets tenant members opened (Help, Contact support); answer, prioritise, close. */
export default function SupportPage() {
  const [status, setStatus] = useState<string>('open')
  const [tickets, setTickets] = useState<SupportTicket[] | null>(null)
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [selected, setSelected] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await fetchTickets(status || undefined)
      setTickets(data.tickets)
      setCounts(data.counts)
    } catch (e: any) {
      setError(e?.message || 'Could not load tickets')
      setTickets([])
    }
  }, [status])

  useEffect(() => { load() }, [load])

  const ticket = tickets?.find(t => t.id === selected) || null

  const replace = (t: SupportTicket) =>
    setTickets(list => (list || []).map(x => (x.id === t.id ? { ...x, ...t } : x)))

  const send = async () => {
    if (!ticket || !draft.trim()) return
    setBusy(true)
    setError(null)
    try {
      replace(await replyTicket(ticket.id, draft))
      setDraft('')
    } catch (e: any) {
      setError(e?.message || 'Could not send the reply')
    } finally {
      setBusy(false)
    }
  }

  const change = async (c: { status?: string; priority?: string }) => {
    if (!ticket) return
    try { replace(await updateTicket(ticket.id, c)) } catch (e: any) { setError(e?.message || 'Could not update the ticket') }
  }

  return (
    <div className="space-y-8">
      <Link href="/" className="text-blue-600 hover:text-blue-800 inline-flex items-center">
        <ArrowLeft className="h-4 w-4 mr-1" /> Back to Dashboard
      </Link>
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Support</h1>
        <p className="text-gray-600">Questions from tenants. A reply notifies the person who asked (bell, and email when SMTP is set up).</p>
      </div>
      {error && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">{error}</p>}

      <div className="flex gap-2" role="tablist">
        {[...STATUSES, ''].map(s => (
          <button key={s || 'all'} role="tab" aria-selected={status === s} data-testid={`tickets-${s || 'all'}`}
            onClick={() => { setStatus(s); setSelected(null) }}
            className={`px-3 py-1.5 rounded text-sm ${status === s ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border border-gray-300'}`}>
            {s || 'all'}{s && counts[s] !== undefined ? ` (${counts[s]})` : ''}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <section className="bg-white rounded-lg shadow divide-y" data-testid="ticket-list">
          {tickets === null && <div className="p-6"><Loader2 className="h-5 w-5 animate-spin text-gray-400" /></div>}
          {tickets?.length === 0 && <p className="p-6 text-sm text-gray-500">No {status} tickets.</p>}
          {tickets?.map(t => (
            <button key={t.id} onClick={() => setSelected(t.id)} data-testid="ticket-row"
              className={`w-full text-left p-4 hover:bg-gray-50 ${selected === t.id ? 'bg-blue-50' : ''}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-gray-900 truncate">{t.subject}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${PRIORITY_STYLE[t.priority]}`}>{t.priority}</span>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {t.tenant_name || t.tenant_id} · {t.created_by} · {t.status} · updated {t.updated_at.slice(0, 16).replace('T', ' ')}
              </div>
            </button>
          ))}
        </section>

        <section className="bg-white rounded-lg shadow p-6 space-y-4" data-testid="ticket-detail">
          {!ticket ? <p className="text-sm text-gray-500">Choose a ticket.</p> : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{ticket.subject}</h2>
                  <p className="text-xs text-gray-500">{ticket.tenant_name || ticket.tenant_id} · opened by {ticket.created_by} on {ticket.created_at.slice(0, 10)}</p>
                </div>
                <div className="flex gap-2 text-sm">
                  <select value={ticket.priority} onChange={e => change({ priority: e.target.value })} data-testid="ticket-priority"
                    className="border border-gray-300 rounded px-2 py-1 text-gray-900">
                    {['low', 'normal', 'high', 'urgent'].map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                  {ticket.status !== 'closed'
                    ? <button onClick={() => change({ status: 'closed' })} data-testid="ticket-close" className="px-3 py-1 rounded border border-gray-300 text-gray-700">Close</button>
                    : <button onClick={() => change({ status: 'open' })} className="px-3 py-1 rounded border border-gray-300 text-gray-700">Reopen</button>}
                </div>
              </div>
              <ol className="space-y-3 max-h-[28rem] overflow-y-auto">
                {ticket.messages.map((m, i) => (
                  <li key={i} className={`rounded p-3 text-sm ${m.from === 'support' ? 'bg-blue-50 ml-8' : 'bg-gray-50 mr-8'}`}>
                    <div className="text-xs text-gray-500 mb-1">{m.author} · {m.at.slice(0, 16).replace('T', ' ')}</div>
                    <p className="whitespace-pre-wrap text-gray-900">{m.text}</p>
                  </li>
                ))}
              </ol>
              <div className="flex gap-2">
                <textarea value={draft} onChange={e => setDraft(e.target.value)} rows={3} placeholder="Reply to the tenant"
                  data-testid="ticket-reply" className="flex-1 border border-gray-300 rounded p-2 text-sm text-gray-900" />
                <button onClick={send} disabled={busy || !draft.trim()} data-testid="ticket-send"
                  className="self-end inline-flex items-center gap-1 px-3 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50">
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Send
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
