import React from 'react'

/** Facet definition: field name + human label + dropdown options */
export interface FacetDef {
  field: string;
  label: string;
  options: string[];
}

export default function FilterBar({ onFilter, facets }: {
  onFilter: (f: Record<string, string>) => void;
  facets: FacetDef[];
}) {
  const [filter, setFilter] = React.useState<Record<string, string>>({})

  const set = (field: string, value: string) => {
    const next = { ...filter, [field]: value }
    if (!value) delete next[field]
    setFilter(next)
    onFilter(next)
  }

  const clearAll = () => {
    setFilter({})
    onFilter({})
  }

  const hasAny = Object.values(filter).some(v => v)

  return (
    <div style={{ marginBottom: 0, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'stretch' }}>
      {facets.map(f => (
        <select
          key={f.field}
          value={filter[f.field] || ''}
          onChange={e => set(f.field, e.target.value)}
          style={{ padding: '6px 8px', border: '1px solid #ccc', borderRadius: 4, fontSize: '0.82rem', minWidth: 120 }}
        >
          <option value="">{f.label}</option>
          {f.options.map(o => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      ))}
      {hasAny && (
        <button onClick={clearAll} style={{ background: 'transparent', color: '#f44336', border: '1px solid #f44336', padding: '6px 12px', borderRadius: 4, fontSize: '0.8rem' }}>
          Clear
        </button>
      )}
    </div>
  )
}
