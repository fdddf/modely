import { useState, useEffect, useMemo } from 'react'
import {
  getRiskTrends, getUsagePopularity, getLifecycleAnalytics,
  listAssets, listSyncJobs, getWatchTargets,
} from '../api/client'
import type { RiskTrendsData, UsageStatsData, AssetItem } from '../api/types'

// -- KPI tile --------------------------------------------------------------

function StatTile({ label, value, color, subtitle }: {
  label: string; value: string | number; color?: string; subtitle?: string;
}) {
  return (
    <div style={{
      background: '#fff', border: '1px solid #e0e0e0', borderRadius: 8,
      padding: '18px 14px', textAlign: 'center',
      borderTop: `3px solid ${color || '#1976d2'}`,
    }}>
      <div style={{ fontSize: '1.7rem', fontWeight: 700, color: color || '#1976d2' }}>{value}</div>
      <div style={{ fontSize: '0.78rem', color: '#666', marginTop: 4 }}>{label}</div>
      {subtitle && <div style={{ fontSize: '0.7rem', color: '#999', marginTop: 2 }}>{subtitle}</div>}
    </div>
  )
}

// -- Mini progress bar -----------------------------------------------------

function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div style={{ background: '#eee', borderRadius: 4, height: 8, width: '100%' }}>
      <div style={{ background: color, borderRadius: 4, height: 8, width: `${pct}%`, transition: 'width 0.3s' }} />
    </div>
  )
}

// -- Main component --------------------------------------------------------

