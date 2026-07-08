import type { ApiResponse, ApiError } from './types';

const BASE = '';

class ModelyApiClient {
  private token: string = '';

  setToken(t: string) { this.token = t; }

  private async req<T>(method: string, path: string, body?: unknown, params?: Record<string, string>): Promise<ApiResponse<T>> {
    const url = new URL(`${BASE}${path}`, window.location.origin);
    if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    const res = await fetch(url.toString(), { method, headers, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json();
    if ((data as ApiError).error) {
      const e = (data as ApiError).error;
      throw new Error(`[${e.code}] ${e.message}`);
    }
    return data as ApiResponse<T>;
  }

  async get<T>(path: string, params?: Record<string, string>) { return this.req<T>('GET', path, undefined, params); }
  async post<T>(path: string, body?: unknown) { return this.req<T>('POST', path, body); }
  async patch<T>(path: string, body?: unknown) { return this.req<T>('PATCH', path, body); }
}

export const api = new ModelyApiClient();

// Convenience functions
import type {
  AssetListData, AssetItem, AssetFilesData, DownloadUrlData,
  SyncJobData, SyncJobLogsData,
  SnapshotData, SnapshotListData,
  CIGateData,
  ServiceAccountData, TokenCreateData,
  SearchData, RiskTrendsData, UsageStatsData,
  WatchTargetListData, WatchTarget, DriftCheckData, WatchHistoryData,
  RemoteSearchData,
  FilePreviewData,
} from './types';

// Encode asset ID for URL use: replace / with -- (cache dir convention)
// Colons are safe in URL path segments; only slashes cause routing issues.
export function encodeAssetId(id: string): string { return id.replace(/\//g, '--'); }

export async function listAssets(params?: Record<string, string>) { return api.get<AssetListData>('/api/v1/assets', params); }
export async function getAsset(id: string) { return api.get<AssetItem>('/api/v1/assets', { id: encodeAssetId(id) }); }
export async function getAssetFiles(id: string) { return api.get<AssetFilesData>(`/api/v1/assets/${encodeAssetId(id)}/files`); }
export async function getDownloadUrl(id: string) { return api.get<DownloadUrlData>(`/api/v1/assets/${encodeAssetId(id)}/download-url`); }
export async function getFilePreview(assetId: string, filePath: string) { return api.get<FilePreviewData>(`/api/v1/assets/${encodeAssetId(assetId)}/files/preview`, { file_path: filePath }); }

export async function createSyncJob(payload: Record<string, unknown>) { return api.post<SyncJobData>('/api/v1/sync-jobs', payload); }
export async function listSyncJobs() { return api.get<{ jobs: SyncJobData[]; total: number }>('/api/v1/sync-jobs'); }
export async function getSyncJob(id: string) { return api.get<SyncJobData>(`/api/v1/sync-jobs/${id}`); }
export async function getSyncLogs(id: string) { return api.get<SyncJobLogsData>(`/api/v1/sync-jobs/${id}/logs`); }

export async function listSnapshots(assetId?: string) { return api.get<SnapshotListData>('/api/v1/snapshots', assetId ? { asset_id: assetId } : undefined); }
export async function getSnapshot(id: string) { return api.get<SnapshotData>(`/api/v1/snapshots/${id}`); }
export async function createSnapshot(payload: { asset_id: string; version_id: string; manifest_digest: string; channel_name?: string }) { return api.post<SnapshotData>('/api/v1/snapshots/create', payload); }
export async function promoteSnapshot(snapshot_id: string, channel_name: string) { return api.post('/api/v1/snapshots/promote', { snapshot_id, channel_name }); }
export async function rollbackSnapshot(id: string, reason: string) { return api.post(`/api/v1/snapshots/${id}/rollback`, { reason }); }

export async function evaluateCIGate(lockfile_path: string, profile = 'production') { return api.post<CIGateData>('/api/v1/ci-gates/evaluate', { lockfile_path, profile }); }

export async function listServiceAccounts() { return api.get<{ service_accounts: ServiceAccountData[] }>('/api/v1/service-accounts'); }
export async function createServiceAccount(name: string, roles: string[]) { return api.post<ServiceAccountData>('/api/v1/service-accounts', { name, roles }); }
export async function getServiceAccount(id: string) { return api.get<ServiceAccountData>(`/api/v1/service-accounts/${id}`); }
export async function createToken(saId: string, scopes: string[]) { return api.post<TokenCreateData>(`/api/v1/service-accounts/${saId}/tokens`, { scopes }); }

export async function search(query: string, filters?: Record<string, string>) { return api.get<SearchData>('/api/v1/search', { q: query, ...filters }); }
export async function getRiskTrends() { return api.get<RiskTrendsData>('/api/v1/analytics/risk'); }
export async function getUsagePopularity() { return api.get<UsageStatsData>('/api/v1/analytics/usage'); }

// -- Watch --
export async function getWatchTargets(config?: string) { return api.get<WatchTargetListData>('/api/v1/watch/targets', config ? { config } : undefined); }
export async function checkWatchDrift(config?: string) { return api.post<DriftCheckData>('/api/v1/watch/check', { config: config }); }
export async function getWatchHistory(targetKey?: string) { return api.get<WatchHistoryData>('/api/v1/watch/history', targetKey ? { target_key: targetKey } : undefined); }
export async function remoteSearch(params: Record<string, string>) { return api.get<RemoteSearchData>('/api/v1/watch/discover', params); }
export async function addWatchTarget(config: string, target: Record<string, unknown>) { return api.post<WatchTarget>('/api/v1/watch/targets/add', { config, target }); }
export async function removeWatchTarget(config: string, targetKey: string) { return api.post<{ removed: boolean }>('/api/v1/watch/targets/remove', { config, target_key: targetKey }); }
