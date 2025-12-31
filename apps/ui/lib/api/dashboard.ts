/**
 * Dashboard API Client
 * 20+ endpoints for dashboard management, widgets, and real-time data
 */

import { apiClient, ApiResponse, PaginatedResponse } from './client'

// Dashboard types
export interface Dashboard {
  id: string
  name: string
  description: string
  type: 'executive' | 'operational' | 'security' | 'compliance' | 'custom'
  layout: DashboardLayout
  widgets: Widget[]
  created_by: string
  created_at: string
  updated_at: string
  is_public: boolean
  tags: string[]
}

export interface DashboardLayout {
  columns: number
  rows: number
  widgets: WidgetPosition[]
}

export interface WidgetPosition {
  widget_id: string
  x: number
  y: number
  width: number
  height: number
}

export interface Widget {
  id: string
  type: WidgetType
  title: string
  description?: string
  config: WidgetConfig
  data_source: DataSource
  refresh_interval: number
  created_at: string
  updated_at: string
}

export type WidgetType = 
  | 'metric_card' 
  | 'line_chart' 
  | 'bar_chart' 
  | 'pie_chart' 
  | 'table'
  | 'heatmap'
  | 'gauge'
  | 'timeline'
  | 'geo_map'
  | 'status_indicator'
  | 'log_stream'
  | 'alert_list'

export interface WidgetConfig {
  query?: string
  aggregation?: string
  time_range?: string
  filters?: Record<string, any>
  display_options?: Record<string, any>
  thresholds?: Array<{
    value: number
    color: string
    label: string
  }>
}

export interface DataSource {
  type: 'logs' | 'metrics' | 'alerts' | 'security' | 'api'
  endpoint?: string
  query?: string
  params?: Record<string, any>
}

export interface DashboardData {
  dashboard_id: string
  widgets: Array<{
    widget_id: string
    data: any
    last_updated: string
    status: 'success' | 'error' | 'loading'
    error?: string
  }>
  generated_at: string
}

export interface DashboardTemplate {
  id: string
  name: string
  description: string
  category: string
  industry?: string
  preview_image?: string
  dashboard_config: Omit<Dashboard, 'id' | 'created_by' | 'created_at' | 'updated_at'>
}

// Dashboard API client
export class DashboardApi {
  /**
   * List All Dashboards
   * GET /v1/dashboards
   */
  static async listDashboards(params?: {
    type?: string
    tags?: string[]
    search?: string
    page?: number
    limit?: number
  }): Promise<PaginatedResponse<Dashboard>> {
    return apiClient.getPaginated('/v1/dashboards', params)
  }

  /**
   * Get Dashboard by ID
   * GET /v1/dashboards/{dashboard_id}
   */
  static async getDashboard(dashboardId: string): Promise<ApiResponse<Dashboard>> {
    return apiClient.get(`/v1/dashboards/${dashboardId}`)
  }

  /**
   * Create New Dashboard
   * POST /v1/dashboards
   */
  static async createDashboard(dashboard: Omit<Dashboard, 'id' | 'created_by' | 'created_at' | 'updated_at'>): Promise<ApiResponse<Dashboard>> {
    return apiClient.post('/v1/dashboards', dashboard)
  }

  /**
   * Update Dashboard
   * PUT /v1/dashboards/{dashboard_id}
   */
  static async updateDashboard(dashboardId: string, updates: Partial<Dashboard>): Promise<ApiResponse<Dashboard>> {
    return apiClient.put(`/v1/dashboards/${dashboardId}`, updates)
  }

