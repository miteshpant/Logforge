'use client'

import { useCallback, useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { mfaConfirm, mfaDisable, mfaSetup, mfaStatus, type MfaStatus } from '@/lib/api/auth'

const field = 'bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm'

/**
 * Settings → Authentication → MFA: the signed-in user's own TOTP. Once on,
 * signing in with a password also needs a code (or a one-time backup code).
 */
export default function MfaSettings() {
  const [status, setStatus] = useState<MfaStatus | null>(null)
  const [setup, setSetup] = useState<{ secret: string; otpauth_url: string } | null>(null)
  const [code, setCode] = useState('')
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const r = await mfaStatus()
    if (r.success && r.data) setStatus(r.data)
    else setError(r.error || 'Failed to load MFA status')
  }, [])
  useEffect(() => { load() }, [load])

  const start = async () => {
    setError(null)
    try { setSetup((await mfaSetup()).data!) } catch (e: any) { setError(e?.message || 'Failed to start') }
  }
  const confirm = async () => {
    setError(null)
    try {
      const r = await mfaConfirm(code)
      setBackupCodes(r.data!.backup_codes); setSetup(null); setCode('')
      await load()
    } catch (e: any) { setError(e?.message || "That code isn't valid") }
  }
  const disable = async () => {
    setError(null)
    const r = await mfaDisable(code)
    if (!r.success) return setError(r.error || "That code isn't valid")
    setCode(''); setBackupCodes(null)
    await load()
  }

  return (
    <div className="rounded-xl bg-slate-900 border border-slate-800 p-5 space-y-4 max-w-2xl" data-testid="mfa-settings">
      <h3 className="text-white font-semibold flex items-center gap-2"><ShieldCheck className="w-4 h-4" /> Two-step sign-in (TOTP)</h3>
      {status && (
        <p className="text-sm text-slate-300" data-testid="mfa-state">
          {status.enabled ? `On. ${status.backup_codes_left} backup code(s) left.` : 'Off: your password alone signs you in.'}
        </p>
      )}
      {error && <p className="text-sm text-red-400" data-testid="mfa-error">{error}</p>}

      {backupCodes && (
        <div className="rounded border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="mfa-backup-codes">
          Keep these one-time backup codes somewhere safe; they aren&apos;t shown again:
          <div className="grid grid-cols-2 gap-1 mt-2 font-mono text-white">{backupCodes.map(c => <span key={c}>{c}</span>)}</div>
        </div>
      )}

      {status && !status.enabled && !setup && (
        <button onClick={start} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm" data-testid="mfa-start">
          Turn on
        </button>
      )}

      {setup && (
        <div className="space-y-3">
          <p className="text-sm text-slate-300">
            Add this account to your authenticator app (open the link on your phone, or type the key), then enter the code it shows.
          </p>
          <p className="text-xs text-slate-400 break-all">Key: <code className="text-white" data-testid="mfa-secret">{setup.secret}</code></p>
          <p className="text-xs text-slate-400 break-all">Link: <a className="text-blue-300" href={setup.otpauth_url}>{setup.otpauth_url}</a></p>
          <div className="flex gap-2">
            <input className={field} placeholder="123456" value={code} onChange={e => setCode(e.target.value)} data-testid="mfa-confirm-code" />
            <button onClick={confirm} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm" data-testid="mfa-confirm">Confirm</button>
          </div>
        </div>
      )}

      {status?.enabled && (
        <div className="flex gap-2 items-center">
          <input className={field} placeholder="Code or backup code" value={code} onChange={e => setCode(e.target.value)} data-testid="mfa-disable-code" />
          <button onClick={disable} className="px-4 py-2 rounded bg-red-700 hover:bg-red-600 text-white text-sm" data-testid="mfa-disable">Turn off</button>
        </div>
      )}
    </div>
  )
}
