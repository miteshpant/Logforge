'use client'

import { useEffect, useState } from 'react'
import { Ticket } from 'lucide-react'
import { caseTickets, type CaseTicket } from '@/lib/api/response'

/**
 * The Jira or GitHub tickets playbooks opened for a case (Phase 13). Each
 * follows the case: resolving one resolves the other.
 */
export default function CaseTickets({ caseId, refreshKey }: { caseId: string; refreshKey?: unknown }) {
  const [tickets, setTickets] = useState<CaseTicket[]>([])

  useEffect(() => {
    let live = true
    caseTickets(caseId).then(out => { if (live) setTickets(out.tickets) }).catch(() => { if (live) setTickets([]) })
    return () => { live = false }
  }, [caseId, refreshKey])

  if (tickets.length === 0) return null
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Ticket className="w-4 h-4" /> Tickets</h2>
      <ul className="space-y-1 text-sm" data-testid="case-tickets">
        {tickets.map(t => (
          <li key={`${t.system}-${t.ticket}`} className="flex items-center justify-between gap-2" data-testid="case-ticket">
            <a href={t.url} target="_blank" rel="noreferrer" className="text-blue-300 hover:underline">{t.ticket}</a>
            <span className="text-xs text-slate-400">{t.system} · {t.ticket_status}
              {t.synced_at && <> · synced {new Date(t.synced_at).toLocaleString()}</>}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
