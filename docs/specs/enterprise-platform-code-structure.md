# Enterprise Platform Code Structure Adjustment

## Context

`docs/enterprise-platform-roadmap.html` describes the evolution of modely-ai from a CLI/API download and governance tool into an enterprise AI asset platform. The phase task files under `tasks/enterprise-platform/` split that roadmap into four implementation phases:

1. Internal mirror and catalog MVP.
2. Governance, approval, and policy.
3. Reproducibility and platform integrations.
4. Intelligent governance and recommendations.

The current package is still mostly organized as a flat CLI/library package. That structure is convenient for a compact tool, but it will become difficult to maintain once server APIs, internal storage, catalog services, workers, RBAC, approvals, CI gates, integrations, analytics, and recommendation features are added.

This document proposes a target directory structure and a staged migration strategy. It is intentionally a structure proposal only; it does not require moving existing modules immediately.

## Goals

- Keep existing `modely-ai` CLI and public Python imports stable.
- Provide clear directories for enterprise platform work before Phase 1-4 implementation begins.
- Avoid import collisions between existing flat modules and new packages.
- Let new enterprise code enter well-defined packages while old modules remain compatibility facades.
- Support future CLI, SDK, server/API, worker, and reporting use cases with shared service layers.
- Make the recommended deliverables (`modely-server`, `modely-worker`, `modely-web`, and `modely-ai` CLI enterprise mode) explicit without splitting the shared Python package prematurely.

## Recommended Deliverables and Runtime Boundaries

The enterprise platform should be planned as four user-facing/runtime deliverables while keeping the shared Python implementation under `src/modely/`:

| Deliverable | Runtime role | Primary implementation packages | Compatibility notes |
| --- | --- | --- | --- |
| `modely-server` | Backend API/service process for catalog, sync, governance, reproducibility, integration, intelligence, and report APIs. | `server/`, `application/`, `cataloging/`, `syncing/`, `governance/`, `reproducibility/`, `integrations/`, `intelligence/`, `reporting/`, `storage/` | Routes and schemas stay thin; business logic belongs in application/domain packages. |
| `modely-worker` | Background job runtime for mirror sync, scanning, checksum/manifest generation, indexing, analytics aggregation, report generation, and lifecycle/cost jobs. | `syncing/`, `storage/`, `cataloging/`, `governance/`, `reproducibility/`, `integrations/`, `intelligence/`, `application/` | Prefer `syncing/workers.py` or documented worker entrypoints before adding any new top-level package. Long-running jobs should not run inline in `modely-server`. |
| `modely-web` | Enterprise catalog, approval, governance, analytics, and reporting UI. | Prefer a separate frontend package/repository; if kept in this repo, isolate any UI package from core business logic. | Consume `modely-server` APIs and documented schemas; do not import private Python internals. |
| `modely-ai` CLI enterprise mode | Additive enterprise commands for admins, developers, CI, and automation. | Existing `cli/` flow plus `application/` services and API/client helpers. | Keep `modely-ai = "modely:main"` and existing commands stable; enterprise mode is additive, not a replacement CLI. |

Future packaging entrypoints such as `modely-server` or `modely-worker` may be added when those runtimes exist, but they must be additive. The existing `modely-ai` console script remains the compatibility anchor for CLI users.

## Current Structure Summary

The project uses a `src/` layout:

```text
src/modely/
  __init__.py
  cli/
  application/
  common/
  search/
  hf/
  github/
  modelscope/
  kaggle/
  *.py
```

Important existing seams:

- `src/modely/__init__.py` is a public compatibility layer and re-exports the CLI `main` and stable Python API helpers.
- `src/modely/cli/parser.py` builds CLI commands.
- `src/modely/cli/handlers.py` dispatches command behavior.
- `src/modely/application/` already contains orchestration-oriented code such as sync-center services.
- `src/modely/search/` is already a package for external/source search.
- `src/modely/common/cache.py` is the existing local cache/config layer.
- `src/modely/hf/`, `src/modely/github/`, `src/modely/modelscope/`, and `src/modely/kaggle/` are existing source adapters.

The package also has many flat modules, including but not limited to:

```text
analyze.py
asset-related commands: info.py, files.py, card.py, detail.py
catalog.py
sync.py
resource_sync.py
auth.py
audit.py
policy.py
manifest.py
report.py
scan.py
score.py
compare.py
compare_many.py
resolve.py
choose.py
doctor.py
sources.py
backends.py
backend_registry.py
```

