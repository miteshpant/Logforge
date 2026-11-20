/**
 * Entities (Phase 11): links, labels and risk colours.
 */

export type EntityType = 'user' | 'host' | 'ip' | 'service' | 'cloud_account'

const LABELS: Record<string, string> = {
  user: 'User', host: 'Host', ip: 'IP address', service: 'Service', cloud_account: 'Cloud account',
}

export function entityLabel(type: string): string {
  return LABELS[type] || type
}

/** /security/entities/<type>/<value>, the value encoded once. */
export function entityHref(type: string, value: string): string {
  return `/security/entities/${encodeURIComponent(type)}/${encodeURIComponent(value)}`
}

/** none (0), low (<40), medium (<70), high (>=70). */
export function riskTone(score: number | null | undefined): 'none' | 'low' | 'medium' | 'high' {
  if (!score) return 'none'
  if (score >= 70) return 'high'
  return score >= 40 ? 'medium' : 'low'
}

/** The copilot's entity types (src_ip, hostname, user) for an entity, or null when it has none. */
export function copilotType(type: string): 'src_ip' | 'hostname' | 'user' | null {
  return ({ ip: 'src_ip', host: 'hostname', user: 'user' } as const)[type as 'ip' | 'host' | 'user'] ?? null
}
