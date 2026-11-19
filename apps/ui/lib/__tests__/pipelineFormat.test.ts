import { describe, expect, it } from 'vitest'
import { diffFields, parseProcessors, routingSummary, sampleDocs } from '../pipelineFormat'

describe('parseProcessors', () => {
  it('accepts a JSON list of single-processor steps', () => {
    const r = parseProcessors('[{"grok": {"field": "msg", "patterns": ["%{IP:ip}"]}}, {"drop": {}, "if": "x"}]')
    expect(r.error).toBeNull()
    expect(r.processors).toHaveLength(2)
  })
  it('explains what is wrong', () => {
    expect(parseProcessors('{').error).toMatch(/JSON/)
    expect(parseProcessors('{"grok": {}}').error).toMatch(/list/)
    expect(parseProcessors('[{"grok": {}, "drop": {}}]').error).toMatch(/step 1.*one processor/)
    expect(parseProcessors('').processors).toEqual([])
  })
})

describe('diffFields', () => {
  it('lists added, changed and removed fields as dotted paths', () => {
    const before = { msg: 'order 7 paid', level: 'info', attrs: { source: 'x', drop: 1 } }
    const after = { msg: 'order 7 paid', level: 'warn', attrs: { source: 'x', order: 7 } }
    expect(diffFields(before, after)).toEqual([
      { path: 'attrs.drop', change: 'removed', before: 1, after: undefined },
      { path: 'attrs.order', change: 'added', before: undefined, after: 7 },
      { path: 'level', change: 'changed', before: 'info', after: 'warn' },
    ])
  })
  it('treats a dropped event as everything removed', () => {
    expect(diffFields({ msg: 'x' }, null)).toEqual([{ path: 'msg', change: 'removed', before: 'x', after: undefined }])
  })
})

describe('sampleDocs and routingSummary', () => {
  it('turns pasted lines into sample events; JSON lines stay objects', () => {
    expect(sampleDocs('line one\n\n{"msg":"two","service":"x"}\n')).toEqual(['line one', { msg: 'two', service: 'x' }])
  })
  it('summarises routing', () => {
    expect(routingSummary({ services: ['nginx', 'ingress'], if: '', priority: 100, default: false })).toBe('service: nginx, ingress')
    expect(routingSummary({ services: [], if: "level == 'error'", priority: 10, default: false })).toBe("if level == 'error'")
    expect(routingSummary({ services: [], if: '', priority: 100, default: true })).toBe('default for unmatched events')
    expect(routingSummary({ services: [], if: '', priority: 100, default: false })).toBe('only when named by the shipper')
  })
})
