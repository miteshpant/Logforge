'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import AccountCard from '@/components/auth/AccountCard'
import { verifyEmail } from '@/lib/api/auth'

function Verify() {
  const token = useSearchParams().get('token') || ''
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    if (!token) return setResult({ ok: false, text: 'This link has no token.' })
    verifyEmail(token) // throws on failure
      .then(() => setResult({ ok: true, text: 'Your email address is confirmed.' }))
      .catch((err: any) => setResult({ ok: false, text: err?.message || 'The link is invalid, has expired, or is for another account.' }))
  }, [token])

  if (!result) return <p className="text-slate-600">Checking the link…</p>
  return <p className={result.ok ? 'text-emerald-700' : 'text-red-600'} data-testid="verify-result">{result.text}</p>
}

/** Needs the session of the account being verified (the route guard sends visitors to sign in first). */
export default function VerifyEmailPage() {
  return <AccountCard title="Confirm your email"><Suspense><Verify /></Suspense></AccountCard>
}
