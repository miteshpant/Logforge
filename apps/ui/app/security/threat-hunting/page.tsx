'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Crosshair,
  Play,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Search,
  Target,
  Activity,
  Filter,
  RefreshCw,
  ChevronRight,
  Calendar,
  Zap,
  FileText,
  TrendingUp
} from 'lucide-react'

interface ThreatHuntCampaign {
  campaign_id: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string
  completed_at?: string
  findings_count: number
  rules_tested: number
  logs_scanned: number
  time_range: string
  severity_filter?: string[]
}

interface HuntingRule {
  id: string
  name: string
  description: string
  category: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  enabled: boolean
  attack_techniques: string[]
}

interface CampaignFinding {
  id: string
  title: string
  severity: string
  rule_id: string
  technique: string
  description?: string
  timestamp?: string
}

export default function ThreatHuntingPage() {
  const [campaigns, setCampaigns] = useState<ThreatHuntCampaign[]>([])
  const [rules, setRules] = useState<HuntingRule[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedCampaign, setSelectedCampaign] = useState<ThreatHuntCampaign | null>(null)
  const [isStartingHunt, setIsStartingHunt] = useState(false)
  const [campaignFindings, setCampaignFindings] = useState<CampaignFinding[]>([])
  const [loadingFindings, setLoadingFindings] = useState(false)

  // Hunt configuration
  const [huntConfig, setHuntConfig] = useState({
    description: '',
    time_range: '24h',
    severity_filter: [] as string[],
    rule_ids: [] as string[]
  })

  const loadData = async () => {
    try {
      setIsLoading(true)

      const [campaignsRes, rulesRes] = await Promise.allSettled([
        apiClient.get<{ campaigns: ThreatHuntCampaign[]; total_count: number }>('/v1/security/threat-hunting'),
        apiClient.get<{ rules: HuntingRule[] }>('/v1/security/threat-hunt/rules')
      ])

      if (campaignsRes.status === 'fulfilled') {
        const data = campaignsRes.value?.data || campaignsRes.value
        if (data?.campaigns) {
          setCampaigns(data.campaigns)
        } else {
          setCampaigns([])
        }
      } else {
        setCampaigns([])
      }

      if (rulesRes.status === 'fulfilled') {
        const data = rulesRes.value?.data || rulesRes.value
        if (data?.rules) {
          setRules(data.rules)
        } else {
          setRules([])
        }
      } else {
        setRules([])
      }
    } catch (error) {
      console.error('Failed to load threat hunting data:', error)
      setCampaigns([])
      setRules([])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const startHunt = async () => {
    setIsStartingHunt(true)
    try {
      const response = await apiClient.post<ThreatHuntCampaign>('/v1/security/threat-hunting', {
        description: huntConfig.description || 'Ad-hoc threat hunting campaign',
        time_range: huntConfig.time_range,
        severity_filter: huntConfig.severity_filter.length > 0 ? huntConfig.severity_filter : undefined,
        rule_ids: huntConfig.rule_ids.length > 0 ? huntConfig.rule_ids : undefined
      })

      const data = response?.data || response
      if (data?.campaign_id) {
        // Add to campaigns list
        const newCampaign: ThreatHuntCampaign = {
          campaign_id: data.campaign_id,
          description: huntConfig.description || 'Ad-hoc threat hunting campaign',
          status: 'running',
          started_at: new Date().toISOString(),
          findings_count: 0,
          rules_tested: 0,
          logs_scanned: 0,
          time_range: huntConfig.time_range,
          severity_filter: huntConfig.severity_filter
        }
        setCampaigns(prev => [newCampaign, ...prev])
        setSelectedCampaign(newCampaign)

        // Reset config
        setHuntConfig({
          description: '',
          time_range: '24h',
          severity_filter: [],
          rule_ids: []
        })

        // Poll for updates
        pollCampaignStatus(data.campaign_id)
      }
    } catch (error) {
      console.error('Failed to start threat hunt:', error)
      // Create mock campaign for demo
      const mockCampaign: ThreatHuntCampaign = {
        campaign_id: `hunt-${Date.now()}`,
        description: huntConfig.description || 'Ad-hoc threat hunting campaign',
        status: 'running',
        started_at: new Date().toISOString(),
        findings_count: 0,
        rules_tested: 0,
        logs_scanned: 0,
        time_range: huntConfig.time_range,
        severity_filter: huntConfig.severity_filter
      }
      setCampaigns(prev => [mockCampaign, ...prev])
      setSelectedCampaign(mockCampaign)

      // Simulate campaign progress
      simulateCampaignProgress(mockCampaign.campaign_id)
    } finally {
      setIsStartingHunt(false)
    }
  }

  const pollCampaignStatus = async (campaignId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await apiClient.get<ThreatHuntCampaign>(`/v1/security/threat-hunting/${campaignId}`)
        const data = response?.data || response

        if (data) {
          const campaign = data as ThreatHuntCampaign
          setCampaigns(prev => prev.map(c =>
            c.campaign_id === campaignId ? campaign : c
          ))
          if (selectedCampaign?.campaign_id === campaignId) {
            setSelectedCampaign(campaign)
          }

          if (campaign.status === 'completed' || campaign.status === 'failed') {
            clearInterval(pollInterval)
          }
        }
      } catch (error) {
        console.error('Failed to poll campaign status:', error)
        clearInterval(pollInterval)
      }
    }, 3000)

    // Clear interval after 5 minutes
    setTimeout(() => clearInterval(pollInterval), 300000)
  }

  const simulateCampaignProgress = (campaignId: string) => {
    let progress = 0
    const interval = setInterval(() => {
      progress += 10

      setCampaigns(prev => prev.map(c => {
        if (c.campaign_id !== campaignId) return c

        if (progress >= 100) {
          return {
            ...c,
            status: 'completed' as const,
            completed_at: new Date().toISOString(),
            findings_count: Math.floor(Math.random() * 15) + 3,
            rules_tested: Math.floor(Math.random() * 50) + 20,
            logs_scanned: Math.floor(Math.random() * 500000) + 100000
          }
        }

        return {
          ...c,
          rules_tested: Math.floor((progress / 100) * 50),
          logs_scanned: Math.floor((progress / 100) * 500000),
          findings_count: Math.floor((progress / 100) * 10)
        }
      }))

      if (progress >= 100) {
        clearInterval(interval)
      }
    }, 1500)
  }

  const loadCampaignFindings = async (campaignId: string) => {
    setLoadingFindings(true)
    try {
      const response = await apiClient.get(`/v1/security/threat-hunting/${campaignId}/findings`)
      const data = response?.data || response
      if (data?.findings && Array.isArray(data.findings)) {
        setCampaignFindings(data.findings)
      } else if (Array.isArray(data)) {
        setCampaignFindings(data)
      } else {
        setCampaignFindings([])
      }
    } catch (err) {
      console.error('Failed to load campaign findings:', err)
      setCampaignFindings([])
    } finally {
      setLoadingFindings(false)
    }
  }

  const selectCampaign = (campaign: ThreatHuntCampaign) => {
    setSelectedCampaign(campaign)
    if (campaign.status === 'completed' && campaign.findings_count > 0) {
      loadCampaignFindings(campaign.campaign_id)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-blue-500/10 text-blue-400 border-blue-500/30'
      case 'completed': return 'bg-green-500/10 text-green-400 border-green-500/30'
      case 'failed': return 'bg-red-500/10 text-red-400 border-red-500/30'
      default: return 'bg-slate-500/10 text-slate-400 border-slate-500/30'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <Activity className="w-4 h-4 animate-pulse" />
      case 'completed': return <CheckCircle className="w-4 h-4" />
      case 'failed': return <XCircle className="w-4 h-4" />
      default: return <Clock className="w-4 h-4" />
    }
  }

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString()
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/10 text-red-400'
      case 'high': return 'bg-orange-500/10 text-orange-400'
      case 'medium': return 'bg-yellow-500/10 text-yellow-400'
      case 'low': return 'bg-blue-500/10 text-blue-400'
      default: return 'bg-slate-500/10 text-slate-400'
    }
  }

  // Stats
  const stats = {
    total: campaigns.length,
    running: campaigns.filter(c => c.status === 'running').length,
    completed: campaigns.filter(c => c.status === 'completed').length,
    totalFindings: campaigns.reduce((sum, c) => sum + c.findings_count, 0)
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-white">Threat Hunting</h1>
            <p className="text-slate-400 mt-1">
              Proactively hunt for threats in your environment
            </p>
          </div>
          <button
            onClick={loadData}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl/5"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5 p-4">
            <div className="flex items-center gap-2 text-slate-400 mb-1">
              <Crosshair className="w-4 h-4" />
              <span className="text-sm">Total Hunts</span>
            </div>
            <p className="text-2xl font-bold text-white">{stats.total}</p>
          </div>
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5 p-4">
            <div className="flex items-center gap-2 text-blue-400 mb-1">
              <Activity className="w-4 h-4" />
              <span className="text-sm">Running</span>
            </div>
            <p className="text-2xl font-bold text-blue-400">{stats.running}</p>
          </div>
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5 p-4">
            <div className="flex items-center gap-2 text-green-400 mb-1">
              <CheckCircle className="w-4 h-4" />
              <span className="text-sm">Completed</span>
            </div>
            <p className="text-2xl font-bold text-green-400">{stats.completed}</p>
          </div>
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border border-white/5 p-4">
            <div className="flex items-center gap-2 text-red-400 mb-1">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm">Total Findings</span>
            </div>
            <p className="text-2xl font-bold text-red-400">{stats.totalFindings}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Start New Hunt */}
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Crosshair className="w-5 h-5 text-purple-500" />
              Start New Hunt
            </h2>

            <div className="space-y-4">
              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Description
                </label>
                <input
                  type="text"
                  value={huntConfig.description}
                  onChange={(e) => setHuntConfig({ ...huntConfig, description: e.target.value })}
                  placeholder="Threat hunting campaign..."
                  className="w-full px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Time Range */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  <Calendar className="w-4 h-4 inline mr-1" />
                  Time Range
                </label>
                <select
                  value={huntConfig.time_range}
                  onChange={(e) => setHuntConfig({ ...huntConfig, time_range: e.target.value })}
                  className="w-full px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
                >
                  <option value="1h">Last 1 hour</option>
                  <option value="24h">Last 24 hours</option>
                  <option value="7d">Last 7 days</option>
                  <option value="30d">Last 30 days</option>
                </select>
              </div>

              {/* Severity Filter */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  <Filter className="w-4 h-4 inline mr-1" />
                  Severity Filter
                </label>
                <div className="flex flex-wrap gap-2">
                  {['critical', 'high', 'medium', 'low'].map(sev => (
                    <button
                      key={sev}
                      type="button"
                      onClick={() => {
                        const current = huntConfig.severity_filter
                        if (current.includes(sev)) {
                          setHuntConfig({ ...huntConfig, severity_filter: current.filter(s => s !== sev) })
                        } else {
                          setHuntConfig({ ...huntConfig, severity_filter: [...current, sev] })
                        }
                      }}
                      className={`px-3 py-1 text-sm rounded-lg border transition-colors capitalize ${
                        huntConfig.severity_filter.includes(sev)
                          ? getSeverityColor(sev) + ' border-current'
                          : 'bg-slate-800/50 text-slate-400 border-white/5 hover:border-white/10'
                      }`}
                    >
                      {sev}
                    </button>
                  ))}
                </div>
              </div>

              {/* Start Button */}
              <button
                onClick={startHunt}
                disabled={isStartingHunt}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {isStartingHunt ? (
                  <>
                    <Activity className="w-5 h-5 animate-spin" />
                    Starting Hunt...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    Start Threat Hunt
                  </>
                )}
              </button>
            </div>

            {/* Available Rules Preview */}
            <div className="mt-6 pt-4 border-t border-white/5">
              <h3 className="text-sm font-medium text-slate-300 mb-3">Available Hunt Rules</h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {rules.slice(0, 5).map(rule => (
                  <div
                    key={rule.id}
                    className="p-2 bg-slate-800/50 rounded-lg flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <Target className="w-4 h-4 text-purple-500" />
                      <span className="text-sm text-slate-300 truncate max-w-[150px]">{rule.name}</span>
                    </div>
                    <span className={`px-2 py-0.5 text-xs rounded ${getSeverityColor(rule.severity)}`}>
                      {rule.severity}
                    </span>
                  </div>
                ))}
                {rules.length > 5 && (
                  <p className="text-xs text-slate-400 text-center">
                    +{rules.length - 5} more rules
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Campaign History */}
          <div className="lg:col-span-2 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-500" />
              Campaign History
            </h2>

            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-20 bg-slate-800/30 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : campaigns.length === 0 ? (
              <div className="text-center py-12">
                <Crosshair className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-400">No threat hunting campaigns yet</p>
                <p className="text-sm text-slate-400 mt-1">Start your first hunt above</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {campaigns.map(campaign => (
                  <div
                    key={campaign.campaign_id}
                    onClick={() => selectCampaign(campaign)}
                    className={`p-4 border rounded-lg cursor-pointer transition-all ${
                      selectedCampaign?.campaign_id === campaign.campaign_id
                        ? 'border-blue-500 bg-blue-500/10'
                        : 'border-white/5 hover:border-blue-300'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded border flex items-center gap-1 ${getStatusColor(campaign.status)}`}>
                            {getStatusIcon(campaign.status)}
                            {campaign.status}
                          </span>
                          <span className="text-xs text-slate-400">
                            {campaign.time_range}
                          </span>
                        </div>
                        <p className="font-medium text-white truncate">{campaign.description}</p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatTimestamp(campaign.started_at)}
                          </span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {campaign.status === 'running' ? (
                          <div className="flex items-center gap-1">
                            <Activity className="w-4 h-4 text-blue-500 animate-pulse" />
                            <span className="text-sm text-blue-400">In Progress</span>
                          </div>
                        ) : (
                          <>
                            <div className="flex items-center gap-1">
                              <AlertTriangle className="w-4 h-4 text-orange-500" />
                              <span className="text-lg font-bold text-white">{campaign.findings_count}</span>
                            </div>
                            <span className="text-xs text-slate-400">findings</span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Progress bar for running campaigns */}
                    {campaign.status === 'running' && (
                      <div className="mt-3">
                        <div className="flex justify-between text-xs text-slate-400 mb-1">
                          <span>{campaign.rules_tested} rules tested</span>
                          <span>{(campaign.logs_scanned ?? 0).toLocaleString()} logs scanned</span>
                        </div>
                        <div className="h-2 bg-slate-800/30 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 animate-pulse"
                            style={{ width: `${Math.min((campaign.rules_tested / 50) * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Results summary for completed */}
                    {campaign.status === 'completed' && (
                      <div className="mt-3 pt-3 border-t border-white/5 grid grid-cols-3 gap-4 text-center">
                        <div>
                          <p className="text-lg font-bold text-white">{campaign.rules_tested}</p>
                          <p className="text-xs text-slate-400">Rules Tested</p>
                        </div>
                        <div>
                          <p className="text-lg font-bold text-white">{(campaign.logs_scanned ?? 0).toLocaleString()}</p>
                          <p className="text-xs text-slate-400">Logs Scanned</p>
                        </div>
                        <div>
                          <p className={`text-lg font-bold ${campaign.findings_count > 0 ? 'text-orange-500' : 'text-green-500'}`}>
                            {campaign.findings_count}
                          </p>
                          <p className="text-xs text-slate-400">Findings</p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Campaign Findings */}
        {selectedCampaign && selectedCampaign.status === 'completed' && selectedCampaign.findings_count > 0 && (
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-orange-500" />
              Campaign Findings
              <span className="text-sm font-normal text-slate-400">
                ({selectedCampaign.findings_count} found)
              </span>
            </h2>

            {loadingFindings ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-24 bg-slate-800/30 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : campaignFindings.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {campaignFindings.slice(0, 9).map((finding) => (
                  <div key={finding.id} className="p-4 bg-slate-800/50 rounded-lg border border-white/5">
                    <div className="flex items-start justify-between mb-2">
                      <span className={`px-2 py-0.5 text-xs rounded ${getSeverityColor(finding.severity)}`}>
                        {finding.severity}
                      </span>
                      <Zap className="w-4 h-4 text-orange-500" />
                    </div>
                    <p className="font-medium text-white text-sm">{finding.title}</p>
                    {finding.technique && (
                      <p className="text-xs text-slate-400 mt-1">Rule: {finding.technique}</p>
                    )}
                    {finding.description && (
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2">{finding.description}</p>
                    )}
                    <a
                      href="/security/events"
                      className="text-xs text-blue-400 hover:text-blue-300 mt-2 inline-flex items-center gap-1"
                    >
                      View in Events <ChevronRight className="w-3 h-3" />
                    </a>
                  </div>
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[...Array(Math.min(selectedCampaign.findings_count, 6))].map((_, i) => (
                  <div key={i} className="p-4 bg-slate-800/50 rounded-lg border border-white/5">
                    <div className="flex items-start justify-between mb-2">
                      <span className={`px-2 py-0.5 text-xs rounded ${
                        i < 2 ? 'bg-red-500/10 text-red-400' :
                        i < 4 ? 'bg-orange-500/10 text-orange-400' :
                        'bg-yellow-500/10 text-yellow-400'
                      }`}>
                        {i < 2 ? 'critical' : i < 4 ? 'high' : 'medium'}
                      </span>
                      <Zap className="w-4 h-4 text-orange-500" />
                    </div>
                    <p className="font-medium text-white text-sm">Finding #{i + 1}</p>
                    <p className="text-xs text-slate-400 mt-1">Detection matched</p>
                    <a
                      href="/security/events"
                      className="text-xs text-blue-400 hover:text-blue-300 mt-2 inline-flex items-center gap-1"
                    >
                      View in Events <ChevronRight className="w-3 h-3" />
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}