These flat modules should be treated as compatibility surface until a deliberate major restructure is completed.

## Compatibility Constraints

Future restructuring must preserve these constraints:

1. Keep package root `src/modely/`.
2. Keep console script in `pyproject.toml`:

   ```text
   modely-ai = "modely:main"
   ```

3. Keep `modely:main` available through `src/modely/__init__.py`.
4. Keep the existing CLI flow available:

   ```text
   modely:main -> modely.cli.main -> cli/parser.py + cli/handlers.py
   ```

5. Keep existing source adapter imports stable:

   ```python
   import modely.hf
   import modely.modelscope
   import modely.github
   import modely.kaggle
   ```

6. Keep existing search/cache imports stable:

   ```python
   import modely.search
   import modely.common.cache
   ```

7. Keep existing flat module imports stable at first:

   ```python
   import modely.catalog
   import modely.sync
   import modely.auth
   import modely.audit
   import modely.policy
   import modely.manifest
   import modely.resource_sync
   import modely.report
   import modely.scan
   import modely.score
   ```

8. Avoid a bulk move of old modules. Tests and user code may import or monkeypatch these paths directly.
9. Prefer adding new internal packages first, then gradually converting old modules into facades.

## Target Directory Structure

The target shape is a layered package structure under the same `src/modely/` root:

```text
src/modely/
  __init__.py                 # Public API facade; keep stable.
  cli/                        # CLI parser/dispatch; keep entry behavior stable.
  application/                # Orchestration services shared by CLI and future server/API.
  common/                     # Existing local cache/config utilities.

  # Existing external source adapters; keep stable.
  hf/
  github/
  modelscope/
  kaggle/
  search/                     # Existing source search package; keep stable.

  # New enterprise platform packages.
  domain/
    __init__.py
    assets.py
    versions.py
    files.py
    scans.py
    sync_jobs.py
    users.py
    audit_events.py
    approvals.py
    policies.py
    snapshots.py
    lineage.py

  storage/
    __init__.py
    base.py
    local.py
    s3.py
    checksums.py
    manifests.py
    download_urls.py

  cataloging/
    __init__.py
    service.py
    repository.py
    queries.py
    serializers.py
    visibility.py

  syncing/
    __init__.py
    jobs.py
    lifecycle.py
    workers.py
    adapters.py
    manifests.py

  governance/
    __init__.py
    rbac.py
    permissions.py
    approvals.py
    policy_engine.py
    audit.py
    reports.py
    redaction.py

  reproducibility/
    __init__.py
    lockfiles.py
    manifest_diff.py
    snapshots.py
    ci_gate.py
    resolver.py

  integrations/
    __init__.py
    mlflow.py
    dvc.py
    github_actions.py
    gitlab.py
    jenkins.py
    training_platform.py
    inference_platform.py

  intelligence/
    __init__.py
    semantic_index.py
    recommendations.py
    alternatives.py
    analytics.py
    lifecycle.py
    cost.py
    asset_graph.py
    admission_score.py

  server/
    __init__.py
    app.py
    routes/
      __init__.py
      health.py
      catalog.py
      sync.py
      auth.py
      governance.py
      reports.py
    schemas/
      __init__.py
      assets.py
      sync.py
      governance.py
      reports.py

  reporting/
    __init__.py
    json.py
    markdown.py
    csv.py
    sarif.py

  # Existing flat modules retained initially as compatibility facades.
  catalog.py
  sync.py
  auth.py
  audit.py
  policy.py
  manifest.py
  resource_sync.py
  report.py
  score.py
  scan.py
```

This target intentionally separates enterprise platform internals from the old public module paths.

## Naming Rules and Collision Avoidance

Do not create top-level packages with the same names as existing `.py` modules unless a later migration intentionally converts file-to-package with dedicated compatibility tests.

Use these safe names:

| Existing file | Avoid new package | Recommended package |
| --- | --- | --- |
| `catalog.py` | `catalog/` | `cataloging/` |
| `sync.py` | `sync/` | `syncing/` |
| `policy.py` | `policy/` | `governance/` + `policy_engine.py` |
| `auth.py` | `auth/` | `governance/` + `rbac.py`, `permissions.py` |
| `audit.py` | `audit/` | `governance/audit.py` |
| `report.py` | `report/` | `reporting/` |
| `manifest.py` | `manifest/` | `reproducibility/` + `lockfiles.py`, `manifest_diff.py` |

These names let old imports keep working while new code enters clearer platform packages.

## Package Responsibilities

