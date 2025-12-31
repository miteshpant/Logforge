/**
 * Ingestion API Client
 * 9 endpoints for comprehensive log ingestion with multiple format support
 * Based on: /docs/wiki/knowledge_base/devDocs/Ingestion-Router-API-Documentation.md
 */

import { apiClient, ApiResponse } from './client'

// Ingestion types
export interface LogEntry {
  ts?: string // ISO timestamp, auto-populated if not provided
  host?: string
  service: string
  level?: string // defaults to "info"
  msg: string
  trace_id?: string
  span_id?: string
  attrs?: Record<string, any>
  status?: number
  src_ip?: string
  user_id?: string
  // Runtime metadata (auto-populated)
  ingested_at?: string
  customer_id?: string
}

export interface BatchLogEntry {
  logs: LogEntry[]
}

export interface OTLPLogsData {
  resource_logs: OTLPResourceLogs[]
}

export interface OTLPResourceLogs {
  resource?: OTLPResource
  scope_logs: OTLPScopeLogs[]
}

export interface OTLPResource {
  attributes: OTLPAttribute[]
}

export interface OTLPScopeLogs {
  scope?: {
    name: string
    version: string
  }
  log_records: OTLPLogRecord[]
}

export interface OTLPLogRecord {
  time_unix_nano: number
  severity_number?: number
  severity_text?: string
  body: string
  attributes: OTLPAttribute[]
  trace_id?: string
  span_id?: string
}

export interface OTLPAttribute {
  key: string
  value: any
}

export interface IngestResponse {
  status: string
  message: string
  log_id?: string
  processed_count: number
}

export interface BatchIngestResponse {
  status: string
  message: string
  processed_count: number
  error_count: number
}

export interface StructuredLogData {
  timestamp?: string
  level?: string
  message: string
  service: string
  metadata?: Record<string, any>
}

export interface BulkIngestData {
  logs: StructuredLogData[]
  metadata?: {
    source?: string
    version?: string
  }
}

// Ingestion API client
export class IngestionApi {
  /**
   * Ingest Single Log Entry
   * POST /v1/ingest/logs
   */
  static async ingestSingleLog(log: LogEntry): Promise<ApiResponse<IngestResponse>> {
    return apiClient.post('/v1/ingest/logs', log)
  }

  /**
   * Ingest Structured Data (JSON)
   * POST /v1/ingest/structured
   */
  static async ingestStructuredData(
    data: StructuredLogData | StructuredLogData[]
  ): Promise<ApiResponse<IngestResponse>> {
    return apiClient.post('/v1/ingest/structured', data)
  }

  /**
   * Auto-Detect Format and Ingest
   * POST /v1/ingest
   */
  static async ingestAutoDetect(
    content: string | Record<string, any>,
    contentType: 'application/json' | 'text/plain' = 'application/json'
  ): Promise<ApiResponse<IngestResponse>> {
    if (contentType === 'application/json') {
      return apiClient.post('/v1/ingest', content, {
        headers: { 'Content-Type': 'application/json' }
      })
    } else {
      return apiClient.post('/v1/ingest', content, {
        headers: { 'Content-Type': 'text/plain' }
      })
    }
  }

  /**
   * Batch Log Ingestion
   * POST /v1/ingest/logs/batch
   */
  static async ingestBatchLogs(batchData: BatchLogEntry): Promise<ApiResponse<BatchIngestResponse>> {
    return apiClient.post('/v1/ingest/logs/batch', batchData)
  }

  /**
   * Bulk Data Ingestion
   * POST /v1/ingest/logs/bulk
   */
  static async ingestBulkData(bulkData: BulkIngestData): Promise<ApiResponse<BatchIngestResponse>> {
    return apiClient.post('/v1/ingest/logs/bulk', bulkData)
  }

  /**
   * OpenTelemetry Protocol (OTLP) Ingestion
   * POST /v1/ingest/otlp
   */
  static async ingestOTLP(otlpData: OTLPLogsData): Promise<ApiResponse<BatchIngestResponse>> {
    return apiClient.post('/v1/ingest/otlp', otlpData)
  }

