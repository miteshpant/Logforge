/**
 * The signed-in user's notifications: /v1/inbox (case @mentions and
 * assignments).
 */
import { apiClient } from '../api'

export interface InboxItem {
  id: string
  kind: 'mention' | 'assigned' | string
  title: string
  body: string
  link: string
  actor: string
  read: boolean
  created_at: string
}

export async function listInbox(limit = 20): Promise<{ items: InboxItem[]; unread: number }> {
  const response = await apiClient.get<{ items: InboxItem[]; unread: number }>('/v1/inbox', { limit })
  if (!response.success) throw new Error(response.error || 'Could not load notifications')
  return response.data as { items: InboxItem[]; unread: number }
}

export async function markRead(ids?: string[]): Promise<number> {
  const response = await apiClient.post<{ marked: number }>('/v1/inbox/read', ids ? { ids } : {})
  if (!response.success) throw new Error(response.error || 'Could not mark notifications read')
  return (response.data as { marked: number }).marked
}
