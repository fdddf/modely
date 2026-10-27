# modely-ai

**modely-ai** is a cross-platform AI asset workspace for discovering, downloading, comparing, locking, scanning, and governing models, datasets, and AI repositories across Hugging Face, ModelScope, GitHub, and Kaggle.

中文：**modely-ai** 是一个跨平台 AI 资产工作台，用于在 Hugging Face、ModelScope、GitHub、Kaggle 等来源之间发现、下载、比较、锁定、扫描和治理模型、数据集与工具仓库。

It offers a command-line tool and Python API for cross-platform asset workflows: search, resolve equivalent resources, choose reliable download sources, analyze metadata/files, score health, scan risks, create reproducible lockfiles, and catalog local assets.

## Positioning

modely-ai complements platform-native tools by providing a unified cross-source asset workflow before models and datasets enter a project or registry. It is designed as a cross-platform AI asset workspace rather than a replacement for Hugging Face Hub, Kaggle CLI, DVC, MLflow, Git-LFS, or git/GitHub CLI.

Single platforms can help users find and download resources hosted in that platform; modely-ai focuses on workflows that require a broader view across sources:

- **Cross-source discovery**: search Hugging Face, ModelScope, GitHub, and Kaggle through one schema.
- **Equivalent-resource resolution**: identify likely matches for the same model or dataset across platforms with confidence signals.
- **Source selection and fallback**: probe endpoints, rank sources, and retry alternative platforms when downloads fail.
- **Deep comparison**: compare files, cards, licenses, and weight formats between two resources.
- **Health and risk evaluation**: score asset quality and scan metadata/security/reproducibility risks without downloading weights.
- **Reproducible installs**: create lockfiles, install from them, and validate local files/checksums.
- **Local asset governance**: catalog downloaded or cached assets for inventory, reporting, and future policy checks.

### Source Support Matrix

| Source | Search | Download | Files | Info | Compare | Score | Scan | Lock | Cache | Default Revision | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---|
| Hugging Face | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `main` | Official SDK |
| ModelScope | ✅ | ✅ | ✅/partial | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `master` | Optional official SDK |
| GitHub | ✅ | ✅ | ✅ | ✅ | ✅ | Partial | ✅ | ✅ | ✅ | `main` | Always treated as `tool` |
| Kaggle | Partial | Partial | Partial | Partial | Partial | Partial | Partial | Partial | Partial | — | Requires Kaggle environment |

### Boundaries with Native Tools

modely-ai should be used alongside native tools, not as a blanket replacement:

- Use Hugging Face Hub CLI/SDK for deep Hugging Face repository operations.
- Use Kaggle CLI/API for Kaggle competition submissions and platform-native Kaggle workflows.
- Use git/GitHub CLI for source-control collaboration, pull requests, issues, and repository administration.
- Use Git-LFS for large-file versioning inside Git repositories.
- Use DVC for training pipeline reproducibility, data/model versioning, and stage dependency tracking.
- Use MLflow Model Registry or a similar registry for model lifecycle management, promotion, aliases, and lineage.

### Reporting and Policy Output Roadmap

modely-ai commands increasingly favor scriptable and policy-friendly outputs. Priority commands for consistent JSON, Markdown, CSV, and policy-summary output are:

- `compare`
- `compare-many`
- `score`
- `scan`
- `catalog scan`
- `catalog gate`
- `license`
- `audit`

### Integration Guides

See `docs/integrations/` for how modely-ai works with platform-native and MLOps tools:

- [`docs/integrations/huggingface.md`](docs/integrations/huggingface.md)
- [`docs/integrations/modelscope.md`](docs/integrations/modelscope.md)
- [`docs/integrations/kaggle.md`](docs/integrations/kaggle.md)
- [`docs/integrations/github.md`](docs/integrations/github.md)
- [`docs/integrations/dvc.md`](docs/integrations/dvc.md)
- [`docs/integrations/mlflow.md`](docs/integrations/mlflow.md)
- [`docs/integrations/git-lfs.md`](docs/integrations/git-lfs.md)

### Security and Compliance Roadmap

Future governance improvements should continue strengthening:

- license classification evidence and SPDX normalization
- secret detection rules
- remote code warnings
- pickle artifact warnings
- unsafe weight format warnings
- policy templates
- CI gate examples
- allowlists and denylists

## Features

- 🚀 **Unified interface**: Download from Hugging Face, ModelScope, GitHub, and experimental Kaggle URI support with a single tool
- 🧭 **Resource URIs**: Address models, datasets, GitHub repositories, and Kaggle assets with `hf://`, `ms://`, `github://`, and `kaggle://` URIs
- 🔍 **Model discovery**: Search models, datasets, and AI/ML repositories by name, task type, date, and more
- 🧭 **Cross-source resolution**: Resolve likely equivalent models/datasets across platforms with confidence signals
- 📋 **Metadata, planning, and file analysis**: Query repository info, list files, summarize asset categories, preview downloads, and create lockfiles
- 🧩 **Cross-platform analysis and comparison**: Resolve likely equivalent resources, parse cards, analyze model assets, score health, scan metadata/security risks, compare repositories, verify mirrors, and group search results across sources
- 🩺 **Aggregate governance commands**: Use `doctor`, `choose`, `catalog gate`, and `report` to turn cross-source metadata into adoption decisions and CI gates
- 🌐 **Source probing and fallback**: Probe Hugging Face, HF mirrors, ModelScope, GitHub, and Kaggle endpoints before downloading, record fallback sources in lockfiles, and install with fallback source order
- ⚡ **Progress tracking**: Real-time download progress with tqdm
- 🔄 **Resumable downloads**: Resume interrupted downloads automatically
- 📁 **Flexible options**: Download entire repositories, specific files, release assets, or filtered file sets
- 🔐 **Authentication support**: Access private models and datasets with explicit, stdin, environment, or saved tokens
- 📦 **Official SDKs**: Uses `huggingface-hub` official SDK and optional ModelScope official SDK support
- 📦 **Minimal dependencies**: Only requires `requests`, `tqdm`, and `huggingface-hub`
- 💾 **Smart caching**: Avoid duplicate downloads with unified cache system and dry-run duplicate blob reporting
- 🗂️ **Local asset catalog**: Inventory local directories or modely cache entries with optional score/scan enrichment, snapshots, diffs, exports, and policy gates
- 🗂️ **Cache management**: CLI commands to view, list, clean, configure, and inspect duplicate cache files
- 🏢 **Enterprise platform**: Built-in REST API server (57+ endpoints), governance (RBAC, approvals, policy engine, audit, quotas), reproducibility (lockfiles, manifest diff, approved snapshots, CI gates), integrations (MLflow, DVC, CI/CD), and intelligence (search, recommendations, analytics, compliance reports)
- 🔑 **Enterprise auth**: Service accounts, API tokens with scoped permissions, multi-tenant isolation, and dev/basic auth modes
- 🌐 **Web UI**: React SPA dashboard for asset browsing, sync management, CI gate evaluation, and analytics (served from `modely-server`)
- 🖥️ **Enterprise CLI**: `snapshot`, `manifest-diff`, `resolve-approved`, `install-approved`, `token-create/rotate/revoke`, `recommend`, `alternatives`, `graph`, `catalog-gate` commands
- 🩺 **Governance engine**: RBAC permission model, approval workflow (submit→approve/reject/cancel), policy evaluation with block/warn/require_approval decisions, audit event recording, quota enforcement, and credential lifecycle management
- 🔎 **Web asset discovery**: Cross-platform search from the Watch UI (Discover tab) with pagination (10/20/30 per page), filtering by source and repo type, and one-click "Add to Watch" with automatic sync job creation
- 📄 **File preview**: Safe text-file preview in the web UI with path traversal protection, syntax-aware rendering, and download links
- 🏷️ **Sidecar metadata**: Local `modely-info.json` persistence alongside cached assets for offline governance enrichment

