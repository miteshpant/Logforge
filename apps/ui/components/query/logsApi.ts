/**
 * Local API bindings for the log search experience (LF-023/LF-024/LF-025).
 *
 * NOTE FOR WS-D: these methods belong in `lib/api` long-term. They live here
 * because `lib/api/**` is owned by another workstream right now — migrate them
 * into the shared client when that file is free.
 */

import { apiClient } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Raw record shape returned by `/v1/logs` and `/v1/query/logql`. */
export interface RawLogRecord {
  ts?: string
  timestamp?: string
  service?: string
  level?: string
  msg?: string
  message?: string
  host?: string
  trace_id?: string
  span_id?: string
  attrs?: Record<string, unknown>
  [key: string]: unknown
}

export interface NormalizedLog {
  id: string
  timestamp: string
  level: 'debug' | 'info' | 'warning' | 'error' | 'critical'
  service: string
  message: string
  host?: string
  trace_id?: string
  span_id?: string
  metadata?: Record<string, unknown>
}

export interface LogsPage {
  logs: NormalizedLog[]
  total: number | null
  offset: number
  limit: number
  hasMore: boolean
}

export interface LogQLResult {
  logs: NormalizedLog[]
  aggregations: Record<string, unknown>
  totalCount: number
  hasMore: boolean
  executionTimeMs: number | null
  /** Pipeline queries (Phase 6): events | table | timechart, with their columns and raw rows. */
  resultType: 'events' | 'table' | 'timechart' | null
  columns: string[]
  rows: Record<string, any>[]
  truncated: boolean
}

export type LiveTailStatus = 'idle' | 'connecting' | 'live' | 'reconnecting' | 'unavailable'

// ---------------------------------------------------------------------------
// Normalisation — the API speaks {ts, msg}, the UI speaks {timestamp, message}
// ---------------------------------------------------------------------------

const KNOWN_LEVELS = new Set(['debug', 'info', 'warning', 'error', 'critical'])

let idCounter = 0

export function normalizeLog(raw: RawLogRecord): NormalizedLog {
  const timestamp = String(raw.timestamp ?? raw.ts ?? '')
  const rawLevel = String(raw.level ?? 'info').toLowerCase()
  const level = (KNOWN_LEVELS.has(rawLevel) ? rawLevel : rawLevel === 'warn' ? 'warning' : 'info') as NormalizedLog['level']

  // Records carry no server id; build a stable-enough key from content plus a
  // monotonic counter so React keys never collide within a session.
  idCounter += 1
  const id = `${timestamp}|${raw.trace_id || ''}|${raw.span_id || ''}|${idCounter}`

  const metadata: Record<string, unknown> = {}
  if (raw.attrs && typeof raw.attrs === 'object') Object.assign(metadata, raw.attrs)
  if (raw.host) metadata.host = raw.host

  return {
    id,
    timestamp,
    level,
    service: String(raw.service ?? 'unknown'),
    message: String(raw.message ?? raw.msg ?? ''),
    host: raw.host,
    trace_id: raw.trace_id || undefined,
    span_id: raw.span_id || undefined,
    metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
  }
}

// ---------------------------------------------------------------------------
// GET /v1/logs — paginated simple retrieval (LF-025)
// ---------------------------------------------------------------------------

export interface FetchLogsParams {
  start_time?: string
  end_time?: string
  service?: string
  level?: string
  limit: number
  offset: number
}

export async function fetchLogs(params: FetchLogsParams): Promise<LogsPage> {
  // apiClient.get takes an AxiosRequestConfig — query params must go under
  // `params` (the previous page passed them as top-level config keys, so
  // filters and limit were silently never sent).
  const response = await apiClient.get('/v1/logs', { params })
  const data = (response as any)?.data ?? response

  const rawLogs: RawLogRecord[] = Array.isArray(data?.logs)
    ? data.logs
    : Array.isArray(data)
      ? data
      : []
  const logs = rawLogs.map(normalizeLog)

  const total = typeof data?.total === 'number' ? data.total : null
  const offset = typeof data?.offset === 'number' ? data.offset : params.offset
  const limit = typeof data?.limit === 'number' ? data.limit : params.limit

  const hasMore =
    total !== null ? offset + rawLogs.length < total : rawLogs.length >= limit

  return { logs, total, offset, limit, hasMore }
}

