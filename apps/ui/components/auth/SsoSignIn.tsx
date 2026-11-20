'use client'

import { useEffect, useState } from 'react'
import { KeyRound, Loader2 } from 'lucide-react'
import { discoverProviders, startUrl } from '@/lib/api/sso'

/**
 * "Sign in with single sign-on" (Phase 14): finds the OIDC provider for the
 * address typed above and sends the browser to it. Shows why a previous SSO
 * attempt was refused (?sso_error=).
 */
export default function SsoSignIn({ email }: { email: string }) {
  const [providers, setProviders] = useState<{ id: string; name: string }[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const refused = new URLSearchParams(window.location.search).get('sso_error')
    if (refused) setError(refused)
  }, [])

  const next = () => new URLSearchParams(window.location.search).get('next')

  const go = async () => {
    setError(null)
    if (!email.includes('@')) return setError('Type your work email above first.')
    setBusy(true)
    try {
      const found = (await discoverProviders(email)).providers
      if (found.length === 1) {
        window.location.assign(startUrl(found[0].id, next()))
        return
      }
      if (!found.length) setError(`Single sign-on isn't set up for ${email.split('@')[1]}. Use your password.`)
      setProviders(found)
    } catch (e: any) {
      setError(e?.message || 'Single sign-on lookup failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2">
      <button type="button" onClick={go} disabled={busy} data-testid="sso-signin"
        className="w-full h-11 rounded-md border border-slate-200 hover:bg-slate-50 text-slate-800 flex items-center justify-center gap-2 disabled:opacity-60">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />} Sign in with single sign-on
      </button>
      {providers && providers.length > 1 && providers.map(p => (
        <a key={p.id} href={startUrl(p.id, next())} className="block text-center text-sm text-blue-700 hover:underline">{p.name}</a>
      ))}
      {error && <p className="text-sm text-red-600" data-testid="sso-signin-error">{error}</p>}
    </div>
  )
}
