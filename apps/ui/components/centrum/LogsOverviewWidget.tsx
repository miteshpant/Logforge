'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Database, AlertCircle, Info, Bug, AlertTriangle, TrendingUp } from 'lucide-react'
import { Progress } from '@/components/ui/progress'

interface LogLevel {
  level: string
  total_logs: number
  affected_services: number
  affected_hosts: number
}

interface LogsOverviewData {
  logs: LogLevel[]
  total_count: number
  execution_time_ms: number
}

interface LogsOverviewWidgetProps {
  data: LogsOverviewData | null
  isLoading: boolean
  timeRange?: string
}

export default function LogsOverviewWidget({ data, isLoading, timeRange }: LogsOverviewWidgetProps) {
  // Calculate totals
  const totalLogs = data?.logs?.reduce((sum, level) => sum + level.total_logs, 0) || 0
  const errorLogs = data?.logs?.find(l => l.level === 'error')?.total_logs || 0
  const warnLogs = data?.logs?.find(l => l.level === 'warn' || l.level === 'warning')?.total_logs || 0
  const infoLogs = data?.logs?.find(l => l.level === 'info')?.total_logs || 0
  const debugLogs = data?.logs?.find(l => l.level === 'debug')?.total_logs || 0

  const errorPercentage = totalLogs > 0 ? (errorLogs / totalLogs) * 100 : 0
  const warnPercentage = totalLogs > 0 ? (warnLogs / totalLogs) * 100 : 0

  // Get unique services and hosts
  const totalServices = Math.max(...(data?.logs?.map(l => l.affected_services) || [0]))
  const totalHosts = Math.max(...(data?.logs?.map(l => l.affected_hosts) || [0]))

  // Determine health status
  const getHealthStatus = () => {
    if (errorPercentage > 5) return { status: 'Critical', color: 'text-red-600', bgColor: 'bg-red-50', borderColor: 'border-red-200' }
    if (errorPercentage > 1 || warnPercentage > 10) return { status: 'Warning', color: 'text-orange-600', bgColor: 'bg-orange-50', borderColor: 'border-orange-200' }
    return { status: 'Healthy', color: 'text-green-600', bgColor: 'bg-green-50', borderColor: 'border-green-200' }
  }

  const health = getHealthStatus()

  if (isLoading) {
    return (
      <Card className="col-span-full">
        <CardHeader>
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
              <Database className="w-6 h-6 text-blue-600 animate-pulse" />
            </div>
            <div>
              <CardTitle className="text-2xl">Logs Overview</CardTitle>
              <p className="text-sm text-slate-500">Loading data...</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="h-32 bg-slate-200 rounded-lg animate-pulse"></div>
            <div className="grid grid-cols-4 gap-4">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="h-24 bg-slate-200 rounded-lg animate-pulse"></div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={`col-span-full border-2 ${health.borderColor} shadow-lg`}>
      <CardHeader className={`${health.bgColor} border-b ${health.borderColor}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="w-14 h-14 bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl flex items-center justify-center shadow-lg">
              <Database className="w-7 h-7 text-white" />
            </div>
            <div>
              <CardTitle className="text-2xl font-bold text-slate-900">Logs Overview</CardTitle>
              <p className="text-sm text-slate-600 mt-1">
                {timeRange || 'Selected time range'} • {data?.execution_time_ms.toFixed(2)}ms query time
              </p>
            </div>
          </div>

          {/* Health Badge */}
          <div className={`px-4 py-2 rounded-full ${health.bgColor} border-2 ${health.borderColor}`}>
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${health.color.replace('text-', 'bg-')} animate-pulse`}></div>
              <span className={`font-semibold ${health.color}`}>{health.status}</span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-6">
        <div className="space-y-6">
          {/* Main Stats Row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Total Logs */}
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-6 rounded-xl border-2 border-blue-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-blue-700">Total Logs</span>
                <TrendingUp className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-4xl font-bold text-blue-900">{totalLogs.toLocaleString()}</div>
              <p className="text-xs text-blue-600 mt-2">
                {totalServices} services • {totalHosts} hosts
              </p>
            </div>

            {/* Error Rate */}
            <div className={`${errorPercentage > 1 ? 'bg-gradient-to-br from-red-50 to-orange-50 border-red-200' : 'bg-gradient-to-br from-green-50 to-emerald-50 border-green-200'} p-6 rounded-xl border-2`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700">Error Rate</span>
                <AlertCircle className={`w-4 h-4 ${errorPercentage > 1 ? 'text-red-600' : 'text-green-600'}`} />
              </div>
              <div className={`text-4xl font-bold ${errorPercentage > 1 ? 'text-red-900' : 'text-green-900'}`}>
                {errorPercentage.toFixed(2)}%
              </div>
              <p className={`text-xs mt-2 ${errorPercentage > 1 ? 'text-red-600' : 'text-green-600'}`}>
                {errorLogs.toLocaleString()} errors
              </p>
            </div>

            {/* Warning Rate */}
            <div className={`${warnPercentage > 5 ? 'bg-gradient-to-br from-orange-50 to-yellow-50 border-orange-200' : 'bg-gradient-to-br from-slate-50 to-gray-50 border-slate-200'} p-6 rounded-xl border-2`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700">Warning Rate</span>
                <AlertTriangle className={`w-4 h-4 ${warnPercentage > 5 ? 'text-orange-600' : 'text-slate-600'}`} />
              </div>
              <div className={`text-4xl font-bold ${warnPercentage > 5 ? 'text-orange-900' : 'text-slate-900'}`}>
                {warnPercentage.toFixed(2)}%
              </div>
              <p className={`text-xs mt-2 ${warnPercentage > 5 ? 'text-orange-600' : 'text-slate-600'}`}>
                {warnLogs.toLocaleString()} warnings
              </p>
            </div>

            {/* Info & Debug */}
            <div className="bg-gradient-to-br from-purple-50 to-indigo-50 p-6 rounded-xl border-2 border-purple-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-purple-700">Info & Debug</span>
                <Info className="w-4 h-4 text-purple-600" />
              </div>
              <div className="text-4xl font-bold text-purple-900">
                {((infoLogs + debugLogs) / totalLogs * 100).toFixed(1)}%
              </div>
              <p className="text-xs text-purple-600 mt-2">
                {(infoLogs + debugLogs).toLocaleString()} logs
              </p>
            </div>
          </div>

          {/* Log Level Breakdown */}
          <div className="bg-slate-50 p-6 rounded-xl border border-slate-200">
            <h3 className="text-sm font-semibold text-slate-700 mb-4">Log Level Distribution</h3>
            <div className="space-y-4">
              {data?.logs
                .sort((a, b) => b.total_logs - a.total_logs)
                .map((levelData) => {
                  const percentage = (levelData.total_logs / totalLogs) * 100
                  const levelConfig = {
                    error: { icon: AlertCircle, color: 'text-red-600', bgColor: 'bg-red-600', lightBg: 'bg-red-50' },
                    warn: { icon: AlertTriangle, color: 'text-orange-600', bgColor: 'bg-orange-600', lightBg: 'bg-orange-50' },
                    warning: { icon: AlertTriangle, color: 'text-orange-600', bgColor: 'bg-orange-600', lightBg: 'bg-orange-50' },
                    info: { icon: Info, color: 'text-blue-600', bgColor: 'bg-blue-600', lightBg: 'bg-blue-50' },
                    debug: { icon: Bug, color: 'text-purple-600', bgColor: 'bg-purple-600', lightBg: 'bg-purple-50' },
                  }[levelData.level] || { icon: Info, color: 'text-slate-600', bgColor: 'bg-slate-600', lightBg: 'bg-slate-50' }

                  const Icon = levelConfig.icon

                  return (
                    <div key={levelData.level} className={`p-4 rounded-lg ${levelConfig.lightBg} border border-slate-200`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-3">
                          <Icon className={`w-5 h-5 ${levelConfig.color}`} />
                          <span className="font-semibold text-slate-900 uppercase text-sm">
                            {levelData.level}
                          </span>
                        </div>
                        <div className="text-right">
                          <span className="text-lg font-bold text-slate-900">
                            {levelData.total_logs.toLocaleString()}
                          </span>
                          <span className={`text-sm ml-2 ${levelConfig.color} font-medium`}>
                            {percentage.toFixed(1)}%
                          </span>
                        </div>
                      </div>
                      <Progress value={percentage} className={`h-2 ${levelConfig.bgColor}`} />
                      <div className="flex items-center justify-between mt-2 text-xs text-slate-600">
                        <span>{levelData.affected_services} services</span>
                        <span>{levelData.affected_hosts} hosts</span>
                      </div>
                    </div>
                  )
                })}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}