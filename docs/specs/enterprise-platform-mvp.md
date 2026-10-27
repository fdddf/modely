# Spec: Enterprise Platform MVP

## Objective

Define the minimum enterprise vertical slices required before expanding into full governance, integrations, and intelligence.

## Phase 1 MVP Cut Line

Phase 1 delivers internal mirror and catalog foundations, not full enterprise governance.

### Local/headless vertical slice

```text
mock source
  -> sync rule
  -> local storage
  -> manifest/checksum
  -> catalog repository
  -> CLI search/detail/download-url diagnostics
```

Acceptance:

- Runs without external network by using fixtures or mocked source adapters.
- Produces asset, version, file, sync job, scan summary, and manifest metadata.
- Uses canonical `operational_state` values from `enterprise-domain-model.md`.

### Server/API vertical slice

```text
catalog repository
  -> /api/v1/assets
  -> /api/v1/assets/{id}
  -> /api/v1/sync-jobs/{id}
  -> /api/v1/assets/{id}/download-url
  -> OpenAPI examples
```

Acceptance:

- API examples use shared response/error envelopes from `enterprise-api.md`.
- Permission/auth placeholders are explicit and do not claim full RBAC before Phase 2.

### Web/API contract slice

This repository should deliver OpenAPI, example payloads, and manual integration checklist first. `modely-web` can live in a separate repository and consume `/api/v1`.

Checklist:

- Asset list/search payload.
- Asset detail payload.
- File list payload.
- Sync job status/log payload.
- Download URL diagnostics payload.
- Baseline scan/license display payload.

## Phase 2 MVP Cut Line

Split Phase 2 into:

- **2a:** tenancy, RBAC, visibility, authorized download.
- **2b:** policy, approval, audit.
- **2c:** reports, admin, quota, redaction, retention.

Vertical slice:

```text
restricted asset
  -> request access
  -> reviewer approve/reject
  -> authorized download
  -> audit event
  -> JSON/Markdown/CSV report
```

## Phase 3 MVP Cut Line

Split Phase 3 into:

- **3a:** lockfile, manifest diff, approved snapshot.
- **3b:** CI gate, service accounts, API tokens.
- **3c:** MLflow/DVC/training/inference contracts.

Vertical slice:

```text
approved snapshot
  -> lockfile
  -> policy check / CI gate
  -> service account auth
  -> platform resolve approved internal URL
```

## Phase 4 MVP Cut Line

Split Phase 4 into:

- **4a:** faceted search, FTS/keyword search, analytics baseline.
- **4b:** recommendations, approved alternatives, admission score.
- **4c:** graph, compliance reports, cost/lifecycle advisory automation.

Vertical slice:

```text
blocked or high-risk asset
  -> permission-filtered alternatives
  -> explanation/evidence/confidence
  -> compliance report evidence
```

## MVP Verification

- Documentation-only: `git diff --check`.
- Code changes: `python -m pytest tests/ -m "not integration"`.
- Contract checks: OpenAPI examples match shared envelopes and domain enums.
- Safety checks: no `blocked` visibility, no approval states in operational lifecycle, Phase 4 intelligence filters before ranking/export.

## Phase 1 Execution Optimization

### Phase 1a: Local Mirror Core

Optimized objective:

> Run a no-network local mirror loop from fixture/local source to storage, manifest, catalog repository, and local CLI/API-ready DTOs.

Required Phase 1a additions:

- `FixtureSourceAdapter` or equivalent local adapter is the required first source provider for deterministic no-network tests.
- `LocalDirectorySourceAdapter` is optional and intended only for developer smoke runs against local files.
- External providers such as Hugging Face, ModelScope, GitHub, Kaggle, internal Git, S3/OSS/MinIO import, and custom HTTP registries are Phase 1a contract/capability targets only; do not require live network calls or real provider credentials in the local core.
- Local repository implementation uses JSON/JSONL or SQLite-style storage and records schema/migration version metadata.
- The local repository boundary should preserve `SyncRegistry`, `CatalogRepository`, `RunHistoryRepository`, and `StorageBackend` responsibilities so the local mode can later migrate behind the same interfaces.
- Local storage backend implements at least put/get/list/checksum and keeps MinIO/S3/object-storage behavior as capability flags or later backends.
- Sync job lifecycle includes idempotency key, retry/backoff metadata, lock owner, attempt count, partial write recovery, atomic commit/rename, failure reason, and task log references.
- Manifest generation with file-level SHA256 is a Phase 1a completion requirement; catalog metadata must preserve manifest/checksum references.
- Source credential placeholder carries credential refs, provider/scope metadata, and redacted display fields without requiring real secrets; offline tests must not need upstream credentials.
- Scan summary fields may be carried as metadata-ready placeholders, but policy enforcement and user-facing governance display remain outside the local core.
- Export/import migration smoke contract:

```text
local repo fixture -> export -> import into selected repository -> catalog query works -> checksum/manifest refs preserved
```

Explicitly out of Phase 1a:

