import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { search, encodeAssetId } from '../api/client'
import type { SearchResultItem, SearchData } from '../api/types'

// Helpers ---------------------------------------------------------------

function formatScore(n: number): string {
  return n.toFixed(2)
}

export default function Search() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [facets, setFacets] = useState<SearchData['facets']>({})
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({})

  const run = useCallback(async (overrideFilters?: Record<string, string>) => {
    setLoading(true); setError('')
    try {
      const filters = overrideFilters ?? activeFilters
      const r = await search(q || '*', filters)
      setResults(r.data.results)
      setTotal(r.data.total)
      setFacets(r.data.facets || {})
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setLoading(false) }
  }, [q, activeFilters])

  const toggleFacet = (facetKey: string, value: string) => {
    const current = activeFilters[facetKey]
    let next: Record<string, string>
    if (current === value) {
      next = { ...activeFilters }
      delete next[facetKey]
    } else {
      next = { ...activeFilters, [facetKey]: value }
    }
    setActiveFilters(next)
    run(next)
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 20 }}>
      {/* -- Sidebar: facets ------------------------------------------------ */}
      <aside style={{ fontSize: '0.82rem' }}>
        <h4 style={{ margin: '0 0 10px', color: '#1976d2', textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.5px' }}>Refine</h4>

        {(['source', 'repo_type', 'license', 'tags'] as const).map(fk => {
          const items = facets[fk]
          if (!items || items.length === 0) return null
          return (
            <div key={fk} style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 6, color: '#333' }}>{fk}</div>
              {items.map(item => {
                const active = activeFilters[fk] === item.value
                return (
                  <div
                    key={item.value}
                    onClick={() => toggleFacet(fk, item.value)}
                    style={{
                      cursor: 'pointer', padding: '3px 6px', borderRadius: 4, marginBottom: 2,
                      background: active ? '#e3f2fd' : 'transparent',
                      color: active ? '#1976d2' : '#555',
                      fontWeight: active ? 700 : 400,
                      display: 'flex', justifyContent: 'space-between',
                    }}>
                    <span>{item.value}</span>
                    <span style={{ color: '#999', fontSize: '0.72rem', marginLeft: 8 }}>{item.count}</span>
                  </div>
                )
              })}
            </div>
          )
        })}

        {Object.keys(activeFilters).length > 0 && (
          <button onClick={() => {
            setActiveFilters({})
            run({})
          }} style={{ background: 'transparent', color: '#f44336', border: '1px solid #f44336', padding: '4px 10px', borderRadius: 4, fontSize: '0.75rem', cursor: 'pointer', marginTop: 8 }}>
            Clear all filters
          </button>
        )}
      </aside>

      {/* -- Main: search + results ----------------------------------------- */}
      <div>
        <h2>Search</h2>
        <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
          <input
            placeholder="Search assets by name, tag, license..."
            value={q} onChange={e => setQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
            style={{ flex: 1, padding: '10px 14px', border: '1px solid #ccc', borderRadius: 8, fontSize: '0.95rem' }}
            autoFocus
          />
          <button onClick={() => run()} style={{ padding: '10px 20px', borderRadius: 8, fontWeight: 600 }}>
            Search
          </button>
        </div>

        {loading && <p>Searching...</p>}
        {error && <p style={{ color: 'red' }}>{error}</p>}

        {!loading && !error && (
          <>
            {total > 0 && (
              <p style={{ color: '#666', fontSize: '0.85rem', marginBottom: 10 }}>
                {total} result{total !== 1 ? 's' : ''}
                {q && q !== '*' ? ` for "${q}"` : ''}
                {activeFilters.source ? ` · source=${activeFilters.source}` : ''}
                {activeFilters.license ? ` · license=${activeFilters.license}` : ''}
                {activeFilters.repo_type ? ` · type=${activeFilters.repo_type}` : ''}
                {activeFilters.tags ? ` · tag=${activeFilters.tags}` : ''}
              </p>
            )}

            {results.length === 0 ? (
              <p style={{ color: '#999' }}>No results found. Try a different search term or clear filters.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#f9f9f9' }}>
                    {['Asset','Source','Type','License','Tags','Score'].map(h => (
                      <th key={h} style={{textAlign:'left',padding:10,borderBottom:'2px solid #ddd',fontSize:'0.8rem',color:'#666'}}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.map(r => (
                    <tr key={r.asset_id} style={{ borderBottom: '1px solid #eee' }}>
                      <td style={{padding:10,fontSize:'0.84rem'}}>
                        <Link
                          to={`/assets/${encodeAssetId(r.asset_id)}`}
                        >
                          {r.repo_id || r.asset_id}
                        </Link>
                      </td>
                      <td style={{padding:10,fontSize:'0.84rem'}}><code>{r.source}</code></td>
                      <td style={{padding:10,fontSize:'0.84rem'}}>{r.repo_type}</td>
                      <td style={{padding:10,fontSize:'0.84rem'}}>{r.license || '-'}</td>
                      <td style={{padding:10}}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, maxWidth: 200 }}>
                          {(r.tags || []).slice(0, 3).map(t => (
                            <span key={t} style={{ background: '#e3f2fd', color: '#1976d2', padding: '1px 6px', borderRadius: 10, fontSize: '0.68rem' }}>{t}</span>
                          ))}
                        </div>
                      </td>
                      <td style={{padding:10,fontSize:'0.82rem',fontWeight:600,color: r.score > 0 ? '#1976d2' : '#999'}}>
                        {formatScore(r.score)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </div>
  )
}
