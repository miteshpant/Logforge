'use client'

import { Suspense, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import AccountCard, { buttonClass, inputClass } from '@/components/auth/AccountCard'
import { acceptInvite } from '@/lib/api/auth'

function InviteForm() {
  const params = useSearchParams()
  const token = params.get('token') || ''
  const email = params.get('email') || ''
  const tenant = params.get('tenant') || ''
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await acceptInvite({ invitation_token: token, email, tenant_id: tenant, name, password }) // throws on failure
      setDone(true)
    } catch (err: any) {
      setError(err?.message || 'The invitation is invalid or has expired.')
    }
  }

  if (!token || !email || !tenant) return <p className="text-red-600">This invitation link is incomplete. Ask for a new one.</p>
  if (done) return <p className="text-slate-700" data-testid="invite-done">Your account is ready. <Link href="/login" className="text-blue-700 underline">Sign in</Link> as {email}.</p>
  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-slate-600">Create the account for <b>{email}</b>.</p>
      <label className="block text-sm text-slate-700">Your name
        <input required value={name} onChange={e => setName(e.target.value)} className={inputClass} autoComplete="name" data-testid="invite-name" />
      </label>
      <label className="block text-sm text-slate-700">Password
        <input type="password" required value={password} onChange={e => setPassword(e.target.value)} className={inputClass}
          autoComplete="new-password" data-testid="invite-password" />
        <span className="text-xs text-slate-500">At least 12 characters, with upper and lower case, a digit and a symbol.</span>
      </label>
      {error && <p className="text-sm text-red-600" data-testid="invite-error">{error}</p>}
      <button type="submit" className={buttonClass} disabled={!name || !password} data-testid="invite-accept">Create account</button>
    </form>
  )
}

export default function AcceptInvitePage() {
  return <AccountCard title="Join Logforge"><Suspense><InviteForm /></Suspense></AccountCard>
}
