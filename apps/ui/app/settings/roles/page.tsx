'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Loader2, Plus, ShieldCheck, Trash2, UserCog, UserMinus } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'

interface CustomRole {
  id: string; name: string; description: string; permissions: string[]; services: string[] | null; members: string[]
}
interface TenantUser { id: string; email: string; name: string; status: string }

const BUILT_IN: [string, string][] = [
  ['tenant_admin', 'Everything in the tenant, including users, roles and settings'],
  ['security_analyst', 'Security: alerts, cases, rules, threat intel, playbooks; read logs'],
  ['devops_engineer', 'Logs, alerts, dashboards, observability and integrations'],
  ['compliance_officer', 'Compliance, audit, reports and legal holds; read logs'],
  ['viewer', 'Read logs, dashboards and reports'],
]

const ACTIONS = ['read', 'write', '*']
const field = 'mt-1 w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-sm'

async function call<T>(promise: Promise<{ success?: boolean; data?: T; error?: string }>, what: string): Promise<T> {
  const r = await promise
  if (!r.success) throw new Error(r.error || what)
  return r.data as T
}

/**
 * Settings → Roles & Access (Phase 14): the built-in roles, and custom roles
 * that add permissions and/or limit which services' logs their holders read.
 */
export default function RolesPage() {
  const [roles, setRoles] = useState<CustomRole[] | null>(null)
  const [resources, setResources] = useState<string[]>([])
  const [users, setUsers] = useState<TenantUser[]>([])
  const [draft, setDraft] = useState<{ id?: string; name: string; description: string; grants: Record<string, string>; scoped: boolean; services: string } | null>(null)
  const [adding, setAdding] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [r, u] = await Promise.all([
        call<{ roles: CustomRole[]; resources: string[] }>(apiClient.get('/v1/roles/custom'), 'Failed to load roles'),
        call<{ users: TenantUser[] }>(apiClient.get('/v1/users'), 'Failed to load users'),
      ])
      setRoles(r.roles); setResources(r.resources)
      setUsers((u.users || []).filter(x => !x.email.endsWith('.system')))
    } catch (e: any) { setError(e?.message || 'Failed to load') }
  }, [])
  useEffect(() => { load() }, [load])

  const byId = useMemo(() => Object.fromEntries(users.map(u => [u.id, u])), [users])

  const edit = (role?: CustomRole) => {
    setMessage(null); setError(null)
    const grants: Record<string, string> = {}
    for (const p of role?.permissions || []) {
      const [res, act] = p.split(':')
      grants[res] = act === '*' ? '*' : act.includes('write') ? 'write' : 'read'
    }
    setDraft({ id: role?.id, name: role?.name || '', description: role?.description || '', grants,
      scoped: !!role && role.services !== null, services: (role?.services || []).join(', ') })
  }

  const save = async () => {
    if (!draft) return
    setError(null)
    const permissions = Object.entries(draft.grants).filter(([, a]) => a)
      .map(([res, a]) => `${res}:${a === 'write' ? 'read,write' : a}:tenant`)
    const body = { name: draft.name, description: draft.description, permissions,
      services: draft.scoped ? draft.services.split(/[\s,]+/).filter(Boolean) : null }
    try {
      await call(draft.id ? apiClient.put(`/v1/roles/custom/${draft.id}`, body) : apiClient.post('/v1/roles/custom', body), 'Failed to save')
      setMessage(`Saved ${draft.name}.`); setDraft(null)
      await load()
    } catch (e: any) { setError(e?.message || 'Failed to save') }
  }

  const remove = async (role: CustomRole) => {
    if (!window.confirm(`Delete ${role.name}? Its ${role.members.length} member(s) lose what it gives them.`)) return
    try { await call(apiClient.delete(`/v1/roles/custom/${role.id}`), 'Failed to delete'); await load() }
    catch (e: any) { setError(e?.message || 'Failed to delete') }
  }

  const member = async (role: CustomRole, userId: string, add: boolean) => {
    setError(null)
    try {
      await call(add ? apiClient.put(`/v1/roles/custom/${role.id}/members/${userId}`, {})
        : apiClient.delete(`/v1/roles/custom/${role.id}/members/${userId}`), 'Failed to update members')
      setAdding({ ...adding, [role.id]: '' })
      await load()
    } catch (e: any) { setError(e?.message || 'Failed to update members') }
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-8">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2"><UserCog className="w-6 h-6" /> Roles & Access</h1>
            <p className="text-slate-400 mt-1">Everyone has a built-in role. Custom roles add permissions, and can limit whose logs their holders see.</p>
          </div>
          <button onClick={() => edit()} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm flex items-center gap-2" data-testid="role-new">
            <Plus className="w-4 h-4" /> New custom role
          </button>
        </div>
        {message && <p className="text-sm text-emerald-300" data-testid="roles-message">{message}</p>}
        {error && <p className="text-sm text-red-400" data-testid="roles-error">{error}</p>}

        {draft && (
          <section className="rounded-xl bg-slate-900 border border-slate-700 p-5 space-y-4" data-testid="role-form">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-sm text-slate-300">Name
                <input className={field} value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} data-testid="role-name" />
              </label>
              <label className="text-sm text-slate-300">Description
                <input className={field} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} />
              </label>
            </div>
            <div>
              <p className="text-sm text-slate-300 mb-2">Extra permissions</p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {resources.map(res => (
                  <label key={res} className="text-xs text-slate-300 flex items-center justify-between gap-2 bg-slate-800 rounded px-2 py-1">
                    {res}
                    <select value={draft.grants[res] || ''} data-testid={`grant-${res}`}
                      onChange={e => setDraft({ ...draft, grants: { ...draft.grants, [res]: e.target.value } })}
                      className="bg-slate-900 border border-slate-700 rounded text-white text-xs px-1 py-0.5">
                      <option value="">—</option>
                      {ACTIONS.map(a => <option key={a} value={a}>{a === '*' ? 'all' : a}</option>)}
                    </select>
                  </label>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm text-slate-300 flex items-center gap-2">
                <input type="checkbox" checked={draft.scoped} onChange={e => setDraft({ ...draft, scoped: e.target.checked })} data-testid="role-scoped" />
                Limit the logs its holders see to these services
              </label>
              {draft.scoped && (
                <input className={field} placeholder="payments-*, billing" value={draft.services} data-testid="role-services"
                  onChange={e => setDraft({ ...draft, services: e.target.value })} />
              )}
              <p className="text-xs text-slate-500">
                Names, or prefixes ending in *. Applies to their logs, traces, metrics, security events and archive
                searches, and to every dashboard, field list and AI answer they get; alerts are hidden from them.
                Several scoped roles add up.
              </p>
            </div>
            <div className="flex gap-2">
              <button onClick={save} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm" data-testid="role-save">Save</button>
              <button onClick={() => setDraft(null)} className="px-4 py-2 rounded bg-slate-700 text-white text-sm">Cancel</button>
            </div>
          </section>
        )}

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-white">Custom roles</h2>
          {!roles && !error && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}
          {roles?.length === 0 && <p className="text-slate-400 text-sm" data-testid="roles-empty">No custom roles yet.</p>}
          {roles?.map(role => (
            <div key={role.id} className="rounded-xl bg-slate-900 border border-slate-800 p-4 space-y-3" data-testid={`role-${role.name}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-white font-medium">{role.name}</p>
                  {role.description && <p className="text-xs text-slate-400">{role.description}</p>}
                  <p className="text-xs text-slate-400 mt-1">
                    {role.permissions.length ? role.permissions.map(p => p.replace(':tenant', '')).join(' · ') : 'no extra permissions'}
                    {' · '}{role.services === null ? 'all logs' : role.services.length ? `logs of ${role.services.join(', ')}` : 'no logs'}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => edit(role)} className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-white text-xs">Edit</button>
                  <button aria-label={`Delete ${role.name}`} onClick={() => remove(role)} className="p-1 text-slate-400 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 items-center">
                {role.members.map(uid => (
                  <span key={uid} className="text-xs bg-slate-800 text-slate-200 rounded px-2 py-1 flex items-center gap-1" data-testid="role-member">
                    {byId[uid]?.email || uid}
                    <button aria-label="Remove" onClick={() => member(role, uid, false)} className="text-slate-400 hover:text-red-300"><UserMinus className="w-3 h-3" /></button>
                  </span>
                ))}
                <select value={adding[role.id] || ''} onChange={e => setAdding({ ...adding, [role.id]: e.target.value })} data-testid={`role-add-${role.name}`}
                  className="bg-slate-800 border border-slate-700 rounded text-white text-xs px-2 py-1">
                  <option value="">Add a member…</option>
                  {users.filter(u => !role.members.includes(u.id)).map(u => <option key={u.id} value={u.id}>{u.email}</option>)}
                </select>
                {adding[role.id] && <button onClick={() => member(role, adding[role.id], true)} className="text-xs px-2 py-1 rounded bg-blue-600 text-white" data-testid={`role-add-confirm-${role.name}`}>Add</button>}
              </div>
            </div>
          ))}
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2"><ShieldCheck className="w-5 h-5" /> Built-in roles</h2>
          <table className="w-full text-sm">
            <tbody>
              {BUILT_IN.map(([role, what]) => (
                <tr key={role} className="border-b border-slate-800"><td className="py-2 text-slate-200 font-mono text-xs w-48">{role}</td><td className="text-slate-400">{what}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-500">Assign built-in roles from the user list or through SSO and SCIM (Settings → Authentication).</p>
        </section>
      </div>
    </DashboardLayout>
  )
}