  /**
   * Syslog Format Ingestion
   * POST /v1/ingest/syslog
   */
  static async ingestSyslog(syslogMessage: string): Promise<ApiResponse<IngestResponse>> {
    return apiClient.post('/v1/ingest/syslog', syslogMessage, {
      headers: { 'Content-Type': 'text/plain' }
    })
  }

  /**
   * Common Event Format (CEF) Ingestion
   * POST /v1/ingest/cef
   */
  static async ingestCEF(cefMessage: string): Promise<ApiResponse<IngestResponse>> {
    return apiClient.post('/v1/ingest/cef', cefMessage, {
      headers: { 'Content-Type': 'text/plain' }
    })
  }

  /**
   * Nginx Access Log Ingestion
   * POST /v1/ingest/nginx
   */
  static async ingestNginx(nginxLog: string): Promise<ApiResponse<IngestResponse>> {
    return apiClient.post('/v1/ingest/nginx', nginxLog, {
      headers: { 'Content-Type': 'text/plain' }
    })
  }

  /**
   * Plain Text Log Ingestion
   * POST /v1/ingest/text
   */
  static async ingestText(textLog: string): Promise<ApiResponse<IngestResponse>> {
    return apiClient.post('/v1/ingest/text', textLog, {
      headers: { 'Content-Type': 'text/plain' }
    })
  }

  // High-level convenience methods
  /**
   * Ingest Application Logs (convenience method)
   */
  static async ingestApplicationLogs(
    appName: string,
    logs: Array<{
      level?: string
      message: string
      timestamp?: string
      metadata?: Record<string, any>
    }>
  ): Promise<ApiResponse<BatchIngestResponse>> {
    const structuredLogs: LogEntry[] = logs.map(log => ({
      service: appName,
      level: log.level || 'info',
      msg: log.message,
      ts: log.timestamp || new Date().toISOString(),
      attrs: log.metadata || {}
    }))

    return this.ingestBatchLogs({ logs: structuredLogs })
  }

  /**
   * Ingest Error Log (convenience method)
   */
  static async ingestErrorLog(
    service: string,
    error: Error | string,
    context: Record<string, any> = {}
  ): Promise<ApiResponse<IngestResponse>> {
    const errorMessage = error instanceof Error ? error.message : String(error)
    const errorLog: LogEntry = {
      service,
      level: 'error',
      msg: errorMessage,
      ts: new Date().toISOString(),
      attrs: {
        error_type: error instanceof Error ? error.name : 'Error',
        stack_trace: error instanceof Error ? error.stack : undefined,
        ...context
      }
    }

    return this.ingestSingleLog(errorLog)
  }

  /**
   * Ingest Performance Metrics (convenience method)
   */
  static async ingestPerformanceLog(
    service: string,
    operation: string,
    metrics: {
      duration_ms: number
      success: boolean
      metadata?: Record<string, any>
    }
  ): Promise<ApiResponse<IngestResponse>> {
    const performanceLog: LogEntry = {
      service,
      level: metrics.success ? 'info' : 'warn',
      msg: `${operation} completed in ${metrics.duration_ms}ms`,
      ts: new Date().toISOString(),
      attrs: {
        operation,
        duration_ms: metrics.duration_ms,
        success: metrics.success,
        ...metrics.metadata
      }
    }

    return this.ingestSingleLog(performanceLog)
  }

  /**
   * Test Ingestion Connectivity
   */
  static async testIngestion(): Promise<ApiResponse<IngestResponse>> {
    const testLog: LogEntry = {
      service: 'logforge-ui',
      level: 'info',
      msg: 'Ingestion connectivity test',
      ts: new Date().toISOString(),
      attrs: {
        test: true,
        client: 'logforge-ui-client'
      }
    }

    return this.ingestSingleLog(testLog)
  }
}

export default IngestionApi