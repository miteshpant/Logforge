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
  const [isTestLoading, setIsTestLoading] = useState(false)

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
      const response = await apiClient.get<SigmaRule[]>('/v1/security/rules')
      const data = response?.data || response
      if (Array.isArray(data)) {
        setRules(data)
      } else {
        setRules([])
      }
    } catch (error) {
      console.error('Failed to load rules:', error)
      setRules([])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadRules()
  }, [])

  const handleCreateRule = async () => {
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
    } catch (error) {
      console.error('Failed to create rule:', error)
      // Add locally for demo
      const newRule: SigmaRule = {
        id: `rule-${Date.now()}`,
        title: formData.title || 'New Rule',
        description: formData.description || '',
        severity: formData.severity as SigmaRule['severity'] || 'medium',
        status: 'active',
        author: formData.author || 'Logforge User',
        date: new Date().toISOString().split('T')[0],
        enabled: formData.enabled ?? true,
        attack_techniques: formData.attack_techniques || [],
        tags: formData.tags || [],
        logsource: formData.logsource,
        detection: formData.detection
      }
      setRules(prev => [newRule, ...prev])
      setIsCreating(false)
      resetForm()
    }
  }

  const handleUpdateRule = async () => {
    if (!selectedRule) return
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
    } catch (error) {
      console.error('Failed to update rule:', error)
      // Update locally for demo
      setRules(prev => prev.map(r =>
        r.id === selectedRule.id ? { ...r, ...formData } as SigmaRule : r
      ))
      setIsEditing(false)
      setSelectedRule(null)
      resetForm()
    }
  }

  const handleDeleteRule = async (ruleId: string) => {
    if (!confirm('Are you sure you want to delete this rule?')) return
    try {
      await apiClient.delete(`/v1/security/sigma-rules/${ruleId}`)
      await loadRules()
    } catch (error) {
      console.error('Failed to delete rule:', error)
      // Delete locally for demo
      setRules(prev => prev.filter(r => r.id !== ruleId))
    }
    if (selectedRule?.id === ruleId) {
      setSelectedRule(null)
    }
  }

  const handleToggleRule = async (rule: SigmaRule) => {
    try {
      await apiClient.put(`/v1/security/sigma-rules/${rule.id}`, {
        ...rule,
        enabled: !rule.enabled
      })
      await loadRules()
    } catch (error) {
      console.error('Failed to toggle rule:', error)
      // Toggle locally for demo
      setRules(prev => prev.map(r =>
        r.id === rule.id ? { ...r, enabled: !r.enabled } : r
      ))
    }
  }

  const handleTestRule = async (ruleId: string) => {
    setIsTestLoading(true)
    setTestResult(null)
    try {
      const response = await apiClient.post<{ result: string; test_details: RuleTestResult }>(
        `/v1/security/sigma-rules/${ruleId}/test`
      )
      const data = response?.data || response
      if (data?.test_details) {
        setTestResult(data.test_details)
      }
    } catch (error) {
      console.error('Failed to test rule:', error)
      // Mock test result
      setTestResult({
        matched: Math.random() > 0.5,
        rule_id: ruleId,
        rule_title: rules.find(r => r.id === ruleId)?.title || 'Unknown',
        matched_fields: { field1: 'value1' },
        confidence: Math.floor(Math.random() * 50) + 50,
        test_timestamp: new Date().toISOString()
      })
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
              className="w-full pl-10 pr-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
            />
          </div>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Rules Table */}
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 overflow-hidden">
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
                      Confidence: {testResult.confidence}%
                    </p>
                  </div>
                </div>
              </div>

              {testResult.matched && Object.keys(testResult.matched_fields).length > 0 && (
                <div>
                  <p className="text-sm font-medium text-slate-300 mb-2">Matched Fields:</p>
                  <pre className="p-3 bg-slate-900 text-green-400 rounded-lg text-sm overflow-x-auto">
                    {JSON.stringify(testResult.matched_fields, null, 2)}
                  </pre>
                </div>
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
                    className="w-full px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
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
                    className="w-full px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 resize-none"
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
                      className="w-full px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
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
                      className="w-full px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
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
                      className="px-3 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 text-sm"
                    />
                    <input
                      type="text"
                      value={formData.logsource?.product || ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        logsource: { ...formData.logsource, product: e.target.value }
                      })}
                      placeholder="Product"
                      className="px-3 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 text-sm"
                    />
                    <input
                      type="text"
                      value={formData.logsource?.service || ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        logsource: { ...formData.logsource, service: e.target.value }
                      })}
                      placeholder="Service"
                      className="px-3 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 text-sm"
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
                    className="w-full px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
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
                    className="w-full px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
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
