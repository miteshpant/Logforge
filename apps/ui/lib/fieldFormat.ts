/**
 * Field explorer helpers (Phase 5): add a field = value filter to a
 * LogforgeQL query, and group catalogue fields for the sidebar.
 */

export interface CatalogueField {
  name: string
  type: string
  schema: boolean
  present: number
  presence_pct: number
  cardinality: number
  cardinality_capped: boolean
  examples: Array<{ value: unknown; count: number }>
  services: string[]
}

function literal(value: unknown, type?: string): string {
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  const text = String(value)
  if (type === 'number' && /^-?\d+(\.\d+)?$/.test(text)) return text
  return `"${text.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
}

/** The query with `| where field = value` (or `!=`) appended. */
export function addFilter(query: string, field: string, value: unknown, exclude = false, type?: string): string {
  const clause = `| where ${field} ${exclude ? '!=' : '='} ${literal(value, type)}`
  const base = query.trim()
  return base ? `${base} ${clause}` : clause
}

export function groupFields(fields: CatalogueField[], search: string): { fields: CatalogueField[]; schema: CatalogueField[] } {
  const needle = search.trim().toLowerCase()
  const shown = needle ? fields.filter(f => f.name.toLowerCase().includes(needle)) : fields
  return { fields: shown.filter(f => !f.schema), schema: shown.filter(f => f.schema) }
}
