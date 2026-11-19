import { describe, expect, it } from 'vitest'
import { ACTION_ORDER, contentsSummary, packStatus, planSummary, techniques } from '../packFormat'

const counts = (c: Partial<Record<string, number>>) =>
  ({ create: 0, update: 0, unchanged: 0, keep_local: 0, deleted: 0, conflict: 0, remove: 0, ...c })

describe('packStatus', () => {
  it('says whether a pack is installed and whether an upgrade is waiting', () => {
    expect(packStatus({ version: '1.0.0', installed_version: null, update_available: false }))
      .toEqual({ label: 'Not installed', tone: 'idle', action: 'Install' })
    expect(packStatus({ version: '1.0.0', installed_version: '1.0.0', update_available: false }))
      .toEqual({ label: 'Installed 1.0.0', tone: 'ok', action: 'Reinstall' })
    expect(packStatus({ version: '1.2.0', installed_version: '1.0.0', update_available: true }))
      .toEqual({ label: 'Update to 1.2.0', tone: 'update', action: 'Upgrade' })
  })
})

describe('contentsSummary', () => {
  it('lists what a pack contains, skipping empty kinds and pluralising', () => {
    expect(contentsSummary({ pipelines: 3, rules: 1, searches: 2, dashboards: 1, lookups: 0 }))
      .toBe('3 pipelines · 1 rule · 2 searches · 1 dashboard')
  })
})

describe('planSummary', () => {
  it('describes a plan in a sentence, changes first', () => {
    expect(planSummary(counts({ create: 10 }))).toBe('10 to create')
    expect(planSummary(counts({ update: 1, keep_local: 1, unchanged: 8 })))
      .toBe('1 to update, 1 kept as changed locally, 8 unchanged')
    expect(planSummary(counts({ conflict: 2, remove: 1, deleted: 1 })))
      .toBe('1 to remove, 1 deleted locally (not recreated), 2 conflicts')
  })
  it('notices a plan that changes nothing', () => {
    expect(planSummary(counts({ unchanged: 10 }))).toBe('10 unchanged: nothing to do')
    expect(planSummary(counts({}))).toBe('Nothing to do')
  })
  it('orders action groups for display', () => {
    expect(ACTION_ORDER.slice(0, 3)).toEqual(['create', 'update', 'remove'])
  })
})

describe('techniques', () => {
  it('pulls ATT&CK technique ids out of Sigma tags', () => {
    expect(techniques(['attack.persistence', 'attack.t1098.001', 'attack.T1556'])).toEqual(['T1098.001', 'T1556'])
  })
})
