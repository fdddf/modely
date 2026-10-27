# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

modely-ai is a Python package providing a unified CLI and Python API for downloading, inspecting, caching, syncing, scanning, reporting, and governing AI models, datasets, and tool repositories across Hugging Face, ModelScope, GitHub, Kaggle, and planned enterprise/internal sources.

The project is evolving from a lightweight downloader into an enterprise AI asset platform. Preserve the existing CLI/API behavior while adding enterprise modules additively.

## Common Commands

### Development Setup

```bash
pip install -e .              # Install in editable mode
pip install -e ".[dev]"       # Install with test dependencies
```

### Build & Install

```bash
pip install .                  # Regular install
pip install -e .               # Editable mode (for development)
```

### Running the CLI

Existing source/download/cache commands include:

```bash
modely-ai hf <repo>            # Download from Hugging Face
modely-ai ms <repo>            # Download from ModelScope
modely-ai github <repo>        # Download from GitHub
modely-ai cache <cmd>          # Cache management
```

The current CLI also includes broader asset/governance commands such as search/info/files/scan/score/report/lock/install/catalog/policy/audit/sync-center/watch depending on the current branch state. Check `src/modely/cli/parser.py`, `README.md`, and `docs/specs/aggregate-governance.md` before adding or renaming commands.

Planned enterprise commands are documented in `docs/specs/enterprise-cli.md`. They are additive and must not be presented as implemented until wired and tested.

### Testing

```bash
# Unit tests (no network)
pytest tests/ -m "not integration"

# Integration tests (require network)
pytest tests/ -m integration

# All tests
pytest tests/
```

**IMPORTANT**: After any code change, run `pytest tests/ -m "not integration"` to verify unit tests pass.

For documentation-only changes, run:

```bash
git diff --check
```

## Architecture

### Compatibility Constraints

- Keep `modely-ai = "modely:main"` as the console entrypoint.
- Preserve existing top-level downloader modules and flat compatibility modules.
- Do not bulk-move existing logic into enterprise packages.
- New enterprise functionality should be additive and routed through structured packages.
- Existing imports verified by `tests/test_enterprise_compatibility.py` must keep working.

### Current and Planned Module Structure

Core/source modules remain under `src/modely/`:

```text
src/modely/
├── __init__.py              # console entrypoint facade
├── hf/                      # Hugging Face downloads
├── modelscope/              # ModelScope downloads
├── github/                  # GitHub downloads
├── kaggle/                  # Kaggle integration where present
├── common/                  # cache/config helpers
├── catalog.py               # compatibility facade
├── sync.py                  # compatibility facade
├── policy.py                # compatibility facade
├── auth.py                  # compatibility facade where present
├── audit.py                 # compatibility facade where present
├── report.py                # compatibility facade
├── manifest.py              # compatibility facade
├── cli/                     # argparse parser and handlers
├── application/             # cross-module application services
├── domain/                  # shared enterprise entities/enums
├── storage/                 # internal mirror/object storage abstraction
├── cataloging/              # enterprise catalog services
├── syncing/                 # sync job lifecycle, adapters, workers
├── governance/              # RBAC, permissions, approvals, policy, audit
├── reproducibility/         # lockfiles, manifest diff, snapshots, CI gate
├── integrations/            # MLflow, DVC, CI, training/inference adapters
├── intelligence/            # search, recommendations, analytics, graph, scoring
├── reporting/               # JSON/Markdown/CSV/SARIF/etc. renderers
└── server/                  # future REST API routes/schemas/app
```

Use `docs/specs/enterprise-platform-code-structure.md` as the authority for package responsibilities and migration staging.

### Key Patterns

**Unified Source Interface**: Platform modules expose downloader-style functions such as `file_download()` and `snapshot_download()` where applicable.

**Cache System** (`common/cache.py`):

- Cache directory priority: CLI arg > `MODELY_CACHE` env > config file > `~/.cache/modely`.
- Cache structure: `{cache_dir}/{source}/{type}/{repo_id}/{revision}/`.
- Source codes include `hf`, `ms`, `github`, and other integrations where implemented.
- Type codes include `models`, `datasets`, and `tools`.
- Repo ID normalization replaces `/` with `--` in directory names.

**CLI Pattern**:

- Uses `argparse` with subparsers.
- Existing commands must remain stable.
- Enterprise commands should be additive and should reuse shared application/governance decisions rather than bypassing server/shared policy.
- Future/planned commands in docs must be clearly labeled until implemented.

**Enterprise Domain Rules**:

- `docs/specs/enterprise-domain-model.md` owns canonical entity and enum definitions.
- `blocked` is a policy/access decision, not a visibility value.
- `pending_approval` and `approved` are approval states, not operational lifecycle states.
- Use `TenantScope` for tenant-scoped entities and queries.
- Phase 3 service accounts/API tokens reuse Phase 2 permission actions.
- Phase 4 intelligence must permission-filter and redact before ranking, graph traversal, recommendations, or report export.

### Dependencies

- `requests>=2.25.0` - HTTP requests
- `tqdm>=4.62.0` - Progress bars
- `huggingface-hub>=0.20.0` - Official HF SDK for reliable downloads
- System: `git` required for GitHub clone feature

Optional enterprise/server/search integrations should remain optional extras or documented extension points until selected.

## Enterprise Planning References

Before implementing enterprise work, read the relevant spec/task docs:

- `tasks/enterprise-platform/enterprise-platform-overall-plan.md`
- `tasks/enterprise-platform/phase-1-internal-mirror-catalog-mvp.md`
- `tasks/enterprise-platform/phase-2-governance-approvals.md`
- `tasks/enterprise-platform/phase-3-reproducibility-integrations.md`
- `tasks/enterprise-platform/phase-4-intelligent-governance.md`
- `docs/specs/enterprise-domain-model.md`
- `docs/specs/enterprise-api.md`
- `docs/specs/enterprise-cli.md`
- `docs/specs/enterprise-governance.md`
- `docs/specs/enterprise-security-threat-model.md`
- `docs/specs/enterprise-multitenancy-isolation.md`
- `docs/specs/enterprise-platform-mvp.md`
- `docs/specs/enterprise-deployment-ops.md`

## Adding a New Platform

To add support for a new external platform:

1. Create or update the source adapter module.
2. Follow existing downloader/source interface patterns.
3. Wire CLI behavior additively.
4. Update README and integration docs.
5. Add no-network unit tests with mocks/fixtures.
6. Mark live external tests as `integration`.
7. Preserve existing imports and compatibility facades.
