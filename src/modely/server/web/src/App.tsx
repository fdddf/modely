import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import AssetList from './pages/AssetList'
import AssetDetail from './pages/AssetDetail'
import SyncJobs from './pages/SyncJobs'
import Snapshots from './pages/Snapshots'
import CIGate from './pages/CIGate'
import Tokens from './pages/Tokens'
import Search from './pages/Search'
import Dashboard from './pages/Dashboard'
import Watch from './pages/Watch'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/assets" replace />} />
        <Route path="/assets" element={<AssetList />} />
        <Route path="/assets/:id" element={<AssetDetail />} />
        <Route path="/sync-jobs" element={<SyncJobs />} />
        <Route path="/snapshots" element={<Snapshots />} />
        <Route path="/ci-gate" element={<CIGate />} />
        <Route path="/tokens" element={<Tokens />} />
        <Route path="/search" element={<Search />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/watch" element={<Watch />} />
      </Routes>
    </Layout>
  )
}
