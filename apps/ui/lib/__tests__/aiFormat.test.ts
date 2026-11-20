import { describe, expect, it } from 'vitest'
import { flagMessages, parseLogsLink, providerNotice, splitCitations } from '../aiFormat'

describe('splitCitations', () => {
  it('splits answer text into text and citation segments', () => {
    expect(splitCitations('Logins failed 40 times [C1]. Mostly root [C2][C3].')).toEqual([
      { text: 'Logins failed 40 times ' }, { cite: 'C1' }, { text: '. Mostly root ' }, { cite: 'C2' }, { cite: 'C3' },
      { text: '.' },
    ])
    expect(splitCitations('No citations here')).toEqual([{ text: 'No citations here' }])
    expect(splitCitations('')).toEqual([])
  })
})

describe('flagMessages', () => {
  it('explains each flag in plain words', () => {
    const msgs = flagMessages(['uncited_sentences', 'unknown_citations', 'no_citations', 'refused', 'tool_limit'])
    expect(msgs).toHaveLength(5)
    expect(msgs[0]).toMatch(/unverified/)
    expect(flagMessages([])).toEqual([])
    expect(flagMessages(['something_new'])).toEqual(['something_new'])
  })
})

describe('providerNotice', () => {
  it('says when data left the deployment', () => {
    expect(providerNotice({ name: 'claude', label: 'Claude (Anthropic)', model: 'claude-opus-5-5', external: true }))
      .toEqual({ external: true, text: 'External model: Claude (Anthropic) (claude-opus-5-5)' })
    expect(providerNotice({ name: 'local', label: 'local', model: 'llama3.1', external: false }).text)
      .toBe('Model in this deployment: local (llama3.1)')
    expect(providerNotice(null)).toEqual({ external: false, text: 'No model: rule-based answer' })
  })
})

describe('parseLogsLink', () => {
  const now = new Date('2026-11-19T12:00:00Z')
  it('reads a query and a window from the URL', () => {
    expect(parseLogsLink('?logql=%7C+where+service+%3D+%22sshd%22&since=24h', now)).toEqual({
      query: '| where service = "sshd"', start: new Date('2026-11-18T12:00:00Z'), end: now })
    expect(parseLogsLink('?logql=x&from=2026-11-19T10:00:00Z&to=2026-11-19T10:00:02Z', now)).toEqual({
      query: 'x', start: new Date('2026-11-19T10:00:00Z'), end: new Date('2026-11-19T10:00:02Z') })
  })
  it('ignores links without a query, and bad windows', () => {
    expect(parseLogsLink('', now)).toBeNull()
    expect(parseLogsLink('?q=198.51.100.7', now)).toBeNull()  // the filter search, not a query link
    expect(parseLogsLink('?since=1h', now)).toBeNull()
    expect(parseLogsLink('?logql=x&since=forever', now)).toEqual({ query: 'x', start: null, end: null })
    expect(parseLogsLink('?logql=x&from=garbage&to=2026-11-19T10:00:00Z', now)).toEqual({ query: 'x', start: null, end: null })
  })
})

// -- Phase 9 ---------------------------------------------------------------------------
import { draftSummary, eventForExplain, fallbackLabel } from '../aiFormat'

describe('fallbackLabel', () => {
  it('says how an answer was made without a model', () => {
    expect(fallbackLabel('rule_based')).toBe('Rule-based draft (AI off)')
    expect(fallbackLabel('template')).toBe('Built from the evidence, without AI')
    expect(fallbackLabel('heuristic')).toBe('Heuristic draft, without AI')
    expect(fallbackLabel('ai')).toBeNull()
  })
})

describe('Phase 9 flags', () => {
  it('explains the new flags', () => {
    expect(flagMessages(['model_answer_unusable'])[0]).toMatch(/nothing usable/)
    expect(flagMessages(['heuristic_parsed_more'])[0]).toMatch(/heuristic draft parsed more/)
    expect(flagMessages(['related_activity_not_permitted'])[0]).toMatch(/permission/)
  })
})

describe('draftSummary', () => {
  it('summarises a simulation report', () => {
    expect(draftSummary({ valid: true, parsed: 6, total: 6, fields: { a: 1, b: 2 }, failures: [], error: null }))
      .toBe('Parsed 6 of 6 lines, 2 fields')
    expect(draftSummary({ valid: true, parsed: 1, total: 3, fields: { a: 1 }, failures: [], error: null }))
      .toBe('Parsed 1 of 3 lines, 1 field')
    expect(draftSummary({ valid: false, parsed: 0, total: 3, fields: {}, failures: [], error: 'bad grok' }))
      .toBe('Invalid: bad grok')
  })
})

describe('eventForExplain', () => {
  it('turns a Log Explorer row back into the event the API stores', () => {
    const row = {
      id: 'x', timestamp: '2026-11-19T10:00:00Z', level: 'warning', service: 'sshd', message: 'Failed password',
      host: 'web-01', trace_id: 't1',
      metadata: { host: 'web-01', src_ip: '203.0.113.5', user_id: 'root', status: 401, port: 22 },
    }
    const event = eventForExplain(row)
    expect(event).toEqual({
      ts: '2026-11-19T10:00:00Z', level: 'warn', service: 'sshd', msg: 'Failed password', host: 'web-01',
      trace_id: 't1', src_ip: '203.0.113.5', user_id: 'root', status: 401,
      attrs: { src_ip: '203.0.113.5', user_id: 'root', status: 401, port: 22 },
    })
  })
})
