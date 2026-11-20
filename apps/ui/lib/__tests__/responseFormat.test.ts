import { describe, expect, it } from 'vitest'
import { fieldLabel, kindFields, runProgress, runTone, scheduleSummary, triggerSummary, waitingApproval } from '../responseFormat'

const JIRA = { kind: 'jira_issue', label: 'Jira', config: ['base_url', 'email', 'project'], secrets: ['api_token'],
  inputs: ['summary'], containment: false, ticket: true }
const WEBHOOK = { kind: 'webhook', label: 'Webhook', config: ['url'], secrets: [], inputs: ['body'], containment: false, ticket: false }

describe('response formatting', () => {
  it('labels fields', () => {
    expect(fieldLabel('base_url')).toBe('Base URL')
    expect(fieldLabel('api_token')).toBe('API token')
    expect(fieldLabel('webhook_secret')).toBe('Webhook secret')
  })

  it('lists the fields a kind needs, with the optional ones', () => {
    const jira = kindFields(JIRA)
    expect(jira.filter(f => f.required).map(f => f.name)).toEqual(['base_url', 'email', 'project', 'api_token'])
    expect(jira.find(f => f.name === 'api_token')!.secret).toBe(true)
    expect(jira.find(f => f.name === 'webhook_secret')).toMatchObject({ secret: true, required: false })
    expect(kindFields(WEBHOOK).find(f => f.name === 'signing_secret')).toMatchObject({ secret: true, required: false })
  })

  it('summarises runs', () => {
    const run = { status: 'waiting_approval', steps: [
      { id: 'notify', type: 'action', status: 'done' },
      { id: 'approve', type: 'approval', status: 'waiting', prompt: 'Block 203.0.113.7?', deadline: '2026-11-20T16:00:00+00:00' },
      { id: 'block', type: 'action', status: 'pending' }] }
    expect(runProgress(run)).toBe('1 of 3 steps done')
    expect(waitingApproval(run)).toMatchObject({ id: 'approve', prompt: 'Block 203.0.113.7?' })
    expect(runTone('succeeded')).toBe('good')
    expect(runTone('waiting_approval')).toBe('waiting')
    expect(runTone('failed')).toBe('bad')
    expect(runTone('rejected')).toBe('bad')
    expect(waitingApproval({ status: 'succeeded', steps: [] })).toBeNull()
  })

  it('summarises triggers and schedules', () => {
    expect(triggerSummary({ trigger: 'alert', when: 'alert.severity == "high"' })).toBe('On alert when alert.severity == "high"')
    expect(triggerSummary({ trigger: 'case_created', when: '' })).toBe('On case created')
    expect(triggerSummary({ trigger: null, error: 'bad yaml' })).toBe('Invalid: bad yaml')
    expect(scheduleSummary({ every: 'weekly', hour: 7, format: 'pdf', recipients: ['a@x', 'b@x'] }))
      .toBe('Weekly (Mondays) at 07:00 UTC, PDF to 2 recipients')
    expect(scheduleSummary({ every: 'monthly', hour: 18, format: 'csv', recipients: ['a@x'] }))
      .toBe('Monthly (the 1st) at 18:00 UTC, CSV to 1 recipient')
  })
})
