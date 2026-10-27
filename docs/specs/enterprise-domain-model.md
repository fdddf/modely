# Spec: Enterprise Domain Model

## Objective

Define the canonical enterprise domain model used by `modely-server`, `modely-worker`, `modely-web`, `modely-ai` enterprise mode, and future `modely_enterprise.Client` flows. This document is the authority for shared states, enums, and cross-phase object boundaries.

## Core Invariants

- The Catalog is the system of record for mirrored or governed AI assets.
- Later phases enrich Catalog objects; they do not define competing resource models.
- Operational lifecycle, approval state, policy decision, visibility, and lifecycle recommendations are separate fields.
- `blocked` is a policy/access decision, not a visibility value and not an operational lifecycle state.
- `pending_approval` and `approved` are approval states, not sync lifecycle states.
- Phase 3 service accounts/API tokens reuse Phase 2 permission actions.
- Phase 4 search, graph, recommendations, and reports apply Phase 2 permission filtering and redaction before ranking, rendering, or export.

## Canonical Enums

### `operational_state`

Represents where the asset is in the mirror/catalog lifecycle.

| Value | Meaning | Owner |
| --- | --- | --- |
| `discovered` | Metadata exists but files may not be mirrored. | Phase 1 |
| `syncing` | A sync job is currently materializing or updating the asset. | Phase 1 |
| `synced` | Files and metadata are available in internal storage. | Phase 1 |
| `scanning` | Baseline scan or policy evidence collection is running. | Phase 1/2 |
| `published` | An explicitly promoted snapshot/channel is available. | Phase 3 |
| `archived` | An explicit admin/policy action archived the asset. | Phase 2/4 action |
| `failed` | Last lifecycle operation failed and requires retry or operator action. | Phase 1 |

### `approval_state`

Represents human or automated usage approval.

| Value | Meaning |
| --- | --- |
| `none` | No approval workflow applies or has been requested. |
| `pending` | A request is awaiting review. |
| `approved` | Use is approved within its scope and expiry. |
| `rejected` | Request was denied. |
| `expired` | Previous approval is no longer valid. |
| `cancelled` | Request was withdrawn or superseded. |

### `policy_decision`

Represents policy evaluation output.

| Value | Meaning |
| --- | --- |
| `allow` | Use is permitted. |
| `warn` | Use is permitted with warning/evidence. |
| `require_approval` | Use requires a valid approval. |
| `block` | Use is denied unless an explicit break-glass/override policy allows otherwise. |

### `visibility`

Represents who can discover a resource before policy and approval checks.

| Value | Meaning |
| --- | --- |
| `organization` | Visible to the organization tenant. |
| `workspace` | Visible to a workspace. |
| `team` | Visible to bound teams. |
| `project` | Visible to a project. |
| `private` | Visible only to owner/admin scopes. |
| `restricted` | Discoverable only to explicitly authorized principals or reviewers. |

### `lifecycle_recommendation`

Advisory overlays from Phase 4. These do not mutate `operational_state` unless an explicit audited action is configured.

- `active`
- `deprecated`
- `quarantined`
- `archive_candidate`
- `cleanup_candidate`
- `requires_review`
- `not_applicable`

## Entity Contracts

### `Asset`

Core fields:

- `id`
- `source`
- `source_url`
- `resource_type`: `model`, `dataset`, `tool`, `space`, `notebook`
- `namespace`
- `name`
- `version`, `revision`, or `commit`
- `license`
- `tags`
- `task_type`
- `framework`
- `size`
- `file_count`
- `checksum`
- `operational_state`
- `visibility`
- `owner_team`
- `risk_level`
- `approval_state`
- `policy_decision`
- `created_at`
- `updated_at`
- `last_synced_at`

Reserved/enriched fields may use `unknown`, `not_evaluated`, or `not_applicable` until the owning phase implements them.

### `AssetVersion`

- `id`
- `asset_id`
- `revision`, `commit`, or `tag`
- `manifest_digest`
- `source_url`
- `internal_url`
- `created_at`
- `synced_at`
- `operational_state`
- `policy_decision`
- `approval_state`

### `AssetFile`

- `id`
- `asset_id`
- `version_id`
- `path`
- `size`
- `sha256`
- `mime_type`
- `storage_uri`
- `integrity_status`

### `SyncJob`

- `id`
- `asset_id` or source reference
- `trigger`: manual, API, schedule, webhook
- `status`: queued, running, succeeded, failed, cancelled, retrying
- `idempotency_key`
- `attempts`
- `started_at`, `finished_at`
- `error_code`, `error_message`
- `log_refs`
- `requested_by`
- `tenant_scope`

### `ScanReport`

- `id`
- `asset_id`
- `version_id`
- `scanner`
- `scanner_version`
- `coverage`: full, partial, metadata_only, missing_evidence
- `findings`
- `risk_level`
- `created_at`

### `PolicyDecision`

- `id`
- `asset_id` or request subject
- `decision`: `allow`, `warn`, `require_approval`, `block`
- `policy_version`
- `matched_rules`
- `evidence_refs`
- `missing_evidence`
- `expires_at` when applicable
- `explanation`

### `ApprovalRequest`

