/**
 * Mutating API calls must fail loudly.
 *
 * apiClient used to report every HTTP error as `{ success: false }`. Most
 * callers wrap mutations in try/catch, so a 4xx/5xx from a save, delete or
 * action never reached the catch block: the UI showed success (or did
 * nothing) while the server had refused the change. That is how the dashboard
 * editor reported failed saves as saved, and the security pages applied
 * statuses the API had rejected.
 *
 * Contract:
 *  - post/put/patch/delete reject with an ApiError on HTTP errors, timeouts and
 *    network failures;
 *  - get keeps resolving to `{ success: false, error }`, because read paths
 *    render empty/error states from it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, ApiError } from '../api'

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('mutations reject on failure', () => {
  for (const method of ['post', 'put', 'patch', 'delete'] as const) {
    it(`${method} rejects with ApiError carrying status and server message`, async () => {
      fetchMock.mockResolvedValue(jsonResponse(422, { detail: 'name is required' }))
      const client = new ApiClient()

      const call = method === 'delete'
        ? client.delete('/v1/things/1')
        : client[method]('/v1/things', { a: 1 })

      await expect(call).rejects.toBeInstanceOf(ApiError)
      await expect(call).rejects.toMatchObject({ status: 422, message: 'name is required' })
    })
  }

  it('post rejects on a network failure, with status 0', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(new ApiClient().post('/v1/things', {})).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
    })
  })

  it('post still resolves with data on success', async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { id: 'abc' }))
    const res = await new ApiClient().post('/v1/things', { a: 1 })
    expect(res.success).toBe(true)
    expect(res.data).toEqual({ id: 'abc' })
  })

  it('a 401 mutation is retried after a successful token refresh', async () => {
    const client = new ApiClient()
    // first call 401, refresh succeeds, retry succeeds
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    ;(client as any).tryRefreshAccessToken = vi.fn().mockResolvedValue(true)

    const res = await client.put('/v1/things/1', { a: 2 })
    expect(res.success).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})

describe('reads keep the result-object contract', () => {
  it('get resolves to success:false with the server message', async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { detail: 'not found' }))
    const res = await new ApiClient().get('/v1/things/1')
    expect(res.success).toBe(false)
    expect(res.error).toBe('not found')
  })
})
