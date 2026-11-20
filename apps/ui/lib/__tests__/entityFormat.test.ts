import { describe, expect, it } from 'vitest'
import { copilotType, entityHref, entityLabel, riskTone } from '../entityFormat'
import { LOGQL_STAGES } from '../../components/query/logqlSyntax'

describe('entityFormat', () => {
  it('links and labels entities', () => {
    expect(entityHref('ip', '10.0.0.1')).toBe('/security/entities/ip/10.0.0.1')
    expect(entityHref('user', 'ACME\\bob smith')).toBe('/security/entities/user/ACME%5Cbob%20smith')
    expect(entityLabel('cloud_account')).toBe('Cloud account')
    expect(entityLabel('planet')).toBe('planet')
  })
  it('colours risk', () => {
    expect([0, 12, 45, 88, null].map(riskTone)).toEqual(['none', 'low', 'medium', 'high', 'none'])
  })
  it('maps entity types to the copilot', () => {
    expect(copilotType('ip')).toBe('src_ip')
    expect(copilotType('host')).toBe('hostname')
    expect(copilotType('service')).toBeNull()
  })
  it('suggests the patterns stage', () => {
    expect(LOGQL_STAGES).toContain('patterns')
  })
})
