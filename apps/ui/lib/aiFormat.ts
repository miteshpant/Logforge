/**
 * AI answers (Phase 8): pure helpers for rendering grounded answers,
 * their citations and flags, and the deep links citations point to.
 */

export type Segment = { text: string } | { cite: string }

/** "Failed 40 times [C1]." -> text and citation segments, in order. */
export function splitCitations(text: string): Segment[] {
  const out: Segment[] = []
  const re = /\[(C\d+)\]/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text || '')) !== null) {
    if (m.index > last) out.push({ text: text.slice(last, m.index) })
    out.push({ cite: m[1] })
    last = m.index + m[0].length
  }
  if (text && last < text.length) out.push({ text: text.slice(last) })
  return out
}

const FLAGS: Record<string, string> = {
  uncited_sentences: 'Some sentences cite nothing: treat them as unverified.',
  unknown_citations: 'The answer cites sources that no lookup returned.',
  no_citations: 'This answer cites nothing it looked up: treat it as unverified.',
  refused: 'The model declined to answer.',
  truncated: 'The answer was cut off.',
  tool_limit: 'The model hit the limit on lookups before finishing.',
}

export function flagMessages(flags: string[]): string[] {
  return flags.map(f => FLAGS[f] || f)
}

export interface AIProviderInfo { name: string; label: string; model: string; external: boolean }

/** The indicator shown with every answer: did data leave the deployment? */
export function providerNotice(p: AIProviderInfo | null): { external: boolean; text: string } {
  if (!p) return { external: false, text: 'No model: rule-based answer' }
  const name = `${p.label || p.name} (${p.model})`
  return p.external ? { external: true, text: `External model: ${name}` }
    : { external: false, text: `Model in this deployment: ${name}` }
}

const SINCE = /^(\d{1,4})([mhd])$/

/** Log Explorer deep link: ?logql=<LogforgeQL>&since=24h or &from=<iso>&to=<iso> (?q= stays the filter search). */
export function parseLogsLink(search: string, now: Date = new Date()):
  { query: string; start: Date | null; end: Date | null } | null {
  const params = new URLSearchParams(search)
  const query = params.get('logql')
  if (!query) return null
  const from = params.get('from'), to = params.get('to'), since = params.get('since')
  if (from && to) {
    const start = new Date(from), end = new Date(to)
    if (!isNaN(start.getTime()) && !isNaN(end.getTime()) && start < end) return { query, start, end }
    return { query, start: null, end: null }
  }
  const m = since ? SINCE.exec(since) : null
  if (m) {
    const ms = Number(m[1]) * { m: 60_000, h: 3_600_000, d: 86_400_000 }[m[2] as 'm' | 'h' | 'd']
    return { query, start: new Date(now.getTime() - ms), end: now }
  }
  return { query, start: null, end: null }
}
