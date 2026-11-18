/**
 * Formatting helpers for the case pages (Phase 2).
 */
import { describe, expect, it } from 'vitest'
import { describeEvent, formatMinutes, nextStatuses, needsReason, evidenceHref } from '../caseFormat'

const ev = (kind: string, data: Record<string, unknown> = {}, actor = 'alice') =>
  ({ id: '1', case_id: 'c', ts: '2026-11-18T09:00:00Z', actor, kind, data })

describe('describeEvent', () => {
  it('describes every timeline event kind', () => {
    expect(describeEvent(ev('created', { title: 'Brute force' }))).toBe('alice opened the case')
    expect(describeEvent(ev('alert_attached', { title: 'Brute force', severity: 'high' }, 'system')))
      .toBe('Alert added: Brute force (high)')
    expect(describeEvent(ev('assigned', { from: null, to: 'bob' }))).toBe('alice assigned the case to bob')
    expect(describeEvent(ev('assigned', { from: 'bob', to: null }))).toBe('alice unassigned the case')
    expect(describeEvent(ev('status_changed', { from: 'new', to: 'false_positive', reason: 'pentest' })))
      .toBe('alice changed status from new to false positive: pentest')
    expect(describeEvent(ev('comment', { text: 'hi' }))).toBe('alice commented')
    expect(describeEvent(ev('evidence_pinned', { kind: 'search', title: 'Failed logins' })))
      .toBe('alice pinned search: Failed logins')
    expect(describeEvent(ev('tags_changed', { from: [], to: ['ssh'] }))).toBe('alice set tags: ssh')
    expect(describeEvent(ev('merged', { sources: ['a', 'b'] }))).toBe('alice merged 2 cases into this one')
    expect(describeEvent(ev('merged_into', { target: 'c9' }))).toBe('alice merged this case into c9')
    expect(describeEvent(ev('split', { alert_ids: ['x'], new_case: 'c2' }))).toBe('alice moved 1 alert to c2')
    expect(describeEvent(ev('split_from', { case_id: 'c1' }))).toBe('alice split this case from c1')
    expect(describeEvent(ev('updated', { severity: { from: 'low', to: 'high' } }))).toBe('alice updated severity')
    expect(describeEvent(ev('something_new'))).toBe('alice: something new')
  })
})

describe('workflow', () => {
  it('offers the statuses a case can move to', () => {
    expect(nextStatuses('new')).toEqual(['investigating', 'contained', 'resolved', 'false_positive'])
    expect(nextStatuses('resolved')).toEqual(['investigating'])
    expect(nextStatuses('false_positive')).toEqual(['investigating'])
  })
  it('requires a reason to close', () => {
    expect(needsReason('resolved')).toBe(true)
    expect(needsReason('false_positive')).toBe(true)
    expect(needsReason('contained')).toBe(false)
  })
})

describe('formatMinutes', () => {
  it('formats durations', () => {
    expect(formatMinutes(null)).toBe('—')
    expect(formatMinutes(0.4)).toBe('<1m')
    expect(formatMinutes(42)).toBe('42m')
    expect(formatMinutes(135)).toBe('2h 15m')
    expect(formatMinutes(60 * 49)).toBe('2d 1h')
  })
})

describe('evidenceHref', () => {
  it('links searches to the Log Explorer and traces to the trace view', () => {
    expect(evidenceHref({ kind: 'search', ref: 'src_ip:1.2.3.4' })).toBe('/observability/logs?q=src_ip%3A1.2.3.4')
    expect(evidenceHref({ kind: 'trace', ref: 'abc' })).toBe('/observability/traces?trace_id=abc')
    expect(evidenceHref({ kind: 'link', ref: 'https://example.com/x' })).toBe('https://example.com/x')
    expect(evidenceHref({ kind: 'link', ref: 'javascript:alert(1)' })).toBeNull()
    expect(evidenceHref({ kind: 'event', ref: 'e1' })).toBeNull()
  })
})
