/** Support tickets: /v1/support/tickets (any member of the tenant). */
import { apiClient } from '../api'

export interface TicketMessage { author: string; from: 'customer' | 'support'; text: string; at: string }
export interface Ticket {
  id: string
  subject: string
  status: 'open' | 'answered' | 'closed'
  priority: 'low' | 'normal' | 'high' | 'urgent'
  created_by: string
  created_at: string
  updated_at: string
  messages: TicketMessage[]
}

const BASE = '/v1/support/tickets'

export async function listTickets(): Promise<Ticket[]> {
  const r = await apiClient.get<{ tickets: Ticket[] }>(BASE)
  if (!r.success) throw new Error(r.error || 'Could not load tickets')
  return (r.data as { tickets: Ticket[] }).tickets
}

export const openTicket = async (body: { subject: string; text: string; priority: string }) =>
  (await apiClient.post<Ticket>(BASE, body)).data as Ticket

export const replyTicket = async (id: string, text: string) =>
  (await apiClient.post<Ticket>(`${BASE}/${encodeURIComponent(id)}/messages`, { text })).data as Ticket

export const closeTicket = async (id: string) =>
  (await apiClient.post<Ticket>(`${BASE}/${encodeURIComponent(id)}/close`, {})).data as Ticket
