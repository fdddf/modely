import { useState, useEffect } from 'react'
import { listServiceAccounts, createServiceAccount, getServiceAccount, createToken } from '../api/client'
import type { ServiceAccountData, TokenCreateData } from '../api/types'

export default function Tokens() {
  const [sas, setSas] = useState<ServiceAccountData[]>([])
  const [name, setName] = useState('')
  const [roles, setRoles] = useState('Developer')
  const [token, setToken] = useState<TokenCreateData | null>(null)
  const [error, setError] = useState('')

  const fetch = async () => {
    try {
      const r = await listServiceAccounts()
      setSas(r.data.service_accounts)
    } catch (e: unknown) { setError((e as Error).message) }
  }

  useEffect(() => { fetch() }, [])

  const create = async () => {
    if (!name) return
    try { await createServiceAccount(name, roles.split(',').map(s => s.trim())); fetch(); setName('') }
    catch (e: unknown) { setError((e as Error).message) }
  }

  const issueToken = async (saId: string) => {
    const scopes = prompt('Scopes (comma-separated)?', 'asset:read,asset:download')
    if (!scopes) return
    try {
      const r = await createToken(saId, scopes.split(',').map(s => s.trim()))
      setToken(r.data)
    } catch (e: unknown) { setError((e as Error).message) }
  }

  return (
    <div>
      <h2>Service Accounts & Tokens</h2>
      <div style={{ marginBottom: 16 }}>
        <input placeholder="SA Name" value={name} onChange={e => setName(e.target.value)} style={{ marginRight: 8 }} />
        <input placeholder="Roles (comma-sep)" value={roles} onChange={e => setRoles(e.target.value)} style={{ marginRight: 8 }} />
        <button onClick={create}>Create SA</button>
      </div>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {token && (
        <div style={{ padding: 16, background: '#e8f5e9', border: '1px solid #4caf50', marginBottom: 16 }}>
          <strong>Token Created!</strong> <code>{token.token || '(secret shown once)'}</code>
          <p>Prefix: {token.prefix} | Expires: {token.expires_at} | ID: {token.id}</p>
          <p style={{ color: '#f44336', fontSize: '0.85em' }}>Copy this token now — it will not be shown again.</p>
        </div>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>{['ID','Name','Owner','Roles','Status','Actions'].map(h => <th key={h} style={{textAlign:'left',padding:8,borderBottom:'1px solid #ddd'}}>{h}</th>)}</tr></thead>
        <tbody>{sas.map(sa => (
          <tr key={sa.id}>
            <td style={{padding:8,borderBottom:'1px solid #eee'}}>{sa.id}</td>
            <td style={{padding:8}}>{sa.name}</td>
            <td style={{padding:8}}>{sa.owner_id}</td>
            <td style={{padding:8}}>{sa.roles.join(', ')}</td>
            <td style={{padding:8}}>{sa.status}</td>
            <td style={{padding:8}}><button onClick={() => issueToken(sa.id)}>Issue Token</button></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}
