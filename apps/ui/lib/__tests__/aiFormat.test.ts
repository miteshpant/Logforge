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
    expect(parseLogsLink('?q=%7C+where+service+%3D+%22sshd%22&since=24h', now)).toEqual({
      query: '| where service = "sshd"', start: new Date('2026-11-18T12:00:00Z'), end: now })
    expect(parseLogsLink('?q=x&from=2026-11-19T10:00:00Z&to=2026-11-19T10:00:02Z', now)).toEqual({
      query: 'x', start: new Date('2026-11-19T10:00:00Z'), end: new Date('2026-11-19T10:00:02Z') })
  })
  it('ignores links without a query, and bad windows', () => {
    expect(parseLogsLink('', now)).toBeNull()
    expect(parseLogsLink('?since=1h', now)).toBeNull()
    expect(parseLogsLink('?q=x&since=forever', now)).toEqual({ query: 'x', start: null, end: null })
    expect(parseLogsLink('?q=x&from=garbage&to=2026-11-19T10:00:00Z', now)).toEqual({ query: 'x', start: null, end: null })
  })
})