- Runtime `modely-server` or `/api/v1` service implementation.
- PostgreSQL schema, production database migrations, queues, or object-storage deployment.
- MinIO/S3 signed URLs, CDN/LAN acceleration, range/resume distribution, quota enforcement, or production download authorization.
- Web UI implementation, full RBAC/resource ACL, approval workflow, policy blocking, CI gates, service accounts/API tokens, and Phase 4 intelligence features.
- Real external source credentials or mandatory live provider network calls.

Phase 1a done definition:

```text
fixture source -> create sync job -> materialize files into local storage -> compute SHA256 -> generate manifest -> write Asset/AssetVersion/AssetFile/SyncJob metadata -> query catalog repository -> export/import smoke preserves manifest/checksum refs
```

### Phase 1b: API Service MVP (COMPLETED)

Optimized objective:

> Expose Phase 1a local capabilities through `/api/v1` with stable response/error envelopes, basic/dev auth, and baseline governance display.

Status: All P0 and P1 endpoints implemented and tested. File: `src/modely/server/`.

API priority:

| Priority | Endpoints | Status | Notes |
| --- | --- | --- | --- |
| P0 | `GET /api/v1/health` | implemented | Service health with envelope. |
| P0 | `GET /api/v1/version` | implemented | Server version. |
| P0 | `GET /api/v1/assets` | implemented | Catalog list with filters/pagination. |
| P0 | `GET /api/v1/assets/{id}` | implemented | Asset detail. |
| P0 | `POST /api/v1/sync-jobs` | implemented | Sync job create with idempotency. |
| P0 | `GET /api/v1/sync-jobs/{id}` | implemented | Sync job status. |
| P1 | `GET /api/v1/assets/{id}/files` | implemented | File list with SHA256/size/metadata. |
| P1 | `GET /api/v1/sync-jobs/{id}/logs` | implemented | Sync job log diagnostics. |
| P1 | `GET /api/v1/assets/{id}/download-url` | implemented | Diagnostic download URL metadata. |
| P2 | `POST /api/v1/assets/{id}/scan` | optional | Scan trigger/ingestion; no policy enforcement. |

### Phase 1c: Consumer Contract (COMPLETED)

Optimized objective:

> Stabilize API, CLI, and Web consumption contracts without pretending planned enterprise commands are already implemented.

Status: All contract documentation complete. See `docs/specs/enterprise-api.md` for examples and `docs/specs/enterprise-cli.md` for status.

### Web Page-Level Integration Checklist

Each Web flow documents: endpoint(s), query/path params, response example, empty state, error state, loading/retry, auth assumption, schema_version, and redaction notes.

| Consumer flow | Endpoint(s) | Happy | Empty | Error | Loading/Retry | Auth | Redaction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Asset list/search | `GET /api/v1/assets?q=&source=&page=&page_size=&sort=` | Paginated asset list with filters | `assets:[]`, `total:0` | `not_found`/`validation_error` | Retry on `upstream_unavailable` (503), backoff | `dev-<role>` Bearer token, unauthenticated=viewer | No raw credentials exposed |
| Asset detail | `GET /api/v1/assets/{id}` | Full asset fields with license/checksum/state | — | `not_found` | Retry on `upstream_unavailable` | `dev-<role>` Bearer token | No raw credentials exposed |
| File list/manifest | `GET /api/v1/assets/{id}/files` | File paths with SHA256/size | `files:[]`, `count:0` | `not_found` | Retry on `upstream_unavailable` | `dev-<role>` Bearer token | Storage keys are redacted where sensitive |
| Sync job detail/logs | `GET /api/v1/sync-jobs/{id}`, `GET /api/v1/sync-jobs/{id}/logs` | Job status with events | `events:[]` | `not_found` | Retry on `upstream_unavailable` | `dev-<role>` Bearer token | Diagnostic mode; no raw paths |
| Download-url diagnostics | `GET /api/v1/assets/{id}/download-url` | Diagnostic metadata with mode/local_ref | — | `not_found` | Retry on `upstream_unavailable` | `dev-<role>` Bearer token | `url_ref` is redacted; no signed URLs or secrets |
| Baseline governance summary | `GET /api/v1/assets/{id}` (license/checksum/state fields) | Read-only display | — | `not_found` | Retry on `upstream_unavailable` | `dev-<role>` Bearer token | No policy enforcement claimed in Phase 1 |

**Loading states:** Consumers should treat HTTP 202 or empty responses as loading indicators. `upstream_unavailable` (503) should trigger retry with exponential backoff. `quota_limited` (429) should use Retry-After or backoff metadata.

**Error contract:** See `docs/specs/enterprise-api.md` for the stable error code matrix. All errors return `{"error": {"code": "...", "message": "...", "details": {}, "request_id": "req_..."}}`.

**Auth contract:** Phase 1 uses dev/basic auth only. Clients send `Authorization: Bearer dev-<role>` with role in `{admin, developer, viewer}`. This is NOT production RBAC — Phase 2 will add full tenancy, SSO, ACL, and approval workflows.

**Redaction rules:** Download URL `url_ref` is redacted or uses `file://` local references only. Sync logs are diagnostic-only and do not expose raw credentials or signed URLs. All response envelopes include `request_id` for audit traceability.
