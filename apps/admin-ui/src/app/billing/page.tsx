'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Download, Loader2, Pencil, Play } from 'lucide-react'
import {
  downloadBill, fetchBills, fetchRates, runBilling, updateRate,
  type AdminBill, type BillingRunResult, type FeatureRate,
} from '@/lib/api'

function thisMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function money(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency || 'USD', maximumFractionDigits: 2 }).format(amount || 0)
}

/** Bills across tenants, the month's billing run, and the per-feature rates. */
export default function BillingPage() {
  const [period, setPeriod] = useState(thisMonth())
  const [bills, setBills] = useState<AdminBill[] | null>(null)
  const [totals, setTotals] = useState<Record<string, number>>({})
  const [rates, setRates] = useState<FeatureRate[] | null>(null)
  const [run, setRun] = useState<BillingRunResult | null>(null)
  const [running, setRunning] = useState(false)
  const [editing, setEditing] = useState<{ name: string; value: string } | null>(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string | null>(null)

  const loadBills = useCallback(async () => {
    try {
      const data = await fetchBills(period || undefined)
      setBills(data.bills)
      setTotals(data.totals)
    } catch (e: any) {
      setError(e?.message || 'Could not load bills')
      setBills([])
    }
  }, [period])

  useEffect(() => { loadBills() }, [loadBills])
  useEffect(() => {
    fetchRates().then(r => setRates(r.rates)).catch(e => { setError(e?.message || 'Could not load rates'); setRates([]) })
  }, [])

  const shown = useMemo(() => (bills || []).filter(b =>
    !filter || `${b.tenant_name} ${b.tenant_id} ${b.subscription_tier}`.toLowerCase().includes(filter.toLowerCase())), [bills, filter])

  const startRun = async () => {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period)) { setError('Choose a month first'); return }
    setRunning(true)
    setError(null)
    try {
      setRun(await runBilling(period))
      await loadBills()
    } catch (e: any) {
      setError(e?.message || 'The billing run failed')
    } finally {
      setRunning(false)
    }
  }

  const saveRate = async () => {
    if (!editing) return
    const value = Number(editing.value)
    if (!Number.isFinite(value) || value < 0) { setError('A rate is a number of 0 or more'); return }
    try {
      await updateRate(editing.name, value)
      setRates(list => (list || []).map(r => (r.feature_name === editing.name ? { ...r, base_rate: value } : r)))
      setEditing(null)
    } catch (e: any) {
      setError(e?.message || 'Could not save the rate')
    }
  }

  return (
    <div className="space-y-8">
      <Link href="/" className="text-blue-600 hover:text-blue-800 inline-flex items-center">
        <ArrowLeft className="h-4 w-4 mr-1" /> Back to Dashboard
      </Link>
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Billing</h1>
        <p className="text-gray-600">Bills across tenants, the monthly billing run and the per-feature rates.</p>
      </div>
      {error && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3" data-testid="billing-error">{error}</p>}

      <section className="bg-white rounded-lg shadow p-6 space-y-4">
        <div className="flex flex-wrap items-end gap-3 justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Bills</h2>
            <p className="text-sm text-gray-500">
              {Object.entries(totals).map(([c, t]) => money(t, c)).join(' + ') || 'No bills'} for {period || 'all months'}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-sm text-gray-600">Month
              <input data-testid="billing-period" type="month" value={period} onChange={e => setPeriod(e.target.value)}
                className="block mt-1 border border-gray-300 rounded px-2 py-1 text-gray-900" />
            </label>
            <input placeholder="Filter by tenant or plan" value={filter} onChange={e => setFilter(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1 text-sm text-gray-900" />
            <button data-testid="billing-run" onClick={startRun} disabled={running}
              title="Bill every active tenant for this month; tenants already billed keep their bill"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50">
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Bill all tenants
            </button>
          </div>
        </div>

        {run && (
          <div className="text-sm rounded border border-blue-200 bg-blue-50 p-3" data-testid="billing-run-result">
            {run.billing_period}: {run.generated} generated, {run.already_billed} already billed, {run.failed.length} not billed, of {run.tenants} active tenants.
            {run.failed.length > 0 && (
              <ul className="mt-2 list-disc ml-5 text-gray-700 max-h-32 overflow-y-auto">
                {run.failed.map(f => <li key={f.tenant_id}>{f.tenant_name || f.tenant_id}: {f.error}</li>)}
              </ul>
            )}
          </div>
        )}

        {bills === null ? <Loader2 className="h-5 w-5 animate-spin text-gray-400" /> : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" data-testid="bills-table">
              <thead className="text-left text-gray-500 border-b">
                <tr><th className="py-2 pr-4">Tenant</th><th className="pr-4">Month</th><th className="pr-4">Plan</th>
                  <th className="pr-4 text-right">Total</th><th className="pr-4">Status</th><th className="pr-4">Due</th><th /></tr>
              </thead>
              <tbody>
                {shown.slice(0, 200).map(b => (
                  <tr key={b.id} className="border-b last:border-0">
                    <td className="py-2 pr-4"><Link href={`/tenants/${b.tenant_id}/subscription`} className="text-blue-600 hover:underline">{b.tenant_name || b.tenant_id}</Link></td>
                    <td className="pr-4">{b.billing_period}</td>
                    <td className="pr-4">{b.subscription_tier}</td>
                    <td className="pr-4 text-right tabular-nums">{money(b.total_amount, b.currency)}</td>
                    <td className="pr-4">{b.paid_at ? 'paid' : b.status}</td>
                    <td className="pr-4">{b.due_date?.slice(0, 10) || '-'}</td>
                    <td><button title="Download PDF" onClick={() => downloadBill(b.id, `bill-${b.billing_period}-${b.tenant_name || b.tenant_id}.pdf`).catch(e => setError(e.message))}
                      className="text-gray-500 hover:text-gray-900" data-testid="bill-pdf"><Download className="h-4 w-4" /></button></td>
                  </tr>
                ))}
                {shown.length === 0 && <tr><td colSpan={7} className="py-6 text-center text-gray-500">{filter ? 'No bills match the filter.' : <>No bills for this month yet. &quot;Bill all tenants&quot; generates them.</>}</td></tr>}
              </tbody>
            </table>
            {shown.length > 200 && <p className="text-xs text-gray-500 mt-2">Showing 200 of {shown.length}; filter to narrow.</p>}
          </div>
        )}
      </section>

      <section className="bg-white rounded-lg shadow p-6 space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">Feature rates</h2>
        <p className="text-sm text-gray-500">Usage prices per feature. A change applies to bills generated after it; history is kept.</p>
        {rates === null ? <Loader2 className="h-5 w-5 animate-spin text-gray-400" /> : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" data-testid="rates-table">
              <thead className="text-left text-gray-500 border-b">
                <tr><th className="py-2 pr-4">Feature</th><th className="pr-4">Model</th><th className="pr-4 text-right">Base rate</th>
                  <th className="pr-4">Per plan</th><th className="pr-4">Since</th></tr>
              </thead>
              <tbody>
                {rates.map(r => (
                  <tr key={r.feature_name} className="border-b last:border-0 align-top">
                    <td className="py-2 pr-4"><div className="font-medium text-gray-900">{r.feature_name}</div><div className="text-gray-500">{r.description}</div></td>
                    <td className="pr-4">{r.pricing_model}</td>
                    <td className="pr-4 text-right tabular-nums">
                      {editing?.name === r.feature_name ? (
                        <span className="inline-flex gap-1">
                          <input autoFocus value={editing.value} onChange={e => setEditing({ ...editing, value: e.target.value })}
                            onKeyDown={e => { if (e.key === 'Enter') saveRate(); if (e.key === 'Escape') setEditing(null) }}
                            className="w-24 border border-gray-300 rounded px-1 text-right" data-testid="rate-input" />
                          <button onClick={saveRate} className="text-blue-600 text-xs" data-testid="rate-save">Save</button>
                        </span>
                      ) : (
                        <button onClick={() => setEditing({ name: r.feature_name, value: String(r.base_rate) })}
                          className="inline-flex items-center gap-1 hover:text-blue-600" data-testid="rate-edit">
                          {r.base_rate} {r.currency} <Pencil className="h-3 w-3" />
                        </button>
                      )}
                    </td>
                    <td className="pr-4 text-gray-600">{Object.entries(r.tier_rates || {}).map(([t, v]) => `${t} ${v}`).join(', ') || '-'}</td>
                    <td className="pr-4 text-gray-500">{r.effective_date?.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
