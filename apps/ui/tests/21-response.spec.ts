import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Response automation (Phase 13): integrations, playbooks with an approval
 * before containment, and reports.
 *
 * Nothing outside the stack is called: integrations point at .invalid hosts,
 * so their test and the approved containment step fail, visibly. The full
 * alert → Slack + Jira → case closed loop runs against mocks in
 * tests/test_response_acceptance_live.py.
 */

const n = Date.now()
const hook = `e2e-hook-${n}`
const firewall = `e2e-firewall-${n}`
const playbookName = `e2e containment ${n}`

const definition = (withApproval: boolean) => `name: ${playbookName}
trigger:
  on: case_created
  when: case.title == "never matches ${n}"
steps:
${withApproval ? `  - id: approve
    approval: {prompt: "Block 198.51.100.7 at the firewall?", timeout: 1h}
` : ''}  - id: block
    action: {integration: ${firewall}, inputs: {action: block_ip, target: "198.51.100.7"}}
`

let headers: Record<string, string> = {}
let caseId = ''

test.beforeAll(async ({ request }) => {
  const { token, tenantId } = await apiSession(request)
  headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const fw = await request.post(`${API}/v1/integrations`, { headers, data: {
    name: firewall, kind: 'containment_webhook', config: { url: `https://firewall-${n}.example.invalid/contain` } } })
  expect(fw.ok(), await fw.text()).toBeTruthy()
  const c = await request.post(`${API}/v1/security/cases`, { headers, data: { title: `Playbook e2e ${n}`, severity: 'high' } })
  expect(c.ok(), await c.text()).toBeTruthy()
  caseId = (await c.json()).id
})

test.afterAll(async ({ request }) => {
  const integrations = (await (await request.get(`${API}/v1/integrations`, { headers })).json()).integrations || []
  for (const i of integrations.filter((x: any) => x.name.startsWith('e2e-') && x.name.endsWith(String(n)))) {
    await request.delete(`${API}/v1/integrations/${i.id}`, { headers })
  }
  const playbooks = (await (await request.get(`${API}/v1/playbooks`, { headers })).json()).playbooks || []
  for (const p of playbooks.filter((x: any) => x.name === playbookName)) {
    await request.delete(`${API}/v1/playbooks/${p.id}`, { headers })
  }
})

test('integrations: add one, test it, see secrets are write-only', async ({ page }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/settings/integrations', { waitUntil: 'load' })
  await expect(page.getByTestId(`integration-${firewall}`)).toContainText('containment', { timeout: 30_000 })

  await page.getByTestId('add-integration').selectOption('webhook')
  await page.getByTestId('integration-name').fill(hook)
  await page.getByTestId('field-url').fill(`https://hooks-${n}.example.invalid/in`)
  await page.getByTestId('field-signing_secret').fill('e2e-signing-secret')
  await page.getByTestId('save-integration').click()
  await expect(page.getByTestId('integrations-message')).toContainText(`Saved ${hook}`)
  const row = page.getByTestId(`integration-${hook}`)
  await expect(row).toContainText('Signing secret')
  await expect(page.locator('body')).not.toContainText('e2e-signing-secret')

  // the host doesn't exist: the test says so instead of pretending
  await page.getByTestId(`test-${hook}`).click()
  await expect(page.getByTestId(`test-result-${hook}`)).not.toBeEmpty({ timeout: 30_000 })
  await expect(page.getByTestId(`test-result-${hook}`)).not.toContainText('OK')

  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('playbooks: containment needs an approval, and a person decides', async ({ page, request }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/security/playbooks', { waitUntil: 'load' })
  await page.getByTestId('new-playbook').click()

  // without an approval the containment step is refused
  await page.getByTestId('playbook-definition').fill(definition(false))
  await page.getByTestId('validate-playbook').click()
  await expect(page.getByTestId('playbook-check')).toContainText('Invalid')
  await expect(page.getByTestId('playbook-check')).toContainText('approval')

  await page.getByTestId('playbook-definition').fill(definition(true))
  await page.getByTestId('validate-playbook').click()
  await expect(page.getByTestId('playbook-check')).toContainText('containment behind an approval')
  await page.getByTestId('save-playbook').click()
  await expect(page.getByTestId('playbooks-message')).toContainText(`Saved ${playbookName}`)
  await expect(page.getByTestId(`playbook-${playbookName}`)).toContainText('approve → block')

  // run it on the case: it stops at the approval
  const playbooks = (await (await request.get(`${API}/v1/playbooks`, { headers })).json()).playbooks
  const id = playbooks.find((p: any) => p.name === playbookName).id
  const started = await request.post(`${API}/v1/playbooks/${id}/run`, { headers, data: { case_id: caseId } })
  expect(started.ok(), await started.text()).toBeTruthy()
  const run = (await started.json()).run
  expect(run.status).toBe('waiting_approval')

  await page.reload({ waitUntil: 'load' })
  const card = page.getByTestId(`approval-${run.id}`)
  await expect(card).toContainText('Block 198.51.100.7 at the firewall?', { timeout: 30_000 })
  await page.getByTestId(`approve-${run.id}`).click()
  // approved; the firewall host doesn't exist, so the block step fails and the run says so
  await expect(page.getByTestId('playbooks-message')).toContainText('Approved')
  await expect(page.getByTestId(`run-status-${run.id}`)).toHaveText('failed')
  await expect(card).toHaveCount(0)

  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('reports: on screen, as PDF and CSV, and the ATT&CK Navigator layer', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/security/reports', { waitUntil: 'load' })
  await expect(page.getByTestId('report-Summary')).toContainText('Alerts', { timeout: 60_000 })
  await expect(page.getByTestId('report-Case response')).toBeVisible()
  await expect(page.getByTestId('report-Detection coverage')).toBeVisible()

  for (const [button, extension] of [['download-pdf', '.pdf'], ['download-csv', '.csv'], ['download-navigator', '.json'], ['download-compliance', '.pdf']]) {
    const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId(button).click()])
    expect(download.suggestedFilename().endsWith(extension)).toBeTruthy()
  }

  await page.getByTestId('report-days').selectOption('7')
  await expect(page.getByTestId('report')).toContainText('(7 days)', { timeout: 60_000 })

  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})
