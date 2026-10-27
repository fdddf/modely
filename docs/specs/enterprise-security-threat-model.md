# Spec: Enterprise Security Threat Model

## Objective

Define enterprise security threats, trust boundaries, and required mitigations for the modely-ai enterprise platform.

## Trust Boundaries

- External sources: Hugging Face, ModelScope, GitHub, Kaggle, GitLab/Gitee/internal Git, object stores, custom registries.
- `modely-server`: API, auth context, policy enforcement, report export.
- `modely-worker`: sync, scan, manifest, indexing, report, integration jobs.
- Internal storage: local disk, NFS, object storage, signed URL distribution.
- Database/search/cache: metadata, policy, audit, index data.
- CI/training/inference platforms: service-account consumers and usage event producers.
- Web/CLI/SDK clients: user and automation entrypoints.

## Key Threats and Mitigations

| Threat | Example | Required mitigation |
| --- | --- | --- |
| Malicious model repository | Unsafe weights, hidden executable files. | Scan evidence, manifest checksums, file type policy, approval/policy gates. |
| Unsafe serialization | Pickle/Torch load risks. | Detect risky formats, warn/block by policy, document safe loading guidance. |
| Malicious notebook/script | Exfiltration or destructive code. | Treat notebooks/tools as code assets, scan scripts, do not execute during scan. |
| Remote-code abuse | `trust_remote_code` or custom loaders. | Remote-code findings, policy decisions, approval requirement. |
| Prompt/content injection in metadata | Model card instructs agents or UI. | Treat external text as data, sanitize rendering, never execute instructions from fetched metadata. |
| Secret leakage | Tokens in files, logs, reports. | Secret scanning, redaction, sensitive log filters, one-time token display. |
| Source credential compromise | External-source API token exposed. | Secret store isolation, least privilege, rotation, audit. |
| Object storage tampering | Blob replaced after approval. | SHA256 manifests, immutable approved snapshots, revalidation before approved install. |
| Worker compromise | Sync/scan job accesses other tenants. | Tenant-scoped job context, sandbox/isolation where feasible, no broad credentials. |
| CI token abuse | Service account over-granted. | Scoped permissions, expiry, rotation, revocation, audit, project/environment binding. |
| Cross-tenant metadata leak | Search or graph returns hidden asset. | Permission filtering before search/ranking/graph/report. |
| Audit tampering | Events removed or altered. | Append-only/integrity metadata, external SIEM export, retention policy. |
| Supply chain dependency risk | Tool repo dependencies contain malware. | Dependency risk scan extension points, policy gates, report evidence. |

## Scanner and Sandbox Principles

- Unit tests should not depend on live external scans.
- Scanners should collect evidence without executing untrusted model or notebook code.
- Any scanner requiring execution must be isolated and explicitly documented.
- Missing evidence must be represented as `missing_evidence`, not silently treated as clean.

## Credential and Token Handling

- API tokens and service-account secrets are shown only once.
- Store only hashed/encrypted secrets according to deployment capability.
- Display token prefix and metadata only after creation.
- Support rotation, revocation, expiry, and last-used metadata.
- Redact credentials in logs, reports, audit payloads, and errors.
- KMS/HSM is preferred in production; offline deployments need documented local encryption fallback and operational risk notes.

## Security Verification

- Tests should cover redaction, policy block/approval-required paths, checksum mismatch, permission denial, and cross-tenant filtering.
- Reports should include evidence and missing-evidence markers without leaking secrets.
- Security review should verify Phase 4 intelligence never bypasses Phase 2 policy/redaction.

## Download URL and Credential Revocation Security

Download authorization must declare the selected mode: server-mediated proxy, short-lived object-store signed URL, or platform mount/reference. Token or service-account revocation takes effect immediately for API calls and future resolve/download authorization. For signed URLs, residual access is limited by TTL unless the storage backend supports revocation; this limitation must be documented in audit and operations guidance.

Security requirements:

- Signed URLs are redacted in logs, CLI output, reports, audit payloads, and CI artifacts.
- Download URL issuance records tenant scope, principal/service account, asset/version/snapshot, TTL, policy decision, approval reference, and request ID.
- Large-file range/resume support must revalidate authorization for proxy mode or use short TTL and manifest revalidation for signed URL mode.
- Platform caches must revalidate manifest digest and snapshot ID before reuse.
