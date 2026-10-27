# Spec: Enterprise CLI Commands

## Objective

Define the target `modely-ai` enterprise CLI information architecture while preserving existing commands and compatibility behavior. This spec coordinates Phase 1-4 enterprise commands with `docs/specs/aggregate-governance.md`.

## Principles

- Enterprise commands are additive; existing `modely-ai hf`, `ms`, `github`, `cache`, and aggregate governance commands must keep working.
- Commands that require server/governance decisions must call shared API/application services and must not bypass RBAC, approval, policy, or audit.
- Future commands must be labeled as planned until implemented.
- JSON output and stable exit codes are required for CI and automation commands.
- `catalog gate`, `policy check`, `lock`, `install`, and report commands must have explicit compatibility behavior.

## Phase 1: Mirror and Catalog MVP

| Command | Status | Purpose | Output |
| --- | --- | --- | --- |
| `modely-ai login` | implemented (existing) | Configure user/server context for enterprise API usage. | Human + optional JSON. |
| `modely-ai sync add` | planned | Create a manual/API sync job. | Job ID and status. |
| `modely-ai sync list` | planned | List sync jobs/rules. | Table/JSON. |
| `modely-ai sync status` | planned | Show sync job state and diagnostics. | Table/JSON. |
| `modely-ai asset search` | planned | Search internal catalog. | Table/JSON. |
| `modely-ai asset detail` | planned | Show asset detail sections. | Markdown/JSON. |
| `modely-ai asset download-url` | planned | Diagnose internal download URL resolution. | JSON. |

**Local mode (planned) example:**

```bash
modely-ai asset search --catalog <local-catalog>
modely-ai asset detail <asset-id> --catalog <local-catalog>
```

**Server mode (planned) example:**

```bash
modely-ai asset search --server https://modely.internal
modely-ai asset detail <asset-id> --server https://modely.internal
```

## Phase 2: Governance and Approval

| Command | Status | Purpose | Output |
| --- | --- | --- | --- |
| `modely-ai request access` | planned | Request usage/download approval for a restricted asset. | Request ID. |
| `modely-ai approval list` | planned | List approval requests for requester/reviewer/admin views. | Table/JSON. |
| `modely-ai approval approve` | planned | Approve a request. | JSON audit/result. |
| `modely-ai approval reject` | planned | Reject a request with reason. | JSON audit/result. |
| `modely-ai policy check` | planned | Evaluate policy for asset, lockfile, or manifest. | JSON/Markdown; exit codes for automation. |
| `modely-ai audit events` | planned | Query audit events with tenant and permission filters. | JSON/CSV. |
| `modely-ai report governance` | planned | Export governance report. | JSON/Markdown/CSV baseline. |

## Phase 3: Reproducibility and Integrations

| Command | Status | API Equivalent | Purpose | Output |
| --- | --- | --- | --- | --- |
| `modely-ai lock validate` | implemented | `POST /api/v1/lockfiles/validate` | Validate lockfile schema, checksums, and approved refs. | JSON/Markdown. |
| `modely-ai manifest-diff` | implemented | `POST /api/v1/manifests/diff` | Compare manifests/versions. | Markdown/JSON. |
| `modely-ai snapshot list` | implemented | `GET /api/v1/snapshots` | List approved snapshots. | Table (local) / JSON (server). |
| `modely-ai snapshot promote` | implemented | `POST /api/v1/snapshots/promote` | Promote approved snapshot to channel. | JSON audit/result (server mode). |
| `modely-ai snapshot rollback` | implemented | `POST /api/v1/snapshots/{id}/rollback` | Roll back channel to prior approved snapshot. | JSON audit/result (server mode). |
| `modely-ai catalog-gate` | implemented | `POST /api/v1/ci-gates/evaluate` | CI gate over lockfile/manifest/asset refs. | JSON/SARIF/Markdown with stable exit codes: 0=pass, 10=warn, 12=blocked, 13=checksum_mismatch. |
| `modely-ai resolve-approved` | implemented | `POST /api/v1/assets/{id}/resolve-approved` | Resolve approved internal asset URL and manifest metadata. | JSON (server mode). |
| `modely-ai install-approved` | implemented | `POST /api/v1/assets/{id}/install` | Install/download exact approved manifest files. | Progress + JSON summary (server mode). |
| `modely-ai token-create` | implemented | `POST /api/v1/service-accounts/{id}/tokens` | Issue scoped automation credential. | One-time secret + metadata (server mode). |
| `modely-ai token-rotate` | implemented | `POST /api/v1/api-tokens/{id}/rotate` | Rotate credential. | One-time secret + audit metadata (server mode). |
| `modely-ai token-revoke` | implemented | `POST /api/v1/api-tokens/{id}/revoke` | Revoke credential. | JSON audit/result (server mode). |

