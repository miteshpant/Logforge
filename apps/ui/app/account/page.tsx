'use client'

import { useState } from 'react'
import { UserCircle } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import MfaSettings from '@/components/settings/MfaSettings'
import { useAuth } from '@/contexts/AuthContext'
import { changePassword } from '@/lib/api/auth'

const field = 'mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm'

/** Your account: who you are, your password and two-step sign-in. Open to every role. */
export default function AccountPage() {
  const { user, userRole } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const change = async (e: React.FormEvent) => {
    e.preventDefault()
    setMessage(null); setError(null)
    try {
      const r = await changePassword({ current_password: current, new_password: next })
      if (r.success === false) throw new Error(r.error || 'Failed to change the password')
      setMessage('Password changed.'); setCurrent(''); setNext('')
    } catch (err: any) { setError(err?.message || 'Failed to change the password') }
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6" data-testid="account-page">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2"><UserCircle className="w-6 h-6" /> Your account</h1>
          <p className="text-slate-400 mt-1">{user?.name} · {user?.email}{userRole ? ` · ${userRole}` : ''}</p>
        </div>

        <MfaSettings />

        <form onSubmit={change} className="rounded-xl bg-slate-900 border border-slate-800 p-5 space-y-3 max-w-2xl">
          <h3 className="text-white font-semibold">Change password</h3>
          {message && <p className="text-sm text-emerald-300">{message}</p>}
          {error && <p className="text-sm text-red-400">{error}</p>}
          <label className="block text-sm text-slate-300">Current password
            <input type="password" autoComplete="current-password" className={field} value={current} onChange={e => setCurrent(e.target.value)} />
          </label>
          <label className="block text-sm text-slate-300">New password (12+ characters, upper and lower case, a digit and a symbol)
            <input type="password" autoComplete="new-password" className={field} value={next} onChange={e => setNext(e.target.value)} />
          </label>
          <button disabled={!current || !next} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm">Change password</button>
        </form>
      </div>
    </DashboardLayout>
  )
}
