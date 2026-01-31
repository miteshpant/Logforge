'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Search,
  Send,
  Clock,
  ThumbsUp,
  ThumbsDown,
  Brain,
  MessageSquare,
  Lightbulb,
  AlertTriangle,
  ChevronRight,
  RefreshCw,
  FileText,
  Code,
  Target,
  Sparkles,
  Plus,
  History,
  ArrowRight,
  CheckCircle,
  XCircle,
  Loader2
} from 'lucide-react'

interface QueryHistoryItem {
  id: string
  question: string
  answer?: string
  created_at: string
  confidence_score?: number
  status?: string
}

interface AIQueryResponse {
  answer: string
  generated_sql?: string
  confidence_score?: number
  suggestions?: string[]
  sources?: string[]
  query_id?: string
}

interface InvestigationResult {
  investigation_id?: string
  root_cause?: string
  contributing_factors?: string[]
  timeline?: Array<{
    timestamp: string
    event: string
    severity?: string
  }>
  recommendations?: string[]
  confidence?: number
  status?: string
}

export default function AIInvestigationsPage() {
  const { getApiTimeRange } = useTimeRange()

  // Query state
  const [queryInput, setQueryInput] = useState('')
  const [queryResponse, setQueryResponse] = useState<AIQueryResponse | null>(null)
  const [isQuerying, setIsQuerying] = useState(false)

  // Investigation state
  const [investigationTitle, setInvestigationTitle] = useState('')
  const [investigationDescription, setInvestigationDescription] = useState('')
  const [investigationResult, setInvestigationResult] = useState<InvestigationResult | null>(null)
  const [isInvestigating, setIsInvestigating] = useState(false)

  // History state
  const [history, setHistory] = useState<QueryHistoryItem[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)

  // UI state
  const [activeTab, setActiveTab] = useState<'query' | 'investigate'>('query')
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, 'up' | 'down'>>({})

  const loadHistory = useCallback(async () => {
    try {
      setIsLoadingHistory(true)
      const response = await apiClient.get<{ queries: QueryHistoryItem[]; history: QueryHistoryItem[] }>('/v1/ai/query/history', {
        limit: 20
      })
      const data = response?.data || response
      if (data?.queries) {
        setHistory(data.queries)
      } else if (data?.history) {
        setHistory(data.history)
      } else if (Array.isArray(data)) {
        setHistory(data)
      } else {
        setHistory([])
      }
    } catch (error) {
      console.error('Failed to load query history:', error)
      setHistory([])
    } finally {
      setIsLoadingHistory(false)
    }
  }, [])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const handleQuery = async () => {
    if (!queryInput.trim()) return

    setIsQuerying(true)
    setQueryResponse(null)

    try {
      const { start_time, end_time } = getApiTimeRange()
      const response = await apiClient.post<AIQueryResponse>('/v1/ai/query', {
        question: queryInput,
        context: {
          start_time,
          end_time
        }
      })

      const data = response?.data || response
      if (data) {
        setQueryResponse(data as AIQueryResponse)
        // Refresh history after new query
        loadHistory()
      }
    } catch (error) {
      console.error('Failed to submit query:', error)
      setQueryResponse({
        answer: 'Failed to process query. Please try again.',
        confidence_score: 0
      })
    } finally {
      setIsQuerying(false)
    }
  }

  const handleInvestigate = async () => {
    if (!investigationTitle.trim()) return

    setIsInvestigating(true)
    setInvestigationResult(null)

    try {
      const { start_time, end_time } = getApiTimeRange()
      const response = await apiClient.post<InvestigationResult>('/v1/ai/investigate', {
        title: investigationTitle,
        description: investigationDescription,
        incident_data: {
          start_time,
          end_time
        }
      })

      const data = response?.data || response
      if (data) {
        setInvestigationResult(data as InvestigationResult)
      }
    } catch (error) {
      console.error('Failed to start investigation:', error)
      setInvestigationResult({
        status: 'failed',
        root_cause: 'Investigation could not be completed. Please try again.'
      })
    } finally {
      setIsInvestigating(false)
    }
  }

  const handleFeedback = async (queryId: string, feedback: 'up' | 'down') => {
    try {
      await apiClient.post('/v1/ai/query/feedback', {
        query_id: queryId,
        feedback: feedback === 'up' ? 'positive' : 'negative'
      })
      setFeedbackGiven(prev => ({ ...prev, [queryId]: feedback }))
    } catch (error) {
      console.error('Failed to submit feedback:', error)
    }
  }

  const handleHistoryClick = (item: QueryHistoryItem) => {
    setQueryInput(item.question)
    setActiveTab('query')
    if (item.answer) {
      setQueryResponse({
        answer: item.answer,
        confidence_score: item.confidence_score
      })
    }
  }

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600 bg-green-50 border-green-200'
    if (score >= 0.5) return 'text-yellow-600 bg-yellow-50 border-yellow-200'
    return 'text-red-600 bg-red-50 border-red-200'
  }

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString()
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <Brain className="w-7 h-7 text-purple-500" />
              AI Investigation Assistant
            </h1>
            <p className="text-slate-600 mt-1">
              Ask questions about your infrastructure, investigate incidents, and get AI-powered insights
            </p>
          </div>
          <button
            onClick={loadHistory}
            disabled={isLoadingHistory}
            className="flex items-center gap-2 px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoadingHistory ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Main Two-Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Panel - History */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 lg:col-span-1">
            <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <History className="w-5 h-5 text-slate-500" />
              Recent Queries
            </h2>

            {isLoadingHistory ? (
              <div className="space-y-3">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : history.length === 0 ? (
              <div className="text-center py-12">
                <MessageSquare className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 text-sm">No query history yet</p>
                <p className="text-slate-400 text-xs mt-1">Ask a question to get started</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {history.map(item => (
                  <button
                    key={item.id}
                    onClick={() => handleHistoryClick(item)}
                    className="w-full text-left p-3 bg-slate-50 hover:bg-slate-100 rounded-lg transition-colors group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-slate-800 font-medium line-clamp-2">
                        {item.question}
                      </p>
                      <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-slate-600 flex-shrink-0 mt-0.5" />
                    </div>
                    <div className="flex items-center gap-2 mt-1.5">
                      <Clock className="w-3 h-3 text-slate-400" />
                      <span className="text-xs text-slate-400">
                        {formatTimestamp(item.created_at)}
                      </span>
                      {item.confidence_score != null && (
                        <span className={`text-xs px-1.5 py-0.5 rounded border ${getConfidenceColor(item.confidence_score)}`}>
                          {Math.round(item.confidence_score * 100)}%
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Right Panel - Query/Investigation */}
          <div className="lg:col-span-2 space-y-6">
            {/* Tab Switcher */}
            <div className="flex gap-2">
              <button
                onClick={() => setActiveTab('query')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'query'
                    ? 'bg-purple-600 text-white'
                    : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
                }`}
              >
                <Search className="w-4 h-4" />
                Ask a Question
              </button>
              <button
                onClick={() => setActiveTab('investigate')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'investigate'
                    ? 'bg-purple-600 text-white'
                    : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
                }`}
              >
                <Target className="w-4 h-4" />
                Start Investigation
              </button>
            </div>

            {/* Query Tab */}
            {activeTab === 'query' && (
              <div className="space-y-6">
                {/* Query Input */}
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    What would you like to know?
                  </label>
                  <div className="flex gap-3">
                    <div className="flex-1 relative">
                      <Search className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                      <textarea
                        value={queryInput}
                        onChange={(e) => setQueryInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault()
                            handleQuery()
                          }
                        }}
                        placeholder="e.g., Why is auth-service erroring? What caused the spike in latency at 3pm?"
                        rows={3}
                        className="w-full pl-10 pr-4 py-2.5 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 resize-none"
                      />
                    </div>
                    <button
                      onClick={handleQuery}
                      disabled={isQuerying || !queryInput.trim()}
                      className="self-end px-5 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                      {isQuerying ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Send className="w-4 h-4" />
                      )}
                      Ask
                    </button>
                  </div>
                  {/* Quick suggestions */}
                  <div className="flex flex-wrap gap-2 mt-3">
                    {[
                      'What services have the highest error rate?',
                      'Explain recent spike in errors',
                      'Which endpoints are slowest?'
                    ].map(suggestion => (
                      <button
                        key={suggestion}
                        onClick={() => setQueryInput(suggestion)}
                        className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-full transition-colors"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Loading State */}
                {isQuerying && (
                  <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
                    <Loader2 className="w-8 h-8 text-purple-500 animate-spin mx-auto mb-3" />
                    <p className="text-slate-600">Analyzing your infrastructure data...</p>
                    <p className="text-slate-400 text-sm mt-1">This may take a few seconds</p>
                  </div>
                )}

                {/* Query Response */}
                {queryResponse && !isQuerying && (
                  <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-center gap-2">
                        <Sparkles className="w-5 h-5 text-purple-500" />
                        <h3 className="text-lg font-semibold text-slate-900">AI Response</h3>
                      </div>
                      {queryResponse.confidence_score != null && (
                        <span className={`text-sm px-2.5 py-1 rounded-lg border font-medium ${getConfidenceColor(queryResponse.confidence_score)}`}>
                          {Math.round(queryResponse.confidence_score * 100)}% confidence
                        </span>
                      )}
                    </div>

                    {/* Answer Text */}
                    <div className="bg-slate-50 rounded-lg p-4">
                      <p className="text-slate-800 whitespace-pre-wrap leading-relaxed">
                        {queryResponse.answer}
                      </p>
                    </div>

                    {/* Generated SQL */}
                    {queryResponse.generated_sql && (
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <Code className="w-4 h-4 text-slate-500" />
                          <h4 className="text-sm font-medium text-slate-700">Generated Query</h4>
                        </div>
                        <pre className="bg-slate-900 text-green-400 p-4 rounded-lg text-sm overflow-x-auto">
                          {queryResponse.generated_sql}
                        </pre>
                      </div>
                    )}

                    {/* Follow-up Suggestions */}
                    {queryResponse.suggestions && queryResponse.suggestions.length > 0 && (
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <Lightbulb className="w-4 h-4 text-amber-500" />
                          <h4 className="text-sm font-medium text-slate-700">Follow-up Questions</h4>
                        </div>
                        <div className="space-y-2">
                          {queryResponse.suggestions.map((suggestion, idx) => (
                            <button
                              key={idx}
                              onClick={() => setQueryInput(suggestion)}
                              className="w-full text-left p-3 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg text-sm text-amber-800 transition-colors flex items-center gap-2"
                            >
                              <ArrowRight className="w-4 h-4 flex-shrink-0" />
                              {suggestion}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Sources */}
                    {queryResponse.sources && queryResponse.sources.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium text-slate-700 mb-2">Data Sources</h4>
                        <div className="flex flex-wrap gap-2">
                          {queryResponse.sources.map((source, idx) => (
                            <span key={idx} className="text-xs px-2.5 py-1 bg-slate-100 text-slate-600 rounded-full">
                              {source}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Feedback */}
                    {queryResponse.query_id && (
                      <div className="flex items-center gap-3 pt-3 border-t border-slate-200">
                        <span className="text-sm text-slate-500">Was this helpful?</span>
                        <button
                          onClick={() => handleFeedback(queryResponse.query_id!, 'up')}
                          disabled={!!feedbackGiven[queryResponse.query_id!]}
                          className={`p-2 rounded-lg transition-colors ${
                            feedbackGiven[queryResponse.query_id!] === 'up'
                              ? 'bg-green-100 text-green-600'
                              : 'hover:bg-slate-100 text-slate-400 hover:text-slate-600'
                          }`}
                        >
                          <ThumbsUp className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleFeedback(queryResponse.query_id!, 'down')}
                          disabled={!!feedbackGiven[queryResponse.query_id!]}
                          className={`p-2 rounded-lg transition-colors ${
                            feedbackGiven[queryResponse.query_id!] === 'down'
                              ? 'bg-red-100 text-red-600'
                              : 'hover:bg-slate-100 text-slate-400 hover:text-slate-600'
                          }`}
                        >
                          <ThumbsDown className="w-4 h-4" />
                        </button>
                        {feedbackGiven[queryResponse.query_id!] && (
                          <span className="text-xs text-slate-400">Thanks for your feedback!</span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Investigation Tab */}
            {activeTab === 'investigate' && (
              <div className="space-y-6">
                {/* Investigation Form */}
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                    <Target className="w-5 h-5 text-purple-500" />
                    New Investigation
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        Investigation Title
                      </label>
                      <input
                        type="text"
                        value={investigationTitle}
                        onChange={(e) => setInvestigationTitle(e.target.value)}
                        placeholder="e.g., Auth service degradation at 3pm"
                        className="w-full px-4 py-2.5 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        Description (optional)
                      </label>
                      <textarea
                        value={investigationDescription}
                        onChange={(e) => setInvestigationDescription(e.target.value)}
                        placeholder="Describe what you observed, affected services, user reports..."
                        rows={4}
                        className="w-full px-4 py-2.5 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 resize-none"
                      />
                    </div>
                    <button
                      onClick={handleInvestigate}
                      disabled={isInvestigating || !investigationTitle.trim()}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isInvestigating ? (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin" />
                          Investigating...
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-5 h-5" />
                          Start Investigation
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Investigation Loading */}
                {isInvestigating && (
                  <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
                    <Loader2 className="w-8 h-8 text-purple-500 animate-spin mx-auto mb-3" />
                    <p className="text-slate-600">Running AI investigation...</p>
                    <p className="text-slate-400 text-sm mt-1">Analyzing logs, traces, and metrics for root cause</p>
                  </div>
                )}

                {/* Investigation Results */}
                {investigationResult && !isInvestigating && (
                  <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-5">
                    <div className="flex items-center gap-2">
                      <FileText className="w-5 h-5 text-purple-500" />
                      <h3 className="text-lg font-semibold text-slate-900">Investigation Results</h3>
                      {investigationResult.confidence != null && (
                        <span className={`ml-auto text-sm px-2.5 py-1 rounded-lg border font-medium ${getConfidenceColor(investigationResult.confidence)}`}>
                          {Math.round(investigationResult.confidence * 100)}% confidence
                        </span>
                      )}
                    </div>

                    {/* Root Cause */}
                    {investigationResult.root_cause && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <AlertTriangle className="w-4 h-4 text-red-600" />
                          <h4 className="text-sm font-semibold text-red-800">Root Cause</h4>
                        </div>
                        <p className="text-red-700 text-sm leading-relaxed">
                          {investigationResult.root_cause}
                        </p>
                      </div>
                    )}

                    {/* Contributing Factors */}
                    {investigationResult.contributing_factors && investigationResult.contributing_factors.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-slate-700 mb-2">Contributing Factors</h4>
                        <div className="space-y-2">
                          {investigationResult.contributing_factors.map((factor, idx) => (
                            <div key={idx} className="flex items-start gap-2 p-3 bg-orange-50 border border-orange-200 rounded-lg">
                              <span className="text-orange-500 font-bold text-sm mt-0.5">{idx + 1}.</span>
                              <p className="text-sm text-orange-800">{factor}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Timeline */}
                    {investigationResult.timeline && investigationResult.timeline.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-slate-700 mb-2">Event Timeline</h4>
                        <div className="space-y-2">
                          {investigationResult.timeline.map((event, idx) => (
                            <div key={idx} className="flex items-start gap-3 p-3 bg-slate-50 border border-slate-200 rounded-lg">
                              <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                                event.severity === 'critical' ? 'bg-red-500' :
                                event.severity === 'high' ? 'bg-orange-500' :
                                event.severity === 'medium' ? 'bg-yellow-500' :
                                'bg-blue-500'
                              }`} />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm text-slate-800">{event.event}</p>
                                <p className="text-xs text-slate-500 mt-0.5">
                                  {formatTimestamp(event.timestamp)}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommendations */}
                    {investigationResult.recommendations && investigationResult.recommendations.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-slate-700 mb-2">Recommendations</h4>
                        <div className="space-y-2">
                          {investigationResult.recommendations.map((rec, idx) => (
                            <div key={idx} className="flex items-start gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                              <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                              <p className="text-sm text-green-800">{rec}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
