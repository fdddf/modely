import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listAssets } from '../api/client'
import type { AssetItem, AssetsSummary } from '../api/types'
import Pagination from '../components/Pagination'
import FilterBar, { FacetDef } from '../components/FilterBar'

const FACETS: FacetDef[] = [
  { field: 'source', label: 'All Sources', options: ['hf', 'ms', 'github', 'kaggle'] },
  { field: 'resource_type', label: 'All Types', options: ['model', 'dataset', 'tool'] },
  { field: 'license', label: 'All Licenses', options: ['apache-2.0', 'mit', 'gpl-3.0', 'bsd-3-clause', 'cc-by-4.0', 'other'] },
  { field: 'operational_state', label: 'All States', options: ['discovered', 'active', 'archived', 'deprecated'] },
]

function formatListSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

// -- badge helpers ---------------------------------------------------------

function statusBadge(state: string) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    active: { bg: '#e8f5e9', color: '#2e7d32', label: 'Active' },
    discovered: { bg: '#e3f2fd', color: '#1565c0', label: 'Discovered' },
    archived: { bg: '#f3e5f5', color: '#7b1fa2', label: 'Archived' },
    deprecated: { bg: '#fff3e0', color: '#e65100', label: 'Deprecated' },
    syncing: { bg: '#fff8e1', color: '#f57f17', label: 'Syncing' },
  }
  const s = map[state] || { bg: '#f5f5f5', color: '#666', label: state || 'Unknown' }
  return (
    <span style={{ background: s.bg, color: s.color, padding: '2px 8px', borderRadius: 10, fontSize: '0.7rem', fontWeight: 700 }}>
      {s.label}
    </span>
  )
}

const RISK_COLORS: Record<string, string> = { high: '#f44336', medium: '#ff9800', low: '#4caf50', unknown: '#999' }

function riskDot(level: string) {
  const color = RISK_COLORS[level] || '#999'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.8rem' }}>
      <span style={{ width: 8, height: 8, borderRadius: 999, background: color, display: 'inline-block' }} />
      {level}
    </span>
  )
}

function licenseBadge(license: string | undefined) {
  if (!license) return <span style={{ color: '#f44336', fontSize: '0.78rem', fontWeight: 600 }}>Missing</span>
  return (
    <span style={{ background: '#e8f5e9', color: '#2e7d32', padding: '2px 8px', borderRadius: 10, fontSize: '0.7rem', fontWeight: 700 }}>
      {license}
    </span>
  )
}

// -- summary card ----------------------------------------------------------

function SummaryCard({ label, value, color, subtitle }: { label: string; value: string; color: string; subtitle?: string }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #ddd', borderRadius: 8, padding: '10px 14px' }}>
      <div style={{ fontSize: '0.68rem', color: '#999', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: '1.1rem', fontWeight: 800, color, lineHeight: 1.2 }}>{value}</div>
      {subtitle && <div style={{ fontSize: '0.68rem', color: '#999', marginTop: 2 }}>{subtitle}</div>}
    </div>
  )
}

// -- main component --------------------------------------------------------

