'use client'

import { Activity, Clock } from 'lucide-react'
import type { Transaction } from '@/app/observability/apm/page'

// Format latency values for display
const formatLatency = (ms: number): string => {
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

interface APMTransactionsProps {
  transactions: Transaction[]
  isLoading: boolean
}

export default function APMTransactions({ transactions, isLoading }: APMTransactionsProps) {
  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Top Transactions</h2>
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-slate-700/50 rounded"></div>
          ))}
        </div>
      </div>
    )
  }

  if (transactions.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[300px] flex items-center justify-center">
        <div className="text-center text-slate-400">
          <Activity className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No transaction data available</p>
        </div>
      </div>
    )
  }

  const maxCount = Math.max(...transactions.map(t => t.count))

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Header */}
      <div className="p-6 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-white">Top Transactions</h2>
        <p className="text-sm text-slate-400 mt-1">Most frequent operations by volume</p>
      </div>

      {/* Transaction List */}
      <div className="p-6 space-y-4">
        {transactions.slice(0, 10).map((transaction, idx) => {
          const widthPercentage = (transaction.count / maxCount) * 100

          return (
            <div key={`${transaction.service}-${transaction.name}`} className="space-y-2">
              {/* Transaction Info */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <span className="text-slate-500 text-sm font-mono w-6">
                    #{idx + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-white truncate">
                      {transaction.name}
                    </div>
                    <div className="text-xs text-slate-400">
                      {transaction.service}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4 flex-shrink-0">
                  {/* Count */}
                  <div className="text-right">
                    <div className="flex items-center gap-1 text-sm text-white">
                      <Activity className="w-4 h-4 text-blue-400" />
                      {transaction.count.toLocaleString()}
                    </div>
                    <div className="text-xs text-slate-500">
                      {transaction.percentage.toFixed(1)}%
                    </div>
                  </div>

                  {/* Avg Duration */}
                  <div className="text-right w-20">
                    <div className="flex items-center gap-1 text-sm text-slate-300">
                      <Clock className="w-4 h-4 text-purple-400" />
                      <span className="font-mono">{formatLatency(transaction.avg_duration_ms)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-slate-700/30 rounded-full h-2 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500"
                  style={{ width: `${widthPercentage}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Footer Stats */}
      <div className="p-6 border-t border-slate-700 bg-slate-900/30">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-white">
              {transactions.reduce((sum, t) => sum + t.count, 0).toLocaleString()}
            </div>
            <div className="text-xs text-slate-400 mt-1">Total Transactions</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {formatLatency(transactions.reduce((sum, t) => sum + t.avg_duration_ms, 0) / transactions.length)}
            </div>
            <div className="text-xs text-slate-400 mt-1">Avg Duration</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {transactions.length}
            </div>
            <div className="text-xs text-slate-400 mt-1">Unique Operations</div>
          </div>
        </div>
      </div>
    </div>
  )
}
