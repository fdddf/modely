# Spec: Enterprise Governance

## Objective

Define the enterprise governance control plane for modely-ai: tenancy, RBAC, visibility, approval lifecycle, policy decisions, audit, reports, quota semantics, redaction, and retention.

## Canonical Tenancy

Use one hierarchy for authorization, audit, reporting, quota, analytics, service accounts, and integrations:

```text
Organization
  └── Workspace
        └── Project
              └── Environment (optional: dev/staging/prod/training/inference)
```

Users belong to teams. Teams can be bound to organizations, workspaces, or projects. Service accounts belong to a project/environment in Phase 3.

## Roles

| Role | Scope |
| --- | --- |
| Platform Admin | Platform configuration, tenant setup, emergency governance operations. |
| Security Admin | Policy, risk, approval override, audit/report review. |
| Asset Admin | Sync, publish, deprecate, archive, and asset owner operations. |
| Team Admin | Team-scoped member and resource administration. |
| Developer | Search, request access, and download approved assets. |
| Viewer | Read-only browsing. |
| Service Account | Machine principal for CI/CD, training, inference, and automation. |

## Visibility and Policy Separation

Visibility controls discoverability. Policy controls whether an action is allowed.

Allowed visibility values:

- `organization`
- `workspace`
- `team`
- `project`
- `private`
- `restricted`

`blocked` is never a visibility value. Blocking is represented by `policy_decision=block`.

## Permission Actions

Initial permission vocabulary:

- `asset:read`
- `asset:download`
- `asset:sync`
- `asset:publish`
- `asset:approve`
- `asset:delete`
- `asset:scan`
- `asset:manage_acl`
- `report:read`
- `policy:manage`
- `audit:read`
- `token:manage`

Phase 3 tokens and service accounts must reuse this vocabulary rather than defining parallel scopes.

## Approval Lifecycle

Approval requests use the states from `docs/specs/enterprise-domain-model.md`:

- `pending`
- `approved`
- `rejected`
- `expired`
- `cancelled`

Approval records include requester, tenant scope, asset/version/snapshot, requested actions, reason, reviewers, decision, expiry, policy decision reference, and audit refs.

Policy conflict rules:

1. `block` denies by default.
2. A break-glass override must name who can override, expiry, reason, second-review requirement where configured, and audit evidence.
3. `require_approval` requires a valid non-expired approval scoped to the asset/action/principal/tenant.
4. `warn` permits but records warning evidence.
5. `allow` permits when RBAC and visibility also allow access.

## Policy Decision Contract

Policy input should include principal, tenant scope, asset/version/snapshot, requested action, license, scan evidence, approval state, environment, source, and request context.

Policy output should include:

- `decision`: `allow`, `warn`, `require_approval`, or `block`
- matched rule IDs and policy version
- evidence refs
- missing evidence
- explanation
- expiry or recheck hints where applicable

## Audit

Audit events are required for:

- login/auth failures and successes where useful;
- sync job creation, retry, failure, success;
- policy checks and decisions;
- approval requests and decisions;
- download authorizations;
- report exports;
- token/service account issuance, rotation, revoke, and use;
- lifecycle recommendations and executed actions.

Enterprise deployments should support append-only storage semantics, integrity metadata/signature hooks, retention policy, and SIEM export. Sensitive fields are redacted before logs or reports leave the trust boundary.

## Reports

Phase 2 baseline report formats:

- JSON
- Markdown
- CSV

SARIF belongs to Phase 3 CI/security gates. HTML compliance, CycloneDX, and SBOM outputs are Phase 4 extensions and require explicit schema/workflow selection.

## Quota Semantics

Quota subjects:

- organization
- workspace
- project
- team
- user
- service account

Quota dimensions:

- storage
- downloads
- API calls
- sync job creation
- concurrent sync/scan/report tasks
- high-risk requests

Each quota has mode: advisory, soft limit, or hard limit. Enforcement points include API admission, worker dispatch, storage write, download URL issuance, and token/service-account access.

## Redaction and Retention

