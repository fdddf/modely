# Training Platform Integration

modely-ai enterprise exposes approved assets to training platforms through governed resolve and download contracts.

## Objective

A training platform should be able to request an approved model, dataset, or tool version and receive internal URLs, manifest/checksum metadata, and audit-traceable usage records without bypassing governance.

## Contract Flow

```text
training job request
  -> service account authentication
  -> approved asset resolve
  -> policy/approval check
  -> internal URL + manifest response
  -> training job records usage/audit event
```

## Request Inputs

- asset URI or internal asset ID;
- desired revision/snapshot/channel;
- project/environment;
- training job ID;
- requested action, usually `asset:read` and `asset:download`;
- service-account credential.

## Response Outputs

- internal download or mount URL;
- manifest digest and file list;
- approved snapshot reference;
- policy decision reference;
- expiry and usage constraints;
- audit/correlation ID.

## Failure Cases

- asset not found;
- approval required;
- policy blocked;
- token expired/revoked/insufficient scope;
- checksum or manifest mismatch;
- quota exceeded.

## Security Notes

- Training platforms must not cache credentials in logs.
- Download URLs should be short-lived and scoped.
- Usage events should include tenant/project/environment and job ID.

## Concrete API Contract

Training platforms should use:

- `POST /api/v1/assets/{id}/resolve-approved`
- `POST /api/v1/platform-usage-events`

Authentication uses an enterprise service-account token, for example:

```text
Authorization: Bearer <redacted>
Idempotency-Key: resolve-training-job-123
```

Resolve requests include tenant scope, requested channel or snapshot ID, job ID, requested actions, and policy profile. Resolve responses include immutable snapshot ID, manifest digest, download mode, expiry, policy/approval refs, and audit ref. Failure responses use the shared error envelope for approval expired, policy blocked, insufficient token, manifest mismatch, quota exceeded, or not found.

Bulk resolve is optional; if implemented it must return per-asset success/error entries and must not partially hide policy failures.
