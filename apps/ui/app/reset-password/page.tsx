'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import AccountCard, { buttonClass, inputClass } from '@/components/auth/AccountCard'
import { resetPassword } from '@/lib/api/auth'

function ResetForm() {
  const token = useSearchParams().get('token') || ''
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== again) return setError("The two passwords don't match.")
    try {
      await resetPassword({ token, new_password: password }) // mutations throw on failure
      setDone(true)
    } catch (err: any) {
      setError(err?.message || 'The link is invalid or has expired.')
    }
  }

  if (!token) return <p className="text-red-600">This link has no reset token. Ask for a new one.</p>
  if (done) return <p className="text-slate-700" data-testid="reset-done">Your password is changed and every session was signed out. Sign in with the new one.</p>
  return (
    <form onSubmit={submit} className="space-y-4">
      <label className="block text-sm text-slate-700">New password
        <input type="password" required value={password} onChange={e => setPassword(e.target.value)} className={inputClass}
          autoComplete="new-password" data-testid="new-password" />
      </label>
      <label className="block text-sm text-slate-700">Again
        <input type="password" required value={again} onChange={e => setAgain(e.target.value)} className={inputClass}
          autoComplete="new-password" data-testid="new-password-again" />
      </label>
      {error && <p className="text-sm text-red-600" data-testid="reset-error">{error}</p>}
      <button type="submit" className={buttonClass} disabled={!password || !again} data-testid="reset-confirm">Change password</button>
    </form>
  )
}

export default function ResetPasswordPage() {
  return <AccountCard title="Choose a new password"><Suspense><ResetForm /></Suspense></AccountCard>
}
