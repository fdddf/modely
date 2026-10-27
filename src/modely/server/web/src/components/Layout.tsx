import { Link, useLocation } from 'react-router-dom'

const nav = [
  { to: '/assets', label: 'Assets' },
  { to: '/watch', label: 'Watch' },
  { to: '/sync-jobs', label: 'Sync Jobs' },
  { to: '/snapshots', label: 'Snapshots' },
  { to: '/ci-gate', label: 'CI Gate' },
  { to: '/tokens', label: 'Tokens' },
  { to: '/search', label: 'Search' },
  { to: '/dashboard', label: 'Dashboard' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const loc = useLocation()
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <nav style={{ width: 200, background: '#1a1a2e', color: '#eee', padding: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>modely-web</h3>
        {nav.map(n => (
          <Link key={n.to} to={n.to} style={{
            display: 'block', padding: '0.5rem', color: loc.pathname.startsWith(n.to) ? '#00d4ff' : '#ccc', textDecoration: 'none',
          }}>{n.label}</Link>
        ))}
      </nav>
      <main style={{ flex: 1, padding: '2rem', background: '#f5f5f5' }}>
        {children}
      </main>
    </div>
  )
}
