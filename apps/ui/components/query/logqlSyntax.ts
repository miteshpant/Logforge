/**
 * LogforgeQL language definition for the query bar (LF-023).
 *
 * The tokens below are the language itself — stages, operators, aggregations
 * and the query-field allow-list from `apps/api/logql.py` /
 * `apps/api/query_engine.py` (`ALLOWED_QUERY_FIELDS`). They are language
 * schema, not data: the server rejects anything outside this set with a 400
 * naming the allowed fields.
 *
 * Service-name suggestions are fetched live from the API (see `logsApi.ts`);
 * they are never hardcoded here.
 *
 * NOTE: the spec'd dynamic field source `GET /v1/schemas/standard-fields`
 * currently returns 403 for tenant admins — see final report; once the
 * permission mapping is fixed this list can be replaced by that endpoint.
 */

export const LOGQL_STAGES = ['where', 'eval', 'stats', 'eventstats', 'timechart', 'top', 'rare', 'sort', 'head',
  'limit', 'dedup', 'fields', 'table', 'rename', 'bin', 'rex', 'parse', 'json', 'lookup', 'join', 'last'] as const

/** eval / where functions (apps/api/logql_pipeline.py FUNCTIONS). */
export const LOGQL_FUNCTIONS = ['if()', 'case()', 'coalesce()', 'isnull()', 'isnotnull()', 'lower()', 'upper()',
  'trim()', 'len()', 'substr()', 'replace()', 'match()', 'like()', 'concat()', 'tonumber()', 'tostring()', 'round()',
  'floor()', 'ceil()', 'abs()', 'sqrt()', 'ln()', 'log10()', 'exp()', 'pow()', 'least()', 'greatest()', 'now()',
  'hour()', 'minute()', 'dayofweek()', 'date()', 'strftime()', 'cidrmatch()', 'json_extract()', 'inlookup()'] as const

const STAGE_OPTIONS: Record<string, string[]> = {
  timechart: ['span=', 'limit='], top: ['limit='], rare: ['limit='], bin: ['span='], join: ['type=', 'max='],
}

export const LOGQL_OPERATORS = [
  '=',
  '!=',
  '>',
  '>=',
  '<',
  '<=',
  '=~',
  'contains',
  'startswith',
  'endswith',
  'in',
] as const

export const LOGQL_AGGREGATIONS = [
  'count()', 'dc()', 'estdc()', 'sum()', 'avg()', 'min()', 'max()', 'median()', 'p50()', 'p90()', 'p95()', 'p99()',
  'percentile()', 'stdev()', 'var()', 'values()', 'list()', 'earliest()', 'latest()',
] as const

/** Mirrors `ALLOWED_QUERY_FIELDS` in `apps/api/query_engine.py`. */
export const LOGQL_FIELDS = [
  'ts',
  'host',
  'service',
  'level',
  'msg',
  'trace_id',
  'span_id',
  'status',
  'src_ip',
  'user_id',
  'ingested_at',
  'severity_num',
  'facility',
  'attrs',
  'parser_version',
  'date',
  'hour',
  'extracted_user_id',
  'extracted_ip',
  'http_method',
  'http_uri',
  'http_status',
  'http_response_time_ms',
  'error_code',
  'is_error',
  'is_slow',
] as const

export const LOGQL_DURATIONS = ['5m', '15m', '1h', '6h', '24h', '7d'] as const

export interface LogQLExample {
  query: string
  description: string
}

export const LOGQL_EXAMPLES: LogQLExample[] = [
  {
    query: 'error | limit 100',
    description: 'Free-text search: the 100 most recent logs containing "error".',
  },
  {
    query: '| where service = "api-service" and level = "error" | limit 50',
    description: 'Field filters: errors from one service.',
  },
  {
    query: '| where msg contains "timeout" | sort ts desc | limit 50',
    description: 'Substring match on the message, newest first.',
  },
  {
    query: '| last 15m | where level = "error"',
    description: 'Relative time window: errors from the last 15 minutes (overrides the global range).',
  },
  {
    query: '| where http_status >= 500 | stats count() by service',
    description: 'Aggregation: server-error counts grouped by service.',
  },
  {
    query: '| where level in ["error", "critical"] | limit 200',
    description: 'Set membership: multiple levels in one filter.',
  },
]

export interface Suggestion {
  value: string
  kind: 'stage' | 'field' | 'operator' | 'aggregation' | 'service' | 'duration'
  /** Text inserted when accepted (may differ from the display value). */
  insert: string
}

