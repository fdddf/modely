import { useState, useEffect } from 'react'
import { listSnapshots, promoteSnapshot, rollbackSnapshot } from '../api/client'
import type { SnapshotData } from '../api/types'

export default function Snapshots() {
  const [snaps, setSnaps] = useState<SnapshotData[]>([])
  const [assetId, setAssetId] = useState('')
  const [error, setError] = useState('')

  const fetch = async () => {
    try {
      const r = await listSnapshots(assetId || undefined)
      setSnaps(r.data.snapshots)
    } catch (e: unknown) { setError((e as Error).message) }
  }

  useEffect(() => { fetch() }, [])

  const promote = async (id: string) => {
    const ch = prompt('Channel name (dev/staging/production)?', 'production')
    if (!ch) return
    try { await promoteSnapshot(id, ch); fetch() } catch (e: unknown) { setError((e as Error).message) }
  }

  const rollback = async (id: string) => {
    const reason = prompt('Rollback reason?', 'bug found')
    if (!reason) return
    try { await rollbackSnapshot(id, reason); fetch() } catch (e: unknown) { setError((e as Error).message) }
  }

  return (
    <div>
      <h2>Snapshots</h2>
      <div style={{ marginBottom: 16 }}>
        <input placeholder="Filter by Asset ID" value={assetId} onChange={e => setAssetId(e.target.value)} style={{ marginRight: 8 }} />
        <button onClick={fetch}>Refresh</button>
      </div>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>{['ID','Asset','Version','Channel','Created','Actions'].map(h => <th key={h} style={{textAlign:'left',padding:8,borderBottom:'1px solid #ddd'}}>{h}</th>)}</tr></thead>
        <tbody>{snaps.map(s => (
          <tr key={s.id}>
            <td style={{padding:8,borderBottom:'1px solid #eee'}}>{s.id}</td>
            <td style={{padding:8}}>{s.asset_id}</td>
            <td style={{padding:8}}>{s.version_id}</td>
            <td style={{padding:8}}>{s.channel}</td>
            <td style={{padding:8}}>{s.created_at}</td>
            <td style={{padding:8}}>
              <button onClick={() => promote(s.id)} style={{ marginRight: 4 }}>Promote</button>
              <button onClick={() => rollback(s.id)}>Rollback</button>
            </td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}
