# Spec: Enterprise API Contract

## Objective

Define the enterprise `/api/v1` contract boundary for modely-ai. The API is REST-first; gRPC is optional and out of MVP unless explicitly selected later.

## API Principles

- `/api/v1` is the stable enterprise API namespace.
- OpenAPI is the source for web integration and future generated clients.
- Route ownership follows phase boundaries; later phases may call earlier APIs but must not redefine them.
- Responses use the canonical domain model in `docs/specs/enterprise-domain-model.md`.
- All list endpoints support consistent pagination, filtering, sorting, and error envelopes.
- Permission filtering is applied before returning resources, search results, graph nodes, reports, or recommendations.

## Route Ownership by Phase

| Phase | Owns |
| --- | --- |
| Phase 1 | Health/version, catalog list/detail/file list, sync job create/status/logs, baseline scan trigger/ingestion, internal download URL metadata, OpenAPI publishing. |
| Phase 2 | Governance APIs: approval request/decision, policy check/decision, download authorization, audit-event query, report export, role/visibility/ACL management, admin governance views, SLA/notification hooks. |
| Phase 3 | Reproducibility/integration APIs: lockfile/manifest validation, manifest diff, approved snapshot promotion/rollback, CI gate evaluation, approved resolve/install, service account/API token lifecycle, MLOps/platform handoff. |
| Phase 4 | Intelligence APIs: faceted/semantic search, recommendation, approved alternatives, analytics, lifecycle/cost suggestions, asset graph, compliance reports, admission scoring. |

Phase 3 may call Phase 2 approval, scan, policy, and audit endpoints but must not redefine `approve`, `scan`, or `audit-events` as Phase 3 deliverables.

## Baseline Endpoints

### Phase 1

- `GET /api/v1/health`
- `GET /api/v1/version`
- `GET /api/v1/assets`
- `GET /api/v1/assets/{id}`
- `GET /api/v1/assets/{id}/files`
- `POST /api/v1/sync-jobs`
- `GET /api/v1/sync-jobs/{id}`
- `GET /api/v1/sync-jobs/{id}/logs`
- `POST /api/v1/assets/{id}/scan` for baseline scan trigger/ingestion only
- `GET /api/v1/assets/{id}/download-url`

### Phase 2

- `POST /api/v1/approval-requests`
- `GET /api/v1/approval-requests/{id}`
- `POST /api/v1/approval-requests/{id}/approve`
- `POST /api/v1/approval-requests/{id}/reject`
- `POST /api/v1/policy/check`
- `POST /api/v1/download-authorizations`
- `GET /api/v1/audit-events`
- `POST /api/v1/reports/governance`
- `GET /api/v1/admin/roles`
- `GET /api/v1/admin/visibility-rules`

### Phase 3

- `POST /api/v1/lockfiles/validate`
- `POST /api/v1/manifests/diff`
- `POST /api/v1/snapshots/promote`
- `POST /api/v1/snapshots/{id}/rollback`
- `POST /api/v1/ci-gates/evaluate`
- `POST /api/v1/assets/{id}/resolve-approved`
- `POST /api/v1/service-accounts`
- `POST /api/v1/api-tokens`
- `POST /api/v1/api-tokens/{id}/rotate`
- `POST /api/v1/api-tokens/{id}/revoke`

### Phase 4

- `GET /api/v1/search`
- `GET /api/v1/assets/{id}/recommendations`
- `GET /api/v1/assets/{id}/alternatives`
- `GET /api/v1/analytics/risk`
- `GET /api/v1/analytics/usage`
- `GET /api/v1/analytics/lifecycle`
- `GET /api/v1/analytics/cost`
- `POST /api/v1/analytics/cost/recommendations`
- `GET /api/v1/graph/assets/{id}`
- `POST /api/v1/reports/compliance`
- `POST /api/v1/assets/{id}/admission-score`

## Common Request Conventions

List endpoints should accept:

- `page` and `page_size` or cursor equivalents;
- `sort` with stable field names;
- filters by `source`, `resource_type`, `license`, `risk_level`, `approval_state`, `policy_decision`, `visibility`, tenant scope, tags, and updated time where relevant;
- `include` for optional detail sections only when safe after permission checks.

## Common Response Envelope

```json
{
  "data": {},
  "meta": {
    "request_id": "req_...",
    "schema_version": "v1",
    "pagination": null
  }
}
```

## Error Envelope

```json
{
  "error": {
    "code": "policy_blocked",
    "message": "Resource is blocked by enterprise policy.",
    "details": {},
    "request_id": "req_..."
  }
}
```

Stable error codes should be used for auth failures, permission denied, policy blocked, approval required, not found, validation error, conflict/idempotency, rate/quota limit, upstream unavailable, and internal error.

## Auth Context