### Enterprise Catalog model expectations

The enterprise Catalog is the system of record for resources mirrored or governed by the platform. The shared domain model should define:

- `Asset` with source, source URL, resource type (`model`, `dataset`, `tool`, `space`, `notebook`), namespace/name, version/revision/commit, license, tags, task type, framework, size, file count, checksum, owner team, visibility, operational state, risk level, approval state, policy decision, and created/updated/last-synced timestamps.
- Canonical operational states: `discovered`, `syncing`, `synced`, `scanning`, `published`, `archived`, and `failed`.
- Separate governance fields: approval states (`none`, `pending`, `approved`, `rejected`, `expired`, `cancelled`), policy decisions (`allow`, `warn`, `require_approval`, `block`), and visibility (`organization`, `workspace`, `team`, `project`, `private`, `restricted`). `pending_approval`/`approved` are not operational states, and `blocked` is not a visibility value or lifecycle state.
- Detail-section DTOs for basics/source, files/versions, governance, usage instructions, relationships, and audit history.

`docs/specs/enterprise-domain-model.md` is the authority for these enums and entity fields.

Phase-specific packages should enrich these Catalog entities instead of defining separate resource models.

### `domain/`

Pure enterprise domain objects, value types, and enums. This package should not depend on CLI, HTTP, concrete storage, or external network calls.

Examples:

- `Asset`
- `AssetVersion`
- `AssetFile`
- `ScanReport`
- `SyncJob`
- `User`
- `Team`
- `Project`
- `PolicyDecision`
- `ApprovalRequest`
- `AuditEvent`
- `ApprovedSnapshot`
- lineage nodes/edges

### Enterprise storage and distribution expectations

The storage package should abstract enterprise storage and internal distribution concerns:

- backends: local disk, NFS, MinIO, AWS S3, Alibaba Cloud OSS, Tencent Cloud COS, Huawei Cloud OBS, enterprise object storage, optional HDFS;
- policies: source/team/resource-type layout, hot/warm/cold tiering, replicas, cross-region replication, quotas, cleanup, and archival metadata;
- integrity: SHA256, blob dedupe, large-file chunking, range requests, resumable downloads, manifest validation, lockfile validation hooks, optional Merkle tree;
- distribution: internal download URLs, signed URLs, temporary tokens, internal mirror addresses, optional CDN/edge cache, LAN acceleration, and training-platform mount integration.

### `storage/`

Internal mirror and object storage abstractions.

Responsibilities:

- Local directory storage backend.
- S3/MinIO-compatible backend interface.
- Checksum calculation.
- Manifest persistence.
- Internal/signed download URL abstraction.

This package is distinct from `common/cache.py`, which remains the local user cache/config layer.

### `cataloging/`

Enterprise asset catalog services. The name avoids collision with existing `catalog.py`.

Responsibilities:

- Asset list/search/detail service.
- Catalog repository abstraction.
- Asset/version/file serializers.
- Canonical resource state transitions exposed to server, worker, web, and CLI surfaces.
- Detail-section DTOs for basics/source, files/versions, governance, usage, relationships, and audit history.
- Visibility filtering.
- Query DTOs used by CLI/server/API.

### `syncing/`

Enterprise sync job and worker logic. The name avoids collision with existing `sync.py`.

Responsibilities:

- Sync job lifecycle and state transitions.
- Worker orchestration.
- Source adapter orchestration.
- Retry/status/log metadata.
- Manifest generation during mirror sync.

### Enterprise access-control model expectations

The governance package should define the shared enterprise access-control model used by server, web, CLI, worker jobs, service accounts, and API tokens:

- Identity and tenancy objects: users, teams, departments, projects/workspaces, roles, service accounts, and API tokens.
- Default roles: Platform Admin, Security Admin, Asset Admin, Team Admin, Developer, Viewer, and Service Account.
- Resource visibility levels: `organization`, `workspace`, `team`, `project`, `private`, and `restricted`. Do not use `blocked` as a visibility value; blocking is a policy/access decision.
- Resource actions: `asset:read`, `asset:download`, `asset:sync`, `asset:publish`, `asset:approve`, `asset:delete`, `asset:scan`, and `asset:manage_acl`.
- Approval controls: usage request, reviewer configuration, expiry time, usage reason, automatic approval rules, and force-deny behavior for blocked/blacklisted resources.

Phase 3 token and service-account scopes should reuse these same actions instead of introducing a parallel permission vocabulary.

### `governance/`

Phase 2 governance core.

