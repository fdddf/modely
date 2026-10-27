// Type definitions derived from docs/specs/enterprise-api.md example payloads

export interface ApiResponse<T> {
  data: T;
  meta: {
    request_id: string;
    schema_version: string;
    pagination: Pagination | null;
  };
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    request_id: string;
  };
}

export interface Pagination {
  total: number;
  page: number;
  page_size: number;
}

// -- Asset types --
export interface AssetItem {
  id: string;
  source: string;
  repo_type: string;
  repo_id: string;
  revision?: string;
  license?: string;
  tags: string[];
  size: number;
  file_count: number;
  checksum?: string;
  operational_state: string;
  visibility: string;
  metadata: Record<string, unknown>;
  governance?: {
    visibility: string;
    access_rules: Record<string, unknown>;
    policy_status: string;
    risk_level: string;
    approval_state: string;
  };
}

export interface AssetsSummary {
  total_count: number;
  total_size: number;
  total_files: number;
  licensed_count: number;
  by_source: Record<string, number>;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  by_risk: Record<string, number>;
}

export interface AssetListData {
  assets: AssetItem[];
  total: number;
  summary?: AssetsSummary;
}

export interface AssetFile {
  path: string;
  size: number;
  sha256?: string;
  file_type: string;
  mime_type?: string;
  mtime?: string;
  storage_key?: string;
  metadata: Record<string, unknown>;
}

export interface AssetFilesData {
  asset_id: string;
  files: AssetFile[];
  count: number;
}

export interface DownloadUrlData {
  asset_id: string;
  download_mode: string;
  url_ref: string;
  manifest_ref?: string;
  checksum_ref?: string;
  security_warning: string;
  metadata: Record<string, unknown>;
}

// -- Sync Job types --
export interface SyncJobData {
  id: string;
  target_id: string;
  resource: string;
  status: string;
  action: string;
  attempts: number;
  error?: string;
  created_at?: string;
  updated_at?: string;
  metadata: Record<string, unknown>;
}

export interface SyncJobLogsData {
  job_id: string;
  status: string;
  events: Array<{ timestamp: string; event: string; details: unknown }>;
  error?: string;
  metadata: Record<string, unknown>;
}

// -- Snapshot types --
export interface SnapshotData {
  id: string;
  tenant_scope: string;
  asset_id: string;
  version_id: string;
  manifest_digest: string;
  channel: string;
  created_by: string;
  created_at: string;
}

export interface SnapshotListData {
  snapshots: SnapshotData[];
  count: number;
}

// -- CI Gate types --
export interface CIGateResourceResult {
  uri: string;
  status: string;
  errors: string[];
  warnings: string[];
}

export interface CIGateData {
  status: string;
  exit_code: number;
  profile: string;
  lockfile_path: string;
  resources: CIGateResourceResult[];
  summary: { total: number; passed: number; failed: number; warning: number };
}

// -- SA/Token types --
export interface ServiceAccountData {
  id: string;
  name: string;
  owner_id: string;
  tenant_scope: string;
  roles: string[];
  status: string;
}

export interface TokenCreateData {
  id: string;
  service_account_id: string;
  prefix: string;
  token?: string;  // one-time secret, only in create/rotate response
  scopes: string[];
  expires_at: string;
}

// -- Search types --
export interface SearchResultItem {
  asset_id: string;
  source: string;
  repo_type: string;
  repo_id: string;
  revision?: string;
  license?: string;
  tags: string[];
  score: number;
}

export interface SearchData {
  results: SearchResultItem[];
  total: number;
  page: number;
  page_size: number;
  facets: Record<string, Array<{ value: string; count: number }>>;
}

// -- Remote search (Watch discover) --
export interface RemoteSearchResult {
  id: string;
  source: string;
  repo_type: string;
  url: string;
  author?: string;
  downloads: number;
  likes: number;
  stars: number;
  forks: number;
  size_bytes: number;
  last_modified?: string;
  created_at?: string;
  pipeline_tag?: string;
  library_name?: string;
  tags: string[];
  license?: string;
  description?: string;
  name?: string;
  modely_uri?: string;
}

export interface RemoteSearchData {
  results: RemoteSearchResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// -- Analytics types --
export interface RiskTrendsData {
  period: string;
  total_findings: number;
  high_severity: number;
  medium_severity: number;
  low_severity: number;
  trend_direction: string;
}

export interface UsageStatsData {
  assets: Array<{ asset_id: string; download_count: number; popularity_score: number }>;
}

// -- Watch types --
export interface WatchTarget {
  key: string;
  source: string;
  repo_type: string;
  repo_id: string;
  revision: string;
  download_mode: string;
  allow_patterns: string[];
  ignore_patterns: string[];
  last_checked_at?: string;
  last_downloaded_at?: string;
  last_download_path?: string;
  fingerprint?: string;
  error?: string;
  // Merged drift fields (from list_watch_targets)
  drift_status?: 'drifted' | 'unchanged' | 'error' | 'idle';
  drifted?: boolean;
  previous_fingerprint?: string;
  current_fingerprint?: string;
}

export interface WatchTargetListData {
  targets: WatchTarget[];
  total: number;
}

export interface DriftResultItem {
  key: string;
  source: string;
  repo_type: string;
  repo_id: string;
  revision: string;
  status: 'drifted' | 'unchanged' | 'error';
  previous_fingerprint?: string;
  current_fingerprint?: string;
  error?: string;
}

export interface DriftCheckData {
  results: DriftResultItem[];
  total: number;
  drifted: number;
  errors: number;
  checked_at: string;
}

export interface WatchHistoryEvent {
  key: string;
  source: string;
  repo_type: string;
  repo_id: string;
  revision: string;
  timestamp: string;
  event: 'downloaded' | 'drifted' | 'error';
  fingerprint: string;
  download_path?: string;
  error?: string;
}

export interface WatchHistoryData {
  events: WatchHistoryEvent[];
  total: number;
}

// -- File preview types --
export interface FilePreviewData {
  path: string;
  size: number;
  previewable: boolean;
  content: string | null;
  content_truncated: boolean;
  encoding: string | null;
  error: string | null;
}