- `id`
- `asset_id`
- `requester_principal`
- `tenant_scope`
- `reason`
- `requested_actions`
- `state`: `pending`, `approved`, `rejected`, `expired`, `cancelled`
- `reviewers`
- `decision_by`
- `decision_at`
- `expires_at`
- `policy_decision_ref`

### `AuditEvent`

- `id`
- `event_type`
- `actor_principal`
- `subject_type`
- `subject_id`
- `tenant_scope`
- `timestamp`
- `request_id` / correlation ID
- `result`
- `redacted_payload`
- `integrity_metadata` for append-only/signature/SIEM export where implemented

### `ApprovedSnapshot`

- `id`
- `asset_id`
- `version_id`
- `manifest_digest`
- `policy_decision_ref`
- `approval_ref`
- `channel`: dev, staging, production, custom
- `created_by`
- `created_at`
- `supersedes`
- `rollback_target`

### `Lockfile`

- `schema_version`
- resource entries with source URI, internal asset ID, pinned revision, manifest digest, files/checksums, approved snapshot ref, policy status, and fallback metadata.
- Backward-compatible readers should accept older lockfile schemas where possible.

### `ServiceAccount` and `ApiTokenMetadata`

- Principal identity, owner, tenant/project/environment binding, issued scopes using Phase 2 permission actions, expiry, rotation/revocation metadata, last used timestamp, and redacted audit refs.
- Secrets are never returned after creation; only metadata and token prefix are shown.

### `Quota`

- Subject: organization, workspace, project, team, user, or service account.
- Dimensions: storage, downloads, API calls, sync jobs, concurrent tasks, high-risk requests.
- Enforcement point and mode: advisory, soft limit, hard limit.

### `Lineage`

Nodes include assets, versions, files, manifests, approvals, policies, CI runs, training jobs, inference deployments, teams/projects, papers, licenses, and tool dependencies. Edges must carry tenant scope and permission-filtering metadata.

## Verification

- Domain/schema tests should validate enum values and serialization.
- Search checks should confirm `blocked` is never documented as visibility and approval states are not operational states.
- Report and API tests should use these contracts as golden references once implementation exists.

## TenantScope

`TenantScope` is the shared value object for tenant-scoped entities and authorization decisions.

Required fields:

- `organization_id`
- `workspace_id`
- `project_id` optional for organization/workspace-level objects
- `environment_id` optional for dev/staging/prod/training/inference-specific objects

Tenant-scoped entities must carry `tenant_scope` unless explicitly marked platform-global. Required tenant-scoped entities include:

- `Asset`
- `AssetVersion`
- `AssetFile`
- `SyncJob`
- `ScanReport`
- `PolicyDecision`
- `ApprovalRequest`
- `AuditEvent`
- `ApprovedSnapshot`
- `SnapshotChannel`
- `SnapshotPromotion`
- `SnapshotRollback`
- `Lockfile`
- `ServiceAccount`
- `ApiTokenMetadata`
- `SourceCredential`
- `Quota`
- `Lineage` nodes and edges

Platform-global entities are limited to deployment-wide configuration, global capability registries, and built-in policy/scanner templates. Any platform-global entity that references tenant data must do so through explicit scoped bindings rather than embedded asset details.

Repository queries, search documents, cache keys, report jobs, graph traversal, recommendation candidate generation, and worker jobs must include tenant scope and principal-sensitive dimensions where the result can differ by caller.

### `SourceCredential`

Source credentials are separate from Phase 3 service-account/API tokens. They grant modely-ai access to upstream or internal sources during sync/import.

Fields:

- `id`
- `tenant_scope`
- `source`: Hugging Face, ModelScope, Kaggle, GitHub, GitLab, S3, OSS, MinIO, custom HTTP registry, or internal source
- `credential_type`: bearer token, username/password, PAT, access-key pair, OAuth app credential, or custom secret reference
- `owner_principal` or `owner_team`
- `allowed_actions`: metadata read, file download, release asset read, object import, webhook verification
- `secret_ref` or encrypted/hashed secret storage pointer
- `created_at`, `rotated_at`, `expires_at`, `revoked_at`
- `last_used_at`
- `audit_refs`

Workers may only request source credentials through tenant-scoped credential resolution. Logs, reports, audit payloads, and errors show only redacted metadata.

### Snapshot promotion model

`ApprovedSnapshot` is immutable. It represents a specific approved asset version + manifest + policy/approval evidence. Do not mutate an approved snapshot during promotion or rollback.

Additional entities:

#### `SnapshotChannel`

- `id`
- `tenant_scope`
- `name`: dev, staging, production, or custom
- `project_id` / `environment_id` where scoped
- `current_snapshot_id`
- `updated_by`
- `updated_at`

#### `SnapshotPromotion`

- `id`
- `tenant_scope`
- `channel_id`
- `from_snapshot_id`
- `to_snapshot_id`
- `reason`
- `promoted_by`
- `promoted_at`
- `audit_ref`

#### `SnapshotRollback`

- `id`
- `tenant_scope`
- `channel_id`
- `from_snapshot_id`
- `to_snapshot_id`
- `reason`
- `rolled_back_by`
- `rolled_back_at`
- `audit_ref`

Platform resolve may accept a channel, but the resolved response and lockfile must record the immutable `snapshot_id` plus channel-resolution evidence.