**Note:** All Phase 3 CLI commands are now implemented. Snapshot list works with local catalog data. Promote, rollback, resolve-approved, install-approved, and token commands require `--server <url>` pointing to a running `modely-server`.

## Phase 4: Intelligent Governance

| Command | Status | Purpose | Output |
| --- | --- | --- | --- |
| `modely-ai search` | existing/planned enterprise extension | Search source or enterprise catalog depending on context. | Table/JSON. |
| `modely-ai recommend` | planned | Recommend similar or safer assets. | JSON/Markdown. |
| `modely-ai alternatives` | planned | Show approved alternatives for blocked/high-risk assets. | JSON/Markdown. |
| `modely-ai score` | existing/planned enterprise extension | Show admission score with evidence. | JSON/Markdown. |
| `modely-ai graph asset` | planned | Show permission-filtered asset graph. | JSON. |
| `modely-ai report compliance` | planned | Generate compliance evidence package. | JSON/Markdown/HTML where implemented. |

## Compatibility and Aliases

| Existing command | Enterprise target | Compatibility rule |
| --- | --- | --- |
| `modely-ai catalog gate` | `modely-ai policy check` | Keep `catalog gate` as compatibility alias for catalog/report CI inputs; new enterprise docs should prefer `policy check` for policy/lockfile gates. |
| `modely-ai lock RESOURCE ...` | `modely-ai lock validate` plus future lock creation flow | Preserve existing lock creation behavior. `lock validate` is additive and validates existing lockfiles. |
| `modely-ai install -f modely.lock` | `modely-ai asset install --approved` | Preserve local lockfile install. Enterprise approved install adds server approval/policy checks. |
| `modely-ai report --format html` | `modely-ai report compliance` | Existing/local HTML report is compatibility behavior; enterprise Phase 2 baseline is JSON/Markdown/CSV, Phase 4 may add HTML compliance when schema is selected. |
| `modely-ai doctor`, `choose`, `verify-mirror`, `benchmark`, `watch drift` | enterprise search/policy/intelligence surfaces | Keep as aggregate governance/source diagnostics commands; do not make them mandatory enterprise server commands. |

## Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Success / policy allow. |
| `1` | Generic failure or validation error where no more specific code exists. |
| `2` | Invalid CLI usage. |
| `10` | Policy warning threshold exceeded where configured as failure. |
| `11` | Approval required. |
| `12` | Policy blocked. |
| `13` | Checksum/manifest mismatch. |
| `14` | Auth or permission denied. |
| `15` | Quota/rate limit. |

## Output Format Ownership

- Phase 2 governance reports: JSON, Markdown, CSV.
- Phase 3 CI gates: JSON, Markdown, SARIF-compatible output.
- Phase 4 compliance/intelligence: JSON/Markdown baseline; HTML, CycloneDX, and SBOM outputs require explicit schema/workflow selection.

## Verification

- CLI help smoke tests should only be required for implemented commands.
- Planned commands in documentation must be marked as planned/future until implementation lands.
- CI gate tests should assert stable exit codes once implemented.

## API Error to CLI Exit Mapping

| API error code | CLI exit | Notes |
| --- | --- | --- |
| `auth_required` | 14 | Authentication required. |
| `permission_denied` | 14 | Authenticated but not authorized. |
| `policy_blocked` | 12 | Enterprise policy blocks the action. |
| `approval_required` | 11 | A valid approval is required. |
| `manifest_mismatch` | 13 | Lockfile/manifest mismatch. |
| `checksum_mismatch` | 13 | Artifact checksum mismatch. |
| `quota_limited` | 15 | Quota/rate limit. |
| `validation_error` | 1 or 2 | Use 2 for invalid CLI usage, otherwise 1. |
| `not_found` | 1 | Missing resource. |
| `conflict_idempotency` | 1 | Idempotency conflict. |
| `upstream_unavailable` | 1 | External source or service unavailable. |
| `internal_error` | 1 | Unhandled server error. |

CI gate implementations must test these mappings against `docs/specs/enterprise-api.md`.

## Phase 1 API-to-CLI Mapping (Implemented for API, CLI commands planned)

Phase 1 API endpoints are implemented and tested. The CLI commands listed above as `planned` will consume these API endpoints when implemented. API error codes map to CLI exit codes per the table in the Exit Codes section below.