- Credentials, tokens, source secrets, signed URLs, PII, and scanner-sensitive findings must be redacted by default.
- Reports should include enough evidence for audit while avoiding secret disclosure.
- Retention policies apply to audit events, approval records, scan evidence, reports, sync logs, and token metadata.

## Verification

- Unit/contract tests should cover RBAC decisions, visibility filtering, policy decisions, approval transitions, audit redaction, and report format stability.
- Documentation checks should confirm `blocked` is only policy/access decision terminology.

## Default Role Permission Matrix

| Role | Scope | Allowed actions | Conditional actions | Forbidden by default |
| --- | --- | --- | --- | --- |
| Platform Admin | Platform / tenant admin | all admin configuration, tenant setup, `audit:read`, `report:read` | asset actions require tenant scope or break-glass | unmanaged secret access |
| Security Admin | Organization/workspace/project | `policy:manage`, `audit:read`, `report:read`, `asset:approve`, `asset:scan`, `asset:read` | `asset:download` when policy and approval allow | routine asset deletion unless also Asset Admin |
| Asset Admin | Organization/workspace/project/team | `asset:read`, `asset:sync`, `asset:publish`, `asset:scan`, `asset:manage_acl`, `report:read` | `asset:delete` requires policy/admin confirmation; high-risk publish may require Security Admin | policy override unless granted |
| Team Admin | Team/project | `asset:read`, `asset:manage_acl`, `report:read` for scope | `asset:sync`/`asset:download` when policy allows | cross-team admin |
| Developer | Project/team | `asset:read`, request access | `asset:download` when visibility, policy, approval, and quota allow | approve, publish, delete, manage policy |
| Viewer | Project/team/org as bound | `asset:read` for visible non-restricted metadata | restricted metadata only when explicitly allowed | download, approve, mutate |
| Service Account | Project/environment | explicitly granted actions only | `asset:download`/resolve only for approved scope and valid token | interactive admin, broad tenant access |

Decision precedence:

```text
tenant scope mismatch > explicit block/deny > RBAC deny > visibility deny > approval required > allow/warn
```

A `warn` policy decision permits access only when RBAC, visibility, quota, and approval requirements are otherwise satisfied.

## Policy Profiles and Rollout

`PolicyProfile` fields:

- `id`
- `name`
- `version`
- `tenant_scope`
- `environment`
- `rules`
- `precedence`
- `default_warning_mode`: pass, warn_only, or fail_ci
- `created_by`
- `effective_from`
- `archived_at`

Policy resolution order:

```text
explicit CLI/API profile > environment binding > project binding > workspace default > organization default
```

Rule conflict precedence: explicit block > explicit approval requirement > warn > allow. Policy rollout should support effective timestamps and rollback to prior profile versions. Existing approvals must record the policy version under which they were granted; deployments choose whether new policy versions require recheck before download, CI gate, or promotion.

## Approval Reviewer Selection and Scope

Reviewer selection precedence:

```text
explicit resource reviewer > project/environment reviewer > team reviewer > risk/license reviewer > workspace/org default reviewer
```

Approval scope must include asset, version or snapshot where applicable, requested actions, principal or service account, tenant scope, project/environment, expiry, and policy version. Multi-level approval must state AND/OR semantics. Default enterprise posture: users cannot self-approve their own high-risk or restricted requests unless a documented break-glass policy allows it.

Expiry or revocation invalidates future downloads, CI gates, and platform resolves that depend on the approval. Already created immutable snapshots remain as historical records, but channel promotion or resolve may require recheck under current policy. Duplicate requests should be merged when subject, action, principal, and tenant scope match; otherwise they remain distinct.

Blocked overrides are temporary access exceptions unless an explicit security policy allows creation or promotion of an approved snapshot.

## Source Credential Governance

Source credentials are governed separately from API tokens and service accounts. They may be scoped to organization, workspace, project, team, source, and allowed adapter actions. Supported credential types include Hugging Face tokens, Kaggle credentials, GitHub PATs, GitLab tokens, S3/OSS access keys, MinIO credentials, and custom registry secrets.

Admin surfaces should show only metadata and redacted prefixes. Workers receive least-privilege temporary access or secret references through tenant-scoped resolution. Creation, rotation, revocation, use, and failed access all emit audit events.