/**
 * Context-aware suggestions for the token at the caret.
 *
 * Looks at the current pipe stage to decide what belongs next:
 * - right after `|`            -> stages
 * - inside `where`, after field -> operators; after operator + `service =` -> services
 * - inside `stats`             -> aggregations / `by` fields
 * - inside `sort`              -> fields
 * - inside `last`              -> durations
 */
export function getSuggestions(
  text: string,
  caret: number,
  services: string[],
  catalogueFields: string[] = []
): { suggestions: Suggestion[]; replaceStart: number } {
  const before = text.slice(0, caret)
  // Built-in fields plus the tenant's own (field catalogue, Phase 5).
  const fields: string[] = Array.from(new Set([...LOGQL_FIELDS, ...catalogueFields]))

  // Current (partial) token being typed.
  const tokenMatch = before.match(/[A-Za-z0-9_."']*$/)
  const token = tokenMatch ? tokenMatch[0] : ''
  const replaceStart = caret - token.length
  const beforeToken = before.slice(0, replaceStart)

  // The active stage = text after the last un-quoted pipe.
  const lastPipe = beforeToken.lastIndexOf('|')
  const stageText = (lastPipe >= 0 ? beforeToken.slice(lastPipe + 1) : beforeToken).trimStart()
  const stageWords = stageText.split(/\s+/).filter(Boolean)
  const stageName = (stageWords[0] || '').toLowerCase()

  const matches = (candidates: readonly string[], kind: Suggestion['kind']): Suggestion[] => {
    const lower = token.replace(/^["']/, '').toLowerCase()
    return candidates
      .filter(c => c.toLowerCase().startsWith(lower) && c.toLowerCase() !== lower)
      .map(c => ({ value: c, kind, insert: c }))
  }

  let suggestions: Suggestion[] = []

  const atStageStart =
    stageWords.length === 0 || (stageWords.length === 1 && !stageText.endsWith(' ') && token.length > 0)

  if (lastPipe >= 0 && atStageStart) {
    suggestions = matches(LOGQL_STAGES, 'stage')
  } else if (stageName === 'where') {
    // Figure out position inside the condition: field / operator / value.
    const condition = stageText.slice('where'.length)
    const condTokens = condition.split(/\s+/).filter(Boolean)
    // Strip trailing partial token if the caret is mid-token.
    const complete = token.length > 0 ? condTokens.slice(0, -1) : condTokens
    const lastComplete = complete[complete.length - 1]?.toLowerCase() || ''

    const afterJoiner = complete.length === 0 || lastComplete === 'and'
    const afterField =
      complete.length > 0 && fields.some(f => f.toLowerCase() === lastComplete)
    const afterOperator = LOGQL_OPERATORS.some(op => op === lastComplete)
    const valueForService =
      afterOperator && complete[complete.length - 2]?.toLowerCase() === 'service'

    if (valueForService) {
      suggestions = services
        .filter(s => s.toLowerCase().startsWith(token.replace(/^["']/, '').toLowerCase()))
        .map(s => ({ value: s, kind: 'service' as const, insert: `"${s}"` }))
    } else if (afterField) {
      suggestions = matches(LOGQL_OPERATORS, 'operator')
    } else if (afterJoiner) {
      suggestions = matches(fields, 'field')
    }
  } else if (['stats', 'eventstats', 'timechart'].includes(stageName)) {
    const afterBy = /\bby\b/i.test(stageText)
    suggestions = afterBy
      ? matches(fields, 'field')
      : [...matches(STAGE_OPTIONS[stageName] ?? [], 'stage'), ...matches(LOGQL_AGGREGATIONS, 'aggregation')]
  } else if (stageName === 'eval') {
    suggestions = [...matches(LOGQL_FUNCTIONS, 'aggregation'), ...matches(fields, 'field')]
  } else if (['top', 'rare', 'dedup', 'fields', 'table', 'rename', 'bin', 'join', 'lookup'].includes(stageName)) {
    suggestions = [...matches(STAGE_OPTIONS[stageName] ?? [], 'stage'), ...matches(fields, 'field')]
  } else if (stageName === 'sort') {
    suggestions = matches(fields, 'field')
  } else if (stageName === 'last') {
    suggestions = matches(LOGQL_DURATIONS, 'duration')
  } else if (lastPipe < 0 && stageWords.length <= 1) {
    // Leading free-text position — offer stage keywords for discoverability.
    suggestions = matches(LOGQL_STAGES, 'stage')
  }

  return { suggestions: suggestions.slice(0, 8), replaceStart }
}