Responsibilities:

- RBAC.
- Permissions and resource action evaluation.
- Default enterprise role matrix.
- Resource visibility rules and ACL management.
- Usage approvals, reviewer configuration, expiry, reasons, and automatic approval rules.
- Blocked/blacklisted resource force-deny behavior.
- Policy decisions.
- Audit event normalization.
- Redaction helpers.
- Governance report domain logic.

### `reproducibility/`

Phase 3 reproducibility and release gate logic.

Responsibilities:

- Enterprise lockfile schema.
- Manifest diff.
- Approved snapshots.
- CI gate decisions.
- Reproducible resolver/install flow.
- Promotion/rollback metadata.

### `integrations/`

External platform adapters and contracts.

Responsibilities:

- MLflow integration.
- DVC integration.
- GitHub Actions, GitLab CI, and Jenkins helpers/examples.
- Training platform handoff.
- Inference platform handoff.
- Notebook platform handoff.
- Argo Workflows, Airflow, Kubernetes, and other internal platform integration contracts where needed.

### `intelligence/`

Phase 4 intelligent governance.

Responsibilities:

- Semantic index.
- Similar/alternative recommendations.
- Risk and usage analytics.
- Lifecycle suggestions.
- Cost optimization suggestions.
- Asset graph.
- Admission scoring.

### `server/`

HTTP/service API adapter layer.

Responsibilities:

- App factory.
- Health/version endpoints.
- Catalog routes.
- Sync routes.
- Auth/governance routes.
- Report routes.
- Request/response schemas.

Routes should parse requests and call application/domain services. They should not contain core business logic.

### `reporting/`

Report output formatters.

Responsibilities:

- JSON formatter.
- Markdown formatter.
- CSV formatter.
- HTML formatter.
- SARIF-compatible formatter.
- Optional CycloneDX/SBOM formatter.

Phase guard: `reporting/` may eventually host all formatters, but Phase 2 only requires JSON/Markdown/CSV; SARIF is Phase 3 CI/security output; HTML, CycloneDX, and SBOM are Phase 4 or selected compliance-workflow extensions.

Existing `report.py` should remain importable and can later delegate to `reporting/`.

### `application/`

Shared orchestration layer for CLI and future server/API.

Responsibilities:

- Coordinate domain services.
- Keep CLI handlers thin.
- Provide use-case level functions callable by server/API and tests.

## Enterprise Operations, Multitenancy, and Access Surfaces

The platform plan should keep these cross-cutting concerns visible across phases:

- operations: sync/scan queues, retries, concurrency, priority, failure recovery, dead-letter queues, task logs, metrics, and deployment modes from single-node to Docker Compose, Kubernetes/Helm, HA, offline, and intranet deployments;
- observability metrics: sync success/latency, source availability, download speed, storage usage, cache hits, scan duration, approval duration, popular resources, and risk-resource counts;
- multitenancy: organization, workspace, project, team, and environment dimensions;
- quota and cost: team storage quota, user download limits, API call limits, sync/concurrent task limits, high-risk request limits, per-team storage, per-source sync cost, duplicate savings, cold resources, and cleanup candidates;
- access surfaces: REST API, `modely-ai` CLI enterprise mode, future Python SDK, CI plugins, web UI, and internal platform integrations.

## Phase Alignment

### Phase 1: Internal Mirror and Catalog MVP

Deliverables:

- `modely-server`: health/version, catalog, sync job, status/log, and internal download URL APIs.
- `modely-worker`: mirror sync, checksum, manifest, scan-summary, retry, and log execution.
- `modely-web`: catalog/search/detail/sync/risk MVP or documented API contract if UI is external.
- `modely-ai` CLI enterprise mode: additive catalog, sync, status, and download/resolve commands.

Primary packages:

- `domain/`
- `storage/`
- `cataloging/`
- `syncing/`
- `server/`
- `application/`

Compatibility modules likely involved:

- `catalog.py`
- `sync.py`
- `resource_sync.py`

### Phase 2: Governance, Approval, and Policy

Deliverables:

- `modely-server`: RBAC, visibility, authorization, approval, policy, audit, and report APIs.
- `modely-worker`: asynchronous policy scans, report generation, audit aggregation, and expiry jobs where needed.
- `modely-web`: approval queue, governance admin, policy/risk, audit, and report views.
- `modely-ai` CLI enterprise mode: request, approve/reject, policy, audit, and report commands.

Primary packages:

- `governance/`
- `cataloging/`
- `reporting/`
- `server/`
- `application/`

