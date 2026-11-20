/**
 * Content packs (Phase 7): pure helpers for the packs pages.
 */

export type PlanAction = 'create' | 'update' | 'unchanged' | 'keep_local' | 'deleted' | 'conflict' | 'remove'

/** Display order of a plan's groups: what changes first. */
export const ACTION_ORDER: PlanAction[] = ['create', 'update', 'remove', 'keep_local', 'deleted', 'conflict', 'unchanged']

export const ACTION_LABELS: Record<PlanAction, string> = {
  create: 'Create',
  update: 'Update',
  remove: 'Remove (dropped by the pack)',
  keep_local: 'Keep (changed locally)',
  deleted: 'Skip (deleted locally)',
  conflict: 'Conflict (exists, not from this pack)',
  unchanged: 'Unchanged',
}

const PHRASES: Record<PlanAction, (n: number) => string> = {
  create: n => `${n} to create`,
  update: n => `${n} to update`,
  remove: n => `${n} to remove`,
  keep_local: n => `${n} kept as changed locally`,
  deleted: n => `${n} deleted locally (not recreated)`,
  conflict: n => `${n} conflict${n === 1 ? '' : 's'}`,
  unchanged: n => `${n} unchanged`,
}

export function planSummary(counts: Record<string, number>): string {
  const parts = ACTION_ORDER.filter(a => (counts[a] || 0) > 0).map(a => PHRASES[a](counts[a]))
  if (parts.length === 0) return 'Nothing to do'
  const changes = (counts.create || 0) + (counts.update || 0) + (counts.remove || 0)
  return changes === 0 && parts.length === 1 && counts.unchanged ? `${parts[0]}: nothing to do` : parts.join(', ')
}

export interface PackStatusInput { version: string; installed_version: string | null; update_available: boolean }

export function packStatus(p: PackStatusInput): { label: string; tone: 'idle' | 'ok' | 'update'; action: string } {
  if (!p.installed_version) return { label: 'Not installed', tone: 'idle', action: 'Install' }
  if (p.update_available) return { label: `Update to ${p.version}`, tone: 'update', action: 'Upgrade' }
  return { label: `Installed ${p.installed_version}`, tone: 'ok', action: 'Reinstall' }
}

const KIND_NAMES: [string, string, string][] = [
  ['pipelines', 'pipeline', 'pipelines'], ['rules', 'rule', 'rules'], ['searches', 'search', 'searches'],
  ['dashboards', 'dashboard', 'dashboards'], ['lookups', 'lookup', 'lookups'],
]

export function contentsSummary(contents: Record<string, number>): string {
  return KIND_NAMES.filter(([k]) => (contents[k] || 0) > 0)
    .map(([k, one, many]) => `${contents[k]} ${contents[k] === 1 ? one : many}`).join(' · ')
}

/** ATT&CK technique ids (T1098.001) from Sigma tags (attack.t1098.001). */
export function techniques(tags: string[]): string[] {
  return tags.map(t => /^attack\.(t\d{4}(?:\.\d{3})?)$/i.exec(t)?.[1]).filter(Boolean).map(t => t!.toUpperCase())
}

/** Badge classes for packStatus().tone. */
export const STATUS_CLASSES: Record<'idle' | 'ok' | 'update', string> = {
  idle: 'border-white/10 text-slate-400',
  ok: 'border-green-500/30 bg-green-500/10 text-green-300',
  update: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
}
