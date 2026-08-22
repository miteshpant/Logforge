'use client'

import { X, BookOpen } from 'lucide-react'
import { LOGQL_EXAMPLES, LOGQL_FIELDS, LOGQL_OPERATORS } from './logqlSyntax'

interface SyntaxHelpProps {
  onClose: () => void
  onUseExample: (query: string) => void
}

/**
 * In-product LogforgeQL syntax reference (LF-023 spec item 6).
 */
export default function SyntaxHelp({ onClose, onUseExample }: SyntaxHelpProps) {
  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md bg-gradient-to-br from-slate-800/95 to-slate-900/95 backdrop-blur-xl shadow-xl border-l border-white/5 z-50 overflow-y-auto">
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <BookOpen className="w-5 h-5 text-blue-400" />
            LogforgeQL Reference
          </h3>
          <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-lg" aria-label="Close syntax help">
            <X className="w-5 h-5 text-slate-300" />
          </button>
        </div>

        <p className="text-sm text-slate-300 mb-4">
          A pipe-oriented query language. Start with optional free-text search
          terms, then chain stages with <code className="text-blue-300">|</code>.
          Run with <kbd className="px-1.5 py-0.5 bg-slate-700 rounded text-xs">Cmd/Ctrl + Enter</kbd>.
        </p>

        <div className="mb-5">
          <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Stages</h4>
          <div className="space-y-1.5 text-sm font-mono">
            <p><span className="text-blue-300">where</span> <span className="text-slate-300">field op value [and ...]</span></p>
            <p><span className="text-blue-300">stats</span> <span className="text-slate-300">count() [by field, ...]</span></p>
            <p><span className="text-blue-300">sort</span> <span className="text-slate-300">field [asc|desc]</span></p>
            <p><span className="text-blue-300">limit</span> <span className="text-slate-300">n</span></p>
            <p><span className="text-blue-300">last</span> <span className="text-slate-300">15m | 24h | 7d</span></p>
          </div>
        </div>

        <div className="mb-5">
          <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Operators</h4>
          <div className="flex flex-wrap gap-1.5">
            {LOGQL_OPERATORS.map(op => (
              <code key={op} className="px-1.5 py-0.5 bg-slate-800/60 border border-white/10 rounded text-xs text-purple-300">
                {op}
              </code>
            ))}
          </div>
        </div>

        <div className="mb-5">
          <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Fields</h4>
          <div className="flex flex-wrap gap-1.5">
            {LOGQL_FIELDS.map(f => (
              <code key={f} className="px-1.5 py-0.5 bg-slate-800/60 border border-white/10 rounded text-xs text-green-300">
                {f}
              </code>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-2">
            JSON keys inside <code className="text-green-300">attrs</code> are addressable as{' '}
            <code className="text-green-300">attrs.key</code>.
          </p>
        </div>

        <div>
          <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Examples</h4>
          <div className="space-y-2">
            {LOGQL_EXAMPLES.map(example => (
              <button
                key={example.query}
                onClick={() => onUseExample(example.query)}
                className="w-full text-left p-3 bg-slate-800/50 hover:bg-slate-800/80 border border-white/5 rounded-lg group"
              >
                <code className="block text-xs text-blue-300 font-mono break-all group-hover:text-blue-200">
                  {example.query}
                </code>
                <p className="text-xs text-slate-400 mt-1">{example.description}</p>
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-500 mt-3">Click an example to load it into the query bar.</p>
        </div>
      </div>
    </div>
  )
}
