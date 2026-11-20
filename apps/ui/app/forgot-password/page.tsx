'use client'

import { useState } from 'react'
import AccountCard, { buttonClass, inputClass } from '@/components/auth/AccountCard'
import { requestPasswordReset } from '@/lib/api/auth'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await requestPasswordReset(email) // the answer is the same whether or not the account exists
    } catch {
      // still say the same thing: don't reveal anything from a failure
    }
    setBusy(false)
    setSent(true)
  }

  return (
    <AccountCard title="Reset your password">
      {sent ? (
        <p className="text-slate-700" data-testid="reset-requested">
          If an account uses {email}, we sent it a link to choose a new password. It works for an hour.
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <label className="block text-sm text-slate-700">Email
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
              className={inputClass} data-testid="reset-email" autoComplete="email" />
          </label>
          <button type="submit" className={buttonClass} disabled={busy || !email} data-testid="reset-request">Email me a link</button>
        </form>
      )}
    </AccountCard>
  )
}
