"use client"

import React, { useState, useEffect } from 'react'

// Types
interface SecurityEvent {
  id: string
  rule_id: string
  rule_title: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  status: 'triggered' | 'investigating' | 'false_positive' | 'true_positive' | 'resolved'
  timestamp: string
  event_data: Record<string, any>
  matched_fields: Record<string, any>
  attack_techniques: string[]
  kill_chain_phase?: string
  assigned_to?: string
  investigation_notes: string[]
  artifacts: string[]
}

interface SigmaRule {
  id: string
  title: string
  description: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  status: string
  author: string
  date: string
  tags: string[]
  attack_techniques: string[]
  kill_chain_phases: string[]
  logsource: Record<string, any>
  detection: Record<string, any>
  enabled: boolean
  created_at?: string
  updated_at?: string
}

interface ThreatIntelIndicator {
  id: string
  indicator_type: string
  value: string
  threat_type: string[]
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  confidence: number
  source: string
  description?: string
  tags: string[]
  first_seen?: string
  last_seen?: string
}

interface SecurityDashboard {
  total_events: number
  events_by_severity: Record<string, number>
  events_by_technique: Record<string, number>
  top_rules: Array<{rule_id: string, rule_title: string, count: number}>
  recent_events: SecurityEvent[]
  threat_intel_stats: Record<string, any>
}

