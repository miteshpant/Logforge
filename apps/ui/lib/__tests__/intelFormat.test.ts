/**
 * Formatting for the threat intel page (Phase 3).
 */
import { describe, expect, it } from 'vitest'
import { feedStatus, threatBadge } from '../intelFormat'

const NOW = new Date('2026-11-18T12:00:00Z')

describe('feedStatus', () => {
  it('says when a feed last ran and how it went', () => {
    expect(feedStatus({ enabled: true, last_status: 'never', last_run_at: null, last_count: 0, last_error: '' }, NOW))
      .toEqual({ tone: 'idle', text: 'Not run yet' })
    expect(feedStatus({ enabled: true, last_status: 'ok', last_run_at: '2026-11-18T11:45:00Z', last_count: 1234, last_error: '' }, NOW))
      .toEqual({ tone: 'ok', text: '1,234 indicators · 15m ago' })
    expect(feedStatus({ enabled: true, last_status: 'error', last_run_at: '2026-11-18T11:58:00Z', last_count: 0,
      last_error: 'HTTP 410 from the feed' }, NOW))
      .toEqual({ tone: 'error', text: 'Failed 2m ago: HTTP 410 from the feed' })
    expect(feedStatus({ enabled: false, last_status: 'ok', last_run_at: null, last_count: 5, last_error: '' }, NOW))
      .toEqual({ tone: 'idle', text: 'Disabled' })
  })
})

describe('threatBadge', () => {
  it('summarises an alert or event threat stamp', () => {
    expect(threatBadge(undefined)).toBeNull()
    expect(threatBadge({ max_confidence: 90, threat_types: ['botnet_cc'], sources: ['abuse.ch Feodo Tracker'] }))
      .toBe('Known botnet C2 · abuse.ch Feodo Tracker · 90%')
    expect(threatBadge({ max_confidence: 60, threat_types: ['malware_download', 'phishing'], sources: [] }))
      .toBe('Known malware download, phishing · 60%')
  })
})