## Installation

Install modely-ai using pip:

```bash
pip install modely-ai
```

## Usage

### Command Line Interface

modely-ai provides a command-line interface with subcommands for downloading (`hf`, `ms`, `github`, `get`, `batch-download`), querying and evaluating (`info`, `files`, `card`, `analyze`, `score`, `scan`, `compare`, `resolve`), inspecting backend support (`capabilities`), searching (`search`), reproducibility and inventory (`lock`, `install`, `validate-lock`, `catalog`, `sync-center`, `sync`, `mirror`), authentication (`login`, `logout`, `whoami`), source probing (`sources`), monitoring (`watch`), and cache management (`cache`). Plain Hugging Face and ModelScope repository IDs default to `--repo-type auto`, so query commands can try model and dataset metadata before asking you to disambiguate. Experimental Kaggle support is available through unified URIs and search/source helpers where a Kaggle environment is configured.

**Enterprise commands** (requires `modely-server`): see the **Enterprise Platform** section below for full details on CLI, SDK, server, web dashboard, worker, and multi-tenant isolation.

### Aggregation Workflows

See also the long-lived specification for these governance features: [`docs/specs/aggregate-governance.md`](docs/specs/aggregate-governance.md).

modely-ai's most useful workflows combine multiple commands into cross-platform asset decisions:

```bash
# 1. Diagnose a model or query in one command
modely-ai doctor qwen2.5-7b-instruct --json

# 2. Choose the best candidate for a strategy
modely-ai choose qwen2.5-7b-instruct --strategy safest --json

# 3. Find likely equivalent resources across platforms
modely-ai resolve qwen2.5-7b-instruct --source all --json

# 4. Verify whether two candidates are actually aligned
modely-ai compare hf://models/Qwen/Qwen2.5-7B-Instruct ms://models/qwen/Qwen2.5-7B-Instruct --files --card --formats --deep
modely-ai verify-mirror hf://models/Qwen/Qwen2.5-7B-Instruct ms://models/qwen/Qwen2.5-7B-Instruct --json

# 5. Evaluate health and risks before adoption
modely-ai score hf://models/Qwen/Qwen2.5-7B-Instruct
modely-ai scan hf://models/Qwen/Qwen2.5-7B-Instruct

# 6. Lock a reproducible selection with fallback metadata and install it locally
modely-ai lock hf://models/Qwen/Qwen2.5-7B-Instruct --profile inference --alternatives hf,ms --output modely.lock
modely-ai install -f modely.lock --fallback --prefer ms,hf --local-dir ./models/qwen2.5-7b
modely-ai validate-lock -f modely.lock --local-dir ./models/qwen2.5-7b --checksum

# 7. Inventory and gate downloaded assets for governance/reporting
modely-ai catalog scan ./models --score --scan --output catalog.json
modely-ai catalog gate catalog.json --fail-on high --json
modely-ai catalog export catalog.json --output catalog.csv

# 8. Generate reports and inspect source/cache health
modely-ai report ./models/qwen2.5-7b --format markdown
modely-ai benchmark qwen2.5-7b --source hf,ms --json
modely-ai cache dedupe --dry-run --json
modely-ai cache serve --open
```

### Enterprise Platform

modely-ai includes a full enterprise AI asset platform with server APIs, CLI commands, web dashboard, worker queues, and Python SDK. See [`docs/enterprise-platform-roadmap.html`](docs/enterprise-platform-roadmap.html) for the overall architecture.

#### Enterprise Server (modely-server)

Start the API server with 57+ REST endpoints across 4 capability phases:

```bash
pip install modely-ai[server]
modely-server --host 0.0.0.0 --port 8000
```

**Phase 1 — Internal Mirror & Catalog:** `/api/v1/assets` (list/detail/files/download-url/file-preview), `/api/v1/sync-jobs` (create/status/logs), `/api/v1/watch` (targets CRUD, drift check, history, discover/search), `/api/v1/health`, `/api/v1/version`

**Phase 2 — Governance:** `/api/v1/governance/policy/evaluate`, `/api/v1/governance/requests` (submit/approve/reject/cancel), `/api/v1/admin/quotas`, `/api/v1/admin/credentials`, `/api/v1/admin/audit`

**Phase 3 — Reproducibility & Integrations:** `/api/v1/lockfiles/validate`, `/api/v1/manifests/diff`, `/api/v1/snapshots` (create/promote/rollback/history), `/api/v1/ci-gates/evaluate`, `/api/v1/service-accounts`, `/api/v1/api-tokens` (create/rotate/revoke), `/api/v1/assets/{id}/resolve-approved`, `/api/v1/platform-usage-events`

**Phase 4 — Intelligent Governance:** `/api/v1/search`, `/api/v1/analytics/risk|usage|lifecycle|cost`, `/api/v1/assets/{id}/recommendations|alternatives|admission-score`, `/api/v1/graph/assets/{id}`, `/api/v1/reports/compliance`

#### Enterprise Python SDK

