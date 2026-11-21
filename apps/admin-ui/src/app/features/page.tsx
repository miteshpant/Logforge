'use client'

import { Fragment, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Check, Loader2, Minus } from 'lucide-react'
import { fetchFeatureMatrix, type FeatureMatrix } from '@/lib/api'

/**
 * Which features each subscription tier includes. The bundles are defined in
 * code (apps/api/services/subscription_service.py), so this is a view, not an
 * editor; a tenant's own features are changed on its subscription page.
 */
export default function FeaturesPage() {
  const [matrix, setMatrix] = useState<FeatureMatrix | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [focus, setFocus] = useState<string>('')

  useEffect(() => {
    fetchFeatureMatrix().then(setMatrix).catch(e => setError(e?.message || 'Could not load the feature matrix'))
  }, [])

  const tiers = matrix ? (focus ? [focus] : matrix.tiers) : []

  return (
    <div className="space-y-8">
      <Link href="/" className="text-blue-600 hover:text-blue-800 inline-flex items-center">
        <ArrowLeft className="h-4 w-4 mr-1" /> Back to Dashboard
      </Link>
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Features by plan</h1>
        <p className="text-gray-600">
          What each subscription tier includes. Tiers are defined in code
          (<code className="text-sm">services/subscription_service.py</code>); change a single tenant&apos;s features on its
          subscription page.
        </p>
      </div>
      {error && <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">{error}</p>}
      {!matrix && !error && <Loader2 className="h-5 w-5 animate-spin text-gray-400" />}
      {matrix && (
        <section className="bg-white rounded-lg shadow p-6 space-y-4">
          <label className="text-sm text-gray-600">Show
            <select data-testid="feature-tier" value={focus} onChange={e => setFocus(e.target.value)}
              className="ml-2 border border-gray-300 rounded px-2 py-1 text-gray-900">
              <option value="">every tier</option>
              {matrix.tiers.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" data-testid="feature-matrix">
              <thead className="text-left text-gray-500 border-b">
                <tr>
                  <th className="py-2 pr-4">Feature</th>
                  {tiers.map(t => <th key={t} className="px-2 text-center capitalize">{t.replace('_', ' ')}</th>)}
                </tr>
              </thead>
              <tbody>
                {matrix.categories.map(c => (
                  <Fragment key={c.name}>
                    <tr className="bg-gray-50">
                      <td colSpan={tiers.length + 1} className="py-1.5 font-semibold text-gray-700 capitalize">{c.name.replace('_', ' ')}</td>
                    </tr>
                    {c.features.map(f => (
                      <tr key={f.name} className="border-b last:border-0">
                        <td className="py-1.5 pr-4 font-mono text-xs text-gray-800">{f.name}</td>
                        {tiers.map(t => (
                          <td key={t} className="px-2 text-center">
                            {f.tiers[t]
                              ? <Check className="h-4 w-4 text-green-600 inline" aria-label="included" />
                              : <Minus className="h-4 w-4 text-gray-300 inline" aria-label="not included" />}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <details className="text-sm text-gray-600">
            <summary className="cursor-pointer">Bundles as defined</summary>
            <ul className="mt-2 space-y-1">
              {matrix.tiers.map(t => <li key={t}><span className="font-medium">{t}</span>: <code className="text-xs">{matrix.bundles[t].join(', ')}</code></li>)}
            </ul>
          </details>
        </section>
      )}
    </div>
  )
}
