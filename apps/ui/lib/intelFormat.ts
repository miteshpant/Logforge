/**
 * Formatting helpers for threat intelligence in the UI (Phase 3).
 */
import { formatMinutes } from './caseFormat'

export interface FeedRunState {
  enabled: boolean
  last_status: string
  last_run_at: string | null
  last_count: number
  last_error: string
}

export function feedStatus(feed: FeedRunState, now: Date = new Date()): { tone: 'ok' | 'error' | 'idle'; text: string } {
  if (!feed.enabled) return { tone: 'idle', text: 'Disabled' }
  if (!feed.last_run_at || feed.last_status === 'never') return { tone: 'idle', text: 'Not run yet' }
  const ago = `${formatMinutes((now.getTime() - new Date(feed.last_run_at).getTime()) / 60000)} ago`
  if (feed.last_status === 'error') return { tone: 'error', text: `Failed ${ago}: ${feed.last_error}` }
  return { tone: 'ok', text: `${feed.last_count.toLocaleString('en-US')} indicators · ${ago}` }
}

const THREAT_LABELS: Record<string, string> = {
  botnet_cc: 'botnet C2',
  malware_download: 'malware download',
  payload: 'malware payload',
}

export interface ThreatSummary { max_confidence?: number | null; threat_types?: string[]; sources?: string[] }

/** One line for an intel badge, or null when nothing matched. */
export function threatBadge(threat: ThreatSummary | undefined | null): string | null {
  if (!threat) return null
  const types = (threat.threat_types || []).map(t => THREAT_LABELS[t] || t.replace(/_/g, ' ')).join(', ') || 'malicious'
  const parts = [`Known ${types}`]
  if (threat.sources && threat.sources.length) parts.push(threat.sources.join(', '))
  if (threat.max_confidence !== undefined && threat.max_confidence !== null) parts.push(`${threat.max_confidence}%`)
  return parts.join(' · ')
}
