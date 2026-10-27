# Spec: Enterprise Multitenancy Isolation

## Objective

Define how modely-ai enforces tenant isolation across metadata, storage, search, cache, workers, reports, graph, recommendations, and service accounts.

## Canonical Hierarchy

```text
Organization
  └── Workspace
        └── Project
              └── Environment (optional)
```

Teams bind to organization/workspace/project scopes. Every tenant-scoped object carries enough scope metadata to enforce access checks.

## Isolation Requirements by Layer

| Layer | Requirement |
| --- | --- |
| API | Resolve auth context before query; apply tenant and permission filters before response. |
| Database | Every tenant-scoped row has organization/workspace/project fields or equivalent scope. Queries use tenant-aware repositories. |
| Object storage | Use tenant-aware bucket/prefix policy; signed URLs must be scoped and short-lived. |
| Search index | Either per-tenant indexes or mandatory tenant filters before ranking/result return. |
| Cache | Cache keys include tenant/principal-sensitive dimensions where needed. |
| Worker | Jobs carry tenant scope, principal/request context, and least-privilege credentials. |
| Reports | Report generation uses same filters as API; exports redact unavailable or hidden data. |
| Asset graph | Nodes and edges are filtered before graph traversal result is returned. |
| Recommendations | Candidate generation and ranking exclude unauthorized assets before scoring. |
| Analytics/cost | Aggregates are scoped; cross-tenant admin views require explicit permission. |

## Cross-tenant Admin

Cross-tenant capabilities must be explicit and audited. Platform Admin may see platform health and aggregate metrics, but access to tenant asset details requires scoped permission or break-glass policy.

## Search and Recommendation Safety

- Do not rank then filter when ranking uses restricted metadata that could leak through scores or counts.
- Filter candidate sets first, then rank and explain.
- Counts, facets, graph edges, and alternative suggestions must not reveal hidden assets.

## Storage and URL Safety

- Internal/signed URLs include tenant and asset/version scope.
- URL issuance checks `asset:download`, visibility, approval, and policy decision.
- URL logs redact secrets and use audit refs.

## Worker Safety

- Worker jobs should not share mutable cross-tenant state.
- Retry/dead-letter entries include tenant scope and redacted error messages.
- Source credentials are tenant/project scoped where possible.

## Verification

- Add cross-tenant denial tests for catalog, search, reports, graph, recommendations, downloads, and worker job lookup.
- Add cache tests to ensure tenant-sensitive data is not reused across principals.
- Add report/export tests for redaction and scoped aggregates.

## TenantScope Contract

Use `TenantScope` from `docs/specs/enterprise-domain-model.md` for all tenant-scoped entities and queries. Required fields are `organization_id` and `workspace_id`; `project_id` and `environment_id` are optional only for higher-level objects.

Tenant/principal-sensitive cache keys should include tenant scope, principal or role-binding hash where results differ by caller, requested action, and policy profile version. Search, graph, report, and recommendation jobs must carry tenant scope in job metadata and output artifact metadata.
