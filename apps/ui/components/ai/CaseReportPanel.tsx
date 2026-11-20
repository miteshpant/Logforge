'use client'

import { useState } from 'react'
import { Download, FileText, Loader2 } from 'lucide-react'
import { caseReport, type CaseReport } from '@/lib/api/ai'
import { reportFilename } from '@/lib/aiFormat'
import CitedSections from './CitedSections'

/** Case reports (Phase 10): a management summary or a post-incident review, every sentence cited. */
export default function CaseReportPanel({ caseId }: { caseId: string }) {
  const [audience, setAudience] = useState<'management' | 'review'>('management')
  const [report, setReport] = useState<CaseReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setReport(await caseReport(caseId, audience))
    } catch (e: any) {
      setError(e?.message || 'The report failed')
    } finally {
      setLoading(false)
    }
  }

  const download = () => {
    if (!report) return
    const url = URL.createObjectURL(new Blob([report.markdown], { type: 'text/markdown' }))
    const a = document.createElement('a')
    a.href = url
    a.download = reportFilename(report.title)
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 space-y-3" data-testid="case-report-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2"><FileText className="w-4 h-4 text-blue-300" /> Report</h3>
        <div className="flex items-center gap-2">
          <select value={audience} onChange={e => setAudience(e.target.value as 'management' | 'review')} data-testid="case-report-audience"
            className="px-2 py-1 rounded bg-slate-900 border border-white/10 text-xs text-white">
            <option value="management">Summary for management</option>
            <option value="review">Post-incident review</option>
          </select>
          <button onClick={load} disabled={loading} data-testid="case-report-run"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50">
            {loading && <Loader2 className="w-3 h-3 animate-spin" />} Write report
          </button>
          {report && (
            <button onClick={download} data-testid="case-report-download" title="Download as Markdown"
              className="p-1.5 rounded border border-white/10 text-slate-300 hover:bg-white/10"><Download className="w-3.5 h-3.5" /></button>
          )}
        </div>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      {report && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-white" data-testid="case-report-title">{report.title}</p>
          <CitedSections summary={report} />
        </div>
      )}
    </div>
  )
}
