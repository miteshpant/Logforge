import { describe, expect, it } from 'vitest'
import { dataParams, panelTypeFor, seriesFromPanel, ALL } from '../dashboardPanels'

describe('dataParams', () => {
  it('sends the time range and every variable as var-<name>', () => {
    expect(dataParams({ start_time: 's', end_time: 'e' }, { service: 'api', level: ALL })).toEqual({
      start_time: 's', end_time: 'e', 'var-service': 'api', 'var-level': '*'
    })
  })
})

describe('seriesFromPanel', () => {
  it('turns labels + named series into one row per label', () => {
    const out = seriesFromPanel({
      labels: ['t1', 't2'],
      series: [{ name: 'api', data: [1, 3] }, { name: 'web', data: [2, 0] }]
    })
    expect(out).toEqual({
      names: ['api', 'web'],
      rows: [{ label: 't1', api: 1, web: 2 }, { label: 't2', api: 3, web: 0 }]
    })
  })

  it('returns null for payloads that are not query panels', () => {
    expect(seriesFromPanel({ series: [{ label: 'a', value: 1 }] })).toBeNull()
    expect(seriesFromPanel(null)).toBeNull()
  })

  it('keeps a series named "label" from overwriting the axis', () => {
    const out = seriesFromPanel({ labels: ['a'], series: [{ name: 'label', data: [5] }] })
    expect(out?.rows[0].label).toBe('a')
    expect(out?.names).toEqual(['label '])
  })
})

describe('panelTypeFor', () => {
  it('suggests a widget type from the result shape', () => {
    expect(panelTypeFor({ resultType: 'timechart', columns: ['_time', 'count'], rows: [] })).toBe('line_chart')
    expect(panelTypeFor({ resultType: 'table', columns: ['n'], rows: [{ n: 4 }] })).toBe('metric')
    expect(panelTypeFor({ resultType: 'table', columns: ['service', 'n'], rows: [{ service: 'a', n: 1 }] }))
      .toBe('bar_chart')
    expect(panelTypeFor({ resultType: 'events', columns: ['ts', 'msg'], rows: [] })).toBe('table')
  })
})
