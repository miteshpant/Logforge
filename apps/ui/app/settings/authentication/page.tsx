'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Key,
  Shield,
  Plus,
  Trash2,
  Copy,
  Eye,
  EyeOff,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  RefreshCw,
  Settings,
  ExternalLink,
  Lock,
  Smartphone,
  Globe,
  Server,
  ChevronRight,
  ChevronDown,
  X,
  Search,
  Filter,
  Calendar,
  Zap
} from 'lucide-react'

// Types
interface APIKey {
  id: string
  name: string
  description: string
  key_prefix: string
  permissions: string[]
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  rate_limit: number
  ip_whitelist: string[]
  status: 'active' | 'expired' | 'revoked'
}

interface AuthProvider {
  id: string
  provider_name: string
  provider_type: 'oidc' | 'saml' | 'okta' | 'azure_ad' | 'google'
  domain: string
  enabled: boolean
  created_at: string
  last_sync?: string
  user_count: number
}

interface MFAStatus {
  enabled: boolean
  enforced: boolean
  methods: string[]
  enrolled_users: number
  total_users: number
}

// Permission options for API keys
const PERMISSION_OPTIONS = [
  { id: 'logs:read', label: 'Read Logs', category: 'Logs' },
  { id: 'logs:write', label: 'Write Logs', category: 'Logs' },
  { id: 'metrics:read', label: 'Read Metrics', category: 'Metrics' },
  { id: 'metrics:write', label: 'Write Metrics', category: 'Metrics' },
  { id: 'traces:read', label: 'Read Traces', category: 'Traces' },
  { id: 'traces:write', label: 'Write Traces', category: 'Traces' },
  { id: 'alerts:read', label: 'Read Alerts', category: 'Alerts' },
  { id: 'alerts:write', label: 'Manage Alerts', category: 'Alerts' },
  { id: 'security:read', label: 'Read Security Events', category: 'Security' },
  { id: 'dashboards:read', label: 'Read Dashboards', category: 'Dashboards' },
  { id: 'dashboards:write', label: 'Manage Dashboards', category: 'Dashboards' },
]

const PROVIDER_TYPE_INFO: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  oidc: { label: 'OpenID Connect', icon: <Globe className="w-5 h-5" />, color: 'text-blue-400 bg-blue-500/20' },
  okta: { label: 'Okta', icon: <Shield className="w-5 h-5" />, color: 'text-indigo-400 bg-indigo-500/20' },
  azure_ad: { label: 'Azure AD', icon: <Server className="w-5 h-5" />, color: 'text-cyan-400 bg-cyan-500/20' },
  google: { label: 'Google Workspace', icon: <Globe className="w-5 h-5" />, color: 'text-red-400 bg-red-500/20' },
  saml: { label: 'SAML 2.0', icon: <Lock className="w-5 h-5" />, color: 'text-purple-400 bg-purple-500/20' },
}

