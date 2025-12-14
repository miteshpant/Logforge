'use client'

import { useState, useEffect, useRef } from 'react'
import { apiClient } from '@/lib/api'

type StreamType = 'alerts' | 'security' | 'traces' | 'metrics'

interface StreamEvent {
  id: string
  timestamp: string
  type: string
  data: any
}

export default function LiveStreamingPanel() {
  const [activeStream, setActiveStream] = useState<StreamType>('alerts')
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isExpanded, setIsExpanded] = useState(true) // Default to expanded
  const cleanupRef = useRef<(() => void) | null>(null)
  const eventsEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (isExpanded && eventsEndRef.current) {
      eventsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events, isExpanded])

  // Connect to SSE stream
  useEffect(() => {
    if (!isExpanded) {
      // Disconnect when panel is collapsed
      if (cleanupRef.current) {
        cleanupRef.current()
        cleanupRef.current = null
        setIsConnected(false)
      }
      return
    }

    // Clear events when switching streams
    setEvents([])
    setIsConnected(false)

    // Connect to stream
    connectToStream()

    return () => {
      if (cleanupRef.current) {
        cleanupRef.current()
        cleanupRef.current = null
        setIsConnected(false)
      }
    }
  }, [activeStream, isExpanded])

  const connectToStream = async () => {
    try {
      const url = `/v1/stream/${activeStream}`

      console.log('Connecting to stream:', url)

      console.log('Stream connected successfully')
      setIsConnected(true)

      // Use apiClient.getStream for proper auth handling
      const cleanup = await apiClient.getStream(
        url,
        (data) => {
          // Handle incoming stream data
          console.log('Received stream data:', data)

          const newEvent: StreamEvent = {
            id: data.id || Date.now().toString(),
            timestamp: data.timestamp || new Date().toISOString(),
            type: data.event_type || data.type || 'message',
            data: data
          }

          setEvents(prev => {
            const updated = [newEvent, ...prev]
            return updated.slice(0, 50) // Keep last 50 events
          })
        },
        (error) => {
          // Handle errors
          console.error('Stream error:', error)
          setIsConnected(false)
        }
      )

      // Store cleanup function for later use
      if (cleanupRef.current) {
        // If there's already a cleanup function, call it
        cleanupRef.current()
      }
      cleanupRef.current = cleanup
    } catch (error) {
      console.error('Stream connection error:', error)
      setIsConnected(false)
    }
  }

  const getEventIcon = (type: string) => {
    if (type.includes('alert')) {
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
          <line x1="12" y1="9" x2="12" y2="13"></line>
          <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
      )
    } else if (type.includes('security')) {
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
        </svg>
      )
    } else if (type.includes('trace')) {
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
      )
    } else {
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="12" y1="1" x2="12" y2="23"></line>
          <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
        </svg>
      )
    }
  }

  const getEventColor = (type: string) => {
    if (type.includes('triggered') || type.includes('critical')) return 'text-red-400'
    if (type.includes('security') || type.includes('threat')) return 'text-purple-400'
    if (type.includes('resolved') || type.includes('acknowledged')) return 'text-green-400'
    if (type.includes('trace')) return 'text-blue-400'
    return 'text-cyan-400'
  }

  const tabs = [
    { id: 'alerts' as StreamType, label: 'Alerts', icon: '🚨' },
    { id: 'security' as StreamType, label: 'Security', icon: '🛡️' },
    { id: 'traces' as StreamType, label: 'Traces', icon: '📊' },
    { id: 'metrics' as StreamType, label: 'Metrics', icon: '📈' }
  ]

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className="text-white font-bold text-lg">Live Streaming</span>
          </div>
          <span className="text-xs text-slate-400">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-2">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveStream(tab.id)}
              className={`px-3 py-2 rounded-lg text-sm font-semibold transition-all duration-200 ${
                activeStream === tab.id
                  ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg'
                  : 'bg-slate-800/50 text-slate-400 hover:bg-slate-700/50 hover:text-white'
              }`}
            >
              <span className="mr-1">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Collapse/Expand Button */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          title={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="18 15 12 9 6 15"></polyline>
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          )}
        </button>
      </div>

      {/* Events Stream - Collapsible */}
      {isExpanded && (
        <div className="overflow-y-auto px-6 py-4 h-96">
          {events.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-500">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mb-4 opacity-50">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
              </svg>
              <p className="text-sm">
                {isConnected ? 'Waiting for events...' : 'Connecting to stream...'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {events.map((event, index) => (
                <div
                  key={event.id}
                  className="p-3 rounded-lg bg-slate-800/50 border border-white/5 hover:border-white/10 transition-all duration-200"
                  style={{
                    opacity: 1 - (index * 0.02),
                    animation: index === 0 ? 'slideIn 0.3s ease-out' : 'none'
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className={`mt-0.5 ${getEventColor(event.type)}`}>
                      {getEventIcon(event.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-sm font-semibold ${getEventColor(event.type)}`}>
                          {event.type}
                        </span>
                        <span className="text-xs text-slate-500 font-mono">
                          {new Date(event.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <pre className="text-xs text-slate-300 overflow-x-auto bg-slate-900/50 p-2 rounded max-h-40">
                        {JSON.stringify(event.data, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              ))}
              <div ref={eventsEndRef} />
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  )
}