  /**
   * Delete Dashboard
   * DELETE /v1/dashboards/{dashboard_id}
   */
  static async deleteDashboard(dashboardId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/dashboards/${dashboardId}`)
  }

  /**
   * Get Dashboard Data
   * GET /v1/dashboards/{dashboard_id}/data
   */
  static async getDashboardData(dashboardId: string, params?: {
    time_range?: string
    refresh?: boolean
  }): Promise<ApiResponse<DashboardData>> {
    return apiClient.get(`/v1/dashboards/${dashboardId}/data`, { params })
  }

  /**
   * Get Widget Data
   * GET /v1/dashboards/{dashboard_id}/widgets/{widget_id}/data
   */
  static async getWidgetData(dashboardId: string, widgetId: string, params?: {
    time_range?: string
    filters?: Record<string, any>
  }): Promise<ApiResponse<any>> {
    return apiClient.get(`/v1/dashboards/${dashboardId}/widgets/${widgetId}/data`, { params })
  }

  /**
   * Add Widget to Dashboard
   * POST /v1/dashboards/{dashboard_id}/widgets
   */
  static async addWidget(dashboardId: string, widget: Omit<Widget, 'id' | 'created_at' | 'updated_at'>): Promise<ApiResponse<Widget>> {
    return apiClient.post(`/v1/dashboards/${dashboardId}/widgets`, widget)
  }

  /**
   * Update Widget
   * PUT /v1/dashboards/{dashboard_id}/widgets/{widget_id}
   */
  static async updateWidget(dashboardId: string, widgetId: string, updates: Partial<Widget>): Promise<ApiResponse<Widget>> {
    return apiClient.put(`/v1/dashboards/${dashboardId}/widgets/${widgetId}`, updates)
  }

  /**
   * Remove Widget from Dashboard
   * DELETE /v1/dashboards/{dashboard_id}/widgets/{widget_id}
   */
  static async removeWidget(dashboardId: string, widgetId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/dashboards/${dashboardId}/widgets/${widgetId}`)
  }

  /**
   * Update Dashboard Layout
   * PUT /v1/dashboards/{dashboard_id}/layout
   */
  static async updateLayout(dashboardId: string, layout: DashboardLayout): Promise<ApiResponse<Dashboard>> {
    return apiClient.put(`/v1/dashboards/${dashboardId}/layout`, layout)
  }

  /**
   * Export Dashboard
   * GET /v1/dashboards/{dashboard_id}/export
   */
  static async exportDashboard(dashboardId: string, format: 'json' | 'pdf' | 'png'): Promise<ApiResponse<{
    download_url: string
    expires_at: string
  }>> {
    return apiClient.get(`/v1/dashboards/${dashboardId}/export`, {
      params: { format }
    })
  }

  /**
   * Import Dashboard
   * POST /v1/dashboards/import
   */
  static async importDashboard(file: File): Promise<ApiResponse<Dashboard>> {
    return apiClient.uploadFile('/v1/dashboards/import', file)
  }

  /**
   * Clone Dashboard
   * POST /v1/dashboards/{dashboard_id}/clone
   */
  static async cloneDashboard(dashboardId: string, name: string): Promise<ApiResponse<Dashboard>> {
    return apiClient.post(`/v1/dashboards/${dashboardId}/clone`, { name })
  }

  /**
   * Share Dashboard
   * POST /v1/dashboards/{dashboard_id}/share
   */
  static async shareDashboard(dashboardId: string, shareConfig: {
    public: boolean
    expires_at?: string
    password?: string
    users?: string[]
  }): Promise<ApiResponse<{
    share_token: string
    share_url: string
    expires_at?: string
  }>> {
    return apiClient.post(`/v1/dashboards/${dashboardId}/share`, shareConfig)
  }

  /**
   * Get Dashboard Templates
   * GET /v1/dashboards/templates
   */
  static async getTemplates(category?: string): Promise<ApiResponse<DashboardTemplate[]>> {
    return apiClient.get('/v1/dashboards/templates', {
      params: category ? { category } : undefined
    })
  }

  /**
   * Create Dashboard from Template
   * POST /v1/dashboards/templates/{template_id}/create
   */
  static async createFromTemplate(templateId: string, name: string, customizations?: Record<string, any>): Promise<ApiResponse<Dashboard>> {
    return apiClient.post(`/v1/dashboards/templates/${templateId}/create`, {
      name,
      customizations
    })
  }

  /**
   * Get Dashboard Analytics
   * GET /v1/dashboards/{dashboard_id}/analytics
   */
  static async getDashboardAnalytics(dashboardId: string, timeRange?: string): Promise<ApiResponse<{
    views: number
    unique_viewers: number
    avg_view_time: number
    popular_widgets: string[]
    performance_metrics: Record<string, any>
  }>> {
    return apiClient.get(`/v1/dashboards/${dashboardId}/analytics`, {
      params: timeRange ? { time_range: timeRange } : undefined
    })
  }

  /**
   * Schedule Dashboard Report
   * POST /v1/dashboards/{dashboard_id}/schedule
   */
  static async scheduleDashboardReport(dashboardId: string, schedule: {
    frequency: 'daily' | 'weekly' | 'monthly'
    time: string
    format: 'pdf' | 'png' | 'json'
    recipients: string[]
    subject?: string
    message?: string
  }): Promise<ApiResponse<{
    schedule_id: string
    next_run: string
  }>> {
    return apiClient.post(`/v1/dashboards/${dashboardId}/schedule`, schedule)
  }

  /**
   * Get Real-time Dashboard Updates
   * Stream: /v1/dashboards/{dashboard_id}/stream
   */
  static async streamDashboardUpdates(
    dashboardId: string,
    onUpdate: (data: any) => void,
    onError?: (error: Error) => void
  ): Promise<() => void> {
    return apiClient.getStream(
      `/v1/dashboards/${dashboardId}/stream`,
      onUpdate,
      onError
    )
  }

  /**
   * Test Widget Query
   * POST /v1/dashboards/widgets/test
   */
  static async testWidgetQuery(widget: Omit<Widget, 'id' | 'created_at' | 'updated_at'>): Promise<ApiResponse<{
    data: any
    execution_time: number
    row_count: number
    status: 'success' | 'error'
    error?: string
  }>> {
    return apiClient.post('/v1/dashboards/widgets/test', widget)
  }

  /**
   * Get Dashboard Performance Metrics
   * GET /v1/dashboards/{dashboard_id}/performance
   */
  static async getDashboardPerformance(dashboardId: string): Promise<ApiResponse<{
    load_time: number
    widget_performance: Array<{
      widget_id: string
      execution_time: number
      data_size: number
      cache_hit: boolean
    }>
    recommendations: string[]
  }>> {
    return apiClient.get(`/v1/dashboards/${dashboardId}/performance`)
  }
}

export default DashboardApi