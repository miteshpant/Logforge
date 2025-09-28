'use client'

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { 
  Activity, 
  X, 
  Minimize2, 
  Maximize2, 
  Filter, 
  Search, 
  RefreshCw, 
  Eye, 
  AlertTriangle,
  Shield,
  User,
  Database,
  Settings,
  Clock,
  ChevronDown,
  ChevronRight
} from 'lucide-react'
import { fetchAdminAuditLogs } from '@/lib/api'

interface AuditEvent {
  id: string
  user_id: string
  tenant_id?: string
  action_type: string
  resource_type: string
  resource_id?: string
  details: string
  ip_address: string
  user_agent: string
  timestamp: string
  customer_id: string
}

interface AdminActivityLogProps {
  isOpen: boolean
  onClose: () => void
}

const getRiskColor = (level: string) => {
  switch (level) {
    case 'critical': return 'red' as const
    case 'high': return 'orange' as const
    case 'medium': return 'yellow' as const
    case 'low': return 'green' as const
    default: return 'secondary' as const
  }
}

const getActionIcon = (actionType: string) => {
  switch (actionType.toLowerCase()) {
    case 'login':
    case 'logout':
    case 'auth': return <User className="h-4 w-4" />
    case 'data_access':
    case 'query': return <Database className="h-4 w-4" />
    case 'admin_action':
    case 'configuration': return <Settings className="h-4 w-4" />
    case 'security':
    case 'permission': return <Shield className="h-4 w-4" />
    default: return <Activity className="h-4 w-4" />
  }
}

