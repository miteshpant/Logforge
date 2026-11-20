/** Formatting for Settings → Storage (Phase 12). */

export function bytes(n: number): string {
  if (!n) return '0 B'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return i === 0 ? `${v} B` : `${v.toFixed(1)} ${units[i]}`
}

export function money(n: number): string {
  if (n > 0 && n < 0.01) return '<$0.01'
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function percent(share: number): string {
  if (share > 0 && share < 0.01) return '<1%'
  return `${Math.round(share * 100)}%`
}

export function retentionSummary(p: { searchable_days: number; archive_days: number }): string {
  const days = (n: number) => (n % 365 === 0 ? (n === 365 ? '1 year' : `${n / 365} years`) : `${n} days`)
  return p.archive_days
    ? `${p.searchable_days} days searchable, archived for ${days(p.archive_days)}`
    : `${p.searchable_days} days searchable, then deleted`
}

export interface SteadyState {
  hot: { days: number; gb: number }; warm: { days: number; gb: number }; cold: { days: number; gb: number }
  monthly_cost: { hot: number; warm: number; cold: number; total: number }
}

export function steadyRows(s: SteadyState) {
  return (['hot', 'warm', 'cold'] as const).map(tier => ({ tier, days: s[tier].days, gb: s[tier].gb, cost: s.monthly_cost[tier] }))
}