Compatibility modules likely involved:

- `auth.py`
- `policy.py`
- `audit.py`
- `report.py`
- `scan.py`
- `score.py`

### Phase 3: Reproducibility and Platform Integrations

Deliverables:

- `modely-server`: lockfile, manifest diff, approved snapshot, service account/token, and integration handoff APIs.
- `modely-worker`: asynchronous export/report/integration jobs and platform handoff processing where needed.
- `modely-web`: version comparison, approved snapshot, service account, token, and integration management views.
- `modely-ai` CLI enterprise mode: lockfile validation, approved resolve/install, manifest diff, and CI gate commands.

Primary packages:

- `reproducibility/`
- `integrations/`
- `governance/`
- `reporting/`
- `server/`
- `application/`

Compatibility modules likely involved:

- `manifest.py`
- `compare.py`
- `policy.py`
- `report.py`

### Phase 4: Intelligent Governance and Recommendations

Deliverables:

- `modely-server`: query-time search, recommendation, analytics, graph, report, and admission-score APIs.
- `modely-worker`: semantic indexing, trend aggregation, graph materialization, compliance reporting, lifecycle, and cost jobs.
- `modely-web`: intelligent search, recommendation panels, analytics dashboards, graph/compliance views, and score explanations.
- `modely-ai` CLI enterprise mode: scripted search, recommendation, score, graph, and report export commands.

Primary packages:

- `intelligence/`
- `cataloging/`
- `governance/`
- `reporting/`
- `server/`

Compatibility modules likely involved:

- `search/`
- `score.py`
- `report.py`

## Flat Module Regularization Map

The flat modules under `src/modely/*.py` can be regularized, but they should become compatibility facades over time rather than disappear in a bulk move. Many of these modules are imported from `src/modely/__init__.py`, `src/modely/cli/handlers.py`, tests, and likely user code.

### Facade-First Rules

- Do not delete or rename a flat module in the first migration slice.
- Do not create a top-level package with the same name as an existing flat module.
- Move implementation into the target internal package first, then keep the old `modely.<module>` path as a facade.
- Preserve monkeypatch-sensitive symbols on old modules until tests are migrated. A simple `from new_module import *` facade may not be enough for modules whose tests patch internal dependencies.
- Keep `modely:main`, CLI command names, and public aliases in `src/modely/__init__.py` stable.
- Move one vertical slice at a time and run focused tests before the full non-integration suite.

### Current Flat Module Mapping