```python
from modely.application.client import Client

client = Client(base_url="http://localhost:8000", token="mod-xxx")

# Catalog & search
assets = client.assets.list(source="hf", page=1)
asset = client.assets.get("hf:model:org--model")
files = client.assets.files("hf:model:org--model")
preview = client.assets.file_preview("hf:model:org--model", file_path="config.json")
download = client.assets.download_url("hf:model:org--model")

# Watch & discover
targets = client.watch.list()
client.watch.add(target={"source": "hf", "repo_type": "model", "repo_id": "org/model", "revision": "main"})
drift = client.watch.drift()
results = client.watch.discover(search="bert", source="hf", page=1, page_size=20)

# Reproducibility
client.lockfiles.validate("modely.lock", profile="production")
client.assets.resolve_approved("hf:model:org--model", channel="production")

# Credential management
sa = client.service_accounts.create("ci-bot", roles=["Developer"])
token = client.tokens.create(sa["id"], scopes=["asset:read", "asset:download"])
client.tokens.rotate(token["id"])
client.tokens.revoke(token["id"])

# Intelligence
results = client.search("nlp", source="hf")
trends = client.get_risk_trends()
usage = client.get_usage_popularity()
```

#### Enterprise CLI Commands

```bash
# Catalog & governance
modely-ai asset search --server http://localhost:8000
modely-ai recommend hf:model:org--model --server http://localhost:8000
modely-ai alternatives hf:model:org--model --server http://localhost:8000

# Watch & discover
modely-ai watch discover --source hf --search bert --page-size 20
modely-ai watch add hf://models/org/model --revision main    # HF default branch
modely-ai watch add ms://models/org/model --revision master  # ModelScope default branch

# Reproducibility & snapshots
modely-ai snapshot list --server http://localhost:8000
modely-ai snapshot promote snap_xxx --channel production --server http://localhost:8000
modely-ai manifest-diff left.lock right.lock
modely-ai catalog-gate catalog.json --profile production

# Credential lifecycle
modely-ai token-create --service-account-id sa_xxx --scopes "asset:read" --server http://localhost:8000
modely-ai token-rotate tok_xxx --server http://localhost:8000
modely-ai token-revoke tok_xxx --server http://localhost:8000
```

#### Web Dashboard (modely-web)

A React SPA dashboard is included at `src/modely/server/web/`:

```bash
cd src/modely/server/web
npm install && npm run dev    # Vite dev server :5173 → proxy /api → :8000
```

Pages: Asset List/Search, Asset Detail (with file tree, preview, download URLs, governance enrichment), Sync Jobs, Watch (Targets + Discover), Snapshots, CI Gate, Token Management, Enterprise Search, Analytics Dashboard.

#### Enterprise Worker (modely-worker)

Background task execution with in-process (MVP) and future RQ/Celery backends:

```python
from modely.application.worker_queue import InProcessTaskQueue, enqueue_sync_job
from modely.syncing.workers import LocalMirrorWorker

queue = InProcessTaskQueue()
task_id = enqueue_sync_job(job, queue=queue, worker=worker)
result = queue.get_result(task_id)
```

#### Dev Mode (DevNullServices)

For local development and demos, the server can run against your local modely cache without a production backend:

```bash
modely-server --dev
```

`DevNullServices` reads from `~/.cache/modely/` and `~/.modely/watch_state.json`, providing real data for the web UI. Sync jobs execute via `CompositeSourceAdapter` using real network adapters (HF, ModelScope, GitHub). File preview supports safe text-file rendering with path traversal protection. The catalog layer persists sidecar `modely-info.json` metadata alongside cached assets for offline governance enrichment.

#### Multi-Tenant Isolation

```python
from modely.governance.tenant_isolation import TenantContext, TenantFilteredRepository
from modely.domain.tenants import TenantScope

ctx = TenantContext(tenant_scope=TenantScope(organization_id="org-1", workspace_id="ws-1"))
filtered_repo = TenantFilteredRepository(repository, ctx)
# All operations now scoped to org-1/ws-1
```

#### Governance & Approval Workflow

```python
from modely.application.governance_service import GovernanceService

svc = GovernanceService()
req = svc.submit_approval({"asset_id": "asset_1", "requester": "user_1"})
svc.approve(req.id, reviewer="admin", reason="OK")
# Full lifecycle: submit → pending → approved/rejected/cancelled

# Quota enforcement
svc.set_quota({"subject": "org1", "dimension": "downloads", "limit": 100, "mode": "hard"})
svc.check_quota("org1", "downloads")  # {"allowed": True, ...}
```

The governance engine provides:

- **RBAC** (`modely.governance.rbac`): Permission-based access control with actions like `asset:read`, `asset:download`, `policy:manage`.
- **Policy evaluation** (`modely.governance.policy`): Evaluate assets against configurable policy profiles with `block`, `require_approval`, `warn`, and `allow` decisions.
- **Approval workflow** (`modely.governance.approvals`): Submit, approve, reject, cancel, escalate, and expire access requests with auto-approval rules and break-glass overrides.
- **Audit** (`modely.governance.audit`): Record and query audit events for all governance actions.
- **API tokens** (`modely.governance.api_tokens`): Token lifecycle management (create/rotate/revoke) for service accounts with scoped permissions.
- **Redaction** (`modely.governance.redaction`): Sensitive field detection and redaction for audit-safe payloads.
- **Download authorization** (`modely.storage.download_urls`): Multi-step authorization pipeline (RBAC → visibility → policy → audit) with signed download URL generation.

### Resource Sync Center

`sync-center` is a local control plane for resources your team wants to keep synchronized. It stores registry state under `~/.modely/sync-center/`, records run history in JSONL, and reuses the existing plan/download/catalog/watch primitives. It does **not** replace direct one-shot `sync` or `mirror`.

```bash
# Register a managed resource. Token values are not stored; use an env var name.
modely-ai sync-center add hf://models/Qwen/Qwen2.5-7B-Instruct \
  --id qwen-7b \
  --local-dir ./vendor/models/qwen \
  --revision main \
  --include "*.json" "*.safetensors" \
  --profile inference \
  --checksum \
  --token-env HF_TOKEN \
  --label llm

# Inspect registry state and run history.
modely-ai sync-center list
modely-ai sync-center show qwen-7b --json
modely-ai sync-center runs --target qwen-7b --limit 20

# Preview and execute managed syncs.
modely-ai sync-center plan qwen-7b
modely-ai sync-center plan --all --json
modely-ai sync-center run qwen-7b
modely-ai sync-center run --all --checksum

# Check remote drift without downloading. MVP drift checks support HF and ModelScope;
# unsupported sources return a warning/status instead of pretending they were checked.
modely-ai sync-center check qwen-7b
modely-ai sync-center check --all --json

# Build inventory from registered local directories.
modely-ai sync-center catalog --snapshot
modely-ai sync-center catalog --output sync-center-catalog.json --json
```

