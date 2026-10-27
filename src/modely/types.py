"""Shared dataclasses for modely-ai aggregation APIs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class _DataclassDictMixin:
    """Provide a JSON-ready dictionary representation for dataclasses."""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RepoRef(_DataclassDictMixin):
    """A normalized reference to a remote repository or file."""

    source: str
    repo_type: str
    repo_id: str
    revision: Optional[str] = None
    path: Optional[str] = None

@dataclass
class FileInfo(_DataclassDictMixin):
    """Unified file metadata across supported sources."""

    path: str
    size: int = 0
    type: str = "blob"
    sha256: Optional[str] = None
    download_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RepoInfo(_DataclassDictMixin):
    """Unified repository metadata across supported sources."""

    source: str
    repo_type: str
    repo_id: str
    url: str = ""
    author: Optional[str] = None
    revision: Optional[str] = None
    private: Optional[bool] = None
    downloads: int = 0
    likes: int = 0
    forks: int = 0
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FileSummary(_DataclassDictMixin):
    """Summary of a file selection."""

    total_files: int = 0
    total_size: int = 0
    selected_files: int = 0
    selected_size: int = 0
    categories: Dict[str, int] = field(default_factory=dict)
    category_sizes: Dict[str, int] = field(default_factory=dict)

@dataclass
class DownloadPlan(_DataclassDictMixin):
    """A dry-run plan describing what a download would select."""

    source: str
    repo_type: str
    repo_id: str
    revision: Optional[str] = None
    include: Optional[List[str]] = None
    exclude: Optional[List[str]] = None
    profile: Optional[str] = None
    files: List[FileInfo] = field(default_factory=list)
    summary: Optional[FileSummary] = None
    cache_dir: Optional[str] = None
    local_dir: Optional[str] = None
    cache_hits: int = 0
    cache_misses: int = 0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SourceProfile(_DataclassDictMixin):
    """A source endpoint profile used for probing and routing."""

    name: str
    source: str
    endpoint: str
    description: str = ""
    builtin: bool = True

@dataclass
class ProbeResult(_DataclassDictMixin):
    """Result of probing a source profile."""

    profile: str
    source: str
    endpoint: str
    ok: bool
    latency_ms: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AssetCard(_DataclassDictMixin):
    """Best-effort model/dataset/repository card content."""

    source: str
    repo_type: str
    repo_id: str
    revision: Optional[str] = None
    path: Optional[str] = None
    text: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AssetAnalysis(_DataclassDictMixin):
    """Analysis of a model/dataset/repository asset."""

    info: RepoInfo
    summary: FileSummary
    files: List[FileInfo] = field(default_factory=list)
    largest_files: List[FileInfo] = field(default_factory=list)
    weight_formats: Dict[str, int] = field(default_factory=dict)
    has_config: bool = False
    has_tokenizer: bool = False
    has_card: bool = False
    card: Optional[AssetCard] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ScoreBreakdown(_DataclassDictMixin):
    """Component scores that make up an asset health score."""

    completeness: int = 0
    metadata: int = 0
    popularity: int = 0
    freshness: int = 0
    reproducibility: int = 0
    safety: int = 0

@dataclass
class AssetScore(_DataclassDictMixin):
    """Health score for a modely asset."""

    resource: str
    score: int
    grade: str
    breakdown: ScoreBreakdown
    strengths: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    analysis: Optional[AssetAnalysis] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ScanFinding(_DataclassDictMixin):
    """A metadata, security, compliance, or reproducibility finding."""

    id: str
    severity: str
    category: str
    message: str
    path: Optional[str] = None
    recommendation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ScanResult(_DataclassDictMixin):
    """Risk scan result for a modely asset."""

    resource: str
    risk_level: str
    findings: List[ScanFinding] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    analysis: Optional[AssetAnalysis] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ComparisonResult(_DataclassDictMixin):
    """Comparison between two analyzed assets."""

    left: AssetAnalysis
    right: AssetAnalysis
    same_license: bool = False
    shared_tags: List[str] = field(default_factory=list)
    different_tags: Dict[str, List[str]] = field(default_factory=dict)
    size_delta: int = 0
    file_count_delta: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

@dataclass
class ResolveCandidate(_DataclassDictMixin):
    """A likely equivalent resource candidate discovered during resolution."""

    result: Dict[str, Any]
    source: str
    repo_type: str
    repo_id: str
    modely_uri: Optional[str] = None
    confidence: float = 0.0
    signals: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResolveResult(_DataclassDictMixin):
    """Search-based resolution of a query to likely equivalent resources."""

    query: str
    canonical: Optional[str] = None
    repo_type: str = "model"
    candidates: List[ResolveCandidate] = field(default_factory=list)
    groups: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BenchmarkResult(_DataclassDictMixin):
    """Endpoint or small-file benchmark result."""

    profile: str
    source: str
    endpoint: str
    ok: bool
    latency_ms: int = 0
    throughput_bps: int = 0
    bytes_read: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BackendCapability(_DataclassDictMixin):
    """Capability declaration for a download/query backend."""

    name: str
    source: str
    kind: str
    available: bool = True
    requires_extra: Optional[str] = None
    supports: Dict[str, bool] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

@dataclass
class AssetDiff(_DataclassDictMixin):
    """Change-oriented diff between two analyzed assets."""

    left: AssetAnalysis
    right: AssetAnalysis
    added_files: List[str] = field(default_factory=list)
    removed_files: List[str] = field(default_factory=list)
    common_files: int = 0
    license_changed: bool = False
    tag_changes: Dict[str, List[str]] = field(default_factory=dict)
    size_delta: int = 0
    file_count_delta: int = 0
    category_delta: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

@dataclass
class CatalogEntry(_DataclassDictMixin):
    """A local or cached asset entry in a catalog report."""

    id: str
    source: Optional[str] = None
    repo_type: Optional[str] = None
    repo_id: Optional[str] = None
    revision: Optional[str] = None
    local_path: str = ""
    size: int = 0
    file_count: int = 0
    manifest_path: Optional[str] = None
    lock_path: Optional[str] = None
    score: Optional[Dict[str, Any]] = None
    scan: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CatalogReport(_DataclassDictMixin):
    """Inventory report for local or cached modely assets."""

    root: str
    entries: List[CatalogEntry] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DownloadManifest(_DataclassDictMixin):
    """Manifest describing a concrete download or lockfile selection."""

    source: str
    repo_type: str
    repo_id: str
    revision: Optional[str] = None
    local_path: Optional[str] = None
    files: List[FileInfo] = field(default_factory=list)
    include: Optional[List[str]] = None
    exclude: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceSyncTarget(_DataclassDictMixin):
    """A resource managed by the local sync center."""

    id: str
    resource: str
    local_dir: str
    source: str = "auto"
    repo_type: str = "auto"
    revision: Optional[str] = None
    include: Optional[List[str]] = None
    exclude: Optional[List[str]] = None
    profile: Optional[str] = None
    prefer: str = "default"
    token_env: Optional[str] = None
    cache_dir: Optional[str] = None
    checksum: bool = False
    force_download: bool = False
    manifest: Optional[str] = None
    report: Optional[str] = None
    enabled: bool = True
    labels: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceSyncState(_DataclassDictMixin):
    """Latest state for a sync-center target."""

    target_id: str
    status: str
    last_planned_at: Optional[str] = None
    last_synced_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    last_download_path: Optional[str] = None
    last_manifest_path: Optional[str] = None
    last_report_path: Optional[str] = None
    last_fingerprint: Optional[str] = None
    last_error: Optional[str] = None
    run_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceSyncRun(_DataclassDictMixin):
    """A sync-center operation record."""

    id: str
    target_id: str
    action: str
    status: str
    started_at: str
    finished_at: Optional[str] = None
    resource: Optional[str] = None
    local_dir: Optional[str] = None
    path: Optional[str] = None
    manifest_path: Optional[str] = None
    report_path: Optional[str] = None
    fingerprint_before: Optional[str] = None
    fingerprint_after: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncCenterReport(_DataclassDictMixin):
    """Aggregate report returned by sync-center operations."""

    targets: List[ResourceSyncTarget] = field(default_factory=list)
    states: Dict[str, ResourceSyncState] = field(default_factory=dict)
    runs: List[ResourceSyncRun] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
