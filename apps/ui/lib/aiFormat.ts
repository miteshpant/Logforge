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
  // Phase 9
  model_answer_unusable: 'The model gave nothing usable, so this was built from the evidence instead.',
  heuristic_parsed_more: "The heuristic draft parsed more lines than the model's, so it is shown instead.",
  model_draft_invalid: "The model's pipeline didn't validate, so the heuristic draft is shown instead.",
  related_activity_not_permitted: "Related activity wasn't looked up: you don't have permission to search logs.",
  related_activity_failed: "Related activity couldn't be looked up.",
  intel_not_permitted: "Threat intelligence wasn't checked: you don't have permission to read it.",
  intel_lookup_failed: "Threat intelligence couldn't be checked.",
  // Phase 10
  fabricated_evidence_dropped: 'The model named evidence not among the events fetched; it was removed.',
  model_draft_failed: "The model's drafts failed the checks twice, so the heuristic draft is shown instead.",
  steps_not_permitted: "Some searches weren't run: you don't have permission to search logs.",
  timeline_truncated: 'The timeline holds the first 200 events found.',
  corroboration_not_permitted: "The root cause wasn't checked against the logs: you don't have permission to search them.",
  corroboration_failed: "The root cause couldn't be checked against the logs.",
  model_unavailable: 'The model was unavailable, so the statistical analysis is shown.',
  analysis_failed: 'The cited analysis could not be built; the statistical result is shown.',
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

// -- Phase 9: query drafts, triage, explanations, pipeline drafts -------------------------

const FALLBACKS: Record<string, string> = {
  rule_based: 'Rule-based draft (AI off)',
  template: 'Built from the evidence, without AI',
  heuristic: 'Heuristic draft, without AI',
  statistical: 'Statistical analysis, without AI',
}

/** How an answer was made when no model made it; null for model answers. */
export function fallbackLabel(mode: string): string | null {
  return FALLBACKS[mode] ?? null
}

export interface DraftReport {
  valid: boolean; parsed: number; total: number; fields: Record<string, unknown>
  failures: { sample: string; status?: string; error: string }[]; error: string | null
}

export function draftSummary(report: DraftReport): string {
  if (!report.valid) return `Invalid: ${report.error}`
  const n = Object.keys(report.fields).length
  return `Parsed ${report.parsed} of ${report.total} lines, ${n} ${n === 1 ? 'field' : 'fields'}`
}

const LIFTED = ['src_ip', 'dst_ip', 'user_id', 'status'] as const

/** A Log Explorer row as the stored event ({ts, msg, attrs, ...}) for /v1/ai/explain. */
export function eventForExplain(log: {
  timestamp: string; level: string; service: string; message: string; host?: string; trace_id?: string
  metadata?: Record<string, unknown>
}): Record<string, unknown> {
  const attrs: Record<string, unknown> = { ...(log.metadata || {}) }
  delete attrs.host
  const event: Record<string, unknown> = {
    ts: log.timestamp, level: log.level === 'warning' ? 'warn' : log.level, service: log.service, msg: log.message,
  }
  if (log.host) event.host = log.host
  if (log.trace_id) event.trace_id = log.trace_id
  for (const key of LIFTED) if (attrs[key] !== undefined) event[key] = attrs[key]
  event.attrs = attrs
  return event
}

// -- Phase 10: copilot, reports -------------------------------------------------------------

/** "bastion-01 compromise: Post-incident review" -> "bastion-01-compromise-post-incident-review.md" */
export function reportFilename(title: string): string {
  const slug = (title || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80)
  return `${slug || 'case-report'}.md`
}

/** How strongly a copilot timeline event stands out: none, weak (a signal) or strong (a root-cause candidate). */
export function signalTone(score: number): 'none' | 'weak' | 'strong' {
  if (score >= 3) return 'strong'
  return score > 0 ? 'weak' : 'none'
}

/** Pasted samples, one per line: a JSON object, or the raw line (Phase 10 rule drafting). */
export function parseSamples(text: string): (Record<string, unknown> | string)[] {
  return (text || '').split('\n').map(line => line.trim()).filter(Boolean).map(line => {
    if (line.startsWith('{')) {
      try {
        const value = JSON.parse(line)
        if (value && typeof value === 'object' && !Array.isArray(value)) return value as Record<string, unknown>
      } catch {
        /* not JSON: keep the line */
      }
    }
    return line
  })
}