`sync-center remove TARGET_ID` removes only the local registry/state entry; it does not delete downloaded files.

#### Download from Hugging Face

Download an entire model repository:
```bash
modely-ai hf bert-base-uncased
```

Download a specific file from a repository:
```bash
modely-ai hf bert-base-uncased --file config.json
```

Download with specific options (repository type defaults to `auto`; pass an explicit type when needed):
```bash
modely-ai hf facebook/opt-2.7b --repo-type model --revision v1.1.0 --local-dir ./models
```

Download from a private repository:
```bash
modely-ai hf username/private-repo --token YOUR_HUGGINGFACE_TOKEN
```

Download only specific files with patterns:
```bash
modely-ai hf gpt2 --include "config.json" "tokenizer.json"
```

Exclude large model weights:
```bash
modely-ai hf meta-llama/Llama-2-7b --exclude "*.safetensors" "*.bin"
```

Use a mirror endpoint (for regions where Hugging Face is slow):
```bash
modely-ai hf gpt2 --endpoint https://hf-mirror.com
```

List files in a repository without downloading:
```bash
modely-ai hf gpt2 --list-files
```

Preview what would be downloaded (dry-run):
```bash
modely-ai hf gpt2 --dry-run --exclude "*.safetensors" "*.bin"
```

#### Download from ModelScope

Download an entire model repository:
```bash
modely-ai ms owner/model-name
```

Download a specific file:
```bash
modely-ai ms owner/model-name --file config.json
```

Download a dataset (repository type also accepts `auto`, which starts from the source default):
```bash
modely-ai ms owner/dataset-name --repo-type dataset
```

Download with specific options:
```bash
modely-ai ms owner/model-name --revision master --local-dir ./models
```

Use the optional official ModelScope SDK backend:
```bash
# Install optional SDK support
pip install "modely-ai[modelscope]"

# Auto uses the official SDK when installed, otherwise the lightweight backend
modely-ai ms owner/model-name --backend auto

# Force official SDK or the built-in lightweight downloader
modely-ai ms owner/model-name --backend official
modely-ai ms owner/model-name --backend lightweight
```

#### Download from GitHub

Download an entire repository:
```bash
modely-ai github owner/repo
```

Download a specific file:
```bash
modely-ai github owner/repo --file README.md
```

Download with specific options:
```bash
modely-ai github owner/repo --revision dev --local-dir ./repos
```

Download with Git LFS support (for large files):
```bash
modely-ai github owner/repo --with-lfs
```

Download from a private repository:
```bash
modely-ai github owner/private-repo --token YOUR_GITHUB_TOKEN
```

Download only selected paths with sparse checkout or remove excluded files after clone:
```bash
modely-ai github owner/repo --include "configs/*" README.md
modely-ai github owner/repo --exclude "*.bin" "*.safetensors"
```

Download a GitHub release asset:
```bash
modely-ai github owner/repo --release v1.0.0 --asset model.tar.gz
```

GitHub repositories are treated as `tool` resources in modely-ai. Even when a unified command is called with `--repo-type model` or `--repo-type auto`, GitHub downloads and cache entries are normalized to `github/tools/...` rather than `github/models/...`.

#### Unified Query, Download, Lock, and Sync

Use modely resource URIs to address repositories across platforms:

```bash
# Repository metadata, cards, and analysis
modely-ai info gpt2                         # plain IDs default to Hugging Face with repo type auto
modely-ai info HennyPr/ps2_hf2              # resolves as a dataset when the model probe misses
modely-ai info HennyPr/ps2_hf2 --repo-type dataset
modely-ai info hf://datasets/HennyPr/ps2_hf2
modely-ai info hf://models/gpt2
modely-ai info ms://models/AI-ModelScope/gpt2
modely-ai info github://owner/repo --json
modely-ai card hf://models/gpt2 --json
modely-ai analyze hf://models/gpt2 --profile minimal
modely-ai analyze hf://models/gpt2 --deep --json
modely-ai score hf://models/gpt2
modely-ai score hf://models/gpt2 --json
modely-ai scan hf://models/gpt2
modely-ai scan hf://models/gpt2 --json
modely-ai compare hf://models/gpt2 ms://models/AI-ModelScope/gpt2
modely-ai compare hf://models/gpt2 ms://models/AI-ModelScope/gpt2 --files --card --formats --deep
modely-ai resolve qwen2.5-7b-instruct
modely-ai resolve qwen2.5-7b-instruct --source all --json
modely-ai resolve hf://models/Qwen/Qwen2.5-7B-Instruct --repo-type model

# File listing and planning
modely-ai files hf://models/gpt2 --include "*.json" --summary
modely-ai files github://owner/repo --release v1.0.0 --json
modely-ai plan hf://models/gpt2 --profile minimal
modely-ai plan Qwen/Qwen2.5-7B --source hf --profile no-weights --json

# Unified download with optional fallback preference
modely-ai get hf://models/gpt2 --file config.json
modely-ai get Qwen/Qwen2.5-7B --source auto --prefer ms,hf --fallback
modely-ai get Qwen/Qwen2.5-7B --source auto --prefer fastest --fallback --profile inference
modely-ai get hf://models/gpt2 --file config.json --retries 5 --timeout 30 --no-resume
modely-ai get hf://models/gpt2 --file config.json --checksum
modely-ai get github://owner/repo --include "examples/*"

# Source endpoint discovery/probing and declared backend capabilities
modely-ai capabilities
modely-ai capabilities --source hf --json
modely-ai sources list
modely-ai sources list --source hf
modely-ai sources probe hf://models/gpt2 --source all
modely-ai sources probe kaggle://datasets/owner/dataset --source kaggle

# Store tokens for private downloads/queries
modely-ai login hf --token YOUR_HF_TOKEN
printf '%s' "$HF_TOKEN" | modely-ai login hf --stdin
modely-ai login ms --token YOUR_MODELSCOPE_TOKEN
modely-ai login github --token YOUR_GITHUB_TOKEN
modely-ai whoami hf
modely-ai logout github

# Reproducible local installs
modely-ai lock hf://models/gpt2 --include "*.json" --output modely.lock
modely-ai lock hf://models/gpt2 --profile minimal --alternatives hf,ms --output modely.lock --json
modely-ai install -f modely.lock --local-dir ./models/gpt2
modely-ai install -f modely.lock --fallback --prefer ms,hf --local-dir ./models/gpt2
modely-ai validate-lock -f modely.lock --local-dir ./models/gpt2 --checksum

# Catalog local assets or modely cache
modely-ai catalog scan ./models
modely-ai catalog scan ./models --json
modely-ai catalog scan --cache --cache-dir ~/.cache/modely
modely-ai catalog scan ./models --output catalog.json
modely-ai catalog scan ./models --score --scan --json
modely-ai catalog scan ./models --snapshot --history-dir .modely/catalog
modely-ai catalog history --dir .modely/catalog
modely-ai catalog diff old-catalog.json new-catalog.json --json
modely-ai catalog export catalog.json --output catalog.csv
modely-ai catalog gate catalog.json --fail-on medium --json

# Aggregate governance and reporting
modely-ai doctor gpt2 --json
modely-ai choose qwen2.5-7b --strategy safest --json
modely-ai verify-mirror hf://models/gpt2 ms://models/AI-ModelScope/gpt2 --json
modely-ai report hf://models/gpt2 --format markdown
modely-ai report ./models/gpt2 --format html --output gpt2-report.html
modely-ai benchmark gpt2 --source hf,ms --json
modely-ai cache dedupe --dry-run --json
modely-ai cache serve --open

# Download-only local sync/mirror (no upload)
modely-ai sync hf://models/gpt2 --local-dir ./mirror/gpt2 --include "*.json"
modely-ai sync hf://models/gpt2 --local-dir ./mirror/gpt2 --report sync-report.json --analyze --deep
modely-ai mirror ms://models/AI-ModelScope/gpt2 --local-dir ./mirror/ms-gpt2 --report mirror-report.json --compare-to hf://models/gpt2 --deep
```

