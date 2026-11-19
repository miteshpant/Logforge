'use client'

import { useCallback, useEffect, useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Globe, Loader2, Play, Plus, Rss, Search, Trash2 } from 'lucide-react'
import {
  addFeed, addIndicator, deleteFeed, deleteIndicator, Feed, IntelIndicator, listFeeds, runFeed, searchIndicators,
  updateFeed,
} from '@/lib/api/intel'
import { feedStatus } from '@/lib/intelFormat'

const TONE: Record<string, string> = { ok: 'text-green-400', error: 'text-red-400', idle: 'text-slate-400' }

export default function ThreatIntelPage() {
  const [tab, setTab] = useState<'indicators' | 'feeds'>('indicators')
  const [feeds, setFeeds] = useState<Feed[]>([])
  const [templates, setTemplates] = useState<Feed[]>([])
  const [indicators, setIndicators] = useState<IntelIndicator[]>([])
  const [total, setTotal] = useState(0)
  const [query, setQuery] = useState('')
  const [type, setType] = useState('')
  const [newValue, setNewValue] = useState('')
  const [newConfidence, setNewConfidence] = useState(80)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const loadFeeds = useCallback(async () => {
    const data = await listFeeds()
    setFeeds(data.feeds)
    setTemplates(data.templates)
  }, [])

  const loadIndicators = useCallback(async () => {
    const data = await searchIndicators({ q: query || undefined, type: type || undefined, limit: 200 })
    setIndicators(data.indicators)
    setTotal(data.total)
  }, [query, type])

  useEffect(() => {
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        await Promise.all([loadFeeds(), loadIndicators()])
        setError(null)
      } catch (e: any) {
        setError(e?.message || 'Failed to load threat intelligence')
      } finally {
        setLoading(false)
      }
    }, query ? 300 : 0)
    return () => clearTimeout(timer)
  }, [loadFeeds, loadIndicators, query])

  const act = async (key: string, change: () => Promise<unknown>, message?: (result: any) => string) => {
    setBusy(key)
    setError(null)
    setNotice(null)
    try {
      const result = await change()
      if (message) setNotice(message(result))
      await Promise.all([loadFeeds(), loadIndicators()])
    } catch (e: any) {
      setError(e?.message || 'The change was not saved')
    } finally {
      setBusy(null)
    }
  }

  const unusedTemplates = templates.filter(t => !feeds.some(f => f.name === t.name))

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Globe className="w-6 h-6 text-blue-400" /> Threat Intelligence</h1>
          <p className="text-sm text-slate-400 mt-1">
            Indicators from your feeds and your own lists. Events are matched as they arrive, and recent logs are searched when new indicators appear.
          </p>
        </div>

        <div className="flex rounded-lg border border-white/10 overflow-hidden w-fit">
          {(['indicators', 'feeds'] as const).map(name => (
            <button key={name} data-testid={`intel-tab-${name}`} onClick={() => setTab(name)}
              className={`px-4 py-2 text-sm capitalize ${tab === name ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-white/5'}`}>
              {name === 'indicators' ? `Indicators (${total})` : `Feeds (${feeds.length})`}
            </button>
          ))}
        </div>

        {error && <div role="alert" data-testid="intel-error" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</div>}
        {notice && <div data-testid="intel-notice" className="p-3 rounded-lg border border-green-500/30 bg-green-500/10 text-sm text-green-300">{notice}</div>}

        {tab === 'indicators' && (
          <section className="space-y-4">
            <div className="flex flex-wrap gap-3">
              <div className="relative flex-1 min-w-[240px]">
                <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input data-testid="intel-search" value={query} onChange={e => setQuery(e.target.value)}
                  placeholder="Search value, source or tag"
                  className="w-full pl-9 pr-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white" />
              </div>
              <select aria-label="Type" value={type} onChange={e => setType(e.target.value)}
                className="px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white">
                <option value="">All types</option>
                {['ip', 'domain', 'url', 'hash', 'email'].map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="flex flex-wrap gap-2 p-4 rounded-lg border border-white/10 bg-slate-800/50">
              <input data-testid="intel-new-value" value={newValue} onChange={e => setNewValue(e.target.value)}
                placeholder="Add an indicator: IP, domain, URL, hash or email (defanged is fine)"
                className="flex-1 min-w-[280px] px-3 py-2 bg-slate-900 border border-white/10 rounded-lg text-white" />
              <label className="flex items-center gap-2 text-sm text-slate-300">Confidence
                <input type="number" min={0} max={100} value={newConfidence} onChange={e => setNewConfidence(Number(e.target.value))}
                  className="w-20 px-2 py-2 bg-slate-900 border border-white/10 rounded-lg text-white" />
              </label>
              <button data-testid="intel-add" disabled={!newValue.trim() || busy === 'add'}
                onClick={() => act('add', () => addIndicator({ value: newValue.trim(), confidence: newConfidence }),
                  (r: IntelIndicator) => { setNewValue(''); return `Added ${r.value}; searching the last 7 days of logs for it.` })}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50">
                <Plus className="w-4 h-4" /> Add
              </button>
            </div>
            <div className="rounded-lg border border-white/10 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-800/80 text-slate-400 text-xs uppercase">
                  <tr>
                    <th className="p-3 text-left">Indicator</th>
                    <th className="p-3 text-left">Type</th>
                    <th className="p-3 text-left">Threat</th>
                    <th className="p-3 text-right">Confidence</th>
                    <th className="p-3 text-left">Source</th>
                    <th className="p-3 text-right" title="Logs that mention it in the last 7 days">Seen (7d)</th>
                    <th className="p-3 text-right">Expires</th>
                    <th className="w-10 p-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {loading && indicators.length === 0 && (
                    <tr><td colSpan={8} className="p-8 text-center"><Loader2 className="w-5 h-5 animate-spin inline text-slate-400" /></td></tr>
                  )}
                  {!loading && indicators.length === 0 && (
                    <tr><td colSpan={8} className="p-8 text-center text-slate-400">No indicators yet. Add a feed or an indicator.</td></tr>
                  )}
                  {indicators.map(i => (
                    <tr key={`${i.indicator_type}:${i.value}`} data-testid="intel-indicator" className="hover:bg-white/5">
                      <td className="p-3 font-mono text-slate-100 break-all">{i.value}
                        {i.tags.length > 0 && <div className="text-xs text-slate-500 font-sans">{i.tags.join(' · ')}</div>}
                      </td>
                      <td className="p-3 text-slate-300">{i.indicator_type}</td>
                      <td className="p-3 text-slate-300">{i.threat_type.replace(/_/g, ' ')}</td>
                      <td className="p-3 text-right text-slate-300">{i.confidence}</td>
                      <td className="p-3 text-slate-400">{i.source}</td>
                      <td className="p-3 text-right">
                        <span className={i.seen_7d > 0 ? 'text-red-300 font-semibold' : 'text-slate-500'} data-testid="intel-seen">{i.seen_7d}</span>
                      </td>
                      <td className="p-3 text-right text-slate-400">{i.expires_at ? new Date(i.expires_at).toLocaleDateString() : '—'}</td>
                      <td className="p-3 text-center">
                        <button aria-label={`Delete ${i.value}`} disabled={busy !== null}
                          onClick={() => act(`del:${i.value}`, () => deleteIndicator(i.indicator_type, i.value))}
                          className="text-slate-500 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {tab === 'feeds' && (
          <section className="space-y-4">
            <div className="rounded-lg border border-white/10 divide-y divide-white/5">
              {feeds.length === 0 && <p className="p-6 text-sm text-slate-400">No feeds yet. Add one of the built-in feeds below.</p>}
              {feeds.map(feed => {
                const status = feedStatus(feed)
                return (
                  <div key={feed.id || feed.name} data-testid="intel-feed" className="p-4 flex flex-wrap items-center gap-4">
                    <Rss className="w-5 h-5 text-orange-400" />
                    <div className="flex-1 min-w-[240px]">
                      <div className="text-white font-medium">{feed.name}</div>
                      <div className="text-xs text-slate-500 break-all">{feed.kind} · every {feed.interval_minutes} min · confidence {feed.confidence} · keep {feed.ttl_days} d</div>
                      <div data-testid="intel-feed-status" className={`text-xs mt-1 ${TONE[status.tone]}`}>{status.text}</div>
                      {feed.secret_env && !feed.secret_configured && (
                        <div className="text-xs mt-1 text-yellow-400">Needs an API key in the {feed.secret_env} environment variable</div>
                      )}
                    </div>
                    <label className="flex items-center gap-2 text-sm text-slate-300">
                      <input type="checkbox" checked={feed.enabled} disabled={busy !== null}
                        onChange={() => act(`toggle:${feed.id}`, () => updateFeed(feed.id!, { enabled: !feed.enabled }))} /> Enabled
                    </label>
                    <button data-testid="intel-feed-run" disabled={busy !== null}
                      onClick={() => act(`run:${feed.id}`, () => runFeed(feed.id!),
                        (r: any) => r.status === 'ok' ? `${feed.name}: ${r.count} indicators, ${r.new.length} new.` : `${feed.name} failed: ${r.error}`)}
                      className="flex items-center gap-1 px-3 py-1.5 border border-white/10 rounded-lg text-sm text-slate-200 hover:bg-white/5 disabled:opacity-50">
                      {busy === `run:${feed.id}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Run now
                    </button>
                    <button aria-label={`Delete ${feed.name}`} disabled={busy !== null}
                      onClick={() => act(`delete:${feed.id}`, () => deleteFeed(feed.id!))}
                      className="text-slate-500 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
                  </div>
                )
              })}
            </div>
            {unusedTemplates.length > 0 && (
              <div className="space-y-2">
                <h2 className="text-sm font-semibold text-white">Built-in feeds</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {unusedTemplates.map(t => (
                    <div key={t.name} className="p-4 rounded-lg border border-white/10 bg-slate-800/40 flex items-center gap-3">
                      <div className="flex-1">
                        <div className="text-white text-sm">{t.name}</div>
                        <div className="text-xs text-slate-500">{t.secret_env ? `Needs ${t.secret_env}` : 'No account needed'}</div>
                      </div>
                      <button data-testid="intel-add-template" disabled={busy !== null}
                        onClick={() => act(`tpl:${t.name}`, () => addFeed({ template: t.name }), () => `Added ${t.name}.`)}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm disabled:opacity-50">Add</button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </DashboardLayout>
  )
}