| Current module | Target internal area | Compatibility note |
| --- | --- | --- |
| `__init__.py` | keep at package root | Public API and `modely:main`; do not move. |
| `analyze.py` | `cataloging/`, `intelligence/`, `domain/assets.py` | Keep `modely.analyze` facade. |
| `audit.py` | `governance/audit.py`, `domain/audit_events.py` | Keep `modely.audit` facade. |
| `auth.py` | `governance/rbac.py`, `governance/permissions.py` | Keep `modely.auth` facade. |
| `backend_registry.py` | source adapter registry; defer or future source-adapter package | Keep stable; many low-level modules depend on it. |
| `backends.py` | source/backend presentation facade | Keep facade. |
| `batch.py` | `application/`, `syncing/jobs.py` | Keep `modely.batch` facade. |
| `benchmark.py` | source diagnostics or `intelligence/analytics.py` | Keep facade. |
| `cache_web.py` | local cache browser; maybe `server/` only if made enterprise API | Keep/defer. |
| `card.py` | `cataloging/serializers.py`, `application/queries.py` | Keep facade. |
| `catalog.py` | `cataloging/service.py`, `cataloging/repository.py`, `cataloging/queries.py` | High-risk; keep facade. |
| `choose.py` | `intelligence/recommendations.py`, `application/` | Keep facade. |
| `compare.py` | `reproducibility/manifest_diff.py`, `cataloging/` | Keep facade. |
| `compare_many.py` | `intelligence/alternatives.py`, `reporting/` | Keep facade. |
| `decision.py` | `application/`, `intelligence/recommendations.py` | Keep facade. |
| `detail.py` | `cataloging/service.py`, `application/queries.py` | Keep facade. |
| `doctor.py` | `application/`, `governance/`, `intelligence/` | Keep facade. |
| `files.py` | `cataloging/`, `storage/`, `domain/files.py` | High-risk; keep facade. |
| `get.py` | `application/`, future download/transfer layer, `syncing/` | High-risk; keep facade. |
| `info.py` | `cataloging/service.py`, source adapters | Keep facade. |
| `labels.py` | `cataloging/`, `domain/users.py` or future labels domain | Keep facade. |
| `license.py` | `governance/policy_engine.py`, `domain/policies.py` | Keep facade. |
| `local.py` | local asset inspection; possibly `cataloging/` | Keep facade. |
| `manifest.py` | `reproducibility/lockfiles.py`, `reproducibility/manifest_diff.py`, `storage/manifests.py` | High-risk; keep facade. |
| `mirror.py` | `syncing/`, `reproducibility/` | Keep facade. |
| `plan.py` | `application/`, `syncing/jobs.py` | Keep facade. |
| `policy.py` | `governance/policy_engine.py`, `domain/policies.py` | Keep facade. |
| `presenters.py` | `reporting/` or `cli/` presentation | Keep/defer. |
| `profiles.py` | `application/` or `common/` | Keep facade. |
| `reliability.py` | `syncing/lifecycle.py`, `storage/checksums.py`, or future transfer layer | Keep facade. |
| `report.py` | `reporting/`, `governance/reports.py` | Keep facade. |
| `resolve.py` | `application/`, `cataloging/queries.py`, future `intelligence/semantic_index.py` | High-risk; keep facade. |
| `resource_sync.py` | `syncing/`, `application/sync_center.py`, `cataloging/`, `storage/` | High-risk; keep facade. |
| `scan.py` | `governance/`, `domain/scans.py` | High-risk; keep facade. |
| `score.py` | `intelligence/admission_score.py`, `governance/` | High-risk; keep facade. |
| `sources.py` | source profiles/probing; keep stable or future source-adapter package | Keep facade. |
| `sync.py` | `syncing/`, `application/` | High-risk; keep facade. |
| `types.py` | gradually split into `domain/*`, `cataloging/*`, `syncing/*` | Highest-risk; keep long-lived facade. |
| `uri.py` | domain/query value utilities | Keep facade. |
| `version.py` | `reproducibility/manifest_diff.py` | Keep facade. |
| `watch.py` | `syncing/workers.py`, `application/` | High-risk; keep facade. |

### High-Risk Modules

Move these last, or only with compatibility wrappers and focused test updates:

- `__init__.py`: public package API and `modely:main` entry surface.
- `types.py`: broad shared dataclass dependency; keep as a long-lived facade even after domain types split out.
- `files.py`, `get.py`, `catalog.py`, `manifest.py`, `resource_sync.py`, `watch.py`: CLI-heavy and test/monkeypatch-heavy orchestration modules.
- `scan.py`, `score.py`, `report.py`, `resolve.py`: chained dependencies with public aliases and tests that patch internals.
- `cli/handlers.py`: dispatch hub; thin it only after migrated services are stable.

### Recommended Migration Order

1. **Compatibility rules first**: lock down facade requirements and import smoke tests.
2. **Low-risk utilities**: `reliability.py`, `policy.py`, `profiles.py`, `auth.py`, `audit.py`, `license.py`.
3. **Foundation/query layer**: `uri.py`, `sources.py`, `info.py`, `files.py`.
4. **Analysis/scanning/scoring**: `card.py`, `analyze.py`, `local.py`, `scan.py`, `score.py`.
5. **Comparison/decision/recommendation**: `compare.py`, `mirror.py`, `resolve.py`, `decision.py`, `choose.py`, `doctor.py`, `compare_many.py`, `detail.py`.
6. **Download/sync/catalog/report orchestration**: `plan.py`, `get.py`, `manifest.py`, `sync.py`, `catalog.py`, `report.py`, `batch.py`, `labels.py`, `version.py`, `cache_web.py`, `benchmark.py`.
7. **Move last or keep long-term**: `watch.py`, `resource_sync.py`, `presenters.py`, `types.py`, `__init__.py`.

### Compatibility Facade Patterns

Use a simple re-export facade only when callers and tests import public symbols without patching module internals:

```python
# src/modely/policy.py
"""Compatibility facade for modely.policy."""

from .governance.policy_engine import evaluate_catalog_policy, evaluate_scan_policy

__all__ = ["evaluate_catalog_policy", "evaluate_scan_policy"]
```

Use wrapper functions or preserve imported dependency symbols when tests patch internals on the old path. For example, if tests patch `modely.manifest.list_repo_files`, the old `manifest.py` facade must either keep that symbol in the execution path or tests must migrate in the same slice.

### Focused Migration Test Groups