Token resolution order is: explicit `--token`, environment variables (`HF_TOKEN`, `HUGGINGFACE_TOKEN`, `MODELSCOPE_TOKEN`, `GITHUB_TOKEN`), then tokens saved in `~/.modely/config.json`. Use `login --stdin` to avoid putting tokens in shell history; saved token config files are chmodded to `0600` on supported systems.

Download profiles provide common file-selection presets across `files`, `plan`, `get`, `sync`, and `mirror`:

- `full`: no additional filtering
- `minimal`: README/model card, config, and tokenizer files
- `no-weights`: exclude common large weight formats such as `.bin`, `.safetensors`, `.gguf`, `.onnx`, `.ckpt`
- `inference`: config/tokenizer plus common inference weight formats such as `.safetensors` and `.gguf`

`plan` is a download preview: it lists the selected files, estimated total size, cache hits/misses, and file categories without downloading. `sources probe` performs lightweight endpoint checks for availability/latency; `--prefer fastest` uses these probes to rank candidate sources, not to benchmark full download throughput.

`get --checksum` verifies downloaded files when the remote file listing exposes SHA256 metadata. Missing remote SHA256 values are treated as skipped checksum checks rather than failures, while local missing files or mismatched hashes fail the command. Retry handling skips non-retryable permanent failures such as 401/403/404 and invalid revisions, but still retries transient timeouts, rate limits, and 5xx/network failures.

#### Search Models and Datasets

Search for models, datasets, and AI/ML repositories across Hugging Face, ModelScope, and GitHub with a unified interface:

```bash
# Browse top models without a keyword
modely-ai search --source hf --limit 10

# Search Hugging Face for models matching "gpt2"
modely-ai search gpt2 --source hf --limit 10

# Search ModelScope for models matching "qwen"
modely-ai search qwen --source ms --limit 10

# Search GitHub for AI/ML repositories matching "llama"
modely-ai search llama --source github --limit 10

# Search Hugging Face datasets
modely-ai search glue --source hf --repo-type dataset

# Search ModelScope datasets
modely-ai search mnist --source ms --repo-type dataset

# Filter by task type
modely-ai search bert --task text-classification

# Filter by library and sort by likes
modely-ai search llama --library transformers --sort likes

# Filter by date range (created after 2024)
modely-ai search gpt2 --after 2024-01-01 --sort created_at

# Sort by newest first
modely-ai search qwen --sort lastModified --direction desc

# JSON output for scripting
modely-ai search gpt2 --source hf --json | jq '.[].id'
modely-ai search qwen --source all --json | jq '.[].modely_uri'

# Search all supported platforms simultaneously; --repo-type auto searches models and datasets where supported
modely-ai search qwen --source all --repo-type auto

# Preview tag-matched batch downloads (dry-run by default)
modely-ai batch-download qwen --source hf --repo-type model --tag text-generation --tag transformers --limit 5 --profile inference
modely-ai batch-download mnist --source ms --repo-type dataset --tag vision --limit 3 --json

# Execute the planned batch download explicitly
modely-ai batch-download qwen --source hf --repo-type model --tag text-generation --tag transformers --limit 5 --profile inference --local-dir ./models --yes

# Search Kaggle datasets when Kaggle credentials/CLI are configured
modely-ai search mnist --source kaggle --repo-type dataset

# Group potential cross-platform matches by normalized repository name
modely-ai search qwen --source all --dedupe
modely-ai search qwen --source hf --compare

# Resolve likely equivalent resources across sources with confidence signals
modely-ai resolve qwen2.5-7b-instruct
modely-ai resolve qwen2.5-7b-instruct --source all --json
```

Search results are displayed as a table showing source, repository type (`model`, `dataset`, `tool`, etc.), repository ID, task type, downloads, likes, created date, last modified date, and the repository's web page URL. Hugging Face result URLs are generated from `repo_type`, so dataset results link to `https://huggingface.co/datasets/...` and Space results link to `https://huggingface.co/spaces/...`. JSON output uses a stable cross-source schema with fields such as `id`, `source`, `repo_type`, `modely_uri`, `name`, `summary`, `downloads`, `likes`, `stars`, `forks`, `size_bytes`, tags, license, and source-specific `metadata`. The keyword argument is optional — omit it to browse all repositories. `--repo-type auto` searches models and datasets on Hugging Face and ModelScope, uses `tool` for GitHub repositories, and uses `dataset` for Kaggle. GitHub search maps stars to likes and forks to downloads. Kaggle search is best-effort and requires the Kaggle package/credentials to be configured in the local environment.



