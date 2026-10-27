# Spec: Enterprise Deployment and Operations

## Objective

Define deployment, migration, backup, disaster recovery, observability, offline operation, and upgrade requirements for modely-ai enterprise deployments.

## Deployment Modes

| Mode | Purpose | Notes |
| --- | --- | --- |
| local/dev | Developer validation and demos. | Local storage, local config, no production secrets. |
| single-node | Pilot or small team trial. | Server + worker + local/MinIO storage. |
| Docker Compose | Repeatable enterprise trial. | Document env vars, volumes, health checks. |
| Kubernetes/Helm | Production target. | Stateless server, scalable workers, external DB/object storage. |
| offline/intranet | Air-gapped or restricted network. | Internal package/image/source mirrors. |

## Runtime Components

- `modely-server`: stateless API where possible.
- `modely-worker`: async sync, scan, report, index, integration jobs.
- Database: metadata, policy, approvals, audit, report refs.
- Object storage: mirrored blobs, manifests, report artifacts.
- Queue: sync/report/index/integration jobs and retry/dead-letter metadata.
- Search/index backend: optional, especially for Phase 4.

## Migration

### Metadata migration

- Local JSON/SQLite-style pilot data should have an explicit export/import path to PostgreSQL or selected enterprise DB.
- Schema versions and migration history are required before production.
- Worker job schema changes must be backward compatible or drain old jobs before upgrade.

### Storage migration

- Local storage to object storage migration should preserve paths, manifests, SHA256 checksums, tenant scope, and audit refs.
- Checksum revalidation is required after migration.
- Signed URL behavior must be re-tested after backend changes.

## Backup and Restore

Backup scope:

- database metadata;
- object storage blobs/manifests/reports;
- configuration excluding secrets or with separate secret backup policy;
- audit logs and integrity metadata;
- search index rebuild inputs.

Restore validation:

- catalog list/detail works;
- approved snapshots and lockfiles validate;
- download authorization works;
- audit/report history is available;
- search/index can be rebuilt.

Target placeholders for production deployments:

- RPO and RTO must be selected by the enterprise deployment.
- Pilot default recommendation: daily backup, restore drill before production trial.

## Worker Reliability

- Jobs have idempotency keys, retry/backoff, lock owner, correlation ID, and tenant scope.
- Dead-letter queue entries include redacted errors and replay guidance.
- Long-running sync/scan/report/index tasks do not run inline in `modely-server`.

## Observability

Metrics:

- API latency and error rate;
- sync success/failure/latency;
- queue depth and job age;
- storage usage and growth;
- scan duration and findings;
- policy decisions by outcome;
- approval SLA and backlog;
- report generation time;
- search/index freshness where enabled.

Logs:

- structured logs with correlation IDs;
- sensitive-field redaction;
- tenant and job context;
- no raw tokens, credentials, signed URLs, or source secrets.

Traces:

- API -> application service -> repository/storage/queue boundaries where enabled.

## Offline/Intranet Operation

- Document internal package mirrors and container image mirrors.
- External source adapters must support metadata fixtures or internal mirror endpoints.
- CI examples should support self-hosted GitLab/Jenkins without internet.
- KMS/HSM absence requires documented local secret encryption fallback and risk note.

## Upgrade and Rollback

- Announce schema changes and command/API deprecations.
- Run migrations before workers process new job schema.
- Support rollback or document non-reversible migrations.
- Validate critical vertical slices after upgrade.

## Verification

- `git diff --check` for documentation updates.
- Deployment smoke checks once runtime exists: health endpoint, worker job, catalog query, authorized download, report export.
- Restore drill before production trial.