export default function AssetList() {
  const navigate = useNavigate()
  const [assets, setAssets] = useState<AssetItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [summary, setSummary] = useState<AssetsSummary | null>(null)
  const [sort, setSort] = useState('-size')

  const fetch = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await listAssets({ page: String(page), page_size: '20', sort, ...filters })
      setAssets(res.data.assets)
      setTotal(res.data.total)
      setSummary(res.data.summary || null)
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setLoading(false) }
  }, [page, filters, sort])

  useEffect(() => { fetch() }, [fetch])

  // -- derived KPI values --------------------------------------------------
  const riskHigh = summary?.by_risk?.high || 0
  const riskMed = summary?.by_risk?.medium || 0
  const statusActive = summary?.by_status?.active || 0
  const statusDiscovered = summary?.by_status?.discovered || 0

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 14 }}>
        <h2 style={{ margin: 0 }}>Assets</h2>
        {summary && <span style={{ color: '#999', fontSize: '0.85rem' }}>{summary.total_count} total</span>}
      </div>

      {/* -- KPI banner ---------------------------------------------------- */}
      {summary && !loading && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(155px, 1fr))', gap: 10,
          marginBottom: 16,
        }}>
          <SummaryCard label="Total Assets" value={String(summary.total_count)}
            color="#1976d2"
            subtitle={Object.entries(summary.by_source).map(([k,v]) => `${k}:${v}`).join(' · ')} />
          <SummaryCard label="Total Size" value={formatListSize(summary.total_size)}
            color="#4caf50"
            subtitle={`${summary.total_files} files`} />
          <SummaryCard label="License Coverage" value={`${summary.licensed_count}/${summary.total_count}`}
            color={summary.licensed_count === summary.total_count ? '#4caf50' : '#ff9800'}
            subtitle={summary.licensed_count === summary.total_count ? 'All licensed' : `${summary.total_count - summary.licensed_count} missing`} />
          <SummaryCard label="Risk Level" value={riskHigh > 0 ? `${riskHigh} high` : riskMed > 0 ? `${riskMed} med` : 'Clear'}
            color={riskHigh > 0 ? '#f44336' : riskMed > 0 ? '#ff9800' : '#4caf50'} />
          <SummaryCard label="Status"
            value={statusActive > 0 ? `${statusActive} active` : `${statusDiscovered} discovered`}
            color="#1565c0" />
        </div>
      )}

      {/* -- Filters + sort ------------------------------------------------ */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'stretch', flexWrap: 'wrap', marginBottom: 12 }}>
        <FilterBar onFilter={f => { setFilters(f); setPage(1) }} facets={FACETS} />
        <select value={sort} onChange={e => { setSort(e.target.value); setPage(1) }}
          style={{ padding: '6px 8px', border: '1px solid #ccc', borderRadius: 4, fontSize: '0.82rem' }}>
          <option value="-size">Largest first</option>
          <option value="size">Smallest first</option>
          <option value="-file_count">Most files</option>
          <option value="file_count">Fewest files</option>
          <option value="repo_id">Name A-Z</option>
          <option value="-repo_id">Name Z-A</option>
        </select>
      </div>

      {/* -- Table --------------------------------------------------------- */}
      {loading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {!loading && !error && assets.length === 0 && (
        <div style={{ padding: 40, textAlign: 'center', color: '#999', background: '#fff', border: '1px solid #ddd', borderRadius: 8 }}>
          <p style={{ fontSize: '1rem', marginBottom: 8 }}>No assets found</p>
          <p style={{ fontSize: '0.85rem' }}>Run <code>modely-ai get &lt;repo&gt;</code> to download models, then refresh this page.</p>
        </div>
      )}
      {!loading && !error && assets.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f9f9f9' }}>
              {['Asset','Source','Type','License','Status','Risk','Size','Tags'].map(h => (
                <th key={h} style={{textAlign:'left',padding:10,borderBottom:'2px solid #ddd',fontSize:'0.78rem',color:'#666'}}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {assets.map(a => {
              const riskLevel = ((a.metadata as Record<string,unknown> | null)?.risk_level as string) || 'unknown'
              return (
              <tr key={a.id} style={{ cursor: 'pointer', borderBottom: '1px solid #eee' }}
                onClick={() => navigate(`/assets/${a.id.replace(/\//g, '--')}`)}>
                <td style={{padding:10,fontSize:'0.84rem',fontWeight:600}}>{a.repo_id || a.id}</td>
                <td style={{padding:10,fontSize:'0.84rem'}}><code>{a.source}</code></td>
                <td style={{padding:10,fontSize:'0.84rem'}}>{a.repo_type}</td>
                <td style={{padding:10}}>{licenseBadge(a.license)}</td>
                <td style={{padding:10}}>{statusBadge(a.operational_state)}</td>
                <td style={{padding:10}}>{riskDot(riskLevel)}</td>
                <td style={{padding:10,fontSize:'0.84rem'}}>{formatListSize(a.size)}</td>
                <td style={{padding:10}}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, maxWidth: 200 }}>
                    {(a.tags || []).slice(0, 3).map(t => (
                      <span key={t} style={{ background: '#e3f2fd', color: '#1976d2', padding: '1px 6px', borderRadius: 10, fontSize: '0.68rem' }}>{t}</span>
                    ))}
                    {(a.tags || []).length > 3 && <span style={{ fontSize: '0.68rem', color: '#999' }}>+{a.tags.length - 3}</span>}
                  </div>
                </td>
              </tr>
            )})}
          </tbody>
        </table>
      )}
      <Pagination total={total} page={page} pageSize={20} onChange={setPage} />
    </div>
  )
}