#### Watch Hugging Face, ModelScope, and GitHub for Updates

Create a watch configuration:
```bash
modely-ai watch init
```

The generated config starts with an empty `targets` list. Edit `~/.modely/watch.json` to list the repositories to monitor:
```json
{
  "state_file": "~/.modely/watch_state.json",
  "targets": [
    {
      "source": "hf",
      "repo_type": "model",
      "repo_id": "bert-base-uncased",
      "revision": "main",
      "download": "snapshot",
      "ignore_patterns": ["*.safetensors"]
    },
    {
      "source": "ms",
      "repo_type": "dataset",
      "repo_id": "owner/dataset-name",
      "revision": "master",
      "download": "files",
      "files": ["README.md", "data/train.jsonl"]
    },
    {
      "source": "github",
      "repo_type": "tool",
      "repo_id": "owner/repo",
      "revision": "main",
      "download": "snapshot"
    }
  ]
}
```

Run one check manually:
```bash
modely-ai watch run
```

Install a recurring check with `crontab`:
```bash
# Every day at 02:30
modely-ai watch install --every day --time 02:30

# Every Monday at 02:30
modely-ai watch install --every week --weekday mon --time 02:30
```

Inspect or remove the installed job:
```bash
modely-ai watch status
modely-ai watch uninstall
```

Watch state is stored in `~/.modely/watch_state.json` by default. Cron output is appended to `~/.modely/watch.log` for the default config, or to `watch.log` next to a custom config file. For private repositories, set `token_env` in the target and put the token in that environment variable instead of writing secrets into the config file. For large models or datasets, prefer `allow_patterns`, `ignore_patterns`, or `download: "files"` so the watcher does not mirror unnecessary large files.

Each source has its own default revision convention: Hugging Face uses `main`, ModelScope uses `master`, and GitHub uses `main`. When adding watch targets, use the revision appropriate for the source — using the wrong revision (e.g., `main` for ModelScope) will cause file listing to return empty results.

ModelScope dataset file listing may not be available for every repository through the lightweight API. When a ModelScope target uses `download: "files"` with explicit `files`, modely refreshes those files on each scheduled run if remote listing is unavailable. Snapshot downloads and pattern-based ModelScope filtering still require a remote file list.

### Python API

You can also use modely-ai directly in your Python code:

```python
from modely import (
    hf_file_download,
    hf_snapshot_download,
    modelscope_snapshot_download,
    github_file_download,
    github_snapshot_download,
)
from modely.card import get_card
from modely.compare import compare_resources
from modely.files import list_repo_files, summarize_files
from modely.get import download_resource
from modely.info import get_repo_info
from modely.manifest import create_lock, install_lock, validate_lock
from modely.plan import create_download_plan
from modely.profiles import resolve_download_profile
from modely.search import search
from modely.search.dedupe import dedupe_results
from modely.sources import list_source_profiles, rank_sources
from modely.sync import sync_resource
from modely.uri import format_modely_uri, parse_modely_uri

# Search for models
results = search("gpt2", source="hf", repo_type="model", task="text-generation", limit=5)
for r in results:
    print(f"{r.id}: {r.downloads} downloads, {r.url}")
groups = dedupe_results(results)

# Download an entire Hugging Face repository
model_path = hf_snapshot_download(
    repo_id="bert-base-uncased",
    repo_type="model",
    revision="main"
)

# Download a specific file from Hugging Face
file_path = hf_file_download(
    repo_id="bert-base-uncased",
    filename="config.json",
    repo_type="model"
)

# Download from ModelScope
ms_model_path = modelscope_snapshot_download(
    repo_id="owner/model-name",
    repo_type="model",
    revision="master"
)

# Download an entire GitHub repository
repo_path = github_snapshot_download(
    repo_id="owner/repo",
    revision="main"
)

# Download a specific file from GitHub
file_path = github_file_download(
    repo_id="owner/repo",
    filename="README.md",
    revision="main"
)

# Use unified resource URIs
ref = parse_modely_uri("hf://models/gpt2?revision=main&file=config.json")
assert format_modely_uri(ref) == "hf://models/gpt2?revision=main&file=config.json"
info = get_repo_info("hf://models/gpt2")
files = list_repo_files("github://owner/repo", revision="main")
summary = summarize_files(files, include=["*.json"])
card = get_card("hf://models/gpt2")
plan = create_download_plan("hf://models/gpt2", profile="minimal")
comparison = compare_resources("hf://models/gpt2", "ms://models/AI-ModelScope/gpt2", include_files=True, include_formats=True, deep=True)
path = download_resource("hf://models/gpt2", file="config.json")

# Resolve profile presets and probe sources
include, exclude = resolve_download_profile("no-weights", include=None, exclude=None)
profiles = list_source_profiles()
probe_results = rank_sources("hf://models/gpt2", candidates=["hf", "hf-mirror"])

# Create, install, and validate reproducible lockfiles
lock = create_lock("hf://models/gpt2", include=["*.json"], output="modely.lock")
installed_path = install_lock("modely.lock", local_dir="./models/gpt2")
validation = validate_lock("modely.lock", local_dir="./models/gpt2", checksum=True)

# Mirror/sync downloads to a local directory
mirror_path = sync_resource("ms://models/AI-ModelScope/gpt2", local_dir="./mirror/ms-gpt2")
```

## Cache Management

modely-ai includes a unified cache system to avoid duplicate downloads. Files are organized by source (Hugging Face / ModelScope / GitHub / Kaggle), repository type, repository ID, and revision. GitHub repositories are always cached as `tool` resources under `github/tools/`, because GitHub is a code/repository backend rather than a model/dataset registry in modely-ai's cache model.

### Cache Directory Configuration

The cache directory is resolved with the following priority:

1. **CLI argument**: `--cache-dir` (for download commands) or `modely cache --cache-dir <DIR>`
2. **Environment variable**: `MODELY_CACHE`
3. **Config file**: `~/.modely/config.json` (set via `modely cache config --set <DIR>`)
4. **Default**: `~/.cache/modely`

```bash
# Set cache directory via environment variable
export MODELY_CACHE=/path/to/cache

# Or set via config file (persistent)
modely-ai cache config --set /path/to/cache

# Or specify per-command
modely-ai --cache-dir /path/to/cache hf gpt2
```

### Cache Structure