Every authenticated request resolves:

- principal type: user or service account;
- tenant scope: organization/workspace/project/environment;
- team bindings;
- role bindings;
- permission actions;
- request/correlation ID for audit.

## Versioning and Deprecation

- Breaking changes require a new version namespace or explicit compatibility adapter.
- Additive fields are allowed when clients must ignore unknown fields.
- Deprecated fields should include replacement guidance and removal timeline.
- OpenAPI examples must distinguish implemented endpoints from planned enterprise endpoints.

## Verification

- Schema tests should validate envelopes and representative payloads.
- Contract tests should confirm route ownership and error code stability.
- Web/manual integration checklists should use OpenAPI examples rather than undocumented payloads.

## Stable Error Code Matrix

| API error code | HTTP | CLI exit | Retry semantics |
| --- | --- | --- | --- |
| `auth_required` | 401 | 14 | Retry after authentication. |
| `permission_denied` | 403 | 14 | Do not retry without permission change. |
| `policy_blocked` | 403 | 12 | Do not retry unless policy/profile changes or audited override is granted. |
| `approval_required` | 403 | 11 | Retry after valid approval. |
| `manifest_mismatch` | 409 | 13 | Retry only after manifest/lockfile correction or resync. |
| `checksum_mismatch` | 409 | 13 | Retry only after artifact validation/resync. |
| `quota_limited` | 429 | 15 | Retry according to quota reset/backoff metadata. |
| `validation_error` | 400 | 1/2 | Fix request; CLI usage errors use exit 2. |
| `not_found` | 404 | 1 | Do not retry unless identifier changes. |
| `conflict_idempotency` | 409 | 1 | Retry with same idempotency key only when response indicates safe replay. |
| `upstream_unavailable` | 503 | 1 | Retry with backoff. |
| `internal_error` | 500 | 1 | Retry according to server guidance. |

SDKs and CI gates should map these API error codes to typed exceptions and stable CLI exit codes.

## Service Account and Token Lifecycle Endpoints

Minimum Phase 3 lifecycle API:

- `POST /api/v1/service-accounts`
- `GET /api/v1/service-accounts`
- `GET /api/v1/service-accounts/{id}`
- `PATCH /api/v1/service-accounts/{id}`
- `POST /api/v1/service-accounts/{id}/disable`
- `POST /api/v1/service-accounts/{id}/transfer-owner`
- `POST /api/v1/service-accounts/{id}/tokens`
- `GET /api/v1/api-tokens`
- `GET /api/v1/api-tokens/{id}`
- `POST /api/v1/api-tokens/{id}/rotate`
- `POST /api/v1/api-tokens/{id}/revoke`

Token creation and rotation responses may include the secret exactly once. Later reads return only metadata: token ID, prefix, owner, service account, tenant scope, scopes/actions, expiry, last-used timestamp, rotation/revocation state, and audit refs.

Rotation policy must declare whether old tokens are revoked immediately or remain valid for a short grace period. Revocation invalidates API use immediately and prevents future platform resolve/download authorization. Already issued signed URLs follow the selected download URL security mode.

## Download URL Security Models

Supported patterns:

| Mode | Description | Revocation | Range/resume | Audit points |
| --- | --- | --- | --- | --- |
| Server-mediated proxy | Client downloads through `modely-server`, which checks auth on each request. | Immediate. | Supported if server validates each range request. | issuance, start/range, complete/failure. |
| Short-lived object-store signed URL | Server issues scoped signed URL after auth/policy/approval checks. | Limited by TTL unless object store supports revocation. | Supported by object store; TTL must account for large files. | issuance required; start/complete if storage callbacks/log import exist. |
| Platform mount/reference | Training/inference platform receives mount or internal reference. | Via platform credential/session and cache invalidation. | Platform-specific. | issuance, platform resolve, usage event, failure. |

All modes must define TTL, tenant scope, asset/version/snapshot binding, principal or service-account binding where supported, redaction behavior, and cache revalidation. Logs must never expose raw signed URLs.

## Platform Resolve and Usage Event Schemas

### `POST /api/v1/assets/{id}/resolve-approved`

Request example:

```json
{
  "tenant_scope": {"organization_id": "org1", "workspace_id": "ws1", "project_id": "proj1", "environment_id": "training"},
  "requested_channel": "production",
  "requested_snapshot_id": null,
  "requested_actions": ["asset:read", "asset:download"],
  "platform": "training",
  "job_id": "train-123",
  "idempotency_key": "resolve-train-123"
}
```

Response example:

```json
{
  "data": {
    "asset_id": "asset_123",
    "snapshot_id": "snap_456",
    "channel_resolution": {"channel": "production", "resolved_at": "2026-06-24T00:00:00Z"},
    "manifest_digest": "sha256:...",
    "download": {"mode": "signed_url", "url_ref": "redacted", "expires_at": "2026-06-24T01:00:00Z"},
    "policy_decision_ref": "pol_123",
    "approval_ref": "apr_123",
    "audit_ref": "aud_123"
  },
  "meta": {"request_id": "req_...", "schema_version": "v1", "pagination": null}
}
```

### `POST /api/v1/platform-usage-events`

Records training/inference/CI usage after resolve or deployment.

Required fields: tenant scope, platform, job/deployment ID, asset ID, snapshot ID, manifest digest, action, result, timestamp, and correlation/audit refs.

Failure examples must use the stable error envelope for `approval_required`, `policy_blocked`, `permission_denied`, `manifest_mismatch`, `quota_limited`, and `not_found`.

## Phase 1 API Priority and Query Contract

Phase 1 implements endpoints in this order:

| Priority | Endpoints | Status | Required behavior |
| --- | --- | --- | --- |
| P0 | `GET /api/v1/health` | implemented | Service health. |
| P0 | `GET /api/v1/version` | implemented | Server version. |
| P0 | `GET /api/v1/assets` | implemented | Catalog list with filters/pagination. |
| P0 | `GET /api/v1/assets/{id}` | implemented | Asset detail. |
| P0 | `POST /api/v1/sync-jobs` | implemented | Sync job create with idempotency. |
| P0 | `GET /api/v1/sync-jobs/{id}` | implemented | Sync job status. |
| P1 | `GET /api/v1/assets/{id}/files` | implemented | File list with SHA256/size/metadata. |
| P1 | `GET /api/v1/sync-jobs/{id}/logs` | implemented | Sync job log diagnostics. |
| P1 | `GET /api/v1/assets/{id}/download-url` | implemented | Diagnostic download URL metadata. |
| P2 | `POST /api/v1/assets/{id}/scan` | optional | Scan trigger/ingestion; no policy enforcement. |

Minimum Phase 1 asset-list filters:

- `q`
- `source`
- `resource_type`
- `operational_state`
- `license`
- `page`
- `page_size`
- `sort`

Phase 1 download-url responses are diagnostic by default. Production signed URL, revocation, and platform mount semantics use the download URL security models in later governance/integration phases.

## Phase 1 Endpoint Examples

### GET /api/v1/health

**Happy path:**

```json
{
  "data": {
    "status": "ok",
    "service": "modely-server",
    "version": "0.1.0"
  },
  "meta": {
    "request_id": "req_a1b2c3d4e5f6g7h8",
    "schema_version": "v1",
    "pagination": null
  }
}
```

### GET /api/v1/version

**Happy path:**

```json
{
  "data": {
    "service": "modely-server",
    "version": "0.1.0"
  },
  "meta": {
    "request_id": "req_version",
    "schema_version": "v1",
    "pagination": null
  }
}
```

### GET /api/v1/assets

**Happy path:**

```json
{
  "data": {
    "assets": [
      {
        "id": "hf:model:org--model",
        "source": "hf",
        "repo_type": "model",
        "repo_id": "org/model",
        "revision": "main",
        "license": "apache-2.0",
        "tags": ["nlp", "transformer"],
        "size": 1024,
        "file_count": 2,
        "checksum": "abc123;def456",
        "operational_state": "synced",
        "visibility": "organization",
        "metadata": {}
      }
    ],
    "total": 1
  },
  "meta": {
    "request_id": "req_list",
    "schema_version": "v1",
    "pagination": {
      "total": 1,
      "page": 1,
      "page_size": 20
    }
  }
}
```

**Empty state:**

```json
{
  "data": {
    "assets": [],
    "total": 0
  },
  "meta": {
    "request_id": "req_empty",
    "schema_version": "v1",
    "pagination": {
      "total": 0,
      "page": 1,
      "page_size": 20
    }
  }
}
```

### GET /api/v1/assets/{id}

**Happy path:**

```json
{
  "data": {
    "id": "hf:model:org--model",
    "source": "hf",
    "repo_type": "model",
    "repo_id": "org/model",
    "revision": "main",
    "license": "apache-2.0",
    "tags": ["nlp"],
    "size": 1024,
    "file_count": 2,
    "checksum": "abc123;def456",
    "operational_state": "synced",
    "visibility": "organization",
    "metadata": {"framework": "pytorch"}
  },
  "meta": {
    "request_id": "req_detail",
    "schema_version": "v1",
    "pagination": null
  }
}
```

**Not found:**

```json
{
  "error": {
    "code": "not_found",
    "message": "Asset not found: nonexistent",
    "details": {},
    "request_id": "req_nf"
  }
}
```

### GET /api/v1/assets/{id}/files

**Happy path:**