// ---------------------------------------------------------------------------
// POST /v1/query/logql — LogforgeQL execution (LF-023)
// ---------------------------------------------------------------------------

/** True when the query carries its own `| last <duration>` window. */
export function queryHasLastStage(query: string): boolean {
  return /(^|\|)\s*last\s+\d+\s*[smhdw]\s*(\||$)/i.test(query)
}

export class LogQLError extends Error {
  public readonly status: number
  public readonly isSyntaxError: boolean

  constructor(message: string, status: number) {
    super(message)
    this.name = 'LogQLError'
    this.status = status
    this.isSyntaxError = status === 400
  }
}

export async function runLogQL(
  query: string,
  timeRange: { start_time: string; end_time: string }
): Promise<LogQLResult> {
  const body: Record<string, unknown> = { query }
  // A `| last 15m` stage resolves its own window server-side; sending the
  // global range too would override it (the router prefers body times).
  if (!queryHasLastStage(query)) {
    body.start_time = timeRange.start_time
    body.end_time = timeRange.end_time
  }

  let data: any
  try {
    const response = await apiClient.post('/v1/query/logql', body)
    data = (response as any)?.data ?? response
  } catch (error: any) {
    const status = error?.response?.status ?? 0
    const detail = error?.response?.data?.detail
    throw new LogQLError(
      typeof detail === 'string'
        ? detail
        : detail
          ? JSON.stringify(detail)
          : error?.message || 'LogQL query failed',
      status
    )
  }

  const rawLogs: RawLogRecord[] = Array.isArray(data?.logs) ? data.logs : []

  return {
    logs: rawLogs.map(normalizeLog),
    aggregations:
      data?.aggregations && typeof data.aggregations === 'object'
        ? data.aggregations
        : {},
    totalCount: typeof data?.total_count === 'number' ? data.total_count : rawLogs.length,
    hasMore: Boolean(data?.has_more),
    executionTimeMs:
      typeof data?.execution_time_ms === 'number' ? data.execution_time_ms : null,
    resultType:
      data?.result_type === 'events' || data?.result_type === 'table' || data?.result_type === 'timechart'
        ? data.result_type
        : null,
    columns: Array.isArray(data?.columns) ? data.columns : [],
    rows: Array.isArray(data?.logs) ? data.logs : [],
    truncated: Boolean(data?.truncated),
  }
}

// ---------------------------------------------------------------------------
// GET /v1/observability/metrics/services — service-name autocomplete source
// ---------------------------------------------------------------------------

export async function fetchServiceNames(): Promise<string[]> {
  const response = await apiClient.get('/v1/observability/metrics/services')
  const data = (response as any)?.data ?? response
  if (Array.isArray(data?.services)) {
    return data.services.filter((s: unknown): s is string => typeof s === 'string')
  }
  return []
}

// ---------------------------------------------------------------------------
// GET /v1/stream/logs — SSE live tail (LF-024)
//
// Contract per LF-024: the backend route is being added to
// `apps/api/routers/streaming_api.py` (owned by WS-D). Until it lands, the
// stream reports `unavailable` — the UI must show that state honestly and
// keep retrying with backoff; it must NEVER synthesise lines.
// ---------------------------------------------------------------------------

export interface StreamLogsFilters {
  service?: string
  level?: string
}

export function streamLogs(
  filters: StreamLogsFilters,
  onLog: (log: NormalizedLog) => void,
  onError: (error: Error) => void
): Promise<() => void> {
  const params = new URLSearchParams()
  if (filters.service) params.set('service', filters.service)
  if (filters.level) params.set('level', filters.level)
  const qs = params.toString()
  const endpoint = `/v1/stream/logs${qs ? `?${qs}` : ''}`

  return apiClient.getStream(
    endpoint,
    (data: any) => {
      // The stream multiplexes status/heartbeat events with log events; only
      // forward things that actually look like a log record.
      const candidate = data?.log ?? data
      if (
        candidate &&
        typeof candidate === 'object' &&
        (candidate.msg !== undefined || candidate.message !== undefined) &&
        (candidate.ts !== undefined || candidate.timestamp !== undefined)
      ) {
        onLog(normalizeLog(candidate as RawLogRecord))
      }
    },
    onError
  )
}
