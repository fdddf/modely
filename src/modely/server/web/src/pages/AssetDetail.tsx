import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getAsset, getAssetFiles, getDownloadUrl, getFilePreview, createSnapshot } from '../api/client'
import type { AssetItem, AssetFile, DownloadUrlData, FilePreviewData } from '../api/types'

// -- helpers ----------------------------------------------------------------

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function downloadFileContent(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.split('/').pop() || filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

const FILE_TYPE_COLORS: Record<string, string> = {
  card: '#1976d2',
  config: '#4caf50',
  tokenizer: '#ff9800',
  safetensors: '#f44336',
  gguf: '#9c27b0',
  weights: '#e91e63',
  metadata: '#607d8b',
  other: '#999',
}

function fileTypeBadge(ft: string) {
  return (
    <span style={{
      background: FILE_TYPE_COLORS[ft] || '#999',
      color: '#fff',
      padding: '2px 8px',
      borderRadius: 10,
      fontSize: '0.7rem',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.5px',
    }}>{ft}</span>
  )
}

function riskLevelColor(level: string): string {
  switch (level) {
    case 'high': return '#f44336'
    case 'medium': return '#ff9800'
    case 'low': return '#4caf50'
    default: return '#999'
  }
}

function policyStatusColor(status: string): string {
  switch (status) {
    case 'blocked': return '#f44336'
    case 'require_approval': return '#ff9800'
    case 'warn': return '#f57f17'
    case 'allowed': return '#4caf50'
    default: return '#999'
  }
}

// -- card sub-component -----------------------------------------------------

function MetaCard({ title, rows }: { title: string; rows: [string, string | number | React.ReactNode][] }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #ddd', borderRadius: 8, padding: 16 }}>
      <h4 style={{ margin: '0 0 10px 0', color: '#1976d2', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.6px' }}>{title}</h4>
      <table style={{ width: '100%' }}>
        <tbody>
          {rows.map(([key, value]) => (
            <tr key={key}>
              <td style={{ fontWeight: 600, padding: '4px 8px', color: '#666', width: '35%', fontSize: '0.82rem', verticalAlign: 'top' }}>{key}</td>
              <td style={{ padding: '4px 8px', fontSize: '0.84rem', wordBreak: 'break-word' }}>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// -- file tree component ---------------------------------------------------

interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children: TreeNode[];
  file?: AssetFile;
  size?: number;
}

function buildTree(files: AssetFile[]): TreeNode[] {
  const root: TreeNode[] = []
  for (const f of files) {
    const parts = f.path.split('/')
    let level = root
    for (let i = 0; i < parts.length; i++) {
      const isLast = i === parts.length - 1
      const name = parts[i]
      const fullPath = parts.slice(0, i + 1).join('/')
      let node = level.find(n => n.name === name)
      if (!node) {
        node = {
          name,
          path: fullPath,
          isDir: !isLast,
          children: [],
          file: isLast ? f : undefined,
          size: isLast ? f.size : undefined,
        }
        level.push(node)
      }
      if (!isLast) level = node.children
    }
  }
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    for (const n of nodes) sortNodes(n.children)
  }
  sortNodes(root)
  return root
}

function FileTree({ files, onFileClick, selectedFile }: {
  files: AssetFile[];
  onFileClick: (f: AssetFile) => void;
  selectedFile: string | null;
}) {
  const tree = buildTree(files)
  return (
    <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.82rem' }}>
      {tree.map(n => <TreeNodeRow key={n.path} node={n} depth={0} onFileClick={onFileClick} selectedFile={selectedFile} />)}
    </div>
  )
}

function TreeNodeRow({ node, depth, onFileClick, selectedFile }: {
  node: TreeNode;
  depth: number;
  onFileClick: (f: AssetFile) => void;
  selectedFile: string | null;
}) {
  const [expanded, setExpanded] = useState(depth < 2)
  const indent = depth * 20

  if (node.isDir) {
    const totalSize = sumSize(node)
    const itemCount = node.children.length + countFiles(node)
    return (
      <div>
        <div
          onClick={() => setExpanded(!expanded)}
          style={{
            cursor: 'pointer', padding: '4px 6px', borderRadius: 4, marginBottom: 1,
            display: 'flex', alignItems: 'center', gap: 6, userSelect: 'none',
          }}
        >
          <span style={{ width: indent, flexShrink: 0 }} />
          <span style={{ fontSize: '0.85rem', width: 16, textAlign: 'center' }}>{expanded ? '▾' : '▸'}</span>
          <span style={{ color: '#1976d2', fontWeight: 600 }}>{node.name}/</span>
          <span style={{ color: '#999', fontSize: '0.72rem', marginLeft: 8 }}>{itemCount} items</span>
          <span style={{ color: '#aaa', fontSize: '0.72rem' }}>· {formatSize(totalSize)}</span>
        </div>
        {expanded && node.children.map(n => (
          <TreeNodeRow key={n.path} node={n} depth={depth + 1} onFileClick={onFileClick} selectedFile={selectedFile} />
        ))}
      </div>
    )
  }

  const f = node.file!
  const isSelected = selectedFile === f.path
  return (
    <div
      onClick={() => onFileClick(f)}
      style={{
        cursor: 'pointer', padding: '3px 6px', borderRadius: 4, marginBottom: 1,
        display: 'flex', alignItems: 'center', gap: 6,
        background: isSelected ? '#e3f2fd' : 'transparent',
      }}
    >
      <span style={{ width: indent, flexShrink: 0 }} />
      <span style={{ width: 16, flexShrink: 0 }} />
      <span style={{ color: '#333', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {node.name}
      </span>
      <span style={{ fontSize: '0.72rem', color: '#666', whiteSpace: 'nowrap', marginRight: 8 }}>{formatSize(f.size)}</span>
      <span style={{ fontSize: '0.72rem', color: '#999', whiteSpace: 'nowrap' }}>{f.mtime ? f.mtime.slice(0, 10) : ''}</span>
    </div>
  )
}

function countFiles(node: TreeNode): number {
  let count = 0
  for (const c of node.children) {
    if (!c.isDir) count += 1; else count += countFiles(c)
  }
  return count
}

function sumSize(node: TreeNode): number {
  let size = 0
  for (const c of node.children) {
    if (!c.isDir) size += c.size || 0
    else size += sumSize(c)
  }
  return size
}

// -- view toggle -----------------------------------------------------------

function ViewToggle({ view, onChange }: { view: string; onChange: (v: 'tree' | 'table') => void }) {
  const btn = (label: string, v: 'tree' | 'table') => (
    <button onClick={() => onChange(v)} style={{
      padding: '4px 10px', fontSize: '0.75rem', fontWeight: 600,
      border: '1px solid #1976d2',
      background: view === v ? '#1976d2' : '#fff',
      color: view === v ? '#fff' : '#1976d2',
      borderRadius: view === v ? 4 : 0,
      borderRightWidth: v === 'table' ? 1 : 0,
      borderTopLeftRadius: v === 'tree' ? 4 : 0,
      borderBottomLeftRadius: v === 'tree' ? 4 : 0,
      borderTopRightRadius: v === 'table' ? 4 : 0,
      borderBottomRightRadius: v === 'table' ? 4 : 0,
      cursor: 'pointer',
    }}>{label}</button>
  )
  return <div style={{ display: 'flex' }}>{btn('Tree', 'tree')}{btn('Table', 'table')}</div>
}

// -- flat file table (GitHub-style) ----------------------------------------

function FlatFileTable({ files, onFileClick, selectedFile }: {
  files: AssetFile[];
  onFileClick: (f: AssetFile) => void;
  selectedFile: string | null;
}) {
  const [dir, setDir] = useState('')
  const [fp, setFp] = useState(1)
  const PER_PAGE = 50

  // Group: directories + files in current dir level
  const dirs = new Set<string>()
  const pageFiles: AssetFile[] = []
  const dirPrefix = dir ? dir + '/' : ''
  for (const f of files) {
    const rest = dir ? f.path.slice(dirPrefix.length) : f.path
    if (!rest || !rest.startsWith(dir ? '' : '')) continue
    // Only match files directly in the current directory
    if (dir && !f.path.startsWith(dirPrefix)) continue
    const rel = dir ? f.path.slice(dirPrefix.length) : f.path
    if (!rel) continue
    const slash = rel.indexOf('/')
    if (slash >= 0) {
      dirs.add(rel.slice(0, slash))  // only the first segment
    } else {
      pageFiles.push(f)
    }
  }
  const sortedDirs = [...dirs].sort()
  const paged = pageFiles.slice((fp - 1) * PER_PAGE, fp * PER_PAGE)
  const totalPages = Math.ceil(pageFiles.length / PER_PAGE)

  const navigateTo = (d: string) => { setDir(dir ? dir + '/' + d : d); setFp(1) }
  const goUp = () => {
    const parts = dir.split('/')
    parts.pop()
    setDir(parts.join('/'))
    setFp(1)
  }

  return (
    <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.82rem' }}>
      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 10, fontSize: '0.8rem', color: '#1976d2' }}>
        <span onClick={() => { setDir(''); setFp(1) }} style={{ cursor: 'pointer' }}>root</span>
        {dir.split('/').filter(Boolean).map((d, i, arr) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: '#ccc' }}>/</span>
            <span onClick={() => { setDir(arr.slice(0, i + 1).join('/')); setFp(1) }} style={{ cursor: 'pointer', fontWeight: i === arr.length - 1 ? 700 : 400 }}>{d}</span>
          </span>
        ))}
      </div>

      {/* Table */}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#f6f8fa', borderBottom: '1px solid #d0d7de' }}>
            <th style={{textAlign:'left',padding:'8px 10px',fontSize:'0.75rem',color:'#57606a',width:28}}></th>
            <th style={{textAlign:'left',padding:'8px 10px',fontSize:'0.75rem',color:'#57606a'}}>Name</th>
            <th style={{textAlign:'right',padding:'8px 10px',fontSize:'0.75rem',color:'#57606a',width:100}}>Size</th>
            <th style={{textAlign:'right',padding:'8px 10px',fontSize:'0.75rem',color:'#57606a',width:140}}>Updated</th>
          </tr>
        </thead>
        <tbody>
          {/* Up/back row */}
          {dir ? (
            <tr onClick={goUp} style={{ cursor: 'pointer', borderBottom: '1px solid #eee' }}>
              <td style={{padding:'6px 10px'}}>📁</td>
              <td style={{padding:'6px 10px',color:'#1976d2',fontWeight:600}}>..</td>
              <td></td><td></td>
            </tr>
          ) : null}
          {/* Directories */}
          {sortedDirs.map(d => {
            const name = d
            return (
              <tr key={d} onClick={() => navigateTo(d)} style={{ cursor: 'pointer', borderBottom: '1px solid #eee' }}>
                <td style={{padding:'6px 10px'}}>📁</td>
                <td style={{padding:'6px 10px',color:'#1976d2',fontWeight:600}}>{name}/</td>
                <td></td><td></td>
              </tr>
            )
          })}
          {/* Files */}
          {paged.map(f => {
            const name = dir ? f.path.slice(dirPrefix.length) : f.path
            return (
              <tr key={f.path}
                onClick={() => onFileClick(f)}
                style={{ cursor: 'pointer', borderBottom: '1px solid #eee', background: selectedFile === f.path ? '#e3f2fd' : undefined }}>
                <td style={{padding:'6px 10px'}}>📄</td>
                <td style={{padding:'6px 10px'}}>{name}</td>
                <td style={{padding:'6px 10px',textAlign:'right',fontSize:'0.75rem',color:'#57606a'}}>{formatSize(f.size)}</td>
                <td style={{padding:'6px 10px',textAlign:'right',fontSize:'0.75rem',color:'#57606a'}}>{f.mtime ? f.mtime.slice(0, 10) : ''}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'center', marginTop: 10 }}>
          <button disabled={fp <= 1} onClick={() => setFp(p => p - 1)} style={_pgBtnStyle(fp <= 1)}>Prev</button>
          <span style={{ fontSize: '0.78rem', color: '#666' }}>{fp} / {totalPages}</span>
          <button disabled={fp >= totalPages} onClick={() => setFp(p => p + 1)} style={_pgBtnStyle(fp >= totalPages)}>Next</button>
        </div>
      )}
    </div>
  )
}

function _pgBtnStyle(disabled: boolean) {
  return {
    padding: '4px 10px', fontSize: '0.78rem', border: 'none', borderRadius: 4,
    background: disabled ? '#eee' : '#1976d2', color: disabled ? '#999' : '#fff',
    cursor: disabled ? 'default' : 'pointer',
  } as React.CSSProperties
}

// -- main component ---------------------------------------------------------

export default function AssetDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [asset, setAsset] = useState<AssetItem | null>(null)
  const [files, setFiles] = useState<AssetFile[]>([])
  const [dl, setDl] = useState<DownloadUrlData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // -- file preview state ---------------------------------------------------
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<FilePreviewData | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [viewMode, setViewMode] = useState<'tree' | 'table'>('tree')
  const [snapshotError, setSnapshotError] = useState('')
  const [snapshotOk, setSnapshotOk] = useState('')
  const [creatingSnapshot, setCreatingSnapshot] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError('')
    Promise.all([getAsset(id), getAssetFiles(id), getDownloadUrl(id)])
      .then(([a, f, d]) => { setAsset(a.data); setFiles(f.data.files); setDl(d.data) })
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [id])

  const handleFileClick = useCallback(async (f: AssetFile) => {
    if (!id) return
    setSelectedFile(f.path)
    setPreviewLoading(true)
    setPreviewError('')
    setPreviewData(null)
    try {
      const res = await getFilePreview(id, f.path)
      setPreviewData(res.data)
    } catch (e) {
      setPreviewError((e as Error).message)
    } finally {
      setPreviewLoading(false)
    }
  }, [id])

  const handleCreateSnapshot = useCallback(async () => {
    if (!id || !asset) return
    const channel = prompt('Channel name (dev/staging/production)?', 'dev')
    if (!channel) return
    setCreatingSnapshot(true)
    setSnapshotError('')
    setSnapshotOk('')
    try {
      // Build a version-like ID from asset fields
      const versionId = `${asset.id}:${asset.revision || 'latest'}`
      // Use checksum as manifest_digest, or fallback to id-based hash
      const manifestDigest = asset.checksum || asset.id
      await createSnapshot({
        asset_id: asset.id,
        version_id: versionId,
        manifest_digest: manifestDigest,
        channel_name: channel,
      })
      setSnapshotOk(`Snapshot created in "${channel}" channel`)
    } catch (e: unknown) {
      setSnapshotError((e as Error).message)
    } finally {
      setCreatingSnapshot(false)
    }
  }, [id, asset])

  // -- render states --------------------------------------------------------
  if (loading) return <p>Loading...</p>
  if (error) return <p style={{ color: 'red' }}>{error}</p>
  if (!asset) return <p>Asset not found</p>

  const gov = asset.governance

  const meta = (asset.metadata || {}) as Record<string, unknown>
  const sourceUrl = (meta.url as string) || ''
  const author = (meta.author as string) || ''
  const lastModified = (meta.last_modified as string) || (meta.updated_at as string) || ''

  // -- metadata sections ----------------------------------------------------
  const identityRows: [string, string | number][] = [
    ['ID', asset.id],
    ['Source', asset.source],
    ['Type', asset.repo_type],
    ['Revision', asset.revision || '-'],
    ['Visibility', asset.visibility],
    ['State', asset.operational_state],
    ...(lastModified ? [['Last Updated', lastModified.slice(0, 10)]] as [string, string][] : []),
  ]

  const sizeRows: [string, string | number][] = [
    ['Size', formatSize(asset.size)],
    ['File Count', asset.file_count],
  ]

  const licenseRows: [string, string | React.ReactNode][] = [
    ['License', asset.license || '-'],
    ['Author', author || '-'],
    ['Tags', asset.tags.length > 0 ? (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {asset.tags.map(tag => (
          <span key={tag} style={{ background: '#e3f2fd', color: '#1976d2', padding: '2px 8px', borderRadius: 12, fontSize: '0.75rem' }}>{tag}</span>
        ))}
      </div>
    ) : '-'],
    ['Source Link', sourceUrl ? (
      <a href={sourceUrl} target="_blank" rel="noopener noreferrer"
        style={{ color: '#1976d2', fontSize: '0.82rem', wordBreak: 'break-all' }}>
        {sourceUrl}
      </a>
    ) : '-'],
  ]

  const riskFromMeta = (meta.risk_level as string) || ''
  const govRisk = gov?.risk_level || riskFromMeta || 'unknown'
  const govStatus = gov?.policy_status || 'not_evaluated'
  const govApproval = gov?.approval_state || 'none'

  const governanceRows: [string, React.ReactNode][] = [
    ['Risk Level',
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span style={{ width: 10, height: 10, borderRadius: 999, background: riskLevelColor(govRisk), display: 'inline-block' }} />
        <span style={{ fontWeight: 700, color: riskLevelColor(govRisk) }}>{govRisk}</span>
      </span>],
    ['Policy Status', <span style={{ fontWeight: 700, color: policyStatusColor(govStatus) }}>{govStatus}</span>],
    ['Approval State', govApproval],
    ['Visibility', asset.visibility],
    ['Operational State',
      <span style={{
        background: asset.operational_state === 'active' ? '#e8f5e9' : '#e3f2fd',
        color: asset.operational_state === 'active' ? '#2e7d32' : '#1565c0',
        padding: '2px 8px', borderRadius: 10, fontSize: '0.75rem', fontWeight: 700,
      }}>{asset.operational_state}</span>],
  ]

  return (
    <div>
      {/* -- Header -------------------------------------------------------- */}
      <button
        onClick={() => navigate('/assets')}
        style={{ marginBottom: 12, background: 'transparent', color: '#1976d2', border: '1px solid #1976d2', padding: '4px 12px', borderRadius: 4, cursor: 'pointer' }}
      >← Back to Assets</button>

      {/* Snapshot feedback */}
      {snapshotError && <div style={{ color: '#f44336', marginBottom: 10, padding: '8px 12px', background: '#ffeef0', borderRadius: 6, fontSize: '0.85rem' }}>{snapshotError}</div>}
      {snapshotOk && <div style={{ color: '#2e7d32', marginBottom: 10, padding: '8px 12px', background: '#e8f5e9', borderRadius: 6, fontSize: '0.85rem' }}>{snapshotOk}</div>}

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0 }}>{asset.repo_id}</h2>
        <span style={{ background: '#1976d2', color: '#fff', padding: '2px 10px', borderRadius: 4, fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase' }}>{asset.source}</span>
        <span style={{ background: '#00d4ff', color: '#1a1a2e', padding: '2px 10px', borderRadius: 4, fontSize: '0.72rem', fontWeight: 700 }}>{asset.repo_type}</span>
        <span style={{
          background: asset.operational_state === 'active' ? '#e8f5e9' : '#e3f2fd',
          color: asset.operational_state === 'active' ? '#2e7d32' : '#1565c0',
          padding: '2px 10px', borderRadius: 10, fontSize: '0.72rem', fontWeight: 700,
        }}>{asset.operational_state}</span>
        {asset.license && (
          <span style={{ background: '#e8f5e9', color: '#2e7d32', padding: '2px 10px', borderRadius: 4, fontSize: '0.72rem', fontWeight: 700 }}>
            {asset.license}
          </span>
        )}
        {!asset.license && (
          <span style={{ background: '#ffebee', color: '#c62828', padding: '2px 10px', borderRadius: 4, fontSize: '0.72rem', fontWeight: 700 }}>
            No License
          </span>
        )}
        {govRisk !== 'unknown' && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: riskLevelColor(govRisk) + '18', padding: '2px 10px', borderRadius: 10, fontSize: '0.72rem', fontWeight: 700, color: riskLevelColor(govRisk) }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: riskLevelColor(govRisk), display: 'inline-block' }} />
            {govRisk} risk
          </span>
        )}
        <span style={{ flex: 1 }} />
        <button
          onClick={handleCreateSnapshot}
          disabled={creatingSnapshot}
          style={{
            padding: '6px 16px', fontSize: '0.82rem', fontWeight: 600,
            background: creatingSnapshot ? '#ccc' : '#4caf50', color: '#fff',
            border: 'none', borderRadius: 6, cursor: creatingSnapshot ? 'default' : 'pointer',
            opacity: creatingSnapshot ? 0.7 : 1,
          }}
        >{creatingSnapshot ? 'Creating...' : '📸 Create Snapshot'}</button>
      </div>

      {/* -- Metadata cards ------------------------------------------------ */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 12, marginBottom: 24 }}>
        <MetaCard title="Identity" rows={identityRows} />
        <MetaCard title="Size & Files" rows={sizeRows} />
        <MetaCard title="License & Tags" rows={licenseRows} />
        <MetaCard title="Governance" rows={governanceRows} />
      </div>

      {/* -- Files ------------------------------------------------------- */}
      <div style={{ background: '#fff', border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h4 style={{ margin: 0, color: '#1976d2', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
            Files ({files.length})
          </h4>
          <ViewToggle view={viewMode} onChange={setViewMode} />
        </div>
        {files.length === 0 ? <p style={{ color: '#666' }}>No files</p> : viewMode === 'tree' ? (
          <FileTree files={files} onFileClick={handleFileClick} selectedFile={selectedFile} />
        ) : (
          <FlatFileTable files={files} onFileClick={handleFileClick} selectedFile={selectedFile} />
        )}
      </div>

      {/* -- File preview panel -------------------------------------------- */}
      {selectedFile && (
        <div style={{ background: '#fff', border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ margin: 0, fontSize: '0.85rem' }}>
              Preview: <code style={{ fontSize: '0.82rem' }}>{selectedFile}</code>
            </h4>
            <div style={{ display: 'flex', gap: 8 }}>
              {previewData && previewData.previewable && previewData.content !== null && selectedFile && (
                <button onClick={() => downloadFileContent(selectedFile, previewData.content!)}
                  style={{ background: '#1976d2', color: '#fff', border: 'none', padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: '0.8rem' }}
                >Download</button>
              )}
              <button onClick={() => { setSelectedFile(null); setPreviewData(null); setPreviewError(''); }}
                style={{ background: '#eee', color: '#333', border: '1px solid #ccc', padding: '4px 12px', borderRadius: 4 }}
              >Close</button>
            </div>
          </div>

          {previewLoading && <p style={{ color: '#666' }}>Loading preview...</p>}

          {previewError && <p style={{ color: '#f44336' }}>{previewError}</p>}

          {previewData && !previewData.previewable && (
            <p style={{ color: '#ff9800', fontSize: '0.85rem' }}>
              Cannot preview this file: {previewData.error || 'Unsupported file type'}
            </p>
          )}

          {previewData && previewData.previewable && previewData.content !== null && (
            <div>
              <pre style={{
                background: '#1a1a2e', color: '#eee', padding: 16, borderRadius: 6,
                maxHeight: 420, overflow: 'auto', fontSize: '0.78rem', lineHeight: 1.5,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0,
              }}>{previewData.content}</pre>
              {previewData.content_truncated && (
                <p style={{ color: '#ff9800', fontSize: '0.78rem', marginTop: 8 }}>
                  Preview truncated (file is {formatSize(previewData.size)}). Showing first 64KB.
                </p>
              )}
              <p style={{ color: '#666', fontSize: '0.72rem', marginTop: 4 }}>
                {formatSize(previewData.size)} · {previewData.encoding || 'unknown'} encoding
              </p>
            </div>
          )}
        </div>
      )}

      {/* -- Download info ------------------------------------------------- */}
      <div style={{ background: '#fff', border: '1px solid #ddd', borderRadius: 8, padding: 16 }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#1976d2', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.6px' }}>Download</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 8, fontSize: '0.85rem' }}>
          <div><strong>Mode:</strong> {dl?.download_mode || 'unknown'}</div>
          <div><strong>Reference:</strong> <code style={{ fontSize: '0.78rem' }}>{dl?.url_ref || 'redacted'}</code></div>
        </div>
        {dl?.security_warning && (
          <p style={{ color: '#ff9800', fontSize: '0.8rem', marginTop: 8, marginBottom: 0 }}>{dl.security_warning}</p>
        )}
      </div>
    </div>
  )
}
