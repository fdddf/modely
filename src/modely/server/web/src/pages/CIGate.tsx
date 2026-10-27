import { useState } from 'react'
import { evaluateCIGate } from '../api/client'
import type { CIGateData } from '../api/types'

export default function CIGate() {
  const [path, setPath] = useState('')
  const [profile, setProfile] = useState('production')
  const [result, setResult] = useState<CIGateData | null>(null)
  const [error, setError] = useState('')

  const run = async () => {
    if (!path) return
    setError(''); setResult(null)
    try {
      const r = await evaluateCIGate(path, profile)
      setResult(r.data)
    } catch (e: unknown) { setError((e as Error).message) }
  }

  return (
    <div>
      <h2>CI Gate</h2>
      <div style={{ marginBottom: 16 }}>
        <input placeholder="Lockfile path" value={path} onChange={e => setPath(e.target.value)} style={{ marginRight: 8, width: 300 }} />
        <select value={profile} onChange={e => setProfile(e.target.value)} style={{ marginRight: 8 }}>
          <option value="production">Production</option>
          <option value="staging">Staging</option>
          <option value="dev">Dev</option>
        </select>
        <button onClick={run}>Evaluate</button>
      </div>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {result && (
        <div style={{ padding: 16, background: result.status === 'passed' ? '#e8f5e9' : result.status === 'failed' ? '#ffebee' : '#fff3e0', border: '1px solid #ddd' }}>
          <h4>Status: {result.status.toUpperCase()} (exit: {result.exit_code})</h4>
          <p>Profile: {result.profile} | Resources: {result.summary.total} (pass: {result.summary.passed}, fail: {result.summary.failed}, warn: {result.summary.warning})</p>
          {result.resources.map(r => (
            <div key={r.uri} style={{ marginBottom: 8, padding: 8, background: r.status === 'failed' ? '#ffcdd2' : r.status === 'warning' ? '#fff9c4' : '#c8e6c9' }}>
              <strong>{r.uri}</strong> — {r.status}
              {r.errors.map((e,i) => <p key={i} style={{color:'red',margin:0}}>{e}</p>)}
              {r.warnings.map((w,i) => <p key={i} style={{color:'#f57f17',margin:0}}>{w}</p>)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
