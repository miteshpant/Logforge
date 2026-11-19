/**
 * Helpers for the ingest pipeline editor (Phase 4): parsing the processors
 * JSON, before/after field diffs for simulation, and short descriptions.
 */

const STEP_KEYS = new Set(['if', 'tag', 'ignore_failure', 'on_failure', 'description'])

export type Step = Record<string, any>

export function parseProcessors(text: string): { processors: Step[]; error: string | null } {
  if (!text.trim()) return { processors: [], error: null }
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch (e: any) {
    return { processors: [], error: `Not valid JSON: ${e?.message || e}` }
  }
  if (!Array.isArray(value)) return { processors: [], error: 'Processors must be a JSON list of steps' }
  for (let i = 0; i < value.length; i++) {
    const step = value[i]
    if (!step || typeof step !== 'object' || Array.isArray(step)) {
      return { processors: [], error: `step ${i + 1} must be an object` }
    }
    const kinds = Object.keys(step).filter(k => !STEP_KEYS.has(k))
    if (kinds.length !== 1) {
      return { processors: [], error: `step ${i + 1} needs exactly one processor (found ${kinds.join(', ') || 'none'})` }
    }
  }
  return { processors: value as Step[], error: null }
}

export interface FieldChange {
  path: string
  change: 'added' | 'changed' | 'removed'
  before: unknown
  after: unknown
}

function flatten(value: unknown, prefix = '', out: Record<string, unknown> = {}): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const [key, inner] of Object.entries(value as Record<string, unknown>)) {
      flatten(inner, prefix ? `${prefix}.${key}` : key, out)
    }
  } else if (prefix) {
    out[prefix] = value
  }
  return out
}

/** Field-level differences between an input event and its pipeline output (null = dropped). */
export function diffFields(before: Record<string, unknown>, after: Record<string, unknown> | null): FieldChange[] {
  const a = flatten(before)
  const b = after ? flatten(after) : {}
  const paths = Array.from(new Set([...Object.keys(a), ...Object.keys(b)])).sort()
  const changes: FieldChange[] = []
  for (const path of paths) {
    const inA = path in a
    const inB = path in b
    if (inA && !inB) changes.push({ path, change: 'removed', before: a[path], after: undefined })
    else if (!inA && inB) changes.push({ path, change: 'added', before: undefined, after: b[path] })
    else if (JSON.stringify(a[path]) !== JSON.stringify(b[path])) {
      changes.push({ path, change: 'changed', before: a[path], after: b[path] })
    }
  }
  return changes
}

/** Pasted sample text -> sample events: one per non-empty line; JSON object lines stay objects. */
export function sampleDocs(text: string): Array<string | Record<string, unknown>> {
  return text.split('\n').map(l => l.replace(/\r$/, '')).filter(l => l.trim()).map(line => {
    const trimmed = line.trim()
    if (trimmed.startsWith('{')) {
      try {
        const parsed = JSON.parse(trimmed)
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed
      } catch {
        // not JSON: keep the raw line
      }
    }
    return line
  })
}

export interface Routing { services: string[]; if: string; priority: number; default: boolean }

export function routingSummary(routing: Partial<Routing> | undefined): string {
  if (!routing) return 'only when named by the shipper'
  if (routing.default) return 'default for unmatched events'
  const parts: string[] = []
  if (routing.services && routing.services.length) parts.push(`service: ${routing.services.join(', ')}`)
  if (routing.if) parts.push(`if ${routing.if}`)
  return parts.length ? parts.join('; ') : 'only when named by the shipper'
}