Before and after any real module migration, run the full import smoke check plus a focused test group for the migrated slice:

```bash
python -c "import modely; import modely.catalog; import modely.sync; import modely.auth; import modely.audit; import modely.policy; import modely.manifest; import modely.resource_sync; import modely.report; import modely.scan; import modely.score; import modely.compare; import modely.files; import modely.info; import modely.resolve"
modely-ai --help
# Once implemented:
# modely-ai enterprise --help
# PYTHONPATH=src python -m modely.server --help
# PYTHONPATH=src python -m modely.syncing.workers --help
```

```bash
python -m pytest tests/test_catalog.py tests/test_detail.py tests/test_info.py tests/test_files.py -m "not integration"
python -m pytest tests/test_sync.py tests/test_resource_sync.py tests/test_sync_center_cli.py -m "not integration"
python -m pytest tests/test_auth.py tests/test_audit.py tests/test_policy.py tests/test_policy_templates.py tests/test_license.py -m "not integration"
python -m pytest tests/test_manifest.py tests/test_compare.py tests/test_version.py -m "not integration"
python -m pytest tests/test_report.py tests/test_score.py tests/test_choose.py -m "not integration"
python -m pytest tests/ -m "not integration"
```

## Migration Strategy

### Stage 0: Document the structure only

Create this structure proposal. Do not move source files.

Verification:

```bash
git diff --check
```

### Stage 1: Verify or complete package skeletons without moving logic

Verify existing enterprise package skeletons and add only missing `__init__.py` files or boundary placeholders needed for import compatibility. The current branch may already contain several target packages, so do not recreate or bulk-move them. Document the additive runtime assumptions for `modely-server`, `modely-worker`, `modely-web`, and `modely-ai` CLI enterprise mode before adding new entrypoints.

Recommended first boundaries to verify or complete:

```text
src/modely/domain/
src/modely/storage/
src/modely/cataloging/
src/modely/syncing/
src/modely/governance/
src/modely/server/
```

Acceptance:

- Existing imports still work.
- CLI help still works.
- Any future `modely-server` or `modely-worker` entrypoint is additive.
- Enterprise CLI mode, when added, is additive and preserves existing command behavior.
- Non-integration tests still pass.

Verification:

```bash
python -m pytest tests/ -m "not integration"
python -c "import modely; import modely.catalog; import modely.sync; import modely.policy; import modely.report"
modely-ai --help
```

### Stage 2: Move Phase 1 vertical slices into new packages

Add or migrate internal mirror/catalog MVP code:

```text
src/modely/domain/assets.py
src/modely/domain/sync_jobs.py
src/modely/storage/base.py
src/modely/storage/local.py
src/modely/cataloging/service.py
src/modely/cataloging/repository.py
src/modely/syncing/jobs.py
src/modely/syncing/workers.py
src/modely/server/routes/catalog.py
src/modely/server/routes/sync.py
```

Old modules remain compatibility facades:

```text
src/modely/catalog.py
src/modely/sync.py
src/modely/resource_sync.py
```

### Stage 3: Move Phase 2 governance into `governance/`

Add RBAC, permissions, approvals, policy decisions, audit events, redaction, and governance reports.

Old modules remain compatibility facades:

```text
src/modely/auth.py
src/modely/policy.py
src/modely/audit.py
src/modely/report.py
```

### Stage 4: Move Phase 3 reproducibility and integration code

Add lockfiles, manifest diff, approved snapshots, CI gate, service account integration points, and MLOps/CI adapters.

Old modules remain compatibility facades:

```text
src/modely/manifest.py
src/modely/compare.py
src/modely/policy.py
src/modely/report.py
```

### Stage 5: Add Phase 4 intelligence code

Add semantic index, recommendations, alternatives, analytics, lifecycle, cost, asset graph, and admission scoring.

Keep existing `search/` as the public/source-search package. Use `intelligence/` for enterprise intelligence and call it from `search/`, API, or application services where appropriate.

### Stage 6: Optional old-module convergence

Only after compatibility is proven:

- Mark old modules as compatibility facades.
- Recommend new internal imports in architecture docs.
- Keep old imports working for at least the first enterprise platform release.
- Do not remove old modules without a separate breaking-change plan.

## Compatibility Facade Pattern

When moving behavior from a flat module to a new package, keep the old module importable. For example:

```python
# src/modely/policy.py
# Compatibility facade for older imports and CLI code.
from .governance.policy_engine import evaluate_policy, load_policy

__all__ = ["evaluate_policy", "load_policy"]
```

