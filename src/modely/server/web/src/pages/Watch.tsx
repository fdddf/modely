import { useState, useEffect, useCallback } from 'react'
import {
  getWatchTargets, checkWatchDrift, getWatchHistory, createSyncJob, getSyncJob,
  remoteSearch, addWatchTarget, removeWatchTarget,
} from '../api/client'
import type { WatchTarget, WatchHistoryEvent, RemoteSearchResult } from '../api/types'

const DEFAULT_WATCH_CONFIG = '~/.modely/voice-models-watch.json'

// Module-level caches to survive component remounts during navigation.
let _syncingKeysCache = new Set<string>()
let _syncJobIdsCache = new Map<string, string>()
let _activeTabCache: 'discover' | 'targets' = 'discover'

function statusBadge(status: string | undefined) {
  const color = status === 'error' ? '#f44336' : '#4caf50'
  return <span style={{ color, fontWeight: 600, fontSize: '0.85rem' }}>{status || 'unknown'}</span>
}

function driftBadge(status: string | undefined) {
  const colors: Record<string, string> = {
    drifted: '#fff8e1',
    unchanged: '#e8f5e9',
    error: '#ffeef0',
    idle: '#f5f5f5',
  }
  const textColors: Record<string, string> = {
    drifted: '#e65100',
    unchanged: '#2e7d32',
    error: '#c62828',
    idle: '#999',
  }
  const bg = colors[status || 'idle'] || colors.idle
  const fg = textColors[status || 'idle'] || textColors.idle
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 10,
      background: bg, color: fg, fontWeight: 600, fontSize: '0.78rem',
    }}>
      {status || 'idle'}
    </span>
  )
}

