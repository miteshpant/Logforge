'use client'

import React, { useState, useRef, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { 
  Brain, 
  Send, 
  Mic, 
  MicOff,
  Loader2, 
  User, 
  Bot,
  Lightbulb,
  Search,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Sparkles,
  Zap,
  Target,
  Eye,
  BarChart3,
  Clock,
  Minimize2,
  Maximize2,
  X
} from 'lucide-react'

interface ChatMessage {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: Date
  isTyping?: boolean
  suggestions?: string[]
  insights?: {
    type: 'metric' | 'alert' | 'prediction' | 'recommendation'
    title: string
    value: string
    confidence?: number
  }[]
}

interface AiChatAssistantProps {
  className?: string
  isMinimized?: boolean
  onToggleMinimize?: () => void
  onClose?: () => void
}

export const AiChatAssistant: React.FC<AiChatAssistantProps> = ({
  className = '',
  isMinimized = false,
  onToggleMinimize,
  onClose
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'assistant',
      content: "Hello! I'm your AI assistant powered by advanced machine learning. I can help you analyze logs, detect anomalies, predict issues, and provide intelligent insights about your infrastructure. What would you like to explore?",
      timestamp: new Date(),
      suggestions: [
        "Show me recent error patterns",
        "Analyze performance trends",
        "Detect security anomalies",
        "Predict potential issues"
      ]
    }
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    // Simulate AI response with realistic delay
    setTimeout(() => {
      const aiResponse = generateAiResponse(inputValue)
      setMessages(prev => [...prev, aiResponse])
      setIsLoading(false)
    }, 1500 + Math.random() * 1000)
  }

  const generateAiResponse = (query: string): ChatMessage => {
    const lowerQuery = query.toLowerCase()
    
    // Analyze query intent and generate appropriate response
    let response = ''
    let insights: ChatMessage['insights'] = []
    let suggestions: string[] = []

    if (lowerQuery.includes('error') || lowerQuery.includes('issue') || lowerQuery.includes('problem')) {
      response = "I've analyzed your error patterns over the last 24 hours. I found 3 significant anomalies that require attention. The payment gateway is experiencing a 15% increase in timeout errors, which correlates with increased load from the marketing campaign launched yesterday."
      insights = [
        {
          type: 'alert',
          title: 'Error Rate Spike',
          value: '+15%',
          confidence: 94
        },
        {
          type: 'recommendation',
          title: 'Scale Payment Service',
          value: '2x instances',
          confidence: 87
        }
      ]
      suggestions = [
        "Show me the payment gateway logs",
        "What's causing the timeout errors?",
        "How can I prevent this in future?"
      ]
    } else if (lowerQuery.includes('performance') || lowerQuery.includes('slow') || lowerQuery.includes('latency')) {
      response = "Performance analysis complete! Your API response times have increased by 23% in the last 6 hours. I've identified the root cause: database query optimization needed for the user profile endpoint. I recommend implementing query caching and adding database indexes."
      insights = [
        {
          type: 'metric',
          title: 'Avg Response Time',
          value: '245ms',
          confidence: 96
        },
        {
          type: 'prediction',
          title: 'Performance Impact',
          value: '40% degradation expected',
          confidence: 82
        }
      ]
      suggestions = [
        "Show me database query analytics",
        "What indexes should I add?",
        "Monitor response time trends"
      ]
    } else if (lowerQuery.includes('security') || lowerQuery.includes('threat') || lowerQuery.includes('attack')) {
      response = "Security analysis reveals potential threat activity. I detected 47 failed login attempts from 3 suspicious IP addresses in the last hour. This matches the pattern of a credential stuffing attack. I've automatically flagged these IPs and recommend implementing rate limiting."
      insights = [
        {
          type: 'alert',
          title: 'Suspicious Activity',
          value: '47 failed logins',
          confidence: 98
        },
        {
          type: 'recommendation',
          title: 'Implement Rate Limiting',
          value: '5 attempts/minute',
          confidence: 92
        }
      ]
      suggestions = [
        "Block suspicious IPs",
        "Show me login attempt patterns",
        "Enable advanced threat detection"
      ]
    } else if (lowerQuery.includes('predict') || lowerQuery.includes('forecast') || lowerQuery.includes('future')) {
      response = "Based on historical patterns and current trends, I predict a 70% chance of increased traffic in the next 4 hours. Your infrastructure should handle this load, but I recommend pre-scaling the API gateway to maintain optimal performance."
      insights = [
        {
          type: 'prediction',
          title: 'Traffic Spike Prediction',
          value: 'In 4 hours',
          confidence: 70
        },
        {
          type: 'recommendation',
          title: 'Pre-scale Infrastructure',
          value: 'API Gateway +50%',
          confidence: 85
        }
      ]
      suggestions = [
        "Set up auto-scaling rules",
        "Monitor traffic patterns",
        "Create scaling alerts"
      ]
    } else if (lowerQuery.includes('cost') || lowerQuery.includes('optimize') || lowerQuery.includes('save')) {
      response = "Cost optimization analysis complete! I identified $2,847/month in potential savings. You have 12 over-provisioned instances and 5 unused load balancers. I can help you implement these optimizations safely without affecting performance."
      insights = [
        {
          type: 'metric',
          title: 'Potential Savings',
          value: '$2,847/month',
          confidence: 91
        },
        {
          type: 'recommendation',
          title: 'Right-size Instances',
          value: '12 instances',
          confidence: 88
        }
      ]
      suggestions = [
        "Show me cost breakdown",
        "Which instances to downsize?",
        "Implement cost alerts"
      ]
    } else {
      response = "I understand you're looking for insights about your infrastructure. I can analyze logs, detect anomalies, predict issues, optimize performance, and provide security recommendations. What specific area would you like me to focus on?"
      suggestions = [
        "Analyze error patterns",
        "Check performance metrics", 
        "Security threat analysis",
        "Cost optimization review"
      ]
    }

    return {
      id: Date.now().toString(),
      type: 'assistant',
      content: response,
      timestamp: new Date(),
      insights,
      suggestions
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    setInputValue(suggestion)
    inputRef.current?.focus()
  }

  const toggleVoiceInput = () => {
    setIsListening(!isListening)
    // Voice recognition would be implemented here
    if (!isListening) {
      setTimeout(() => setIsListening(false), 3000) // Auto-stop after 3 seconds for demo
    }
  }

  const getInsightIcon = (type: string) => {
    switch (type) {
      case 'metric': return <BarChart3 className="w-4 h-4" />
      case 'alert': return <AlertTriangle className="w-4 h-4" />
      case 'prediction': return <Target className="w-4 h-4" />
      case 'recommendation': return <Lightbulb className="w-4 h-4" />
      default: return <Eye className="w-4 h-4" />
    }
  }

  const getInsightColor = (type: string) => {
    switch (type) {
      case 'metric': return 'bg-blue-500/10 text-blue-400 border-blue-500/30'
      case 'alert': return 'bg-red-500/10 text-red-400 border-red-500/30'
      case 'prediction': return 'bg-purple-500/10 text-purple-400 border-purple-500/30'
      case 'recommendation': return 'bg-green-500/10 text-green-400 border-green-500/30'
      default: return 'bg-slate-500/10 text-slate-400 border-slate-500/30'
    }
  }

  if (isMinimized) {
    return (
      <div className={`fixed bottom-4 right-4 z-50 ${className}`}>
        <Button 
          onClick={onToggleMinimize}
          className="w-14 h-14 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 shadow-lg"
          data-testid="ai-chat-minimized"
        >
          <Brain className="w-6 h-6 text-white" />
          <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-400 rounded-full animate-pulse"></div>
        </Button>
      </div>
    )
  }

  return (
    <Card className={`${className} w-96 h-[600px] bg-gradient-to-br from-white to-slate-50 border-0 shadow-2xl`} data-testid="ai-chat-assistant">
      <CardHeader className="pb-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-t-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="relative">
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                <Brain className="w-5 h-5" />
              </div>
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
            </div>
            <div>
              <CardTitle className="text-lg">AI Assistant</CardTitle>
              <p className="text-sm opacity-90">Powered by Advanced ML</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleMinimize}
              className="text-white hover:bg-white/20 w-8 h-8 p-0"
              data-testid="minimize-chat"
            >
              <Minimize2 className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="text-white hover:bg-white/20 w-8 h-8 p-0"
              data-testid="close-chat"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="flex flex-col h-[520px] p-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4" data-testid="chat-messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`flex items-start space-x-2 max-w-[85%] ${message.type === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  message.type === 'user' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gradient-to-r from-purple-600 to-blue-600 text-white'
                }`}>
                  {message.type === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>
                
                <div className={`rounded-lg p-3 ${
                  message.type === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-900'
                }`}>
                  <p className="text-sm leading-relaxed">{message.content}</p>
                  
                  {/* AI Insights */}
                  {message.insights && message.insights.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center space-x-1 text-xs font-medium text-slate-600">
                        <Sparkles className="w-3 h-3" />
                        <span>AI Insights</span>
                      </div>
                      {message.insights.map((insight, index) => (
                        <div key={index} className={`flex items-center justify-between p-2 rounded border ${getInsightColor(insight.type)}`}>
                          <div className="flex items-center space-x-2">
                            {getInsightIcon(insight.type)}
                            <span className="text-xs font-medium">{insight.title}</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <span className="text-xs font-bold">{insight.value}</span>
                            {insight.confidence && (
                              <Badge variant="secondary" className="text-xs">
                                {insight.confidence}%
                              </Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* Suggestions */}
                  {message.suggestions && message.suggestions.length > 0 && (
                    <div className="mt-3">
                      <div className="text-xs font-medium text-slate-600 mb-2">Suggested follow-ups:</div>
                      <div className="space-y-1">
                        {message.suggestions.map((suggestion, index) => (
                          <button
                            key={index}
                            onClick={() => handleSuggestionClick(suggestion)}
                            className="block w-full text-left text-xs p-2 bg-white/60 hover:bg-white/80 rounded border text-slate-700 transition-colors"
                            data-testid={`suggestion-${index}`}
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  <div className={`text-xs mt-2 ${message.type === 'user' ? 'text-blue-200' : 'text-slate-500'}`}>
                    {message.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            </div>
          ))}
          
          {/* Typing Indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="flex items-start space-x-2">
                <div className="w-8 h-8 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 text-white flex items-center justify-center">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="bg-slate-100 rounded-lg p-3">
                  <div className="flex items-center space-x-1">
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
        
        {/* Input */}
        <div className="border-t border-white/10 p-4 bg-slate-800">
          <div className="flex items-center space-x-2">
            <div className="flex-1 relative">
              <Input
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="Ask me anything about your logs, metrics, or infrastructure..."
                className="pr-12"
                disabled={isLoading}
                data-testid="chat-input"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleVoiceInput}
                className={`absolute right-1 top-1/2 transform -translate-y-1/2 w-8 h-8 p-0 ${
                  isListening ? 'text-red-500' : 'text-slate-400'
                }`}
                data-testid="voice-input"
              >
                {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </Button>
            </div>
            <Button
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || isLoading}
              className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
              data-testid="send-message"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default AiChatAssistant