```
~/.cache/modely/
├── hf/                    # Hugging Face cache
│   ├── models/            # repo_type = model
│   │   └── gpt2/
│   │       └── main/     # revision
│   │           ├── config.json
│   │           └── pytorch_model.bin
│   └── datasets/         # repo_type = dataset
├── ms/                    # ModelScope cache
│   ├── models/
│   │   └── owner--model-name/
│   │       └── master/
│   └── datasets/
└── github/                # GitHub cache
    └── tools/             # GitHub resources are always repo_type = tool
        └── owner--repo/
            └── main/
                ├── README.md
                └── (repository files)
```

### Cache Hit

When downloading the same file again, modely-ai detects the cached file and skips the download:

```bash
# First download
modely-ai hf gpt2 --file config.json
# Output: Downloading config.json from gpt2...

# Second download (cached)
modely-ai hf gpt2 --file config.json
# Output: File already cached at: ~/.cache/modely/hf/models/gpt2/main/config.json
```

### Cache Commands

```bash
# Show cache directory and total size
modely-ai cache info

# List all cached repositories
modely-ai cache list

# List with detailed file information
modely-ai cache list --detail

# Clean all cache
modely-ai cache clean

# Clean specific repository cache
modely-ai cache clean gpt2

# Show current cache directory configuration
modely-ai cache config

# Set new cache directory
modely-ai cache config --set /tmp/my-cache
```

## Command Reference

### Hugging Face Commands

```bash
modely-ai hf <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file path to download from the repository
- `--repo-type {auto,model,dataset,space}`: Type of repository (default: auto; explicit `dataset`/`space` is available when needed)
- `--revision REVISION`: Revision of the model (default: main)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: Access token for private repositories
- `--force-download`: Force re-download even if file exists
- `--include PATTERN [PATTERN ...]`: Glob patterns to include (e.g., `"*.json" "*.safetensors"`)
- `--exclude PATTERN [PATTERN ...]`: Glob patterns to exclude (e.g., `"*.bin" "*.msgpack"`)
- `--endpoint URL`: HF API endpoint for mirrors (e.g., `https://hf-mirror.com`)
- `--list-files`: List remote repository files without downloading
- `--dry-run`: Show what would be downloaded (count, total size) without downloading

### ModelScope Commands

```bash
modely-ai ms <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file path to download from the repository
- `--repo-type {auto,model,dataset}`: Type of repository (default: auto; explicit `dataset` is available when needed)
- `--revision REVISION`: Revision of the model (default: master)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: Access token for private models
- `--backend {auto,official,lightweight}`: ModelScope backend to use (default: auto)
- `--include PATTERN [PATTERN ...]`: Glob patterns to include (e.g., `"*.json" "*.safetensors"`)
- `--exclude PATTERN [PATTERN ...]`: Glob patterns to exclude (e.g., `"*.bin" "*.msgpack"`)
- `--endpoint URL`: ModelScope API endpoint
- `--list-files`: List remote repository files without downloading
- `--dry-run`: Show what would be downloaded (count, total size) without downloading

### GitHub Commands

```bash
modely-ai github <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file to download from the repository
- `--revision REVISION`: Branch, tag, or commit SHA (default: main)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: GitHub personal access token for private repositories
- `--with-lfs`: Enable Git LFS support for large files
- `--force-download`: Force re-download even if file exists
- `--include PATTERN [PATTERN ...]`: Sparse checkout/include patterns for repository clones
- `--exclude PATTERN [PATTERN ...]`: Remove matching files after clone
- `--release TAG`: Release tag for asset operations
- `--asset NAME`: Release asset name to download
- `--submodules`: Initialize git submodules after clone

### Unified Aggregation Commands

```bash
modely-ai info <URI> [--json]
modely-ai card <URI> [--json]
modely-ai analyze <URI> [--profile PROFILE] [--deep] [--json]
modely-ai score <URI> [--profile PROFILE] [--json]
modely-ai scan <URI> [--profile PROFILE] [--json]
modely-ai compare <URI> <URI> [--files] [--card] [--formats] [--deep] [--json]
modely-ai resolve <query-or-URI> [--source SOURCE] [--threshold N] [--json]
modely-ai files <URI> [--include PATTERN ...] [--exclude PATTERN ...] [--profile PROFILE] [--summary] [--json]
modely-ai plan <URI-or-repo> [--source SOURCE] [--profile PROFILE] [--json]
modely-ai get <URI-or-repo> [OPTIONS]
modely-ai capabilities [--source SOURCE | --backend BACKEND] [--json]
modely-ai sources <list|probe> [OPTIONS]
modely-ai login <hf|ms|github> (--token TOKEN | --stdin)
modely-ai logout <hf|ms|github>
modely-ai whoami <hf|ms|github>
modely-ai lock <URI> [--profile PROFILE] [--alternatives hf,ms] [--output modely.lock] [--json]
modely-ai validate-lock -f modely.lock [--local-dir DIR] [--checksum] [--json]
modely-ai install -f modely.lock [--fallback] [--prefer ms,hf] [--local-dir DIR]
modely-ai catalog scan [ROOT] [--cache] [--score] [--scan] [--remote] [--json] [--output FILE]
modely-ai catalog <diff|export|history|gate> [OPTIONS]
modely-ai doctor <query-or-URI> [--source SOURCE] [--probe] [--json]
modely-ai choose <query-or-URI> [--strategy STRATEGY] [--json]
modely-ai verify-mirror <URI> <URI> [--no-deep] [--json]
modely-ai report <URI-or-path> [--format markdown|html|json] [--output FILE]
modely-ai benchmark [URI-or-query] [--source hf,ms] [--json]
modely-ai batch-download [keyword] [--tag TAG ...] [--task TASK] [--limit N] [--yes] [--json]
modely-ai cache dedupe --dry-run [--json]
modely-ai cache serve [--host 127.0.0.1] [--port 8765] [--open]
modely-ai sync <URI> --local-dir DIR
modely-ai mirror <URI> --local-dir DIR
```

Supported URI forms include `hf://models/<repo>`, `hf://datasets/<repo>`, `ms://models/<repo>`, `ms://datasets/<repo>`, `github://owner/repo`, `kaggle://datasets/<owner>/<dataset>`, and `kaggle://competitions/<competition>`. Query parameters such as `?revision=...&file=...` are supported where the backend can use them.

