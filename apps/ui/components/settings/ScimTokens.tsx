'use client'

import { useCallback, useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import { API_CONFIG } from '@/lib/api'
import { createScimToken, listScimTokens, revokeScimToken, type ScimToken } from '@/lib/api/sso'

/** Settings → Authentication → SSO: SCIM tokens for the IdP to provision users (Phase 14). */
export default function ScimTokens() {
  const [tokens, setTokens] = useState<ScimToken[]>([])
  const [basePath, setBasePath] = useState('/scim/v2')
  const [name, setName] = useState('')
  const [fresh, setFresh] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const out = await listScimTokens()
      setTokens(out.tokens); setBasePath(out.base_path)
    } catch (e: any) { setError(e?.message || 'Failed to load SCIM tokens') }
  }, [])
  useEffect(() => { load() }, [load])

  const create = async () => {
    setError(null)
    try {
      const out = await createScimToken(name || 'Identity provider')
      setFresh(out.token); setName('')
      await load()
    } catch (e: any) { setError(e?.message || 'Failed to create the token') }
  }

  const revoke = async (t: ScimToken) => {
    if (!window.confirm(`Revoke ${t.name}? The IdP stops provisioning until it gets a new token.`)) return
    try { await revokeScimToken(t.id); await load() } catch (e: any) { setError(e?.message || 'Failed to revoke') }
  }

  return (
    <div className="space-y-3 mt-8" data-testid="scim-tokens">
      <h3 className="text-white font-semibold flex items-center gap-2"><Users className="w-4 h-4" /> User provisioning (SCIM 2.0)</h3>
      <p className="text-sm text-slate-400">
        Point your IdP's SCIM app at <code className="text-slate-200">{API_CONFIG.baseURL}{basePath}</code> with a token
        from here. It creates, updates and deprovisions this tenant's users and their roles.
      </p>
      <div className="flex gap-2">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Token name (e.g. Okta)" data-testid="scim-name"
          className="bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm flex-1" />
        <button onClick={create} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm" data-testid="scim-create">Create token</button>
      </div>
      {fresh && (
        <div className="rounded border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="scim-fresh">
          Copy it now, it isn't shown again: <code className="break-all text-white">{fresh}</code>
        </div>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {tokens.map(t => (
        <div key={t.id} className="flex items-center justify-between text-sm bg-slate-900 border border-slate-800 rounded px-3 py-2" data-testid={`scim-token-${t.name}`}>
          <span className="text-slate-200">{t.name} <span className="text-slate-500">· created {new Date(t.created_at + 'Z').toLocaleString()}</span></span>
          <button onClick={() => revoke(t)} className="text-red-300 hover:text-red-200 text-xs">Revoke</button>
        </div>
      ))}
    </div>
  )
}