function timeAgo(iso?: string): string {
  if (!iso) return '-'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatDate(iso?: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso.slice(0, 10)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// Build the resource URI for sync jobs.
// hf/ms:  <source>://<repo_type>s/<repo_id>  (e.g. hf://models/gpt2)
// github: github://<owner>/<repo>            (no repo_type segment)
function buildResourceUri(source: string, repo_type: string, repo_id: string): string {
  if (source === 'github') {
    return `github://${repo_id}`
  }
  return `${source}://${repo_type || 'model'}s/${repo_id}`
}

function isSyncedUnchanged(t: WatchTarget): boolean {
  return !!(t.last_downloaded_at && t.fingerprint && t.drift_status === 'unchanged')
}

// ── Discover tab ──────────────────────────────────────────────────────────────

const PAGE_SIZE_OPTIONS = [10, 20, 30]
const MAX_PAGES_SHOWN = 10

function DiscoverTab({ watchedKeys, onAdded }: {
  watchedKeys: Set<string>
  onAdded: () => void
}) {
  const [query, setQuery] = useState('')
  const [source, setSource] = useState('all')
  const [repoType, setRepoType] = useState('all')
  const [results, setResults] = useState<RemoteSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [addingKey, setAddingKey] = useState('')
  const [addedKeys, setAddedKeys] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [totalResults, setTotalResults] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  // Track which (query+source+repoType+pageSize) combo was last searched
  const [lastSearchKey, setLastSearchKey] = useState('')

  const doSearch = async (targetPage: number, targetPageSize?: number) => {
    const ps = targetPageSize ?? pageSize
    if (!query.trim()) return
    setSearching(true); setSearchError(''); setResults([])
    try {
      const params: Record<string, string> = { q: query.trim(), page: String(targetPage), page_size: String(ps) }
      if (source !== 'all') params.source = source
      if (repoType !== 'all') params.repo_type = repoType
      const res = await remoteSearch(params)
      setResults(res.data.results || [])
      setTotalResults(res.data.total)
      setTotalPages(res.data.total_pages || 1)
      setPage(res.data.page)
      setPageSize(ps)
      setLastSearchKey(`${query.trim()}|${source}|${repoType}|${ps}`)
    } catch (e: unknown) { setSearchError((e as Error).message) }
    finally { setSearching(false) }
  }

  const handleSearch = () => {
    setPage(1)
    doSearch(1)
  }

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize)
    setPage(1)
    // Trigger search with new page size only if we have an active search
    const sk = `${query.trim()}|${source}|${repoType}|${newSize}`
    if (lastSearchKey && sk !== lastSearchKey) {
      doSearch(1, newSize)
    }
  }

  const goToPage = (p: number) => {
    if (p < 1 || p > totalPages || p === page) return
    doSearch(p)
  }

  const handleAdd = async (r: RemoteSearchResult) => {
    // Use source-appropriate default: ModelScope defaults to 'master', HF/GitHub to 'main'
    const revision = r.source === 'ms' ? 'master' : 'main'
    const key = `${r.source}:${r.repo_type}:${r.id || r.name || ''}:${revision}`
    setAddingKey(key)
    try {
      const target = {
        source: r.source,
        repo_type: r.repo_type,
        repo_id: r.id || r.name || '',
        revision,
      }
      await addWatchTarget(DEFAULT_WATCH_CONFIG, target as Record<string, unknown>)
      setAddedKeys(prev => new Set(prev).add(key))
      onAdded()
    } catch (e: unknown) {
      setSearchError((e as Error).message)
    }
    setAddingKey('')
  }

  const isAdded = (r: RemoteSearchResult) => {
    const revision = r.source === 'ms' ? 'master' : 'main'
    const key = `${r.source}:${r.repo_type}:${r.id || r.name || ''}:${revision}`
    return watchedKeys.has(key) || addedKeys.has(key)
  }

  const formatNum = (n: number | undefined) => {
    if (n === undefined || n === null) return '-'
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
    return String(n)
  }

  const formatSize = (bytes: number | undefined): string => {
    if (bytes === undefined || bytes === null || bytes === 0) return '-'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let i = 0
    let size = bytes
    while (size >= 1024 && i < units.length - 1) {
      size /= 1024
      i++
    }
    return `${size.toFixed(size < 10 ? 1 : 0)} ${units[i]}`
  }

  // Build pagination page numbers — show at most MAX_PAGES_SHOWN, centered around current
  const buildPageNumbers = (): number[] => {
    if (totalPages <= 1) return []
    const half = Math.floor(MAX_PAGES_SHOWN / 2)
    let startPage = Math.max(1, page - half)
    let endPage = Math.min(totalPages, startPage + MAX_PAGES_SHOWN - 1)
    if (endPage - startPage + 1 < MAX_PAGES_SHOWN) {
      startPage = Math.max(1, endPage - MAX_PAGES_SHOWN + 1)
    }
    const pages: number[] = []
    for (let i = startPage; i <= endPage; i++) pages.push(i)
    return pages
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
          placeholder="Search models, datasets, tools..."
          style={{ flex: 1, minWidth: 200, padding: '6px 12px', fontSize: '0.9rem', border: '1px solid #ccc', borderRadius: 6 }}
        />
        <select value={source} onChange={e => setSource(e.target.value)}
          style={{ padding: '6px 10px', fontSize: '0.85rem', border: '1px solid #ccc', borderRadius: 6 }}>
          <option value="all">All Sources</option>
          <option value="hf">HuggingFace</option>
          <option value="ms">ModelScope</option>
          <option value="github">GitHub</option>
        </select>
        <select value={repoType} onChange={e => setRepoType(e.target.value)}
          style={{ padding: '6px 10px', fontSize: '0.85rem', border: '1px solid #ccc', borderRadius: 6 }}>
          <option value="all">All Types</option>
          <option value="model">Models</option>
          <option value="dataset">Datasets</option>
          <option value="tool">Tools</option>
        </select>
        <button onClick={handleSearch} disabled={searching || !query.trim()} style={{
          padding: '6px 18px', cursor: (searching || !query.trim()) ? 'default' : 'pointer',
          border: 'none', borderRadius: 6, background: '#1976d2', color: '#fff', fontWeight: 600,
          opacity: (searching || !query.trim()) ? 0.7 : 1,
        }}>
          {searching ? 'Searching...' : 'Search'}
        </button>
      </div>

      {searchError && <div style={{ color: '#f44336', marginBottom: 12, padding: '8px 12px', background: '#ffeef0', borderRadius: 6 }}>{searchError}</div>}

      {/* Top pagination bar */}
      {totalResults > 0 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, fontSize: '0.85rem', color: '#666' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{totalResults} results</span>
            <span>·</span>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              Per page:
              <select value={pageSize} onChange={e => handlePageSizeChange(Number(e.target.value))}
                style={{ padding: '2px 6px', fontSize: '0.82rem', border: '1px solid #ccc', borderRadius: 4 }}>
                {PAGE_SIZE_OPTIONS.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>
          </div>
          {totalPages > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontWeight: 500, color: '#333' }}>{page} / {totalPages}</span>
              <button onClick={() => goToPage(1)} disabled={page <= 1}
                style={paginationBtnStyle(false, page <= 1)} title="First">««</button>
              <button onClick={() => goToPage(page - 1)} disabled={page <= 1}
                style={paginationBtnStyle(false, page <= 1)} title="Previous">«</button>
              {buildPageNumbers().map(p => (
                <button key={p} onClick={() => goToPage(p)}
                  style={paginationBtnStyle(p === page, false)}>
                  {p}
                </button>
              ))}
              <button onClick={() => goToPage(page + 1)} disabled={page >= totalPages}
                style={paginationBtnStyle(false, page >= totalPages)} title="Next">»</button>
              <button onClick={() => goToPage(totalPages)} disabled={page >= totalPages}
                style={paginationBtnStyle(false, page >= totalPages)} title="Last">»»</button>
            </div>
          )}
        </div>
      )}

      {results.length > 0 && (
        <table style={{ width: '100%', tableLayout: 'fixed', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <colgroup>
            <col style={{ width: '14%' }} />
            <col style={{ width: '7%' }} />
            <col style={{ width: '6%' }} />
            <col style={{ width: '8%' }} />
            <col style={{ width: '6%' }} />
            <col style={{ width: '7%' }} />
            <col style={{ width: '9%' }} />
            <col style={{ width: '7%' }} />
            <col style={{ width: '18%' }} />
            <col style={{ width: '10%' }} />
          </colgroup>
          <thead>
            <tr style={{ background: '#f9f9f9' }}>
              {['Name', 'Source', 'Type', 'Author', 'Stars', 'License', 'Updated', 'Size', 'Description', 'Actions'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: 10, borderBottom: '2px solid #ddd' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((r, idx) => {
              const added = isAdded(r)
              const adding = addingKey === `${r.source}:${r.repo_type}:${r.id || r.name || ''}:main`
              return (
                <tr key={idx}>
                  <td style={cellEllipsisStyle}>
                    <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2', fontWeight: 500 }} title={r.name || r.id || r.modely_uri || ''}>
                      {r.name || r.id || r.modely_uri || '-'}
                    </a>
                  </td>
                  <td style={cellEllipsisStyle}>
                    <code style={{ fontSize: '0.78rem' }} title={r.source}>{r.source}</code>
                  </td>
                  <td style={cellEllipsisStyle}>
                    <code style={{ fontSize: '0.78rem' }} title={r.repo_type}>{r.repo_type}</code>
                  </td>
                  <td style={{ ...cellEllipsisStyle, color: '#666' }} title={r.author || ''}>
                    {r.author || '-'}
                  </td>
                  <td style={{ ...cellEllipsisStyle, color: '#666' }}>
                    {formatNum(r.stars || r.likes)}
                  </td>
                  <td style={cellEllipsisStyle} title={r.license || ''}>
                    {r.license ? <span style={{ color: '#2e7d32', fontSize: '0.8rem' }}>{r.license}</span> : '-'}
                  </td>
                  <td style={{ ...cellEllipsisStyle, color: '#666', fontSize: '0.8rem' }}>
                    {formatDate(r.last_modified)}
                  </td>
                  <td style={{ ...cellEllipsisStyle, color: '#666', fontSize: '0.8rem' }}>
                    {formatSize(r.size_bytes)}
                  </td>
                  <td style={{ ...cellEllipsisStyle, color: '#888', fontSize: '0.8rem' }} title={r.description || ''}>
                    {r.description || '-'}
                  </td>
                  <td style={cellEllipsisStyle}>
                    {added ? (
                      <span style={{ color: '#999', fontSize: '0.78rem' }}>Added</span>
                    ) : (
                      <button disabled={adding} onClick={() => handleAdd(r)} style={{
                        padding: '4px 10px', fontSize: '0.72rem', background: '#1976d2', color: '#fff',
                        border: 'none', borderRadius: 4, cursor: adding ? 'default' : 'pointer', opacity: adding ? 0.7 : 1,
                      }}>
                        {adding ? 'Adding...' : 'Add to Watch'}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      {/* Bottom pagination bar */}
      {totalResults > 0 && totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginTop: 12, fontSize: '0.85rem' }}>
          <span style={{ fontWeight: 500, color: '#333', marginRight: 4 }}>Page {page} of {totalPages}</span>
          <button onClick={() => goToPage(1)} disabled={page <= 1}
            style={paginationBtnStyle(false, page <= 1)}>««</button>
          <button onClick={() => goToPage(page - 1)} disabled={page <= 1}
            style={paginationBtnStyle(false, page <= 1)}>«</button>
          {buildPageNumbers().map(p => (
            <button key={p} onClick={() => goToPage(p)}
              style={paginationBtnStyle(p === page, false)}>
              {p}
            </button>
          ))}
          <button onClick={() => goToPage(page + 1)} disabled={page >= totalPages}
            style={paginationBtnStyle(false, page >= totalPages)}>»</button>
          <button onClick={() => goToPage(totalPages)} disabled={page >= totalPages}
            style={paginationBtnStyle(false, page >= totalPages)}>»»</button>
        </div>
      )}

      {!searching && results.length === 0 && !searchError && (
        <p style={{ color: '#999', padding: '32px 0', textAlign: 'center', border: '1px dashed #ddd', borderRadius: 8 }}>
          Search for repositories across HuggingFace, ModelScope, and GitHub.
        </p>
      )}
    </div>
  )
}

// Shared pagination button style helper
function paginationBtnStyle(active: boolean, disabled: boolean): React.CSSProperties {
  return {
    padding: '3px 10px',
    fontSize: '0.8rem',
    cursor: disabled ? 'default' : 'pointer',
    border: active ? '1px solid #1976d2' : '1px solid #ccc',
    borderRadius: 4,
    background: active ? '#1976d2' : '#fff',
    color: active ? '#fff' : disabled ? '#bbb' : '#333',
    fontWeight: active ? 600 : 400,
    opacity: disabled ? 0.5 : 1,
    minWidth: 32,
  }
}

// Shared table cell style with fixed-width truncation
const cellEllipsisStyle: React.CSSProperties = {
  padding: 8,
  borderBottom: '1px solid #eee',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

// ── Targets tab ──────────────────────────────────────────────────────────────

function TargetsTab({ targets, loading, error, syncingKeys, onRefresh, onCheck, checking, onSync, onRemove, onSelectKey, selectedKey, history }: {
  targets: WatchTarget[]
  loading: boolean
  error: string
  syncingKeys: Set<string>
  onRefresh: () => void
  onCheck: () => void
  checking: boolean
  onSync: (t: WatchTarget, e: React.MouseEvent) => void
  onRemove: (t: WatchTarget, e: React.MouseEvent) => void
  onSelectKey: (key: string) => void
  selectedKey: string
  history: WatchHistoryEvent[]
}) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20 }}>
      {/* Left column: targets table */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Targets ({targets.length})</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onRefresh} style={{ padding: '6px 14px', cursor: 'pointer', border: 'none', borderRadius: 6, background: '#1976d2', color: '#fff' }}>
              Refresh
            </button>
            <button onClick={onCheck} disabled={checking} style={{
              padding: '6px 14px', cursor: checking ? 'wait' : 'pointer', border: 'none', borderRadius: 6,
              background: '#1976d2', color: '#fff', opacity: checking ? 0.7 : 1,
            }}>
              {checking ? 'Checking...' : 'Check Drift'}
            </button>
          </div>
        </div>

        {error && <div style={{ color: '#f44336', marginBottom: 12, padding: '8px 12px', background: '#ffeef0', borderRadius: 6 }}>{error}</div>}

        {loading ? <p>Loading...</p> : targets.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#999', border: '1px dashed #ddd', borderRadius: 8 }}>
            No watch targets configured. Go to <strong>Discover</strong> to add targets.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: '#f9f9f9' }}>
                {['Source', 'Type', 'Repo ID', 'Revision', 'Last Checked', 'Drift', 'Fingerprint', 'Actions'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: 10, borderBottom: '2px solid #ddd' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {targets.map(t => (
                <tr key={t.key} onClick={() => onSelectKey(t.key)} style={{
                  cursor: 'pointer',
                  background: selectedKey === t.key ? '#e3f2fd' : 'transparent',
                }}>
                  <td style={{ padding: 10, borderBottom: '1px solid #eee' }}><code>{t.source}</code></td>
                  <td style={{ padding: 10, borderBottom: '1px solid #eee' }}><code>{t.repo_type || 'model'}</code></td>
                  <td style={{ padding: 10, borderBottom: '1px solid #eee' }}>{t.repo_id}</td>
                  <td style={{ padding: 10, borderBottom: '1px solid #eee' }}><code style={{ fontSize: '0.8rem' }}>{t.revision}</code></td>
                  <td style={{ padding: 10, borderBottom: '1px solid #eee', fontSize: '0.8rem' }}>{timeAgo(t.last_checked_at)}</td>
                  <td style={{ padding: 10, borderBottom: '1px solid #eee' }}>{driftBadge(t.drift_status)}</td>
                  <td style={{ padding: 10, borderBottom: '1px solid #eee', fontFamily: 'monospace', fontSize: '0.7rem', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.current_fingerprint ? t.current_fingerprint.slice(0, 10) + '...' : '-'}
                  </td>
                  <td style={{ padding: 10, borderBottom: '1px solid #eee', whiteSpace: 'nowrap' }}>
                    {syncingKeys.has(t.key) ? (
                      <span style={{ color: '#1976d2', fontSize: '0.78rem', fontWeight: 600 }}>Syncing...</span>
                    ) : isSyncedUnchanged(t) ? (
                      <>
                        <span style={{ color: '#2e7d32', fontSize: '0.78rem', fontWeight: 600, marginRight: 6 }}>
                          Synced ✓
                        </span>
                        <button onClick={(e) => onSync(t, e)}
                          style={{ padding: '2px 6px', fontSize: '0.68rem', background: 'transparent', color: '#1976d2', border: '1px solid #1976d2', borderRadius: 4, cursor: 'pointer', marginRight: 4 }}>
                          Re-sync
                        </button>
                        <button onClick={(e) => onRemove(t, e)}
                          style={{ padding: '4px 8px', fontSize: '0.72rem', background: '#f44336', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                          Remove
                        </button>
                      </>
                    ) : (
                      <>
                        <button onClick={(e) => onSync(t, e)}
                          style={{ padding: '4px 8px', fontSize: '0.72rem', background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', marginRight: 4 }}>
                          Sync
                        </button>
                        <button onClick={(e) => onRemove(t, e)}
                          style={{ padding: '4px 8px', fontSize: '0.72rem', background: '#f44336', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                          Remove
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Right column: history timeline */}
      <div>
        <h3 style={{ marginTop: 0 }}>
          {selectedKey ? `Change History` : 'Recent Changes'}
        </h3>
        {selectedKey && (
          <div style={{ marginBottom: 8, fontSize: '0.85rem', color: '#666', wordBreak: 'break-all' }}>
            {selectedKey}
          </div>
        )}
        {history.length === 0 ? (
          <p style={{ color: '#999', fontSize: '0.9rem' }}>
            {selectedKey ? 'No change history for this target.' : 'Select a target to see its change history.'}
          </p>
        ) : (
          <div style={{ maxHeight: 500, overflowY: 'auto' }}>
            {history.map((evt, idx) => (
              <div key={idx} style={{
                padding: '10px 12px', marginBottom: 8, borderLeft: `3px solid ${evt.event === 'downloaded' ? '#4caf50' : evt.event === 'error' ? '#f44336' : '#ff9800'}`,
                background: '#fff', borderRadius: '0 6px 6px 0', fontSize: '0.85rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{evt.event}</span>
                  <span style={{ color: '#999' }}>{timeAgo(evt.timestamp)}</span>
                </div>
                <div style={{ color: '#666', wordBreak: 'break-all' }}>{evt.repo_id}</div>
                {evt.error && <div style={{ color: '#f44336', marginTop: 4 }}>{evt.error}</div>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Watch component ────────────────────────────────────────────────────

export default function Watch() {
  const [targets, setTargets] = useState<WatchTarget[]>([])
  const [history, setHistory] = useState<WatchHistoryEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [selectedKey, setSelectedKey] = useState('')
  const [syncingKeys, setSyncingKeys] = useState<Set<string>>(_syncingKeysCache)
  const [syncJobIds, setSyncJobIds] = useState<Map<string, string>>(_syncJobIdsCache)
  const [activeTab, setActiveTab] = useState<'discover' | 'targets'>(_activeTabCache)

  // Sync module-level caches
  useEffect(() => { _syncingKeysCache = syncingKeys }, [syncingKeys])
  useEffect(() => { _syncJobIdsCache = syncJobIds }, [syncJobIds])
  useEffect(() => { _activeTabCache = activeTab }, [activeTab])

  const fetchTargets = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await getWatchTargets(DEFAULT_WATCH_CONFIG)
      setTargets(res.data.targets)
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setLoading(false) }
  }, [])

  const fetchHistory = useCallback(async (targetKey?: string) => {
    try {
      const res = await getWatchHistory(targetKey || undefined)
      setHistory(res.data.events)
    } catch { /* history is optional; ignore errors */ }
  }, [])

  useEffect(() => { fetchTargets(); fetchHistory() }, [fetchTargets, fetchHistory])

  // Poll active sync jobs
  useEffect(() => {
    if (syncingKeys.size === 0) return
    const timer = setInterval(async () => {
      for (const [key, jobId] of syncJobIds) {
        if (!syncingKeys.has(key)) continue
        try {
          const res = await getSyncJob(jobId)
          if (res.data.status !== 'syncing') {
            setSyncingKeys(prev => { const next = new Set(prev); next.delete(key); return next })
            setSyncJobIds(prev => { const next = new Map(prev); next.delete(key); return next })
            fetchTargets()
          }
        } catch { /* keep polling */ }
      }
    }, 2000)
    return () => clearInterval(timer)
  }, [syncingKeys, syncJobIds])

  const handleCheck = async () => {
    setChecking(true); setError('')
    try {
      await checkWatchDrift(DEFAULT_WATCH_CONFIG)
      await fetchTargets()
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setChecking(false) }
  }

  const handleSelectKey = (key: string) => {
    setSelectedKey(key === selectedKey ? '' : key)
    fetchHistory(key)
  }

  const handleSync = async (t: WatchTarget, e: React.MouseEvent) => {
    e.stopPropagation()
    setSyncingKeys(prev => new Set(prev).add(t.key))
    try {
      const resource = buildResourceUri(t.source, t.repo_type, t.repo_id)
      const res = await createSyncJob({ target_id: t.key, resource, revision: t.revision })
      setSyncJobIds(prev => new Map(prev).set(t.key, res.data.id))
      setError('')
    } catch (e: unknown) {
      setError((e as Error).message)
      setSyncingKeys(prev => { const next = new Set(prev); next.delete(t.key); return next })
    }
  }

  const handleRemove = async (t: WatchTarget, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await removeWatchTarget(DEFAULT_WATCH_CONFIG, t.key)
      fetchTargets()
    } catch (e: unknown) { setError((e as Error).message) }
  }

  // Compute watched keys for Discover tab button state
  const watchedKeys = new Set(targets.map(t => t.key))

  return (
    <div>
      <h2>Watch — Repository Monitoring</h2>
      <p style={{ color: '#666', marginBottom: 16 }}>
        Discover repositories across HuggingFace, ModelScope, and GitHub, then monitor them for changes.
      </p>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 20, borderBottom: '2px solid #e0e0e0' }}>
        {(['targets', 'discover'] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} style={{
            padding: '10px 24px',
            cursor: 'pointer',
            border: 'none',
            background: 'transparent',
            color: activeTab === tab ? '#1976d2' : '#666',
            fontWeight: activeTab === tab ? 600 : 400,
            fontSize: '0.95rem',
            borderBottom: activeTab === tab ? '3px solid #1976d2' : '3px solid transparent',
            marginBottom: -2,
            transition: 'all 0.15s',
          }}>
            {tab === 'discover' ? 'Discover' : 'Targets'}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'discover' ? (
        <DiscoverTab watchedKeys={watchedKeys} onAdded={fetchTargets} />
      ) : (
        <TargetsTab
          targets={targets}
          loading={loading}
          error={error}
          syncingKeys={syncingKeys}
          onRefresh={fetchTargets}
          onCheck={handleCheck}
          checking={checking}
          onSync={handleSync}
          onRemove={handleRemove}
          onSelectKey={handleSelectKey}
          selectedKey={selectedKey}
          history={history}
        />
      )}
    </div>
  )
}