However, during early migration, be careful with tests that monkeypatch dependencies inside old modules. If tests patch `modely.policy.some_dependency`, the facade must either continue exposing that symbol or the test must be updated in the same migration slice.

## Testing and Verification Requirements

### Documentation-only changes

```bash
git diff --check
```

For this deliverable-boundary documentation pass, also inspect for stale collision-prone paths and either remove them or mark them as avoided legacy names.

### After adding package skeletons

```bash
python -m pytest tests/ -m "not integration"
python -c "import modely; import modely.catalog; import modely.sync; import modely.auth; import modely.audit; import modely.policy; import modely.manifest; import modely.resource_sync; import modely.report"
modely-ai --help
```

### After each migrated area

Run focused tests for the moved area, then the full non-integration suite. Examples:

```bash
python -m pytest tests/test_catalog.py tests/test_resource_sync.py tests/test_sync_center_cli.py -m "not integration"
python -m pytest tests/test_policy.py tests/test_report.py tests/test_audit.py -m "not integration"
python -m pytest tests/test_manifest.py tests/test_compare.py -m "not integration"
python -m pytest tests/ -m "not integration"
```

### Import compatibility smoke checks

Maintain a small import smoke check during migration:

```python
import modely
import modely.catalog
import modely.sync
import modely.auth
import modely.audit
import modely.policy
import modely.manifest
import modely.resource_sync
import modely.report
import modely.search.hf_search
import modely.common.cache
```

## Risks and Mitigations

- Risk: Creating `catalog/`, `sync/`, `policy/`, or `report/` packages breaks imports because same-named `.py` files exist.
  - Mitigation: Use `cataloging/`, `syncing/`, `governance/`, and `reporting/`.

- Risk: Moving flat modules breaks external users and tests.
  - Mitigation: Keep flat modules as compatibility facades and migrate one vertical slice at a time.

- Risk: CLI handlers become tightly coupled to server/API implementation.
  - Mitigation: Put shared orchestration in `application/`; keep `cli/` and `server/` as adapters.

- Risk: Enterprise code continues accumulating in the package root.
  - Mitigation: Require new Phase 1-4 platform code to land in the new packages unless it is explicitly a compatibility facade.

- Risk: Phase boundaries blur during implementation.
  - Mitigation: Align packages to phases and keep deferred capabilities out of earlier phase packages.

- Risk: Storage and cache concepts are mixed.
  - Mitigation: Keep `common/cache.py` for local user cache/config and use `storage/` for enterprise internal mirror/object storage.

- Risk: Runtime deliverable boundaries are hidden inside one Python package.
  - Mitigation: Document `modely-server`, `modely-worker`, `modely-web`, and `modely-ai` CLI enterprise mode ownership, and add smoke checks when entrypoints are implemented.

- Risk: Server routes run long sync, scan, index, or report jobs inline.
  - Mitigation: Route long-running work through job contracts handled by `modely-worker`; keep `modely-server` request handlers thin.

- Risk: Enterprise CLI mode duplicates server or governance logic.
  - Mitigation: Route CLI behavior through `application/` services or `modely-server` client boundaries and reuse the same policy/catalog/reproducibility logic.

- Risk: `modely-web` location remains unclear.
  - Mitigation: Treat `modely-web` as an API consumer; if it is external, Phase 1 must produce API contracts and manual integration checks before UI implementation.

## Recommended First Implementation Slice

Before implementing Phase 1 features, create only minimal skeletons:

```text
src/modely/domain/__init__.py
src/modely/storage/__init__.py
src/modely/cataloging/__init__.py
src/modely/syncing/__init__.py
src/modely/governance/__init__.py
src/modely/server/__init__.py
```

Then add Phase 1 models and services incrementally behind tests.

## Decision Summary

- Deliver the enterprise platform as `modely-server`, `modely-worker`, `modely-web`, and `modely-ai` CLI enterprise mode.
- Keep `src/modely/` and `modely-ai = "modely:main"` stable.
- Treat `modely-server` and `modely-worker` as additive runtime entrypoints over shared packages, not as replacements for the Python package root.
- Treat `modely-web` as an API consumer that may live outside this Python package.
- Add enterprise platform code in new layered packages.
- Avoid package names that collide with existing flat modules.
- Preserve old modules as compatibility facades.
- Use `application/` as the shared use-case layer for CLI, server, and worker runtimes.
- Migrate one vertical slice at a time and run compatibility checks after every move.