```json
{
  "data": {
    "asset_id": "hf:model:org--model",
    "files": [
      {
        "path": "config.json",
        "size": 100,
        "sha256": "abc123",
        "file_type": "blob",
        "mime_type": null,
        "storage_key": "assets/hf/model/org--model/main/config.json",
        "manifest_ref": null,
        "metadata": {}
      },
      {
        "path": "model.bin",
        "size": 924,
        "sha256": "def456",
        "file_type": "blob",
        "mime_type": null,
        "storage_key": "assets/hf/model/org--model/main/model.bin",
        "manifest_ref": null,
        "metadata": {"framework": "pytorch"}
      }
    ],
    "count": 2
  },
  "meta": {
    "request_id": "req_files",
    "schema_version": "v1",
    "pagination": null
  }
}
```

**Not found:**

```json
{
  "error": {
    "code": "not_found",
    "message": "Asset not found: nonexistent",
    "details": {},
    "request_id": "req_nf"
  }
}
```

### POST /api/v1/sync-jobs

**Happy path:**

```json
{
  "data": {
    "id": "job_1",
    "target_id": "t1",
    "status": "registered",
    "action": "sync",
    "attempts": 0,
    "error": null,
    "created_at": "2026-06-25T00:00:00Z",
    "updated_at": "2026-06-25T00:00:00Z",
    "metadata": {}
  },
  "meta": {
    "request_id": "req_sync",
    "schema_version": "v1",
    "pagination": null
  }
}
```

**Validation error:**

```json
{
  "error": {
    "code": "validation_error",
    "message": "Missing required field: target_id",
    "details": {"field": "target_id"},
    "request_id": "req_v"
  }
}
```

**Idempotency conflict:**

```json
{
  "error": {
    "code": "conflict_idempotency",
    "message": "Sync job with idempotency key 'idem-1' already exists.",
    "details": {
      "existing_job_id": "job_1",
      "existing_status": "registered"
    },
    "request_id": "req_conflict"
  }
}
```

### GET /api/v1/sync-jobs/{id}

**Happy path:**

```json
{
  "data": {
    "id": "job_1",
    "target_id": "t1",
    "status": "synced",
    "action": "sync",
    "attempts": 1,
    "error": null,
    "created_at": "2026-06-25T00:00:00Z",
    "updated_at": "2026-06-25T00:00:00Z",
    "metadata": {}
  },
  "meta": {
    "request_id": "req_status",
    "schema_version": "v1",
    "pagination": null
  }
}
```

**Not found:**

```json
{
  "error": {
    "code": "not_found",
    "message": "Sync job not found: nonexistent",
    "details": {},
    "request_id": "req_nf"
  }
}
```

### GET /api/v1/sync-jobs/{id}/logs

**Happy path:**

```json
{
  "data": {
    "job_id": "job_1",
    "status": "synced",
    "events": [
      {
        "timestamp": "",
        "event": "synced",
        "details": {
          "status": "synced",
          "asset_id": "hf:model:org--model",
          "version_id": "hf:model:org--model:main:default"
        }
      }
    ],
    "error": null,
    "metadata": {
      "source": "job_metadata",
      "diagnostic_mode": true
    }
  },
  "meta": {
    "request_id": "req_logs",
    "schema_version": "v1",
    "pagination": null
  }
}
```

**Empty logs:**

```json
{
  "data": {
    "job_id": "job_1",
    "status": "registered",
    "events": [],
    "error": null,
    "metadata": {
      "source": "job_metadata",
      "diagnostic_mode": true
    }
  },
  "meta": {
    "request_id": "req_logs",
    "schema_version": "v1",
    "pagination": null
  }
}
```

### GET /api/v1/assets/{id}/download-url

**Happy path (diagnostic mode):**

```json
{
  "data": {
    "asset_id": "hf:model:org--model",
    "download_mode": "local_reference",
    "url_ref": "redacted",
    "manifest_ref": null,
    "checksum_ref": "abc123;def456",
    "expires_at": null,
    "security_warning": "Phase 1 diagnostic mode: production download authorization is deferred to later phases.",
    "metadata": {
      "diagnostic_mode": true,
      "production_authorization_deferred": true
    }
  },
  "meta": {
    "request_id": "req_dl",
    "schema_version": "v1",
    "pagination": null
  }
}
```

**Not found:**

```json
{
  "error": {
    "code": "not_found",
    "message": "Asset not found: nonexistent",
    "details": {},
    "request_id": "req_nf"
  }
}
```

## Auth Required Example

```json
{
  "error": {
    "code": "auth_required",
    "message": "Authentication required. Use Authorization: Bearer dev-<role> header.",
    "details": {
      "supported_roles": ["admin", "developer", "viewer"],
      "auth_mode": "dev_basic"
    },
    "request_id": "req_auth"
  }
}
```
