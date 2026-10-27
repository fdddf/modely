import { useState, useEffect } from 'react'
import { createSyncJob, getSyncJob, getSyncLogs, listSyncJobs } from '../api/client'
import type { SyncJobData } from '../api/types'

export default function SyncJobs() {
  const [jobs, setJobs] = useState<SyncJobData[]>([])
  const [targetId, setTargetId] = useState('')
  const [resource, setResource] = useState('hf://models/test/model')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const loadJobs = async () => {
    setLoading(true)
    try {
      const r = await listSyncJobs()
      setJobs(r.data.jobs || [])
    } catch (e: unknown) { /* no jobs yet */ }
    finally { setLoading(false) }
  }

  useEffect(() => { loadJobs() }, [])

  // Auto-refresh when there are syncing jobs
  useEffect(() => {
    if (jobs.some(j => j.status === 'syncing')) {
      const t = setInterval(loadJobs, 2000)
      return () => clearInterval(t)
    }
  }, [jobs])

  const retry = async (j: SyncJobData) => {
    try {
      const r = await createSyncJob({ target_id: j.target_id, resource: j.resource })
      setJobs(prev => [r.data, ...prev])
      setError('')
    } catch (e: unknown) { setError((e as Error).message) }
  }

  const create = async () => {
    try {
      const r = await createSyncJob({ target_id: targetId || 'target-1', resource })
      setJobs(prev => [r.data, ...prev])
    } catch (e: unknown) { setError((e as Error).message) }
  }

  const [selectedJob, setSelectedJob] = useState<SyncJobData | null>(null)
  const [logs, setLogs] = useState('')

  const viewLogs = async (id: string) => {
    try {
      const j = await getSyncJob(id)
      setSelectedJob(j.data)
      const lines: string[] = []

      // Basic job info
      lines.push(`Job ID:     ${j.data.id}`)
      lines.push(`Target:     ${j.data.target_id || '-'}`)
      lines.push(`Resource:   ${j.data.resource || '-'}`)
      lines.push(`Status:     ${j.data.status}`)
      lines.push(`Attempts:   ${j.data.attempts}`)

      // Error info (when failed)
      if (j.data.error) {
        lines.push(`\n── Error ──`)
        lines.push(j.data.error)
      }

      // Worker result details (from metadata)
      const wr = (j.data.metadata as Record<string,unknown> | null)?.result as Record<string,unknown> | null
      if (wr) {
        if (wr.asset_id) lines.push(`\nAsset ID:   ${wr.asset_id}`)
        if (wr.version_id) lines.push(`Version ID:  ${wr.version_id}`)
        if (wr.local_path) lines.push(`Local Path:  ${wr.local_path}`)
        if (wr.error && wr.error !== j.data.error) {
          lines.push(`\n── Worker Error ──`)
          lines.push(String(wr.error))
        }

        const manifest = wr.manifest as Record<string,unknown> | null
        if (manifest) {
          lines.push(`\n── Manifest ──`)
          if (manifest.local_path) lines.push(`Storage:     ${manifest.local_path}`)
          const files = wr.files as Array<Record<string,unknown>> | null
          if (files && files.length > 0) {
            lines.push(`Files:       ${files.length}`)
            for (const f of files) {
              const lp = (f.local_path as string) || (f.uri as string) || '-'
              lines.push(`  ${f.path}  →  ${lp}`)
            }
          }
        }
      }

      // Fallback: raw JSON dump if nothing parsed
      if (lines.length <= 5 && !j.data.error) {
        lines.push('')
        lines.push(JSON.stringify(j.data, null, 2))
      }

      setLogs(lines.join('\n'))
    } catch (e: unknown) { setError((e as Error).message) }
  }

  return (
    <div>
      <h2>Sync Jobs</h2>
      <div style={{ marginBottom: 16 }}>
        <input placeholder="Target ID" value={targetId} onChange={e => setTargetId(e.target.value)} style={{ marginRight: 8 }} />
        <input placeholder="Resource URI" value={resource} onChange={e => setResource(e.target.value)} style={{ marginRight: 8 }} />
        <button onClick={create}>Create Sync Job</button>
      </div>
      {loading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {!loading && jobs.length === 0 && (
        <p style={{ color: '#999', marginBottom: 16 }}>No sync jobs yet. Create one below.</p>
      )}
      {!loading && jobs.length > 0 && (
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>{['ID','Target','Resource','Status','Attempts','Error','Actions'].map(h => <th key={h} style={{textAlign:'left',padding:8,borderBottom:'1px solid #ddd'}}>{h}</th>)}</tr></thead>
        <tbody>{jobs.map(j => (
          <tr key={j.id}>
            <td style={{padding:8,borderBottom:'1px solid #eee',cursor:'pointer'}} onClick={() => viewLogs(j.id)}>{j.id}</td>
            <td style={{padding:8,cursor:'pointer'}} onClick={() => viewLogs(j.id)}>{j.target_id}</td>
            <td style={{padding:8,cursor:'pointer',fontSize:'0.82rem'}} onClick={() => viewLogs(j.id)}><code>{j.resource || '-'}</code></td>
            <td style={{padding:8,cursor:'pointer'}} onClick={() => viewLogs(j.id)}>{j.status}</td>
            <td style={{padding:8,cursor:'pointer'}} onClick={() => viewLogs(j.id)}>{j.attempts}</td>
            <td style={{padding:8,color:j.error?'red':'#999',cursor:'pointer',maxWidth:280,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} onClick={() => viewLogs(j.id)} title={j.error || ''}>{j.error ? j.error.slice(0, 120) : '-'}</td>
            <td style={{padding:8}}>
              <button onClick={(e) => { e.stopPropagation(); retry(j) }}
                style={{ padding: '4px 10px', fontSize: '0.75rem', background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                Retry
              </button>
            </td>
          </tr>
        ))}</tbody>
      </table>
      )}
      {selectedJob && (
        <div style={{ marginTop: 16, padding: 16, background: '#fff', border: '1px solid #ddd' }}>
          <h4>Logs for {selectedJob.id}</h4>
          <pre style={{ fontSize: '0.85em', maxHeight: 300, overflow: 'auto' }}>{logs}</pre>
        </div>
      )}
    </div>
  )
}
