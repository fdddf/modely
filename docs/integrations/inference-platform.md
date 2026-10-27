# Inference Platform Integration

modely-ai enterprise exposes approved assets to inference platforms through governed deployment-time resolve contracts.

## Objective

An inference platform should deploy only approved model/tool artifacts and record reproducible, auditable usage metadata.

## Contract Flow

```text
inference deployment request
  -> service account authentication
  -> approved snapshot resolve
  -> policy/approval check
  -> internal URL + manifest response
  -> deployment records asset usage and audit event
```

## Request Inputs

- asset URI or internal asset ID;
- approved snapshot/channel, commonly staging or production;
- project/environment;
- inference service/deployment ID;
- requested actions, usually `asset:read` and `asset:download`;
- service-account credential.

## Response Outputs

- immutable approved snapshot reference;
- internal download URL or platform mount reference;
- manifest digest and file checksums;
- policy decision and approval references;
- runtime usage constraints;
- audit/correlation ID.

## Failure Cases

- no approved production snapshot;
- policy blocked or approval expired;
- token insufficient for target environment;
- manifest validation failure;
- quota or download limit exceeded.

## Operational Notes

- Deployments should pin immutable snapshot IDs rather than floating source revisions.
- Rollback should use prior approved snapshots.
- Platform caches must revalidate manifest digests before serving artifacts.

## Concrete API Contract

Inference platforms should use:

- `POST /api/v1/assets/{id}/resolve-approved`
- `POST /api/v1/platform-usage-events`

Authentication uses a project/environment-bound service-account token, for example:

```text
Authorization: Bearer <redacted>
Idempotency-Key: resolve-inference-deploy-456
```

Deployments should resolve production/staging channels to immutable snapshot IDs and store the snapshot ID, manifest digest, policy/approval refs, and audit/correlation ID with deployment metadata. Floating channels may be used for lookup, but deployed services must pin the resolved snapshot.

Failure responses use the shared error envelope for no approved snapshot, approval expired, policy blocked, insufficient token, manifest mismatch, quota exceeded, or not found. Platform caches must revalidate snapshot ID and manifest digest before reuse.
