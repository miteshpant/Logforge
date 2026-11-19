import { describe, expect, it } from 'vitest'
import { addFilter, groupFields } from '../fieldFormat'
import { getSuggestions } from '../../components/query/logqlSyntax'

describe('addFilter', () => {
  it('appends a where clause, quoting strings and keeping numbers', () => {
    expect(addFilter('', 'attrs.path', '/a')).toBe('| where attrs.path = "/a"')
    expect(addFilter('error | last 1h', 'ocsf.status_id', 2)).toBe('error | last 1h | where ocsf.status_id = 2')
    expect(addFilter('*', 'service', 'api', true)).toBe('* | where service != "api"')
  })
  it('escapes quotes and backslashes in values', () => {
    expect(addFilter('', 'msg', 'say "hi" \\ there')).toBe('| where msg = "say \\"hi\\" \\\\ there"')
  })
  it('compares numeric-looking strings from the catalogue as numbers only when the field is numeric', () => {
    expect(addFilter('', 'attrs.code', '404', false, 'number')).toBe('| where attrs.code = 404')
    expect(addFilter('', 'attrs.code', '404', false, 'string')).toBe('| where attrs.code = "404"')
  })
})

describe('groupFields', () => {
  it('splits schema fields from the rest and filters by search', () => {
    const fields = [
      { name: 'service', schema: false }, { name: 'attrs.path', schema: false },
      { name: 'ocsf.src_endpoint.ip', schema: true },
    ] as any
    expect(groupFields(fields, '')).toEqual({ fields: fields.slice(0, 2), schema: [fields[2]] })
    expect(groupFields(fields, 'IP')).toEqual({ fields: [], schema: [fields[2]] })
  })
})

describe('catalogue-aware suggestions', () => {
  it('offers catalogue fields and the extraction stages', () => {
    const { suggestions } = getSuggestions('| where attrs.pa', 16, [], ['attrs.path', 'attrs.http.status'])
    expect(suggestions.map(s => s.value)).toEqual(['attrs.path'])
    expect(getSuggestions('| re', 4, []).suggestions.map(s => s.value)).toContain('rex')
    const op = getSuggestions('| where attrs.path ', 19, [], ['attrs.path']).suggestions.map(s => s.kind)
    expect(op[0]).toBe('operator')
  })
})
