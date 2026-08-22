'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  LiveTailStatus,
  NormalizedLog,
  StreamLogsFilters,
  streamLogs,
} from './logsApi'

/** Bound the in-memory tail so long sessions stay responsive (LF-024). */
const MAX_BUFFER = 2000
/** Reconnect backoff: 1s, 2s, 4s ... capped. */
const BACKOFF_BASE_MS = 1000
const BACKOFF_MAX_MS = 30000
/** Batch prepends so a burst of events causes one render, not hundreds. */
const FLUSH_INTERVAL_MS = 250

export interface LiveTail {
  logs: NormalizedLog[]
  status: LiveTailStatus
  error: string | null
  start: () => void
  stop: () => void
  clear: () => void
}

/**
 * Live tail over `GET /v1/stream/logs` (LF-024).
 *
 * - Prepends arriving lines (list is newest-first), capped at MAX_BUFFER.
 * - Reconnects with exponential backoff and surfaces the disconnected state;
 *   it never synthesises lines.
 * - `filters` are passed to the stream and re-applied client-side, so a
 *   filter change mid-tail takes effect immediately.
 */
export function useLiveTail(filters: StreamLogsFilters): LiveTail {
  const [logs, setLogs] = useState<NormalizedLog[]>([])
  const [status, setStatus] = useState<LiveTailStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  const enabledRef = useRef(false)
  const stopStreamRef = useRef<(() => void) | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const flushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pendingRef = useRef<NormalizedLog[]>([])
  const attemptRef = useRef(0)
  const filtersRef = useRef(filters)
  filtersRef.current = filters

  const teardown = useCallback(() => {
    if (stopStreamRef.current) {
      stopStreamRef.current()
      stopStreamRef.current = null
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (flushTimerRef.current) {
      clearInterval(flushTimerRef.current)
      flushTimerRef.current = null
    }
    pendingRef.current = []
  }, [])

  const connect = useCallback(async () => {
    if (!enabledRef.current) return

    setStatus(attemptRef.current === 0 ? 'connecting' : 'reconnecting')

    const scheduleReconnect = () => {
      if (!enabledRef.current) return
      const delay = Math.min(
        BACKOFF_BASE_MS * 2 ** attemptRef.current,
        BACKOFF_MAX_MS
      )
      attemptRef.current += 1
      setStatus('unavailable')
      reconnectTimerRef.current = setTimeout(() => {
        if (stopStreamRef.current) {
          stopStreamRef.current()
          stopStreamRef.current = null
        }
        connect()
      }, delay)
    }

    try {
      let receivedAny = false
      const stop = await streamLogs(
        filtersRef.current,
        log => {
          if (!enabledRef.current) return
          if (!receivedAny) {
            receivedAny = true
          }
          // Any event proves the connection is live.
          attemptRef.current = 0
          setStatus('live')
          setError(null)
          pendingRef.current.push(log)
        },
        streamError => {
          if (!enabledRef.current) return
          setError(streamError.message)
          scheduleReconnect()
        }
      )
      stopStreamRef.current = stop
      // The fetch resolved and the stream is being read; report connected
      // until an error says otherwise.
      if (enabledRef.current && attemptRef.current === 0) {
        setStatus('live')
      }
    } catch (connectError: any) {
      if (!enabledRef.current) return
      setError(connectError?.message || 'Failed to open log stream')
      scheduleReconnect()
    }
  }, [])

  const start = useCallback(() => {
    if (enabledRef.current) return
    enabledRef.current = true
    attemptRef.current = 0
    setError(null)
    setLogs([])

    // Flush pending events in batches.
    flushTimerRef.current = setInterval(() => {
      if (pendingRef.current.length === 0) return
      const batch = pendingRef.current
      pendingRef.current = []
      setLogs(prev => {
        const next = [...batch.reverse(), ...prev]
        return next.length > MAX_BUFFER ? next.slice(0, MAX_BUFFER) : next
      })
    }, FLUSH_INTERVAL_MS)

    connect()
  }, [connect])

  const stop = useCallback(() => {
    enabledRef.current = false
    teardown()
    setStatus('idle')
  }, [teardown])

  const clear = useCallback(() => setLogs([]), [])

  // Restart the stream when filters change mid-tail.
  const filterKey = `${filters.service ?? ''}|${filters.level ?? ''}`
  const previousFilterKeyRef = useRef(filterKey)
  useEffect(() => {
    if (previousFilterKeyRef.current === filterKey) return
    previousFilterKeyRef.current = filterKey
    if (!enabledRef.current) return
    if (stopStreamRef.current) {
      stopStreamRef.current()
      stopStreamRef.current = null
    }
    attemptRef.current = 0
    connect()
  }, [filterKey, connect])

  // Teardown on unmount.
  useEffect(() => {
    return () => {
      enabledRef.current = false
      teardown()
    }
  }, [teardown])

  return { logs, status, error, start, stop, clear }
}