export default function AuthenticationPage() {
  const [activeTab, setActiveTab] = useState<'api-keys' | 'sso' | 'mfa'>('api-keys')
  const [isLoading, setIsLoading] = useState(true)

  // API Keys state
  const [apiKeys, setApiKeys] = useState<APIKey[]>([])
  const [showCreateKeyModal, setShowCreateKeyModal] = useState(false)
  const [newKeyData, setNewKeyData] = useState({
    name: '',
    description: '',
    permissions: [] as string[],
    expires_at: '',
    rate_limit: 10000,
    ip_whitelist: ''
  })
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [showKeyValue, setShowKeyValue] = useState(false)
  // ENH-040/041/047: failures must be visible to the operator, not just logged.
  const [keyError, setKeyError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  // SSO state
  const [authProviders, setAuthProviders] = useState<AuthProvider[]>([])
  const [showConfigureSSO, setShowConfigureSSO] = useState(false)
  const [ssoConfig, setSsoConfig] = useState({
    provider_name: '',
    provider_type: 'oidc' as const,
    client_id: '',
    client_secret: '',
    domain: '',
    scopes: ['openid', 'profile', 'email'],
    enabled: true
  })

  // MFA state
  const [mfaStatus, setMfaStatus] = useState<MFAStatus | null>(null)

  // Search
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    setLoadError(null)
    try {
      // ENH-046: `/v1/enterprise/auth/mfa/status` was requested here but does
      // not exist -- `enterprise_api.py` defines only `POST /auth/mfa/setup`.
      // Inside `allSettled` the 404 was discarded and the MFA panel rendered
      // blank forever. The call is removed; the panel now states plainly that
      // status reporting is unavailable rather than implying "MFA is off".
      const [keysRes, providersRes] = await Promise.allSettled([
        apiClient.get('/v1/enterprise/auth/api-keys'),
        apiClient.get('/v1/enterprise/auth/providers')
      ])

      // ENH-047: a rejected promise, or the client's resolved-but-failed shape,
      // must be surfaced. Silently leaving the list empty makes a broken
      // backend indistinguishable from a tenant with no keys.
      const failures: string[] = []

      if (keysRes.status === 'fulfilled' && keysRes.value?.success !== false) {
        const data = keysRes.value?.data || keysRes.value
        const keys = data?.api_keys ?? (Array.isArray(data) ? data : [])
        // Server returns `key_id`; the table keys off `id`.
        setApiKeys(
          keys.map((k: any) => ({
            ...k,
            id: k.key_id ?? k.id,
            status: k.status ?? 'active',
            last_used_at: k.last_used ?? k.last_used_at ?? null
          }))
        )
      } else {
        const reason =
          keysRes.status === 'rejected'
            ? keysRes.reason?.message
            : keysRes.value?.error
        failures.push(`API keys: ${reason || 'request failed'}`)
      }

      if (providersRes.status === 'fulfilled' && providersRes.value?.success !== false) {
        const data = providersRes.value?.data || providersRes.value
        setAuthProviders(data?.providers || (Array.isArray(data) ? data : []))
      } else {
        const reason =
          providersRes.status === 'rejected'
            ? providersRes.reason?.message
            : providersRes.value?.error
        failures.push(`SSO providers: ${reason || 'request failed'}`)
      }

      if (failures.length > 0) {
        setLoadError(failures.join(' · '))
      }
    } finally {
      setIsLoading(false)
    }
  }

  // API Key functions
  const handleCreateAPIKey = async () => {
    if (!newKeyData.name) return

    try {
      const payload = {
        name: newKeyData.name,
        description: newKeyData.description,
        permissions: newKeyData.permissions,
        expires_at: newKeyData.expires_at || null,
        rate_limit: newKeyData.rate_limit,
        ip_whitelist: newKeyData.ip_whitelist
          ? newKeyData.ip_whitelist.split(',').map(ip => ip.trim()).filter(Boolean)
          : []
      }

      // ENH-040: this must throw on failure; apiClient mutations reject with
      // ApiError, so a refused creation never reaches the code below.
      const response = await apiClient.post('/v1/enterprise/auth/api-keys', payload)
      const data = response?.data || response

      // The secret is returned exactly once, as `api_key`
      // (apps/api/services/enterprise_service.py:333).
      const secret = data?.api_key
      if (!secret) {
        throw new Error('Server did not return an API key')
      }
      setCreatedKey(secret)

      // Field names mirror the server response; nothing is invented here.
      const newKey: APIKey = {
        id: data.key_id,
        name: data.name,
        description: data.description ?? '',
        key_prefix: `${String(secret).slice(0, 12)}****`,
        permissions: data.permissions ?? [],
        created_at: data.created_at,
        expires_at: data.expires_at ?? null,
        last_used_at: null,
        rate_limit: data.rate_limit,
        ip_whitelist: data.ip_whitelist ?? [],
        status: 'active'
      }
      setApiKeys(prev => [newKey, ...prev])

      // Reset form but keep modal open to show key
      setNewKeyData({
        name: '',
        description: '',
        permissions: [],
        expires_at: '',
        rate_limit: 10000,
        ip_whitelist: ''
      })
    } catch (error) {
      // ENH-040: previously this fabricated `lf_live_<random>` and presented it
      // as a working credential. A key that does not exist server-side must
      // never be shown -- the user would store it and get 401s forever. Surface
      // the real failure and add nothing to the list.
      setKeyError(error instanceof Error ? error.message : 'Failed to create API key')
      setCreatedKey(null)
    }
  }

  const handleRevokeKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) return

    // ENH-041: the revocation state must reflect the server, not the intent.
    // Previously this marked the key "revoked" even when the DELETE failed --
    // during a leaked-credential incident that is a false sense of containment
    // while the key stays live.
    try {
      // Rejects with ApiError if the revocation fails.
      await apiClient.delete(`/v1/enterprise/auth/api-keys/${keyId}`)
    } catch (error) {
      setKeyError(
        `Failed to revoke key: ${error instanceof Error ? error.message : 'unknown error'}. The key is still active.`
      )
      return
    }

    setKeyError(null)
    setApiKeys(prev => prev.map(key =>
      key.id === keyId ? { ...key, status: 'revoked' as const } : key
    ))
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const togglePermission = (permId: string) => {
    setNewKeyData(prev => ({
      ...prev,
      permissions: prev.permissions.includes(permId)
        ? prev.permissions.filter(p => p !== permId)
        : [...prev.permissions, permId]
    }))
  }

  // SSO functions
  const handleConfigureSSO = async () => {
    if (!ssoConfig.client_id || !ssoConfig.domain) return

    // ENH-041: a failed SSO configuration previously still added the provider
    // row and closed the dialog, telling the operator that federated login was
    // configured when the server had rejected it. Only reflect confirmed state,
    // then re-read from the server rather than guessing the stored shape.
    try {
      // Rejects with ApiError if the server refuses the configuration.
      await apiClient.post('/v1/enterprise/auth/oidc/configure', ssoConfig)

      setShowConfigureSSO(false)
      setSsoConfig({
        provider_name: '',
        provider_type: 'oidc',
        client_id: '',
        client_secret: '',
        domain: '',
        scopes: ['openid', 'profile', 'email'],
        enabled: true
      })
      await loadData()
    } catch (error) {
      setKeyError(
        `Failed to configure SSO: ${error instanceof Error ? error.message : 'unknown error'}`
      )
    }
  }

  // ENH-041: this used to flip `enabled` in local state with no API call at
  // all, so the switch appeared to work and silently reverted on reload. The
  // backend exposes no enable/disable route for auth providers -- only
  // `GET /v1/enterprise/auth/providers` and
  // `POST /v1/enterprise/auth/oidc/configure` exist. Rather than fake a
  // persisted change to a security control, the control is disabled in the UI
  // and the missing capability is stated. Implementing the endpoint is
  // follow-up work.
  const PROVIDER_TOGGLE_UNAVAILABLE =
    'Enabling or disabling a provider is not supported by the API yet.'

  // Utility functions
  const formatDate = (date: string | null) => {
    if (!date) return 'Never'
    return new Date(date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  const formatTimeAgo = (timestamp: string | null) => {
    if (!timestamp) return 'Never'
    const diff = Date.now() - new Date(timestamp).getTime()
    const days = Math.floor(diff / 86400000)
    const hours = Math.floor(diff / 3600000)
    if (days > 0) return `${days}d ago`
    if (hours > 0) return `${hours}h ago`
    return 'Just now'
  }

  const getKeyStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'expired': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'revoked': return 'bg-red-500/20 text-red-400 border-red-500/30'
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30'
    }
  }

  const filteredKeys = apiKeys.filter(key =>
    key.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    key.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Stats
  const activeKeys = apiKeys.filter(k => k.status === 'active').length
  const enabledProviders = authProviders.filter(p => p.enabled).length

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Authentication</h1>
            <p className="text-slate-400 mt-1">Manage API keys, SSO providers, and multi-factor authentication</p>
          </div>
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4 min-w-0">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/20 rounded-lg flex-shrink-0">
                <Key className="w-5 h-5 text-blue-400" />
              </div>
              <div className="min-w-0">
                <p className="text-slate-400 text-sm">Active API Keys</p>
                <p className="text-2xl font-bold text-white">{activeKeys}</p>
              </div>
            </div>
          </div>
          <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4 min-w-0">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-500/20 rounded-lg flex-shrink-0">
                <Shield className="w-5 h-5 text-purple-400" />
              </div>
              <div className="min-w-0">
                <p className="text-slate-400 text-sm">SSO Providers</p>
                <p className="text-2xl font-bold text-white">{enabledProviders}</p>
              </div>
            </div>
          </div>
          <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4 min-w-0">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-500/20 rounded-lg flex-shrink-0">
                <Smartphone className="w-5 h-5 text-green-400" />
              </div>
              <div className="min-w-0">
                <p className="text-slate-400 text-sm">MFA Enrolled</p>
                {/* ENH-046: no MFA status endpoint exists, so "0/0" would be a
                    fabricated reading of a security control. Show unknown. */}
                <p className="text-2xl font-bold text-white">
                  {mfaStatus ? `${mfaStatus.enrolled_users}/${mfaStatus.total_users}` : '—'}
                </p>
              </div>
            </div>
          </div>
          <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4 min-w-0">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-500/20 rounded-lg flex-shrink-0">
                <Lock className="w-5 h-5 text-orange-400" />
              </div>
              <div className="min-w-0">
                <p className="text-slate-400 text-sm">MFA Status</p>
                {/* ENH-046: reporting "Disabled" for an unknown state would tell
                    an operator their tenant is unprotected when we simply have
                    no data. Unknown is reported as unknown. */}
                <p className="text-2xl font-bold text-white">
                  {mfaStatus
                    ? mfaStatus.enforced
                      ? 'Enforced'
                      : mfaStatus.enabled
                        ? 'Optional'
                        : 'Disabled'
                    : 'Unknown'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-800/50 p-1 rounded-lg w-fit">
          <button
            onClick={() => setActiveTab('api-keys')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'api-keys'
                ? 'bg-blue-500/20 text-blue-400'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Key className="w-4 h-4" />
            API Keys ({apiKeys.length})
          </button>
          <button
            onClick={() => setActiveTab('sso')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'sso'
                ? 'bg-blue-500/20 text-blue-400'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Shield className="w-4 h-4" />
            SSO / OIDC ({authProviders.length})
          </button>
          <button
            onClick={() => setActiveTab('mfa')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'mfa'
                ? 'bg-blue-500/20 text-blue-400'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Smartphone className="w-4 h-4" />
            MFA
          </button>
        </div>

        {/* ENH-047: request failures are rendered, not just logged, so a broken
            backend is never mistaken for "no data". */}
        {loadError && (
          <div className="flex items-start gap-3 rounded-lg border border-red-500/40 bg-red-500/10 p-4">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-red-300">Failed to load authentication data</p>
              <p className="text-sm text-red-200/80 break-words">{loadError}</p>
            </div>
            <button
              onClick={loadData}
              className="ml-auto flex-shrink-0 text-sm text-red-300 hover:text-white underline"
            >
              Retry
            </button>
          </div>
        )}

        {keyError && (
          <div className="flex items-start gap-3 rounded-lg border border-red-500/40 bg-red-500/10 p-4">
            <XCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-200 break-words">{keyError}</p>
            <button
              onClick={() => setKeyError(null)}
              className="ml-auto flex-shrink-0 text-red-300 hover:text-white"
              aria-label="Dismiss error"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : (
          <>
            {/* API Keys Tab */}
            {activeTab === 'api-keys' && (
              <div className="space-y-4">
                {/* Actions Bar */}
                <div className="flex items-center justify-between">
                  <div className="relative w-64">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Search API keys..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-white/10 rounded-lg text-white placeholder-slate-500 text-sm"
                    />
                  </div>
                  <button
                    onClick={() => {
                      setShowCreateKeyModal(true)
                      setCreatedKey(null)
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    Create API Key
                  </button>
                </div>

                {/* API Keys List */}
                {filteredKeys.length === 0 ? (
                  <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-12 text-center">
                    <Key className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <h3 className="text-lg font-semibold text-white mb-2">No API Keys</h3>
                    <p className="text-slate-400 text-sm max-w-md mx-auto">
                      Create API keys to authenticate external applications and services with Logforge.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredKeys.map((key) => (
                      <div
                        key={key.id}
                        className={`rounded-xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border p-4 ${
                          (key.status || 'active') === 'revoked' ? 'opacity-60 border-white/5' : 'border-white/5'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4">
                            <div className={`p-2 rounded-lg ${
                              (key.status || 'active') === 'active' ? 'bg-blue-500/20' : 'bg-slate-500/20'
                            }`}>
                              <Key className={`w-5 h-5 ${
                                (key.status || 'active') === 'active' ? 'text-blue-400' : 'text-slate-400'
                              }`} />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="text-white font-semibold">{key.name}</h3>
                                <span className={`px-2 py-0.5 rounded text-xs font-medium border ${getKeyStatusColor(key.status || 'active')}`}>
                                  {(key.status || 'active').toUpperCase()}
                                </span>
                              </div>
                              <p className="text-slate-400 text-sm mt-1">{key.description || 'No description'}</p>

                              {/* Key prefix */}
                              {key.key_prefix && (
                                <div className="flex items-center gap-2 mt-2">
                                  <code className="px-2 py-1 bg-slate-700/50 rounded text-sm text-slate-300 font-mono">
                                    {key.key_prefix}
                                  </code>
                                  <button
                                    onClick={() => copyToClipboard(key.key_prefix)}
                                    className="p-1 text-slate-400 hover:text-white"
                                    title="Copy key prefix"
                                  >
                                    <Copy className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              )}

                              {/* Permissions */}
                              <div className="flex flex-wrap gap-1 mt-3">
                                {(key.permissions || []).slice(0, 4).map((perm) => (
                                  <span key={perm} className="px-2 py-0.5 bg-slate-700 text-slate-300 text-xs rounded">
                                    {perm}
                                  </span>
                                ))}
                                {(key.permissions || []).length > 4 && (
                                  <span className="px-2 py-0.5 bg-slate-700 text-slate-400 text-xs rounded">
                                    +{(key.permissions || []).length - 4} more
                                  </span>
                                )}
                              </div>

                              {/* Metadata */}
                              <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                                <span className="flex items-center gap-1">
                                  <Calendar className="w-3 h-3" />
                                  Created {formatDate(key.created_at)}
                                </span>
                                <span className="flex items-center gap-1">
                                  <Clock className="w-3 h-3" />
                                  Expires {key.expires_at ? formatDate(key.expires_at) : 'Never'}
                                </span>
                                <span className="flex items-center gap-1">
                                  <Zap className="w-3 h-3" />
                                  {(key.rate_limit || 1000).toLocaleString()} req/hr
                                </span>
                                {key.last_used_at && (
                                  <span className="flex items-center gap-1">
                                    <Clock className="w-3 h-3" />
                                    Last used {formatTimeAgo(key.last_used_at)}
                                  </span>
                                )}
                              </div>

                              {/* IP Whitelist */}
                              {(key.ip_whitelist || []).length > 0 && (
                                <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
                                  <Globe className="w-3 h-3" />
                                  <span>IP Restricted: {(key.ip_whitelist || []).join(', ')}</span>
                                </div>
                              )}
                            </div>
                          </div>

                          {(key.status || 'active') === 'active' && (
                            <button
                              onClick={() => handleRevokeKey(key.id)}
                              className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                              title="Revoke key"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* SSO Tab */}
            {activeTab === 'sso' && (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <button
                    onClick={() => setShowConfigureSSO(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    Configure SSO Provider
                  </button>
                </div>

                {authProviders.length === 0 ? (
                  <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-12 text-center">
                    <Shield className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <h3 className="text-lg font-semibold text-white mb-2">No SSO Providers Configured</h3>
                    <p className="text-slate-400 text-sm max-w-md mx-auto">
                      Configure Single Sign-On with your identity provider (Okta, Azure AD, Google, or any OIDC provider).
                    </p>
                  </div>
                ) : (
                  <div className="grid gap-4">
                    {authProviders.map((provider) => {
                      const typeInfo = PROVIDER_TYPE_INFO[provider.provider_type] || PROVIDER_TYPE_INFO.oidc
                      return (
                        <div
                          key={provider.id}
                          className={`rounded-xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border p-4 ${
                            provider.enabled ? 'border-white/5' : 'border-white/5 opacity-60'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                              <div className={`p-3 rounded-lg ${typeInfo.color}`}>
                                {typeInfo.icon}
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <h3 className="text-white font-semibold">{provider.provider_name}</h3>
                                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                    provider.enabled
                                      ? 'bg-green-500/20 text-green-400'
                                      : 'bg-slate-500/20 text-slate-400'
                                  }`}>
                                    {provider.enabled ? 'Active' : 'Disabled'}
                                  </span>
                                </div>
                                <p className="text-slate-400 text-sm mt-1">
                                  {typeInfo.label} - {provider.domain}
                                </p>
                                <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                                  <span>{provider.user_count} users</span>
                                  <span>Created {formatDate(provider.created_at)}</span>
                                  {provider.last_sync && (
                                    <span>Last sync {formatTimeAgo(provider.last_sync)}</span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <button
                                disabled
                                title={PROVIDER_TOGGLE_UNAVAILABLE}
                                className="px-3 py-1.5 rounded-lg text-sm bg-slate-800 text-slate-500 cursor-not-allowed"
                              >
                                {provider.enabled ? 'Enabled' : 'Disabled'}
                              </button>
                              <button
                                className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                                title="Configure"
                              >
                                <Settings className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}

            {/* MFA Tab */}
            {activeTab === 'mfa' && (
              <div className="space-y-4">
                {/* ENH-046: there is no endpoint that reports MFA status, so the
                    panel below cannot show live state. Say so explicitly --
                    rendering the per-method cards as "Disabled" would assert a
                    security posture we have not measured. */}
                {!mfaStatus && (
                  <div className="flex items-start gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4">
                    <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-amber-300">MFA status is unavailable</p>
                      <p className="text-sm text-amber-200/80">
                        This deployment does not expose an MFA status endpoint, so enrolment and
                        enforcement cannot be reported here. The settings below are not live state.
                      </p>
                    </div>
                  </div>
                )}
                <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
                  <div className="flex items-start justify-between mb-6">
                    <div>
                      <h3 className="text-lg font-semibold text-white">Multi-Factor Authentication</h3>
                      <p className="text-slate-400 text-sm mt-1">
                        Require users to verify their identity with a second factor
                      </p>
                    </div>
                    <div className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                      !mfaStatus
                        ? 'bg-slate-500/20 text-slate-400'
                        : mfaStatus.enforced
                          ? 'bg-green-500/20 text-green-400'
                          : mfaStatus.enabled
                            ? 'bg-blue-500/20 text-blue-400'
                            : 'bg-slate-500/20 text-slate-400'
                    }`}>
                      {!mfaStatus
                        ? 'Unknown'
                        : mfaStatus.enforced
                          ? 'Enforced'
                          : mfaStatus.enabled
                            ? 'Optional'
                            : 'Disabled'}
                    </div>
                  </div>

                  {/* MFA Options */}
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="p-4 bg-slate-700/30 rounded-lg border border-white/5">
                      <div className="flex items-center gap-3 mb-3">
                        <div className="p-2 bg-blue-500/20 rounded-lg">
                          <Smartphone className="w-5 h-5 text-blue-400" />
                        </div>
                        <div>
                          <h4 className="text-white font-medium">Authenticator App</h4>
                          <p className="text-xs text-slate-400">TOTP-based (Google, Authy)</p>
                        </div>
                      </div>
                      <div className={`px-2 py-1 rounded text-xs font-medium inline-block ${
                        mfaStatus?.methods?.includes('totp')
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-slate-500/20 text-slate-400'
                      }`}>
                        {mfaStatus?.methods?.includes('totp') ? 'Enabled' : 'Disabled'}
                      </div>
                    </div>

                    <div className="p-4 bg-slate-700/30 rounded-lg border border-white/5">
                      <div className="flex items-center gap-3 mb-3">
                        <div className="p-2 bg-purple-500/20 rounded-lg">
                          <Key className="w-5 h-5 text-purple-400" />
                        </div>
                        <div>
                          <h4 className="text-white font-medium">Security Keys</h4>
                          <p className="text-xs text-slate-400">FIDO2/WebAuthn</p>
                        </div>
                      </div>
                      <div className={`px-2 py-1 rounded text-xs font-medium inline-block ${
                        mfaStatus?.methods?.includes('webauthn')
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-slate-500/20 text-slate-400'
                      }`}>
                        {mfaStatus?.methods?.includes('webauthn') ? 'Enabled' : 'Disabled'}
                      </div>
                    </div>

                    <div className="p-4 bg-slate-700/30 rounded-lg border border-white/5">
                      <div className="flex items-center gap-3 mb-3">
                        <div className="p-2 bg-orange-500/20 rounded-lg">
                          <Lock className="w-5 h-5 text-orange-400" />
                        </div>
                        <div>
                          <h4 className="text-white font-medium">Backup Codes</h4>
                          <p className="text-xs text-slate-400">One-time recovery codes</p>
                        </div>
                      </div>
                      <div className={`px-2 py-1 rounded text-xs font-medium inline-block ${
                        mfaStatus?.methods?.includes('backup_codes')
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-slate-500/20 text-slate-400'
                      }`}>
                        {mfaStatus?.methods?.includes('backup_codes') ? 'Enabled' : 'Disabled'}
                      </div>
                    </div>
                  </div>

                  {/* MFA Enrollment Stats */}
                  <div className="mt-6 pt-6 border-t border-white/5">
                    <h4 className="text-white font-medium mb-4">Enrollment Status</h4>
                    <div className="flex items-center gap-4">
                      <div className="flex-1">
                        <div className="flex justify-between text-sm mb-2">
                          <span className="text-slate-400">Users with MFA</span>
                          <span className="text-white font-medium">
                            {mfaStatus?.enrolled_users || 0} / {mfaStatus?.total_users || 0}
                          </span>
                        </div>
                        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-green-500 rounded-full transition-all duration-500"
                            style={{
                              width: mfaStatus?.total_users
                                ? `${(mfaStatus.enrolled_users / mfaStatus.total_users) * 100}%`
                                : '0%'
                            }}
                          />
                        </div>
                      </div>
                      <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm transition-colors">
                        Enforce MFA
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* Create API Key Modal */}
        {showCreateKeyModal && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-slate-900 border border-white/10 rounded-xl w-full max-w-xl mx-4 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-4 border-b border-white/5">
                <h3 className="text-lg font-semibold text-white">
                  {createdKey ? 'API Key Created' : 'Create API Key'}
                </h3>
                <button
                  onClick={() => {
                    setShowCreateKeyModal(false)
                    setCreatedKey(null)
                  }}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-4 space-y-4">
                {createdKey ? (
                  /* Show created key */
                  <div className="space-y-4">
                    <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                      <div className="flex items-start gap-3">
                        <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                        <div>
                          <p className="text-green-400 font-medium">API Key Created Successfully</p>
                          <p className="text-green-400/80 text-sm mt-1">
                            Copy this key now. You won't be able to see it again.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-2">Your API Key</label>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 relative">
                          <input
                            type={showKeyValue ? 'text' : 'password'}
                            value={createdKey}
                            readOnly
                            className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white font-mono text-sm pr-20"
                          />
                          <button
                            onClick={() => setShowKeyValue(!showKeyValue)}
                            className="absolute right-10 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                          >
                            {showKeyValue ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                          <button
                            onClick={() => copyToClipboard(createdKey)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                          >
                            <Copy className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                      <div className="flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5" />
                        <p className="text-yellow-400 text-sm">
                          Store this key securely. It will not be shown again.
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Create key form */
                  <>
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-1">Name *</label>
                      <input
                        type="text"
                        value={newKeyData.name}
                        onChange={(e) => setNewKeyData({ ...newKeyData, name: e.target.value })}
                        placeholder="e.g., Production API Key"
                        className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-1">Description</label>
                      <textarea
                        value={newKeyData.description}
                        onChange={(e) => setNewKeyData({ ...newKeyData, description: e.target.value })}
                        placeholder="API key for production integration"
                        rows={2}
                        className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500 resize-none"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-2">Permissions</label>
                      <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto p-3 bg-slate-800/50 rounded-lg border border-white/10">
                        {PERMISSION_OPTIONS.map((perm) => (
                          <label
                            key={perm.id}
                            className="flex items-center gap-2 p-2 rounded hover:bg-slate-700/50 cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={newKeyData.permissions.includes(perm.id)}
                              onChange={() => togglePermission(perm.id)}
                              className="w-4 h-4 rounded border-white/10 bg-slate-700 text-blue-500"
                            />
                            <span className="text-sm text-slate-300">{perm.label}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1">Expiration Date</label>
                        <input
                          type="datetime-local"
                          value={newKeyData.expires_at}
                          onChange={(e) => setNewKeyData({ ...newKeyData, expires_at: e.target.value })}
                          className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white"
                        />
                        <p className="text-xs text-slate-500 mt-1">Leave empty for no expiration</p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-slate-400 mb-1">Rate Limit (req/hr)</label>
                        <input
                          type="number"
                          value={newKeyData.rate_limit}
                          onChange={(e) => setNewKeyData({ ...newKeyData, rate_limit: parseInt(e.target.value) || 10000 })}
                          min="100"
                          max="1000000"
                          className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-1">IP Whitelist</label>
                      <input
                        type="text"
                        value={newKeyData.ip_whitelist}
                        onChange={(e) => setNewKeyData({ ...newKeyData, ip_whitelist: e.target.value })}
                        placeholder="192.168.1.100, 10.0.0.0/24"
                        className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500"
                      />
                      <p className="text-xs text-slate-500 mt-1">Comma-separated IPs or CIDR ranges. Leave empty for no restriction.</p>
                    </div>
                  </>
                )}
              </div>

              <div className="flex justify-end gap-3 p-4 border-t border-white/5">
                <button
                  onClick={() => {
                    setShowCreateKeyModal(false)
                    setCreatedKey(null)
                  }}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >
                  {createdKey ? 'Close' : 'Cancel'}
                </button>
                {!createdKey && (
                  <button
                    onClick={handleCreateAPIKey}
                    disabled={!newKeyData.name || newKeyData.permissions.length === 0}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
                  >
                    Create API Key
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Configure SSO Modal */}
        {showConfigureSSO && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-slate-900 border border-white/10 rounded-xl w-full max-w-xl mx-4 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-4 border-b border-white/5">
                <h3 className="text-lg font-semibold text-white">Configure SSO Provider</h3>
                <button
                  onClick={() => setShowConfigureSSO(false)}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Provider Name *</label>
                  <input
                    type="text"
                    value={ssoConfig.provider_name}
                    onChange={(e) => setSsoConfig({ ...ssoConfig, provider_name: e.target.value })}
                    placeholder="e.g., Okta Production"
                    className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Provider Type</label>
                  <select
                    value={ssoConfig.provider_type}
                    onChange={(e) => setSsoConfig({ ...ssoConfig, provider_type: e.target.value as any })}
                    className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white"
                  >
                    <option value="oidc">OpenID Connect (Generic)</option>
                    <option value="okta">Okta</option>
                    <option value="azure_ad">Azure AD</option>
                    <option value="google">Google Workspace</option>
                    <option value="saml">SAML 2.0</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Domain / Issuer URL *</label>
                  <input
                    type="text"
                    value={ssoConfig.domain}
                    onChange={(e) => setSsoConfig({ ...ssoConfig, domain: e.target.value })}
                    placeholder="e.g., company.okta.com"
                    className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Client ID *</label>
                  <input
                    type="text"
                    value={ssoConfig.client_id}
                    onChange={(e) => setSsoConfig({ ...ssoConfig, client_id: e.target.value })}
                    placeholder="Your OIDC client ID"
                    className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Client Secret *</label>
                  <input
                    type="password"
                    value={ssoConfig.client_secret}
                    onChange={(e) => setSsoConfig({ ...ssoConfig, client_secret: e.target.value })}
                    placeholder="Your OIDC client secret"
                    className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500"
                  />
                </div>

                <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <h4 className="text-blue-400 font-medium text-sm mb-2">Callback URL</h4>
                  <code className="text-xs text-blue-300 bg-blue-500/20 px-2 py-1 rounded">
                    https://your-subdomain.logforge.io/auth/oidc/callback
                  </code>
                  <p className="text-blue-400/80 text-xs mt-2">
                    Add this URL to your identity provider's allowed callback URLs.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="sso_enabled"
                    checked={ssoConfig.enabled}
                    onChange={(e) => setSsoConfig({ ...ssoConfig, enabled: e.target.checked })}
                    className="w-4 h-4 rounded border-white/10 bg-slate-700 text-blue-500"
                  />
                  <label htmlFor="sso_enabled" className="text-sm text-slate-300">
                    Enable SSO login immediately
                  </label>
                </div>
              </div>

              <div className="flex justify-end gap-3 p-4 border-t border-white/5">
                <button
                  onClick={() => setShowConfigureSSO(false)}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfigureSSO}
                  disabled={!ssoConfig.provider_name || !ssoConfig.client_id || !ssoConfig.domain}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
                >
                  Configure SSO
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
