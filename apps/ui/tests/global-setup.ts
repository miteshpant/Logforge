import { FullConfig, request } from '@playwright/test'
import { API, EMAIL, PASSWORD } from './support/session'

/**
 * Fail fast, with a useful message, when the stack the specs need is missing.
 *
 * The specs run against a live stack seeded by `scripts/bootstrap_demo.py`.
 * Without this check every spec would fail on its own with a timeout.
 */
async function globalSetup(_config: FullConfig) {
  const api = await request.newContext()
  try {
    const health = await api.get(`${API}/health`).catch(() => null)
    if (!health || !health.ok()) {
      throw new Error(`API not reachable at ${API}/health. Start the stack with ./deploy.sh.`)
    }
    const login = await api.post(`${API}/v1/auth/login`, { data: { email: EMAIL, password: PASSWORD } })
    if (!login.ok()) {
      throw new Error(
        `Test user ${EMAIL} cannot log in (HTTP ${login.status()}). ` +
        'Create it with: python scripts/bootstrap_demo.py',
      )
    }
  } finally {
    await api.dispose()
  }
}

export default globalSetup