export default function AdminActivityLog({ isOpen, onClose }: AdminActivityLogProps) {
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isMinimized, setIsMinimized] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  
  // Filters
  const [timeFilter, setTimeFilter] = useState('1h') // 1h, 4h, 24h, 7d
  const [userFilter, setUserFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [riskFilter, setRiskFilter] = useState('')
  
  // Expanded event details
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set())
  
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (isOpen) {
      fetchAuditLogs()
      
      if (autoRefresh) {
        refreshIntervalRef.current = setInterval(fetchAuditLogs, 30000) // Refresh every 30 seconds
      }
    }
    
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
      }
    }
  }, [isOpen, timeFilter, userFilter, actionFilter, riskFilter, autoRefresh])

  const fetchAuditLogs = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const endTime = new Date()
      const startTime = new Date()
      
      // Calculate start time based on filter
      switch (timeFilter) {
        case '1h':
          startTime.setHours(startTime.getHours() - 1)
          break
        case '4h':
          startTime.setHours(startTime.getHours() - 4)
          break
        case '24h':
          startTime.setDate(startTime.getDate() - 1)
          break
        case '7d':
          startTime.setDate(startTime.getDate() - 7)
          break
      }
      
      const params = {
        start_time: startTime.toISOString(),
        end_time: endTime.toISOString(),
        ...(userFilter && { user_id: userFilter }),
        ...(actionFilter && { action_types: actionFilter }),
        ...(riskFilter && { risk_level: riskFilter })
      }
      
      const response = await fetchAdminAuditLogs(params)
      console.log('🔍 Audit logs API response:', response)
      setAuditEvents(response.audit_logs || [])
      
    } catch (error) {
      console.error('Failed to fetch audit logs:', error)
      setError('Failed to fetch audit logs: ' + (error instanceof Error ? error.message : 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }

  const toggleEventExpansion = (eventId: string) => {
    setExpandedEvents(prev => {
      const newSet = new Set(prev)
      if (newSet.has(eventId)) {
        newSet.delete(eventId)
      } else {
        newSet.add(eventId)
      }
      return newSet
    })
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  const handleRefresh = () => {
    fetchAuditLogs()
  }

  const clearFilters = () => {
    setUserFilter('')
    setActionFilter('')
    setRiskFilter('')
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 pointer-events-none">
      <div className="absolute bottom-4 right-4 pointer-events-auto">
        <Card className={`bg-white shadow-2xl border-2 transition-all duration-300 ${
          isMinimized ? 'w-80 h-16' : 'w-[900px] h-[600px]'
        }`}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 bg-blue-50 border-b">
            <CardTitle className="text-sm font-medium flex items-center">
              <Activity className="h-4 w-4 mr-2 text-blue-600" />
              Admin Activity Log
              {auditEvents.length > 0 && (
                <Badge variant="secondary" className="ml-2">
                  {auditEvents.length} events
                </Badge>
              )}
            </CardTitle>
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={loading}
                className="h-6 w-6 p-0"
              >
                <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsMinimized(!isMinimized)}
                className="h-6 w-6 p-0"
              >
                {isMinimized ? <Maximize2 className="h-3 w-3" /> : <Minimize2 className="h-3 w-3" />}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                className="h-6 w-6 p-0"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          </CardHeader>

          {!isMinimized && (
            <CardContent className="p-4 flex flex-col h-full">
              {/* Filters */}
              <div className="flex items-center space-x-4 mb-4 pb-4 border-b">
                <div className="flex items-center space-x-2">
                  <Clock className="h-4 w-4 text-gray-500" />
                  <Select value={timeFilter} onValueChange={setTimeFilter}>
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1h">1h</SelectItem>
                      <SelectItem value="4h">4h</SelectItem>
                      <SelectItem value="24h">24h</SelectItem>
                      <SelectItem value="7d">7d</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center space-x-2">
                  <Filter className="h-4 w-4 text-gray-500" />
                  <Select value={actionFilter} onValueChange={setActionFilter}>
                    <SelectTrigger className="w-32">
                      <SelectValue placeholder="Action" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">All Actions</SelectItem>
                      <SelectItem value="login">Login</SelectItem>
                      <SelectItem value="logout">Logout</SelectItem>
                      <SelectItem value="data_access">Data Access</SelectItem>
                      <SelectItem value="admin_action">Admin Action</SelectItem>
                      <SelectItem value="configuration">Configuration</SelectItem>
                      <SelectItem value="security">Security</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center space-x-2">
                  <AlertTriangle className="h-4 w-4 text-gray-500" />
                  <Select value={riskFilter} onValueChange={setRiskFilter}>
                    <SelectTrigger className="w-24">
                      <SelectValue placeholder="Risk" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">All</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Button variant="outline" size="sm" onClick={clearFilters}>
                  Clear
                </Button>

                <div className="flex items-center space-x-2 ml-auto">
                  <input
                    type="checkbox"
                    checked={autoRefresh}
                    onChange={(e) => setAutoRefresh(e.target.checked)}
                    className="rounded"
                  />
                  <label className="text-xs text-gray-600">Auto-refresh</label>
                </div>
              </div>

              {/* Activity Log Content */}
              <div className="flex-1 overflow-y-auto">
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                    <p className="text-red-800 text-sm">{error}</p>
                  </div>
                )}

                {loading && auditEvents.length === 0 ? (
                  <div className="flex items-center justify-center h-32">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  </div>
                ) : auditEvents.length === 0 ? (
                  <div className="flex items-center justify-center h-32 text-gray-500">
                    <div className="text-center">
                      <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
                      <p>No admin activity in the selected time range</p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {auditEvents.map((event) => {
                      const isExpanded = expandedEvents.has(event.id)
                      let parsedDetails: any = {}
                      
                      try {
                        parsedDetails = JSON.parse(event.details)
                      } catch (e) {
                        console.warn('Failed to parse audit event details:', e)
                      }
                      
                      // Convert action_type enum to readable string
                      const actionTypeMap: { [key: string]: string } = {
                        '1': 'create',
                        '2': 'update', 
                        '3': 'delete',
                        '4': 'view',
                        '5': 'login',
                        '6': 'logout'
                      }
                      const actionTypeDisplay = actionTypeMap[event.action_type] || event.action_type
                      
                      return (
                        <div key={event.id} className="border rounded-lg p-3 hover:bg-gray-50 transition-colors">
                          {/* Event Summary */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3 flex-1">
                              <div className="flex items-center space-x-2">
                                {getActionIcon(actionTypeDisplay)}
                                <Badge variant="secondary" className="text-xs">
                                  {actionTypeDisplay}
                                </Badge>
                              </div>
                              
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center space-x-2">
                                  <span className="font-medium text-sm">{event.resource_type}</span>
                                  <span className="text-gray-500 text-xs">•</span>
                                  <span className="text-gray-600 text-xs">{event.user_id.slice(0, 8)}...</span>
                                  <span className="text-gray-500 text-xs">•</span>
                                  <span className="text-gray-500 text-xs">{formatTimestamp(event.timestamp)}</span>
                                </div>
                                <div className="text-xs text-gray-600 truncate">
                                  {parsedDetails.endpoint && `${parsedDetails.method} ${parsedDetails.endpoint}`}
                                  {parsedDetails.status_code && ` → ${parsedDetails.status_code}`}
                                </div>
                              </div>
                            </div>
                            
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleEventExpansion(event.id)}
                              className="h-6 w-6 p-0"
                            >
                              {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                            </Button>
                          </div>

                          {/* Expanded Details */}
                          {isExpanded && (
                            <div className="mt-3 pt-3 border-t space-y-2">
                              <div className="grid grid-cols-2 gap-4 text-xs">
                                <div>
                                  <span className="font-medium">Event ID:</span> {event.id.slice(0, 8)}...
                                </div>
                                <div>
                                  <span className="font-medium">Action:</span> {actionTypeDisplay}
                                </div>
                                <div>
                                  <span className="font-medium">Resource Type:</span> {event.resource_type}
                                </div>
                                {event.resource_id && (
                                  <div>
                                    <span className="font-medium">Resource ID:</span> {event.resource_id.slice(0, 8)}...
                                  </div>
                                )}
                                <div>
                                  <span className="font-medium">IP Address:</span> {event.ip_address}
                                </div>
                                {parsedDetails.status_code && (
                                  <div>
                                    <span className="font-medium">Status:</span> {parsedDetails.status_code}
                                  </div>
                                )}
                                {event.tenant_id && (
                                  <div>
                                    <span className="font-medium">Target Tenant:</span> {event.tenant_id.slice(0, 8)}...
                                  </div>
                                )}
                                {parsedDetails.platform_roles && (
                                  <div>
                                    <span className="font-medium">Platform Roles:</span>
                                    <div className="flex flex-wrap gap-1 mt-1">
                                      {parsedDetails.platform_roles.map((role: string, index: number) => (
                                        <Badge key={index} variant="outline" className="text-xs">
                                          {role}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                              
                              {parsedDetails.endpoint && (
                                <div>
                                  <span className="font-medium text-xs">API Endpoint:</span>
                                  <div className="mt-1 p-2 bg-gray-100 rounded text-xs font-mono">
                                    {parsedDetails.method} {parsedDetails.endpoint}
                                    {parsedDetails.query_params && ` → ${parsedDetails.query_params}`}
                                  </div>
                                </div>
                              )}
                              
                              <div>
                                <span className="font-medium text-xs">User Agent:</span>
                                <div className="text-xs text-gray-600 mt-1 break-all">
                                  {event.user_agent}
                                </div>
                              </div>
                              
                              {parsedDetails.has_request_body && (
                                <div>
                                  <span className="font-medium text-xs">Request Body:</span>
                                  <div className="text-xs text-gray-600 mt-1">
                                    Body present ({parsedDetails.content_length} bytes)
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </CardContent>
          )}
        </Card>
      </div>
    </div>
  )
}