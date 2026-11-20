'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { Bell } from 'lucide-react'
import { listInbox, markRead, type InboxItem } from '@/lib/api/inbox'

const POLL_MS = 60_000

function ago(iso: string): string {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z').getTime()) / 60_000))
  if (minutes < 60) return `${minutes} min ago`
  if (minutes < 48 * 60) return `${Math.round(minutes / 60)} h ago`
  return `${Math.round(minutes / 1440)} d ago`
}

/** Bell with the unread count; opens the latest notifications. */
export default function InboxBell() {
  const [items, setItems] = useState<InboxItem[]>([])
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  const load = useCallback(async () => {
    try {
      const inbox = await listInbox()
      setItems(inbox.items)
      setUnread(inbox.unread)
    } catch {
      // Notifications are secondary: keep the last state rather than break the header.
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, POLL_MS)
    return () => clearInterval(timer)
  }, [load])

  useEffect(() => {
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const readOne = async (item: InboxItem) => {
    setOpen(false)
    if (!item.read) {
      setItems(list => list.map(i => (i.id === item.id ? { ...i, read: true } : i)))
      setUnread(n => Math.max(0, n - 1))
      try { await markRead([item.id]) } catch { load() }
    }
  }

  const readAll = async () => {
    setItems(list => list.map(i => ({ ...i, read: true })))
    setUnread(0)
    try { await markRead() } catch { load() }
  }

  return (
    <div className="relative" ref={box}>
      <button data-testid="inbox-bell" aria-label={`Notifications, ${unread} unread`}
        onClick={() => { setOpen(o => !o); if (!open) load() }}
        className="relative p-2 rounded hover:bg-white/5 text-slate-300">
        <Bell className="w-5 h-5" />
        {unread > 0 && (
          <span data-testid="inbox-unread"
            className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[11px] leading-[18px] text-center">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div data-testid="inbox-panel"
          className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-50">
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700">
            <span className="text-sm font-medium text-white">Notifications</span>
            {unread > 0 && (
              <button data-testid="inbox-read-all" onClick={readAll} className="text-xs text-blue-400 hover:text-blue-300">
                Mark all read
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="px-3 py-6 text-sm text-slate-400 text-center">Nothing yet. You&apos;ll see case mentions and assignments here.</p>
          ) : (
            <ul className="max-h-96 overflow-y-auto divide-y divide-slate-800">
              {items.map(item => (
                <li key={item.id}>
                  <Link href={item.link} onClick={() => readOne(item)} data-testid="inbox-item"
                    className={`block px-3 py-2 hover:bg-slate-800 ${item.read ? 'opacity-60' : ''}`}>
                    <p className="text-sm text-white">{item.title}</p>
                    {item.kind === 'mention' && <p className="text-xs text-slate-400 truncate">{item.body}</p>}
                    <p className="text-[11px] text-slate-500 mt-0.5">{ago(item.created_at)}</p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
