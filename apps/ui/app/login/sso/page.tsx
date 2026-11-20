'use client'

import { useEffect, useRef, useState } from 'react'
import AccountCard from '@/components/auth/AccountCard'
import { useAuth } from '@/contexts/AuthContext'

/**
 * Back from single sign-on (Phase 14). The API's callback put the session in
 * the URL fragment, which browsers never send to a server; it's read here,
 * removed from the address bar, and the session set up as for a password
 * sign-in.
 */
export default function SsoLandingPage() {
  const { loginWithTokens } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    const params = new URLSearchParams(window.location.hash.slice(1))
    window.history.replaceState(null, '', window.location.pathname)
    const access = params.get('access_token')
    if (!access) return setError('The sign-in didn\'t return a session. Try again.')
    const next = params.get('next') || '/centrum'
    // establish() sends the user on to ?next=, so put it there
    window.history.replaceState(null, '', `${window.location.pathname}?next=${encodeURIComponent(next)}`)
    loginWithTokens(access, params.get('refresh_token')).catch((e: any) => setError(e?.message || 'Single sign-on failed.'))
  }, [loginWithTokens])

  return (
    <AccountCard title="Signing you in">
      {error ? <p className="text-red-600" data-testid="sso-landing-error">{error}</p> : <p className="text-slate-600">One moment…</p>}
    </AccountCard>
  )
}
