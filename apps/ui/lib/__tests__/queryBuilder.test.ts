import { describe, expect, it } from 'vitest'
import { buildQuery, type QuerySpec } from '../queryBuilder'
import { getSuggestions, LOGQL_STAGES } from '../../components/query/logqlSyntax'

const base: QuerySpec = { search: '', filters: [], aggregations: [], groupBy: [], span: '', sort: '', limit: null }

describe('buildQuery', () => {
  it('writes filters, a stats stage and a sort', () => {
    expect(buildQuery({
      ...base,
      filters: [{ field: 'service', op: '=', value: 'checkout' }, { field: 'status', op: '>=', value: '500' }],
      aggregations: [{ fn: 'count', field: '', as: 'errors' }, { fn: 'p95', field: 'http_response_time_ms', as: '' }],
      groupBy: ['host'], sort: '-errors', limit: 10,
    })).toBe('| where service = "checkout" and status >= 500 | stats count() as errors, '
      + 'p95(http_response_time_ms) by host | sort -errors | head 10')
  })

  it('uses timechart when a span is chosen', () => {
    expect(buildQuery({ ...base, aggregations: [{ fn: 'count', field: '', as: '' }], groupBy: ['service'], span: '1h' }))
      .toBe('| timechart span=1h count() by service')
  })

  it('quotes text, keeps numbers, and handles lists and text operators', () => {
    expect(buildQuery({
      ...base, search: 'connection reset',
      filters: [{ field: 'level', op: 'in', value: 'error, fatal' }, { field: 'msg', op: 'contains', value: 'say "hi"' },
        { field: 'attrs.code', op: '!=', value: '0042' }],
    })).toBe('"connection reset" | where level in ["error", "fatal"] and msg contains "say \\"hi\\"" '
      + 'and attrs.code != "0042"')
  })

  it('returns an empty query for an empty spec, and skips incomplete rows', () => {
    expect(buildQuery(base)).toBe('')
    expect(buildQuery({ ...base, filters: [{ field: '', op: '=', value: 'x' }] })).toBe('')
  })
})

describe('autocomplete knows the pipeline commands', () => {
  it('offers the new stages and functions', () => {
    for (const stage of ['eval', 'timechart', 'top', 'dedup', 'lookup', 'join']) {
      expect(LOGQL_STAGES).toContain(stage)
    }
    expect(getSuggestions('| time', 6, []).suggestions.map(s => s.value)).toContain('timechart')
    expect(getSuggestions('| stats p9', 10, []).suggestions.map(s => s.value)).toContain('p95()')
    expect(getSuggestions('| eval x = cid', 14, []).suggestions.map(s => s.value)).toContain('cidrmatch()')
    expect(getSuggestions('| top lim', 9, []).suggestions.map(s => s.value)).toContain('limit=')
  })
})
