import { describe, expect, it } from 'vitest'
import { bytes, money, percent, retentionSummary, steadyRows } from '../storageFormat'

describe('storage formatting', () => {
  it('formats bytes in binary units', () => {
    expect(bytes(0)).toBe('0 B')
    expect(bytes(1536)).toBe('1.5 KiB')
    expect(bytes(3 * 1024 ** 3)).toBe('3.0 GiB')
    expect(bytes(2.5 * 1024 ** 4)).toBe('2.5 TiB')
  })

  it('formats money and shares', () => {
    expect(money(0)).toBe('$0.00')
    expect(money(1234.5)).toBe('$1,234.50')
    expect(money(0.004)).toBe('<$0.01')
    expect(percent(0.256)).toBe('26%')
    expect(percent(0.004)).toBe('<1%')
  })

  it('describes a retention policy in words', () => {
    expect(retentionSummary({ searchable_days: 30, archive_days: 365 })).toBe('30 days searchable, archived for 1 year')
    expect(retentionSummary({ searchable_days: 90, archive_days: 0 })).toBe('90 days searchable, then deleted')
    expect(retentionSummary({ searchable_days: 30, archive_days: 730 })).toBe('30 days searchable, archived for 2 years')
    expect(retentionSummary({ searchable_days: 14, archive_days: 100 })).toBe('14 days searchable, archived for 100 days')
  })

  it('lists the steady-state tiers with their cost', () => {
    const rows = steadyRows({
      hot: { days: 7, gb: 10 }, warm: { days: 23, gb: 30 }, cold: { days: 335, gb: 200 },
      monthly_cost: { hot: 0.8, warm: 0.69, cold: 2.5, total: 3.99 },
    })
    expect(rows.map(r => r.tier)).toEqual(['hot', 'warm', 'cold'])
    expect(rows[2]).toEqual({ tier: 'cold', days: 335, gb: 200, cost: 2.5 })
  })
})
