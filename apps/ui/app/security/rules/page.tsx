'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Shield,
  Plus,
  Search,
  Edit2,
  Trash2,
  Play,
  ToggleLeft,
  ToggleRight,
  AlertTriangle,
  CheckCircle,
  X,
  Code,
  Target,
  Tag,
  FileText
} from 'lucide-react'

interface SigmaRule {
  id: string
  title: string
  description: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  status: string
  author: string
  date: string
  enabled: boolean
  attack_techniques: string[]
  tags: string[]
  logsource?: {
    category?: string
    product?: string
    service?: string
  }
  detection?: Record<string, unknown>
}

interface RuleTestResult {
  matched: boolean
  rule_id: string
  rule_title: string
  matched_fields: Record<string, unknown>
  confidence: number
  test_timestamp: string
}

export default function SigmaRulesPage() {
  const [rules, setRules] = useState<SigmaRule[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [severityFilter, setSeverityFilter] = useState<string>('all')
  const [selectedRule, setSelectedRule] = useState<SigmaRule | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [testResult, setTestResult] = useState<RuleTestResult | null>(null)
  const [testError, setTestError] = useState<string | null>(null)
  const [isTestLoading, setIsTestLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  // Form state
  const [formData, setFormData] = useState<Partial<SigmaRule>>({
    title: '',
    description: '',
    severity: 'medium',
    author: 'Logforge User',
    enabled: true,
    attack_techniques: [],
    tags: [],
    logsource: { category: '', product: '', service: '' },
    detection: {}
  })

  const loadRules = async () => {
    try {
      setIsLoading(true)
      setLoadError(null)
      // LF-016: the endpoint returns a paginated envelope
      // {rules: [...], total, limit, offset}
      const response = await apiClient.get<{ rules: SigmaRule[]; total: number; limit: number; offset: number }>(
        '/v1/security/sigma-rules',
        { params: { limit: 500, offset: 0 } }
      )
      const data: any = response?.data || response
      if (Array.isArray(data?.rules)) {
        setRules(data.rules)
      } else if (Array.isArray(data)) {
        // Pre-LF-016 bare-array shape
        setRules(data)
      } else {
        setRules([])
      }
    } catch (error: any) {
      console.error('Failed to load rules:', error)
      setRules([])
      setLoadError(
        `Failed to load rules: GET /v1/security/sigma-rules returned ${error?.status ?? 'a network error'}`
      )
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadRules()
  }, [])

  const handleCreateRule = async () => {
    setActionError(null)
    try {
      await apiClient.post('/v1/security/sigma-rules', {
        title: formData.title,
        description: formData.description,
        severity: formData.severity,
        author: formData.author,
        tags: formData.tags,
        logsource: formData.logsource,
        detection: formData.detection || { selection: { field: 'value' } },
        attack_techniques: formData.attack_techniques,
        enabled: formData.enabled
      })
      await loadRules()
      setIsCreating(false)
      resetForm()
    } catch (error: any) {
      console.error('Failed to create rule:', error)
      // The rule was NOT created — surface the failure, keep the form open
      setActionError(
        `Rule was not created: POST /v1/security/sigma-rules returned ${error?.status ?? 'a network error'}${error?.message ? ` — ${error.message}` : ''}`
      )
    }
  }

  const handleUpdateRule = async () => {
    if (!selectedRule) return
    setActionError(null)
    try {
      await apiClient.put(`/v1/security/sigma-rules/${selectedRule.id}`, {
        title: formData.title,
        description: formData.description,
        severity: formData.severity,
        author: formData.author,
        tags: formData.tags,
        logsource: formData.logsource,
        detection: formData.detection,
        attack_techniques: formData.attack_techniques,
        enabled: formData.enabled
      })
      await loadRules()
      setIsEditing(false)
      setSelectedRule(null)
      resetForm()
    } catch (error: any) {
      console.error('Failed to update rule:', error)
      // The rule was NOT updated — surface the failure, keep the form open
      setActionError(
        `Rule was not updated: PUT /v1/security/sigma-rules/${selectedRule.id} returned ${error?.status ?? 'a network error'}${error?.message ? ` — ${error.message}` : ''}`
      )
    }
  }

  const handleDeleteRule = async (ruleId: string) => {
    if (!confirm('Are you sure you want to delete this rule?')) return
    setActionError(null)
    try {
      await apiClient.delete(`/v1/security/sigma-rules/${ruleId}`)
      await loadRules()
      if (selectedRule?.id === ruleId) {
        setSelectedRule(null)
      }
    } catch (error: any) {
      console.error('Failed to delete rule:', error)
      // The rule was NOT deleted — keep it in the list and surface the failure
      setActionError(
        `Rule was not deleted: DELETE /v1/security/sigma-rules/${ruleId} returned ${error?.status ?? 'a network error'}${error?.message ? ` — ${error.message}` : ''}`
      )
    }
  }

  const handleToggleRule = async (rule: SigmaRule) => {
    setActionError(null)
    try {
      await apiClient.put(`/v1/security/sigma-rules/${rule.id}`, {
        ...rule,
        enabled: !rule.enabled
      })
      await loadRules()
    } catch (error: any) {
      console.error('Failed to toggle rule:', error)
      // The rule state did NOT change on the server — do not flip it locally
      setActionError(
        `Rule was not ${rule.enabled ? 'disabled' : 'enabled'}: PUT /v1/security/sigma-rules/${rule.id} returned ${error?.status ?? 'a network error'}`
      )
    }
  }

  const handleTestRule = async (ruleId: string) => {
    setIsTestLoading(true)
    setTestResult(null)
    setTestError(null)
    try {
      const response = await apiClient.post<{ result: string; test_details: RuleTestResult }>(
        `/v1/security/sigma-rules/${ruleId}/test`
      )
      const data = response?.data || response
      if (data?.test_details) {
        setTestResult(data.test_details)
      } else {
        setTestError(
          `POST /v1/security/sigma-rules/${ruleId}/test returned no test_details — the rule was not evaluated`
        )
      }
    } catch (error: any) {
      console.error('Failed to test rule:', error)
      // Never invent a test verdict — show the failure instead
      setTestError(
        `Rule test failed: POST /v1/security/sigma-rules/${ruleId}/test returned ${error?.status ?? 'a network error'}${error?.message ? ` — ${error.message}` : ''}`
      )
    } finally {
      setIsTestLoading(false)
    }
  }

  const resetForm = () => {
    setFormData({
      title: '',
      description: '',
      severity: 'medium',
      author: 'Logforge User',
      enabled: true,
      attack_techniques: [],
      tags: [],
      logsource: { category: '', product: '', service: '' },
      detection: {}
    })
  }

  const startEditing = (rule: SigmaRule) => {
    setSelectedRule(rule)
    setFormData({
      title: rule.title,
      description: rule.description,
      severity: rule.severity,
      author: rule.author,
      enabled: rule.enabled,
      attack_techniques: rule.attack_techniques,
      tags: rule.tags,
      logsource: rule.logsource,
      detection: rule.detection
    })
    setIsEditing(true)
  }

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'bg-red-500/10 text-red-400 border-red-500/30'
      case 'high': return 'bg-orange-500/10 text-orange-400 border-orange-500/30'
      case 'medium': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
      case 'low': return 'bg-blue-500/10 text-blue-400 border-blue-500/30'
      default: return 'bg-slate-500/10 text-slate-400 border-slate-500/30'
    }
  }

  const filteredRules = rules.filter(rule => {
    const matchesSearch = searchQuery === '' ||
      rule.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.tags.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()))

    const matchesSeverity = severityFilter === 'all' || rule.severity === severityFilter

    return matchesSearch && matchesSeverity
  })

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-white">Sigma Detection Rules</h1>
            <p className="text-slate-400 mt-1">
              Manage Sigma rules for threat detection
            </p>
          </div>
          <button
            onClick={() => { setIsCreating(true); resetForm(); }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Rule
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5 p-4">
            <p className="text-sm text-slate-400">Total Rules</p>
            <p className="text-2xl font-bold text-white">{rules.length}</p>
          </div>
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5 p-4">
            <p className="text-sm text-slate-400">Active</p>
            <p className="text-2xl font-bold text-green-400">{rules.filter(r => r.enabled).length}</p>
          </div>
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5 p-4">
            <p className="text-sm text-slate-400">Critical/High</p>
            <p className="text-2xl font-bold text-red-400">
              {rules.filter(r => r.severity === 'critical' || r.severity === 'high').length}
            </p>
          </div>
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5 p-4">
            <p className="text-sm text-slate-400">ATT&CK Coverage</p>
            <p className="text-2xl font-bold text-purple-400">
              {new Set(rules.flatMap(r => r.attack_techniques)).size}
            </p>
          </div>
        </div>

        {/* Search and Filter */}
        <div className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search rules..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 placeholder-slate-500"
            />
          </div>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 placeholder-slate-500"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Errors */}
        {loadError && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <p className="text-sm text-red-400">{loadError}</p>
          </div>
        )}
        {actionError && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start justify-between gap-2">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <p className="text-sm text-red-400">{actionError}</p>
            </div>
            <button onClick={() => setActionError(null)} className="text-red-400 hover:text-red-300">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Rules Table. overflow-x-auto (not overflow-hidden): at narrower widths
            the Actions column was clipped instead of scrollable. */}
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-800/50 border-b border-white/5">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase">Status</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase">Rule</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase">Severity</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase">ATT&CK</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-400 uppercase">Tags</th>
                <th className="text-right px-6 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {isLoading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    <td colSpan={6} className="px-6 py-4">
                      <div className="h-8 bg-slate-800/30 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : filteredRules.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center">
                    <Shield className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-400">No rules found</p>
                  </td>
                </tr>
              ) : (
                filteredRules.map(rule => (
                  <tr key={rule.id} className="hover:bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl/5">
                    <td className="px-6 py-4">
                      <button
                        onClick={() => handleToggleRule(rule)}
                        className="flex items-center"
                      >
                        {rule.enabled ? (
                          <ToggleRight className="w-8 h-8 text-green-500" />
                        ) : (
                          <ToggleLeft className="w-8 h-8 text-slate-400" />
                        )}
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-white">{rule.title}</p>
                        <p className="text-sm text-slate-400 truncate max-w-md">{rule.description}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs font-medium rounded border ${getSeverityColor(rule.severity)}`}>
                        {rule.severity.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {rule.attack_techniques.slice(0, 2).map(tech => (
                          <span key={tech} className="px-2 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded">
                            {tech}
                          </span>
                        ))}
                        {rule.attack_techniques.length > 2 && (
                          <span className="px-2 py-0.5 text-xs bg-slate-800/30 text-slate-400 rounded">
                            +{rule.attack_techniques.length - 2}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {rule.tags.slice(0, 2).map(tag => (
                          <span key={tag} className="px-2 py-0.5 text-xs bg-slate-800/30 text-slate-400 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleTestRule(rule.id)}
                          className="p-2 text-slate-400 hover:text-green-400 hover:bg-green-500/10 rounded-lg transition-colors"
                          title="Test Rule"
                        >
                          <Play className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => startEditing(rule)}
                          className="p-2 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-colors"
                          title="Edit Rule"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteRule(rule.id)}
                          className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                          title="Delete Rule"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Test Error Modal */}
        {testError && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl shadow-xl w-full max-w-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Test Failed</h3>
                <button onClick={() => setTestError(null)} className="p-2 hover:bg-white/5 rounded-lg">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-4 rounded-lg mb-4 bg-red-500/10">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-8 h-8 text-red-500" />
                  <div>
                    <p className="font-medium text-white">The rule could not be tested</p>
                    <p className="text-sm text-slate-400">{testError}</p>
                  </div>
                </div>
              </div>

              <button
                onClick={() => setTestError(null)}
                className="w-full mt-2 px-4 py-2 bg-slate-900 text-white rounded-lg font-medium hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        )}

        {/* Test Result Modal */}
        {testResult && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl shadow-xl w-full max-w-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Test Result</h3>
                <button onClick={() => setTestResult(null)} className="p-2 hover:bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl/5 rounded-lg">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className={`p-4 rounded-lg mb-4 ${testResult.matched ? 'bg-green-500/10' : 'bg-yellow-500/10'}`}>
                <div className="flex items-center gap-3">
                  {testResult.matched ? (
                    <CheckCircle className="w-8 h-8 text-green-500" />
                  ) : (
                    <AlertTriangle className="w-8 h-8 text-yellow-500" />
                  )}
                  <div>
                    <p className="font-medium text-white">
                      {testResult.matched ? 'Rule Triggered' : 'No Match'}
                    </p>
                    <p className="text-sm text-slate-400">
                      Confidence: {typeof testResult.confidence === 'number' && testResult.confidence <= 1 ? Math.round(testResult.confidence * 100) : testResult.confidence}%
                    </p>
                  </div>
                </div>
              </div>

              {testResult.matched && (
                testResult.matched_fields && Object.keys(testResult.matched_fields).length > 0 ? (
                  <div>
                    <p className="text-sm font-medium text-slate-300 mb-2">Matched Fields:</p>
                    <pre className="p-3 bg-slate-900 text-green-400 rounded-lg text-sm overflow-x-auto">
                      {JSON.stringify(testResult.matched_fields, null, 2)}
                    </pre>
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">No field detail returned by the server</p>
                )
              )}

              <button
                onClick={() => setTestResult(null)}
                className="w-full mt-4 px-4 py-2 bg-slate-900 text-white rounded-lg font-medium hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        )}

        {/* Create/Edit Modal */}
        {(isCreating || isEditing) && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto py-8">
            <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl shadow-xl w-full max-w-2xl p-6 m-4">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-white">
                  {isCreating ? 'Create New Rule' : 'Edit Rule'}
                </h3>
                <button
                  onClick={() => { setIsCreating(false); setIsEditing(false); resetForm(); }}
                  className="p-2 hover:bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl/5 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4 max-h-[60vh] overflow-y-auto">
                {/* Title */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    <FileText className="w-4 h-4 inline mr-1" />
                    Title *
                  </label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="Brute Force Attack Detection"
                    className="w-full px-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 placeholder-slate-500"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Description</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Detects multiple failed login attempts from a single source..."
                    rows={3}
                    className="w-full px-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 resize-none placeholder-slate-500"
                  />
                </div>

                {/* Severity and Status */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      <AlertTriangle className="w-4 h-4 inline mr-1" />
                      Severity
                    </label>
                    <select
                      value={formData.severity}
                      onChange={(e) => setFormData({ ...formData, severity: e.target.value as SigmaRule['severity'] })}
                      className="w-full px-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 placeholder-slate-500"
                    >
                      <option value="critical">Critical</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                      <option value="info">Info</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Author</label>
                    <input
                      type="text"
                      value={formData.author}
                      onChange={(e) => setFormData({ ...formData, author: e.target.value })}
                      placeholder="Logforge User"
                      className="w-full px-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 placeholder-slate-500"
                    />
                  </div>
                </div>

                {/* Log Source */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    <Code className="w-4 h-4 inline mr-1" />
                    Log Source
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    <input
                      type="text"
                      value={formData.logsource?.category || ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        logsource: { ...formData.logsource, category: e.target.value }
                      })}
                      placeholder="Category"
                      className="px-3 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 text-sm placeholder-slate-500"
                    />
                    <input
                      type="text"
                      value={formData.logsource?.product || ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        logsource: { ...formData.logsource, product: e.target.value }
                      })}
                      placeholder="Product"
                      className="px-3 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 text-sm placeholder-slate-500"
                    />
                    <input
                      type="text"
                      value={formData.logsource?.service || ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        logsource: { ...formData.logsource, service: e.target.value }
                      })}
                      placeholder="Service"
                      className="px-3 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 text-sm placeholder-slate-500"
                    />
                  </div>
                </div>

                {/* MITRE ATT&CK Techniques */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    <Target className="w-4 h-4 inline mr-1" />
                    MITRE ATT&CK Techniques (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={formData.attack_techniques?.join(', ')}
                    onChange={(e) => setFormData({
                      ...formData,
                      attack_techniques: e.target.value.split(',').map(t => t.trim()).filter(Boolean)
                    })}
                    placeholder="T1110, T1078"
                    className="w-full px-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 placeholder-slate-500"
                  />
                </div>

                {/* Tags */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    <Tag className="w-4 h-4 inline mr-1" />
                    Tags (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={formData.tags?.join(', ')}
                    onChange={(e) => setFormData({
                      ...formData,
                      tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean)
                    })}
                    placeholder="authentication, brute-force"
                    className="w-full px-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 placeholder-slate-500"
                  />
                </div>

                {/* Enabled */}
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, enabled: !formData.enabled })}
                    className="flex items-center"
                  >
                    {formData.enabled ? (
                      <ToggleRight className="w-10 h-10 text-green-500" />
                    ) : (
                      <ToggleLeft className="w-10 h-10 text-slate-400" />
                    )}
                  </button>
                  <span className="text-sm text-slate-300">
                    {formData.enabled ? 'Rule Enabled' : 'Rule Disabled'}
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3 mt-6 pt-4 border-t border-white/5">
                <button
                  onClick={() => { setIsCreating(false); setIsEditing(false); resetForm(); }}
                  className="flex-1 px-4 py-2 border border-white/10 rounded-lg font-medium text-slate-300 hover:bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl/5"
                >
                  Cancel
                </button>
                <button
                  onClick={isCreating ? handleCreateRule : handleUpdateRule}
                  disabled={!formData.title}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isCreating ? 'Create Rule' : 'Update Rule'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
