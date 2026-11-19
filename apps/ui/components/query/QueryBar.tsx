'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertCircle, HelpCircle, Loader2, Play, Terminal } from 'lucide-react'
import { getSuggestions, Suggestion } from './logqlSyntax'
import SyntaxHelp from './SyntaxHelp'

interface QueryBarProps {
  value: string
  onChange: (value: string) => void
  onRun: () => void
  isRunning: boolean
  /** Verbatim parser message from the API's 400, rendered inline (LF-023). */
  syntaxError: string | null
  /** Live service names for value autocomplete (fetched, never hardcoded). */
  services: string[]
  /** The tenant's field names from the field catalogue (Phase 5). */
  fields?: string[]
}

const KIND_STYLES: Record<Suggestion['kind'], string> = {
  stage: 'text-blue-300',
  field: 'text-green-300',
  operator: 'text-purple-300',
  aggregation: 'text-yellow-300',
  service: 'text-cyan-300',
  duration: 'text-orange-300',
}

/**
 * LogforgeQL query bar (LF-023): text input + run button, Cmd/Ctrl+Enter,
 * context-aware autocomplete and an inline syntax-reference drawer.
 */
export default function QueryBar({
  value,
  onChange,
  onRun,
  isRunning,
  syntaxError,
  services,
  fields = [],
}: QueryBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [replaceStart, setReplaceStart] = useState(0)
  const [highlightIndex, setHighlightIndex] = useState(0)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [showHelp, setShowHelp] = useState(false)

  const refreshSuggestions = useCallback(
    (text: string, caret: number) => {
      const result = getSuggestions(text, caret, services, fields)
      setSuggestions(result.suggestions)
      setReplaceStart(result.replaceStart)
      setHighlightIndex(0)
      setShowSuggestions(result.suggestions.length > 0)
    },
    [services, fields]
  )

  const acceptSuggestion = useCallback(
    (suggestion: Suggestion) => {
      const input = inputRef.current
      const caret = input?.selectionStart ?? value.length
      const next = value.slice(0, replaceStart) + suggestion.insert + value.slice(caret)
      onChange(next)
      setShowSuggestions(false)
      // Restore focus and place the caret after the inserted token.
      requestAnimationFrame(() => {
        if (input) {
          const pos = replaceStart + suggestion.insert.length
          input.focus()
          input.setSelectionRange(pos, pos)
        }
      })
    },
    [value, replaceStart, onChange]
  )

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      setShowSuggestions(false)
      onRun()
      return
    }

    if (showSuggestions && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setHighlightIndex(i => (i + 1) % suggestions.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setHighlightIndex(i => (i - 1 + suggestions.length) % suggestions.length)
        return
      }
      if (e.key === 'Tab' || e.key === 'Enter') {
        e.preventDefault()
        acceptSuggestion(suggestions[highlightIndex])
        return
      }
      if (e.key === 'Escape') {
        setShowSuggestions(false)
        return
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      onRun()
    }
  }

  // Close the dropdown when clicking elsewhere.
  useEffect(() => {
    const close = () => setShowSuggestions(false)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [])

  return (
    <div className="relative">
      <div className="flex gap-2">
        <div className="flex-1 relative" onClick={e => e.stopPropagation()}>
          <Terminal className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-400" />
          <input
            ref={inputRef}
            type="text"
            spellCheck={false}
            autoComplete="off"
            placeholder='LogforgeQL — e.g. error | where service = "api-service" | limit 100'
            value={value}
            onChange={e => {
              onChange(e.target.value)
              refreshSuggestions(e.target.value, e.target.selectionStart ?? e.target.value.length)
            }}
            onKeyDown={handleKeyDown}
            className={`w-full pl-10 pr-4 py-2 border rounded-lg bg-slate-800/50 text-white font-mono text-sm placeholder-slate-500 focus:outline-none ${
              syntaxError ? 'border-red-500/60 focus:border-red-500' : 'border-white/10 focus:border-blue-500'
            }`}
          />

          {/* Autocomplete dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute top-full mt-1 left-0 min-w-[16rem] bg-gradient-to-br from-slate-800/95 to-slate-900/95 backdrop-blur-xl border border-white/10 rounded-lg shadow-xl z-50 overflow-hidden">
              {suggestions.map((s, i) => (
                <button
                  key={`${s.kind}-${s.value}`}
                  onClick={() => acceptSuggestion(s)}
                  onMouseEnter={() => setHighlightIndex(i)}
                  className={`w-full flex items-center justify-between gap-6 px-3 py-1.5 text-left text-sm font-mono ${
                    i === highlightIndex ? 'bg-white/10' : ''
                  }`}
                >
                  <span className={KIND_STYLES[s.kind]}>{s.value}</span>
                  <span className="text-[10px] uppercase text-slate-500">{s.kind}</span>
                </button>
              ))}
              <div className="px-3 py-1 border-t border-white/5 text-[10px] text-slate-500">
                Tab/Enter to accept - Esc to dismiss
              </div>
            </div>
          )}
        </div>

        <button
          onClick={() => setShowHelp(true)}
          className="flex items-center gap-2 px-3 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5"
          title="LogforgeQL syntax reference"
        >
          <HelpCircle className="w-4 h-4" />
        </button>

        <button
          onClick={onRun}
          disabled={isRunning || !value.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50"
          title="Run (Cmd/Ctrl+Enter)"
        >
          {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Run
        </button>
      </div>

      {/* Inline syntax error — verbatim parser message, input preserved */}
      {syntaxError && (
        <div className="flex items-start gap-2 px-3 py-2 mt-2 rounded-lg text-sm bg-red-500/10 text-red-400 border border-red-500/30">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span className="font-mono text-xs whitespace-pre-wrap">{syntaxError}</span>
        </div>
      )}

      {showHelp && (
        <SyntaxHelp
          onClose={() => setShowHelp(false)}
          onUseExample={query => {
            onChange(query)
            setShowHelp(false)
            requestAnimationFrame(() => inputRef.current?.focus())
          }}
        />
      )}
    </div>
  )
}
