'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Globe,
  Search,
  Plus,
  Filter,
  AlertTriangle,
  Server,
  Link,
  Hash,
  Mail,
  FileText,
  Clock,
  ExternalLink,
  Trash2,
  RefreshCw,
  X,
  Database,
  Shield
} from 'lucide-react'

interface ThreatIndicator {
  id: string
  indicator_type: 'ip' | 'domain' | 'url' | 'hash' | 'email' | 'file'
  value: string
  threat_type: string[]
  severity: 'critical' | 'high' | 'medium' | 'low'
  confidence: number
  source: string
  description?: string
  tags: string[]
  first_seen: string
  last_seen: string
}

const INDICATOR_ICONS: Record<string, React.ReactNode> = {
  ip: <Server className="w-4 h-4" />,
  domain: <Globe className="w-4 h-4" />,
  url: <Link className="w-4 h-4" />,
  hash: <Hash className="w-4 h-4" />,
  email: <Mail className="w-4 h-4" />,
  file: <FileText className="w-4 h-4" />
}

const THREAT_TYPES = [
  'malware', 'c2', 'phishing', 'spam', 'scanning', 'brute-force',
  'botnet', 'ransomware', 'trojan', 'apt', 'exploit', 'suspicious'
]

export default function ThreatIntelPage() {
  const [indicators, setIndicators] = useState<ThreatIndicator[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [severityFilter, setSeverityFilter] = useState<string>('all')
  const [isAddingIndicator, setIsAddingIndicator] = useState(false)

  // Form state
  const [formData, setFormData] = useState({
    indicator_type: 'ip' as ThreatIndicator['indicator_type'],
    value: '',
    threat_type: [] as string[],
    severity: 'medium' as ThreatIndicator['severity'],
    confidence: 75,
    source: 'Manual Entry',
    description: '',
    tags: [] as string[]
  })

  const loadIndicators = async () => {
    try {
      setIsLoading(true)
      const response = await apiClient.get<ThreatIndicator[]>('/v1/security/threat-intel', {
        indicator_type: typeFilter !== 'all' ? typeFilter : undefined
      })
      const data = response?.data || response
      if (Array.isArray(data)) {
        setIndicators(data)
      } else {
        setIndicators([])
      }
    } catch (error) {
      console.error('Failed to load threat intel:', error)
      setIndicators([])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadIndicators()
  }, [typeFilter])

  const handleAddIndicator = async () => {
    try {
      await apiClient.post('/v1/security/threat-intel', formData)
      await loadIndicators()
      setIsAddingIndicator(false)
      resetForm()
    } catch (error) {
      console.error('Failed to add indicator:', error)
      // Add locally for demo
      const newIndicator: ThreatIndicator = {
        id: `ioc-${Date.now()}`,
        ...formData,
        first_seen: new Date().toISOString(),
        last_seen: new Date().toISOString()
      }
      setIndicators(prev => [newIndicator, ...prev])
      setIsAddingIndicator(false)
      resetForm()
    }
  }

  const handleDeleteIndicator = async (id: string) => {
    if (!confirm('Delete this threat indicator?')) return
    try {
      await apiClient.delete(`/v1/security/threat-intel/${id}`)
      await loadIndicators()
    } catch (error) {
      console.error('Failed to delete indicator:', error)
      setIndicators(prev => prev.filter(i => i.id !== id))
    }
  }

  const resetForm = () => {
    setFormData({
      indicator_type: 'ip',
      value: '',
      threat_type: [],
      severity: 'medium',
      confidence: 75,
      source: 'Manual Entry',
      description: '',
      tags: []
    })
  }

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'bg-red-500/10 text-red-600 border-red-500/30'
      case 'high': return 'bg-orange-500/10 text-orange-600 border-orange-500/30'
      case 'medium': return 'bg-yellow-500/10 text-yellow-600 border-yellow-500/30'
      case 'low': return 'bg-blue-500/10 text-blue-600 border-blue-500/30'
      default: return 'bg-slate-500/10 text-slate-600 border-slate-500/30'
    }
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 80) return 'text-green-600 bg-green-50'
    if (confidence >= 50) return 'text-yellow-600 bg-yellow-50'
    return 'text-red-600 bg-red-50'
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString()
  }

  const filteredIndicators = indicators.filter(ind => {
    const matchesSearch = searchQuery === '' ||
      ind.value.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ind.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ind.tags.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()))

    const matchesSeverity = severityFilter === 'all' || ind.severity === severityFilter

    return matchesSearch && matchesSeverity
  })

  // Stats
  const stats = {
    total: indicators.length,
    byType: {
      ip: indicators.filter(i => i.indicator_type === 'ip').length,
      domain: indicators.filter(i => i.indicator_type === 'domain').length,
      hash: indicators.filter(i => i.indicator_type === 'hash').length,
      url: indicators.filter(i => i.indicator_type === 'url').length
    },
    bySeverity: {
      critical: indicators.filter(i => i.severity === 'critical').length,
      high: indicators.filter(i => i.severity === 'high').length,
      medium: indicators.filter(i => i.severity === 'medium').length,
      low: indicators.filter(i => i.severity === 'low').length
    }
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Threat Intelligence</h1>
            <p className="text-slate-600 mt-1">
              Manage Indicators of Compromise (IOCs) and threat feeds
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={loadIndicators}
              className="flex items-center gap-2 px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
            <button
              onClick={() => setIsAddingIndicator(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
            >
              <Plus className="w-4 h-4" />
              Add IOC
            </button>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-slate-600 mb-1">
              <Database className="w-4 h-4" />
              <span className="text-sm">Total IOCs</span>
            </div>
            <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-slate-600 mb-1">
              <Server className="w-4 h-4" />
              <span className="text-sm">IPs</span>
            </div>
            <p className="text-2xl font-bold text-slate-900">{stats.byType.ip}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-slate-600 mb-1">
              <Globe className="w-4 h-4" />
              <span className="text-sm">Domains</span>
            </div>
            <p className="text-2xl font-bold text-slate-900">{stats.byType.domain}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-slate-600 mb-1">
              <Hash className="w-4 h-4" />
              <span className="text-sm">Hashes</span>
            </div>
            <p className="text-2xl font-bold text-slate-900">{stats.byType.hash}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-red-600 mb-1">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm">Critical</span>
            </div>
            <p className="text-2xl font-bold text-red-600">{stats.bySeverity.critical}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-orange-600 mb-1">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm">High</span>
            </div>
            <p className="text-2xl font-bold text-orange-600">{stats.bySeverity.high}</p>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search indicators..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500"
            />
          </div>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Types</option>
            <option value="ip">IP Address</option>
            <option value="domain">Domain</option>
            <option value="url">URL</option>
            <option value="hash">File Hash</option>
            <option value="email">Email</option>
          </select>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Indicators Table */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-600 uppercase">Type</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-600 uppercase">Indicator</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-600 uppercase">Threat</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-600 uppercase">Severity</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-600 uppercase">Confidence</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-600 uppercase">Source</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-slate-600 uppercase">Last Seen</th>
                <th className="text-right px-6 py-3 text-xs font-semibold text-slate-600 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    <td colSpan={8} className="px-6 py-4">
                      <div className="h-8 bg-slate-100 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : filteredIndicators.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center">
                    <Shield className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">No threat indicators found</p>
                  </td>
                </tr>
              ) : (
                filteredIndicators.map(indicator => (
                  <tr key={indicator.id} className="hover:bg-slate-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="p-2 bg-slate-100 rounded">
                          {INDICATOR_ICONS[indicator.indicator_type]}
                        </div>
                        <span className="text-sm text-slate-600 capitalize">{indicator.indicator_type}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <code className="text-sm font-mono bg-slate-100 px-2 py-1 rounded break-all">
                        {indicator.value}
                      </code>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {indicator.threat_type.slice(0, 2).map(type => (
                          <span key={type} className="px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded capitalize">
                            {type}
                          </span>
                        ))}
                        {indicator.threat_type.length > 2 && (
                          <span className="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded">
                            +{indicator.threat_type.length - 2}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs font-medium rounded border ${getSeverityColor(indicator.severity)}`}>
                        {indicator.severity.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className={`inline-flex items-center px-2 py-1 rounded text-sm font-medium ${getConfidenceColor(indicator.confidence)}`}>
                        {indicator.confidence}%
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      {indicator.source}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1 text-sm text-slate-500">
                        <Clock className="w-3 h-3" />
                        {formatDate(indicator.last_seen)}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        <a
                          href={`https://www.virustotal.com/gui/search/${encodeURIComponent(indicator.value)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg"
                          title="Check on VirusTotal"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                        <button
                          onClick={() => handleDeleteIndicator(indicator.id)}
                          className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
                          title="Delete"
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

        {/* Add IOC Modal */}
        {isAddingIndicator && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 m-4">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-slate-900">Add Threat Indicator</h3>
                <button
                  onClick={() => { setIsAddingIndicator(false); resetForm(); }}
                  className="p-2 hover:bg-slate-100 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                {/* Type */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Indicator Type</label>
                  <select
                    value={formData.indicator_type}
                    onChange={(e) => setFormData({ ...formData, indicator_type: e.target.value as ThreatIndicator['indicator_type'] })}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500"
                  >
                    <option value="ip">IP Address</option>
                    <option value="domain">Domain</option>
                    <option value="url">URL</option>
                    <option value="hash">File Hash</option>
                    <option value="email">Email Address</option>
                    <option value="file">File Name</option>
                  </select>
                </div>

                {/* Value */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Value *</label>
                  <input
                    type="text"
                    value={formData.value}
                    onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                    placeholder={
                      formData.indicator_type === 'ip' ? '192.168.1.100' :
                      formData.indicator_type === 'domain' ? 'malicious-domain.com' :
                      formData.indicator_type === 'hash' ? 'd41d8cd98f00b204e9800998ecf8427e' :
                      'Enter indicator value'
                    }
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500 font-mono"
                  />
                </div>

                {/* Threat Types */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Threat Types</label>
                  <div className="flex flex-wrap gap-2">
                    {THREAT_TYPES.map(type => (
                      <button
                        key={type}
                        type="button"
                        onClick={() => {
                          const current = formData.threat_type
                          if (current.includes(type)) {
                            setFormData({ ...formData, threat_type: current.filter(t => t !== type) })
                          } else {
                            setFormData({ ...formData, threat_type: [...current, type] })
                          }
                        }}
                        className={`px-3 py-1 text-sm rounded-lg border transition-colors ${
                          formData.threat_type.includes(type)
                            ? 'bg-red-100 text-red-700 border-red-300'
                            : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        {type}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Severity and Confidence */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Severity</label>
                    <select
                      value={formData.severity}
                      onChange={(e) => setFormData({ ...formData, severity: e.target.value as ThreatIndicator['severity'] })}
                      className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500"
                    >
                      <option value="critical">Critical</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Confidence: {formData.confidence}%
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={formData.confidence}
                      onChange={(e) => setFormData({ ...formData, confidence: parseInt(e.target.value) })}
                      className="w-full"
                    />
                  </div>
                </div>

                {/* Source */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Source</label>
                  <input
                    type="text"
                    value={formData.source}
                    onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                    placeholder="VirusTotal, AlienVault, Manual, etc."
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Additional context about this indicator..."
                    rows={2}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-blue-500 resize-none"
                  />
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3 mt-6 pt-4 border-t border-slate-200">
                <button
                  onClick={() => { setIsAddingIndicator(false); resetForm(); }}
                  className="flex-1 px-4 py-2 border border-slate-300 rounded-lg font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddIndicator}
                  disabled={!formData.value}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  Add Indicator
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
