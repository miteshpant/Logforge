'use client'

import { useCallback, useEffect, useState } from 'react'
import { KeyRound, Plus, Trash2 } from 'lucide-react'
import { API_CONFIG } from '@/lib/api'
import { deleteProvider, listProviders, saveProvider, type SsoProvider, type SsoProviderBody } from '@/lib/api/sso'

const BLANK: SsoProviderBody = {
  name: '', issuer: 'https://', client_id: '', client_secret: '', scopes: 'openid email profile', groups_claim: 'groups',
  role_mapping: {}, default_role: null, allowed_domains: [], enabled: true,
}

const field = 'mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm'

/**
 * Settings → Authentication → SSO (Phase 14): OIDC providers. Each lists
 * the email domains it signs in, and maps IdP groups to Logforge roles.
 */
export default function SsoProviders() {
  const [providers, setProviders] = useState<SsoProvider[]>([])
  const [roles, setRoles] = useState<string[]>([])
  const [callbackPath, setCallbackPath] = useState('/v1/auth/sso/callback')
  const [draft, setDraft] = useState<(SsoProviderBody & { id?: string; mapping: string; domains: string }) | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const out = await listProviders()
      setProviders(out.providers); setRoles(out.roles); setCallbackPath(out.callback_url_path)
    } catch (e: any) {
      setError(e?.message || 'Failed to load providers')
    }
  }, [])

  useEffect(() => { load() }, [load])

  const edit = (p?: SsoProvider) => {
    setMessage(null); setError(null)
    const base = p ? { ...p, client_secret: '' } : BLANK
    setDraft({ ...base, mapping: Object.entries(base.role_mapping).map(([g, r]) => `${g} = ${r}`).join('\n'),
      domains: base.allowed_domains.join(', ') })
  }

  const save = async () => {
    if (!draft) return
    setError(null)
    const role_mapping = Object.fromEntries(draft.mapping.split('\n').map(l => l.split('=').map(s => s.trim()))
      .filter(([g, r]) => g && r))
    const { id, mapping, domains, ...rest } = draft
    const body: SsoProviderBody = { ...rest, role_mapping, allowed_domains: domains.split(/[\s,]+/).filter(Boolean),
      default_role: draft.default_role || null }
    if (id && !draft.client_secret) delete body.client_secret // keep the stored one
    try {
      await saveProvider(body, id)
      setMessage(`Saved ${draft.name}.`); setDraft(null)
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to save')
    }
  }

  const remove = async (p: SsoProvider) => {
    if (!window.confirm(`Delete ${p.name}? Its users will need a password to sign in.`)) return
    try { await deleteProvider(p.id); await load() } catch (e: any) { setError(e?.message || 'Failed to delete') }
  }

  return (
    <div className="space-y-4" data-testid="sso-providers">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <p className="text-sm text-slate-400 max-w-2xl">
          OpenID Connect (Okta, Entra ID, Google Workspace, Keycloak, Auth0…). Register Logforge with your IdP using the
          redirect URI <code className="text-slate-200">{API_CONFIG.baseURL}{callbackPath}</code>.
        </p>
        <button data-testid="sso-add" onClick={() => edit()}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm">
          <Plus className="w-4 h-4" /> Add OIDC provider
        </button>
      </div>
      {message && <p className="text-sm text-emerald-300" data-testid="sso-message">{message}</p>}
      {error && <p className="text-sm text-red-400" data-testid="sso-error">{error}</p>}

      {draft && (
        <div className="rounded-xl bg-slate-900 border border-slate-700 p-5 grid gap-3 md:grid-cols-2" data-testid="sso-form">
          <label className="text-sm text-slate-300">Name (shown on the sign-in page)
            <input className={field} value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} data-testid="sso-name" />
          </label>
          <label className="text-sm text-slate-300">Issuer URL
            <input className={field} value={draft.issuer} onChange={e => setDraft({ ...draft, issuer: e.target.value })} data-testid="sso-issuer" />
          </label>
          <label className="text-sm text-slate-300">Client ID
            <input className={field} value={draft.client_id} onChange={e => setDraft({ ...draft, client_id: e.target.value })} data-testid="sso-client-id" />
          </label>
          <label className="text-sm text-slate-300">Client secret{draft.id ? ' (leave empty to keep)' : ''}
            <input type="password" autoComplete="off" className={field} value={draft.client_secret || ''}
              onChange={e => setDraft({ ...draft, client_secret: e.target.value })} data-testid="sso-client-secret" />
          </label>
          <label className="text-sm text-slate-300">Email domains it signs in
            <input className={field} value={draft.domains} placeholder="acme.com, acme.co.uk"
              onChange={e => setDraft({ ...draft, domains: e.target.value })} data-testid="sso-domains" />
          </label>
          <label className="text-sm text-slate-300">Groups claim
            <input className={field} value={draft.groups_claim} onChange={e => setDraft({ ...draft, groups_claim: e.target.value })} />
          </label>
          <label className="text-sm text-slate-300 md:col-span-2">Groups to roles, one per line (<code>group = role</code>; roles: {roles.join(', ')})
            <textarea rows={3} className={`${field} font-mono`} value={draft.mapping} placeholder="secops = security_analyst"
              onChange={e => setDraft({ ...draft, mapping: e.target.value })} data-testid="sso-mapping" />
          </label>
          <label className="text-sm text-slate-300">Role when no group matches
            <select className={field} value={draft.default_role || ''} onChange={e => setDraft({ ...draft, default_role: e.target.value || null })}>
              <option value="">None (refuse the sign-in)</option>
              {roles.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <label className="text-sm text-slate-300 flex items-end gap-2">
            <input type="checkbox" checked={draft.enabled} onChange={e => setDraft({ ...draft, enabled: e.target.checked })} /> Enabled
          </label>
          <div className="md:col-span-2 flex gap-2">
            <button onClick={save} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm" data-testid="sso-save">Save</button>
            <button onClick={() => setDraft(null)} className="px-4 py-2 rounded bg-slate-700 text-white text-sm">Cancel</button>
          </div>
        </div>
      )}

      {providers.length === 0 && !draft && (
        <p className="text-slate-400 text-sm" data-testid="sso-empty">No single sign-on yet: everyone signs in with a password.</p>
      )}
      {providers.map(p => (
        <div key={p.id} className="rounded-xl bg-slate-900 border border-slate-800 p-4 flex items-start justify-between gap-4" data-testid={`sso-provider-${p.name}`}>
          <div>
            <p className="text-white font-medium flex items-center gap-2"><KeyRound className="w-4 h-4" /> {p.name}
              <span className={`text-xs px-2 py-0.5 rounded ${p.enabled ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-600/30 text-slate-400'}`}>{p.enabled ? 'on' : 'off'}</span>
            </p>
            <p className="text-xs text-slate-400 mt-1">{p.issuer} · client {p.client_id}{p.client_secret_set ? ' · secret set' : ''}</p>
            <p className="text-xs text-slate-400">Domains: {p.allowed_domains.join(', ')} · {Object.entries(p.role_mapping).map(([g, r]) => `${g} → ${r}`).join(', ') || 'no group mapping'}
              {p.default_role ? ` · otherwise ${p.default_role}` : ' · otherwise refused'}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => edit(p)} className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-white text-xs">Edit</button>
            <button aria-label={`Delete ${p.name}`} onClick={() => remove(p)} className="p-1 text-slate-400 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
          </div>
        </div>
      ))}
    </div>
  )
}