export default function Dashboard() {
  const [risk, setRisk] = useState<RiskTrendsData | null>(null)
  const [usage, setUsage] = useState<UsageStatsData | null>(null)
  const [assets, setAssets] = useState<AssetItem[]>([])
  const [syncJobs, setSyncJobs] = useState<Array<{ id: string; status: string; error?: string }>>([])
  const [watchCount, setWatchCount] = useState(0)
  const [staleCount, setStaleCount] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getRiskTrends().catch(() => null),
      getUsagePopularity().catch(() => null),
      getLifecycleAnalytics(90).catch(() => null),
      listAssets({ page: '1', page_size: '1000' }).catch(() => null),
      listSyncJobs().catch(() => null),
      getWatchTargets().catch(() => null),
    ]).then(([_risk, _usage, _lifecycle, _asets, _jobs, _watch]) => {
      if (_risk) setRisk(_risk.data)
      if (_usage) setUsage(_usage.data)
      if (_lifecycle) setStaleCount(_lifecycle.data.count ?? 0)
      if (_asets) setAssets((_asets.data as { assets?: AssetItem[] }).assets ?? [])
      if (_jobs) setSyncJobs((_jobs.data as { jobs?: Array<{ id: string; status: string; error?: string }> }).jobs ?? [])
      if (_watch) setWatchCount(((_watch.data as { targets?: unknown[] }).targets ?? []).length)
    }).catch(e => setError((e as Error).message))
     .finally(() => setLoading(false))
  }, [])

  // Derived stats
  const stats = useMemo(() => {
    const totalSize = assets.reduce((sum, a) => sum + (a.size || 0), 0)
    const bySource: Record<string, number> = {}
    const byType: Record<string, number> = {}
    assets.forEach(a => {
      const src = a.source || 'unknown'
      const typ = a.repo_type || 'unknown'
      bySource[src] = (bySource[src] || 0) + 1
      byType[typ] = (byType[typ] || 0) + 1
    })
    const synced = syncJobs.filter(j => j.status === 'synced').length
    const failed = syncJobs.filter(j => j.status === 'failed').length
    const syncing = syncJobs.filter(j => j.status === 'syncing').length
    return { totalSize, bySource, byType, synced, failed, syncing }
  }, [assets, syncJobs])

  const fmtSize = (bytes: number) => {
    if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`
    if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`
    if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(1)} KB`
    return `${bytes} B`
  }

  const riskMax = risk ? Math.max(risk.total_findings, 1) : 1

  return (
    <div>
      <h2>Dashboard</h2>
      {loading && <p style={{ color: '#999' }}>Loading...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {/* KPI tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(155px, 1fr))', gap: 10, marginBottom: 20 }}>
        <StatTile label="Catalog Assets" value={assets.length} color="#1976d2" />
        <StatTile label="Total Size" value={fmtSize(stats.totalSize)} color="#388e3c" />
        <StatTile label="Sync Jobs" value={syncJobs.length} color="#f57c00"
          subtitle={`${stats.synced} done · ${stats.syncing} running · ${stats.failed} failed`} />
        <StatTile label="Watch Targets" value={watchCount} color="#7b1fa2" />
        <StatTile label="Stale Assets" value={staleCount !== null ? staleCount : '-'} color="#c62828"
          subtitle="&gt; 90 days" />
        <StatTile label="Sources" value={Object.keys(stats.bySource).length} color="#00838f"
          subtitle={Object.entries(stats.bySource).map(([k, v]) => `${k}:${v}`).join(' · ')} />
      </div>

      {/* Main grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>

        {/* Risk Trends */}
        {risk && (
          <div style={cardStyle}>
            <h4 style={{ margin: '0 0 12px' }}>Risk Trends ({risk.period})</h4>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ color: '#f44336', fontWeight: 600 }}>High: {risk.high_severity}</span>
              <span style={{ color: '#ff9800', fontWeight: 600 }}>Med: {risk.medium_severity}</span>
              <span style={{ color: '#4caf50', fontWeight: 600 }}>Low: {risk.low_severity}</span>
            </div>
            <MiniBar value={risk.high_severity} max={riskMax} color="#f44336" />
            <div style={{ margin: '6px 0' }}><MiniBar value={risk.medium_severity} max={riskMax} color="#ff9800" /></div>
            <MiniBar value={risk.low_severity} max={riskMax} color="#4caf50" />
            <p style={{ marginTop: 10, fontSize: '0.82rem', color: '#666' }}>
              Trend: <strong>{risk.trend_direction}</strong>
            </p>
          </div>
        )}

        {/* Asset Distribution */}
        <div style={cardStyle}>
          <h4 style={{ margin: '0 0 12px' }}>Asset Distribution</h4>
          {assets.length === 0 ? <p style={{ color: '#999' }}>No assets cataloged</p> : (
            <>
              <p style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: 6 }}>By Source</p>
              {Object.entries(stats.bySource).sort(([,a], [,b]) => b - a).map(([src, count]) => (
                <div key={src} style={{ marginBottom: 5 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                    <span>{src}</span><span>{count}</span>
                  </div>
                  <MiniBar value={count} max={assets.length} color="#1976d2" />
                </div>
              ))}
              <p style={{ fontSize: '0.82rem', fontWeight: 600, margin: '10px 0 6px' }}>By Type</p>
              {Object.entries(stats.byType).sort(([,a], [,b]) => b - a).map(([typ, count]) => (
                <div key={typ} style={{ marginBottom: 5 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                    <span>{typ}</span><span>{count}</span>
                  </div>
                  <MiniBar value={count} max={assets.length} color="#388e3c" />
                </div>
              ))}
            </>
          )}
        </div>

        {/* Top Assets */}
        {usage && usage.assets.length > 0 && (
          <div style={cardStyle}>
            <h4 style={{ margin: '0 0 12px' }}>Top Assets (Popularity)</h4>
            <table style={{ width: '100%', fontSize: '0.82rem' }}>
              <thead><tr>
                <th style={thStyle}>Asset</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Downloads</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Score</th>
              </tr></thead>
              <tbody>
                {usage.assets.slice(0, 8).map(a => (
                  <tr key={a.asset_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={tdStyle}><code style={{ fontSize: '0.76rem' }}>{a.asset_id}</code></td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{a.download_count}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
                      <span style={{
                        color: a.popularity_score > 0.7 ? '#2e7d32' : a.popularity_score > 0.3 ? '#f57c00' : '#999',
                        fontWeight: 600,
                      }}>{(a.popularity_score * 100).toFixed(0)}%</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Sync Jobs */}
        <div style={cardStyle}>
          <h4 style={{ margin: '0 0 12px' }}>Sync Jobs</h4>
          {syncJobs.length === 0 ? <p style={{ color: '#999' }}>No sync jobs yet</p> : (
            <table style={{ width: '100%', fontSize: '0.82rem' }}>
              <thead><tr>
                <th style={thStyle}>Job ID</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Error</th>
              </tr></thead>
              <tbody>
                {syncJobs.slice(0, 6).map(j => (
                  <tr key={j.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={tdStyle}><code style={{ fontSize: '0.75rem' }}>{j.id}</code></td>
                    <td style={tdStyle}>
                      <span style={{
                        display: 'inline-block', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem',
                        background: j.status === 'synced' ? '#e8f5e9' : j.status === 'failed' ? '#ffebee' : j.status === 'syncing' ? '#fff3e0' : '#f5f5f5',
                        color: j.status === 'synced' ? '#2e7d32' : j.status === 'failed' ? '#c62828' : j.status === 'syncing' ? '#e65100' : '#666',
                      }}>{j.status}</span>
                    </td>
                    <td style={{ ...tdStyle, color: '#c62828', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {j.error || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Catalog Assets */}
        <div style={cardStyle}>
          <h4 style={{ margin: '0 0 12px' }}>Catalog Assets</h4>
          {assets.length === 0 ? <p style={{ color: '#999' }}>No assets cataloged</p> : (
            <table style={{ width: '100%', fontSize: '0.82rem' }}>
              <thead><tr>
                <th style={thStyle}>Asset ID</th>
                <th style={thStyle}>Source</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Size</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Files</th>
              </tr></thead>
              <tbody>
                {assets.slice(0, 8).map(a => (
                  <tr key={a.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={tdStyle}><code style={{ fontSize: '0.75rem' }}>{a.id}</code></td>
                    <td style={tdStyle}>{a.source || '-'}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{fmtSize(a.size || 0)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{a.file_count ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </div>
  )
}

// -- shared inline styles --------------------------------------------------

const cardStyle: React.CSSProperties = {
  padding: 16, background: '#fff', border: '1px solid #e0e0e0',
  borderRadius: 8,
}

const thStyle: React.CSSProperties = {
  textAlign: 'left', padding: '6px 4px', borderBottom: '2px solid #e0e0e0',
  fontSize: '0.76rem', color: '#666', fontWeight: 600,
}

const tdStyle: React.CSSProperties = {
  padding: '6px 4px', fontSize: '0.82rem',
}