const SecurityAnalytics: React.FC = () => {
  const [dashboard, setDashboard] = useState<SecurityDashboard | null>(null)
  const [sigmaRules, setSigmaRules] = useState<SigmaRule[]>([])
  const [securityEvents, setSecurityEvents] = useState<SecurityEvent[]>([])
  const [threatIntel, setThreatIntel] = useState<ThreatIntelIndicator[]>([])
  const [activeTab, setActiveTab] = useState<'dashboard' | 'events' | 'rules' | 'threat-intel' | 'hunting'>('dashboard')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [huntingResults, setHuntingResults] = useState<any>(null)

  const API_BASE = 'http://localhost:7080'
  const headers = {
    'X-Customer-ID': 'test-customer',
    'Content-Type': 'application/json'
  }

  // Fetch dashboard data
  const fetchDashboard = async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/security/dashboard?time_range=24h`, { headers })
      if (response.ok) {
        const data = await response.json()
        setDashboard(data)
      }
    } catch (err) {
      console.error('Failed to fetch dashboard:', err)
    }
  }

  // Fetch Sigma rules
  const fetchSigmaRules = async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/security/sigma-rules`, { headers })
      if (response.ok) {
        const data = await response.json()
        setSigmaRules(data)
      }
    } catch (err) {
      console.error('Failed to fetch Sigma rules:', err)
    }
  }

  // Fetch security events
  const fetchSecurityEvents = async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/security/events?limit=50`, { headers })
      if (response.ok) {
        const data = await response.json()
        setSecurityEvents(data)
      }
    } catch (err) {
      console.error('Failed to fetch security events:', err)
    }
  }

  // Fetch threat intelligence
  const fetchThreatIntel = async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/security/threat-intel`, { headers })
      if (response.ok) {
        const data = await response.json()
        setThreatIntel(data)
      }
    } catch (err) {
      console.error('Failed to fetch threat intel:', err)
    }
  }

  // Run threat hunting
  const runThreatHunting = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`${API_BASE}/v1/security/threat-hunting`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          time_range: '24h',
          severity_filter: null,
          rule_ids: null
        })
      })
      
      if (response.ok) {
        const data = await response.json()
        setHuntingResults(data)
        // Refresh dashboard and events after hunting
        await Promise.all([fetchDashboard(), fetchSecurityEvents()])
      } else {
        setError('Failed to run threat hunting')
      }
    } catch (err) {
      setError('Error running threat hunting: ' + err)
    } finally {
      setLoading(false)
    }
  }

  // Test a specific Sigma rule
  const testSigmaRule = async (ruleId: string) => {
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/v1/security/sigma-rules/${ruleId}/test`, {
        method: 'POST',
        headers
      })
      
      if (response.ok) {
        const result = await response.json()
        alert(`Rule test result: ${result.result}\n${JSON.stringify(result.event || {}, null, 2)}`)
      } else {
        alert('Failed to test rule')
      }
    } catch (err) {
      alert('Error testing rule: ' + err)
    } finally {
      setLoading(false)
    }
  }

  // Update event status
  const updateEventStatus = async (eventId: string, status: string) => {
    try {
      const response = await fetch(`${API_BASE}/v1/security/events/${eventId}/status?new_status=${status}`, {
        method: 'PUT',
        headers
      })
      
      if (response.ok) {
        // Refresh events
        await fetchSecurityEvents()
      }
    } catch (err) {
      console.error('Failed to update event status:', err)
    }
  }

  // Initialize data
  useEffect(() => {
    Promise.all([
      fetchDashboard(),
      fetchSigmaRules(),
      fetchSecurityEvents(),
      fetchThreatIntel()
    ])
  }, [])

  // Get severity color
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-600 bg-red-100'
      case 'high': return 'text-orange-600 bg-orange-100'
      case 'medium': return 'text-yellow-600 bg-yellow-100'
      case 'low': return 'text-blue-600 bg-blue-100'
      case 'info': return 'text-gray-600 bg-gray-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'triggered': return 'text-red-600 bg-red-100'
      case 'investigating': return 'text-yellow-600 bg-yellow-100'
      case 'resolved': return 'text-green-600 bg-green-100'
      case 'false_positive': return 'text-gray-600 bg-gray-100'
      case 'true_positive': return 'text-red-600 bg-red-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="p-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">🛡️ Security Analytics - M4 SIEM</h1>
        
        {/* Tab Navigation */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8">
            {['dashboard', 'events', 'rules', 'threat-intel', 'hunting'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={`py-2 px-1 border-b-2 font-medium text-sm capitalize ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.replace('-', ' ')}
              </button>
            ))}
          </nav>
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="bg-white p-6 rounded-lg shadow">
                <div className="text-2xl font-bold text-gray-900">{dashboard?.total_events || 0}</div>
                <div className="text-gray-600">Total Events</div>
              </div>
              <div className="bg-white p-6 rounded-lg shadow">
                <div className="text-2xl font-bold text-red-600">{dashboard?.events_by_severity?.critical || 0}</div>
                <div className="text-gray-600">Critical Events</div>
              </div>
              <div className="bg-white p-6 rounded-lg shadow">
                <div className="text-2xl font-bold text-orange-600">{dashboard?.events_by_severity?.high || 0}</div>
                <div className="text-gray-600">High Severity</div>
              </div>
              <div className="bg-white p-6 rounded-lg shadow">
                <div className="text-2xl font-bold text-blue-600">{sigmaRules.filter(r => r.enabled).length}</div>
                <div className="text-gray-600">Active Rules</div>
              </div>
            </div>

            {/* Events by Severity Chart */}
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Events by Severity</h3>
              <div className="grid grid-cols-5 gap-4">
                {Object.entries(dashboard?.events_by_severity || {}).map(([severity, count]) => (
                  <div key={severity} className="text-center">
                    <div className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center text-xl font-bold ${getSeverityColor(severity)}`}>
                      {count}
                    </div>
                    <div className="mt-2 text-sm capitalize">{severity}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Top Rules */}
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Most Triggered Rules</h3>
              <div className="space-y-3">
                {dashboard?.top_rules?.map((rule, index) => (
                  <div key={rule.rule_id} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <div>
                      <div className="font-medium">{rule.rule_title}</div>
                      <div className="text-sm text-gray-600">Rule ID: {rule.rule_id}</div>
                    </div>
                    <div className="text-lg font-bold text-red-600">{rule.count}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* MITRE ATT&CK Techniques */}
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="text-lg font-medium text-gray-900 mb-4">MITRE ATT&CK Techniques Detected</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(dashboard?.events_by_technique || {}).map(([technique, count]) => (
                  <div key={technique} className="text-center p-3 bg-gray-50 rounded">
                    <div className="font-bold text-red-600">{technique}</div>
                    <div className="text-sm text-gray-600">{count} events</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Security Events Tab */}
        {activeTab === 'events' && (
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Security Events</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Event</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Severity</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Techniques</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {securityEvents.map((event) => (
                    <tr key={event.id}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">{event.rule_title}</div>
                          <div className="text-sm text-gray-500">{event.id}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getSeverityColor(event.severity)}`}>
                          {event.severity}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(event.status)}`}>
                          {event.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {event.attack_techniques.join(', ')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(event.timestamp).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <select 
                          onChange={(e) => updateEventStatus(event.id, e.target.value)}
                          value={event.status}
                          className="border rounded px-2 py-1 text-sm"
                        >
                          <option value="triggered">Triggered</option>
                          <option value="investigating">Investigating</option>
                          <option value="false_positive">False Positive</option>
                          <option value="true_positive">True Positive</option>
                          <option value="resolved">Resolved</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Sigma Rules Tab */}
        {activeTab === 'rules' && (
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Sigma Detection Rules</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rule</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Severity</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Techniques</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {sigmaRules.map((rule) => (
                    <tr key={rule.id}>
                      <td className="px-6 py-4">
                        <div>
                          <div className="text-sm font-medium text-gray-900">{rule.title}</div>
                          <div className="text-sm text-gray-500">{rule.description}</div>
                          <div className="text-xs text-gray-400">{rule.id}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getSeverityColor(rule.severity)}`}>
                          {rule.severity}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${rule.enabled ? 'text-green-600 bg-green-100' : 'text-gray-600 bg-gray-100'}`}>
                          {rule.enabled ? 'Enabled' : 'Disabled'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {rule.attack_techniques.join(', ')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <button
                          onClick={() => testSigmaRule(rule.id)}
                          disabled={loading}
                          className="text-blue-600 hover:text-blue-900 disabled:opacity-50"
                        >
                          Test Rule
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Threat Intelligence Tab */}
        {activeTab === 'threat-intel' && (
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Threat Intelligence Indicators</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Indicator</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Severity</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Confidence</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Source</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {threatIntel.map((indicator) => (
                    <tr key={indicator.id}>
                      <td className="px-6 py-4">
                        <div>
                          <div className="text-sm font-medium text-gray-900">{indicator.value}</div>
                          <div className="text-sm text-gray-500">{indicator.description}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 capitalize">
                        {indicator.indicator_type}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getSeverityColor(indicator.severity)}`}>
                          {indicator.severity}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        <div className="flex items-center">
                          <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                            <div 
                              className="bg-blue-600 h-2 rounded-full" 
                              style={{width: `${indicator.confidence}%`}}
                            ></div>
                          </div>
                          {indicator.confidence}%
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {indicator.source}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Threat Hunting Tab */}
        {activeTab === 'hunting' && (
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">Threat Hunting</h3>
                <button
                  onClick={runThreatHunting}
                  disabled={loading}
                  className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                >
                  {loading ? 'Running Hunt...' : 'Run Threat Hunt'}
                </button>
              </div>
              
              <div className="text-sm text-gray-600 mb-4">
                Execute all active Sigma rules against recent log data to hunt for threats across the environment.
              </div>

              {huntingResults && (
                <div className="mt-6 p-4 bg-gray-50 rounded">
                  <h4 className="font-medium text-gray-900 mb-3">Latest Hunt Results</h4>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <div className="text-2xl font-bold text-red-600">{huntingResults.events_found}</div>
                      <div className="text-gray-600">Events Found</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-blue-600">{sigmaRules.filter(r => r.enabled).length}</div>
                      <div className="text-gray-600">Rules Executed</div>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <h5 className="font-medium text-gray-900">Detected Events:</h5>
                    {huntingResults.events?.map((event: any, index: number) => (
                      <div key={index} className="p-3 bg-white rounded border-l-4 border-red-500">
                        <div className="font-medium">{event.rule_title}</div>
                        <div className="text-sm text-gray-600">
                          Severity: {event.severity} | Techniques: {event.attack_techniques.join(', ')}
                        </div>
                        <div className="text-xs text-gray-500">{event.timestamp}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default SecurityAnalytics