Common options:
- `--profile {full,minimal,no-weights,inference}`: Apply a reusable file-selection preset.
- `--include PATTERN [PATTERN ...]`: Include only matching paths.
- `--exclude PATTERN [PATTERN ...]`: Exclude matching paths.
- `--summary`: Show file counts, selected size, and asset categories for `files`.
- `--prefer fastest`: Probe configured source endpoints and try the lowest-latency available source first.
- `--manifest FILE --checksum`: Write a local download manifest with optional SHA256 checksums.
- `--max-workers N`: Pass concurrency through to supported backends such as Hugging Face snapshot downloads.
- `--retries N`: Retry unified `get` backend calls before failing.
- `--timeout SECONDS`: Pass timeout controls to supported HTTP/probe backends.
- `--backend {auto,official,lightweight}` or a registered backend name such as `hf-sdk`, `modelscope-official`, `modelscope-lightweight`, `github-git`, `github-http`, or `kaggle-api`: Select the backend implementation where supported.
- `--no-resume`: Disable backend resume behavior where supported by `get`.

#### Command Notes

- `plan` is a dry-run planning command. It does not download files; it shows selected files, estimated size, cache hits/misses, and model asset categories.
- `card` fetches a README/model card and parses simple YAML-style frontmatter.
- `analyze` combines metadata, file summaries, weight-format detection, card presence, and largest-file reporting. `analyze --deep` adds filename/metadata-derived format byte counts, quantization hints, profile recommendations, and risk flags without downloading file contents.
- `score` is metadata/file-list based and does not download weights; it summarizes asset health across completeness, metadata, popularity, freshness, reproducibility, and safety.
- `scan` flags metadata, safety, and reproducibility risks based on file names and remote metadata; it does not execute code or inspect binary contents.
- `catalog scan` inventories local directories or the modely cache and is local/offline by default. `--score` and `--scan` use local path enrichment by default, while `--remote` allows remote metadata/API enrichment for entries that have source metadata.
- `catalog gate` evaluates saved catalog scan summaries for CI policy decisions.
- `doctor` and `choose` compose resolve/score/scan/probe signals into recommendations.
- `verify-mirror` is a read-only comparison wrapper for mirror-equivalence checks.
- `report` renders markdown, HTML, or JSON reports for remote resources or local paths.
- `benchmark` performs lightweight source endpoint availability/latency checks; it is not a full bandwidth benchmark.
- `batch-download` searches resources, optionally filters results by tags using AND semantics, and previews the matching downloads by default. Pass `--yes` to perform the batch download.
- `cache dedupe --dry-run` reports duplicate cache blobs without modifying files.
- `cache serve` starts a read-only local cache browser at `http://127.0.0.1:8765` by default, showing cached assets by source, type, revision, size, and file list in a card-based web UI.
- `resolve` is search-based and heuristic: it finds likely equivalent resources across sources, assigns confidence scores, and explains matching signals. Use `compare --files --card --formats --deep` to verify whether two candidates are actually identical.
- `compare` performs a deep pairwise comparison of two explicit resources. `--files`, `--card`, `--formats`, and `--deep` add file diffs, normalized card metadata diffs, and format/deep-analysis deltas.
- `capabilities` reports registered backend support and optional dependency availability. Official SDK/API plugins include `hf-sdk`, `modelscope-official`, and `kaggle-api`; lightweight/API backends include `modelscope-lightweight`, `github-http`, and `github-git`.
- `validate-lock` is local-only and verifies that files described by a lockfile exist under `--local-dir`. With `--checksum`, it also compares SHA256 values when present.
- `sources probe` performs lightweight endpoint checks and should be treated as availability/latency routing rather than a full bandwidth benchmark.

### Watch Commands

```bash
modely-ai watch <init|run|list|drift|install|status|uninstall|discover> [OPTIONS]
```

Options:
- `init --config FILE --force`: Create a JSON watch config template
- `run --config FILE`: Check configured targets once and download changed repositories
- `list --config FILE`: Show configured targets and their last known state
- `drift --config FILE --json`: Check configured targets for remote drift without downloading or updating state
- `discover --config FILE [--source hf|ms|github] [--repo-type model|dataset|tool] [--search QUERY] [--page N] [--page-size 10|20|30]` : Cross-platform search to discover repositories to watch (also available via the Watch UI Discover tab)
- `install --config FILE --every {day,week} --time HH:MM --weekday mon`: Install a crontab job
- `status --config FILE`: Show the installed crontab job
- `uninstall --config FILE`: Remove the installed crontab job

### Search Commands

```bash
modely-ai search [keyword] [OPTIONS]
```

Search is available across Hugging Face (models and datasets), ModelScope (models and datasets), GitHub (AI/ML repositories), and experimental Kaggle dataset search. The keyword is optional — omit it to browse all repositories. GitHub search maps stars to likes and forks to downloads.

Options:
- `--source, -s {hf,ms,github,kaggle,all}`: Platform to search (default: all)
- `--repo-type, -t {auto,model,dataset,tool}`: Type of repository (default: auto; HF/MS auto searches models and datasets, GitHub uses `tool`)
- `--task TASK`: Filter by task type (e.g., text-classification, text-generation)
- `--library LIBRARY`: Filter by library, HF only (e.g., transformers, pytorch)
- `--license LICENSE`: Filter by license, HF only
- `--sort {downloads,lastModified,likes,created_at}`: Sort field (default: downloads)
- `--direction {asc,desc}`: Sort direction (default: desc)
- `--limit, -n N`: Max results per source (default: 20)
- `--author AUTHOR`: Filter by author/owner
- `--after DATE`: Only repos modified after this date (YYYY-MM-DD)
- `--before DATE`: Only repos modified before this date (YYYY-MM-DD)
- `--json`: Output results as JSON instead of a table
- `--dedupe`: Group potential cross-platform matches by normalized repository name
- `--compare`: Show grouped search-result comparison rows (lightweight; use `modely-ai compare` for deep pairwise comparison)

## Requirements

- Python 3.10 or higher
- requests >= 2.25.0
- tqdm >= 4.62.0
- huggingface-hub >= 0.20.0
- Optional: modelscope >= 1.0.0 for `modely-ai[modelscope]` official ModelScope SDK backend
- Optional: kaggle for experimental Kaggle dataset/competition search and downloads

## Development

### Setup

```bash
pip install -e ".[dev]"
```

### Running Tests

Unit tests (no network required):
```bash
pytest tests/ -m "not integration"
```

Integration tests (require network access):
```bash
pytest tests/ -m integration
```

All tests:
```bash
pytest tests/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue to improve the functionality or documentation.

## Support

If you encounter any issues or have questions, please open an issue on the GitHub repository.
