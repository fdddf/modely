# DVC Integration

modely-ai and DVC solve complementary parts of the ML asset lifecycle.

## What modely-ai does

- Finds, compares, downloads, locks, scans, and catalogs external assets before they enter a project.
- Produces local directories, lockfiles, reports, and catalog entries for selected models, datasets, and tool repositories.

## What DVC does

Use DVC for project-level data/model versioning and reproducibility:

- `dvc.yaml` pipelines
- stage dependencies and outputs
- remote storage
- data/model version control
- experiment and metric workflows

## Recommended combination

Use modely-ai to choose and pull external assets, then use DVC to track those assets inside a training or evaluation project.

## Examples

```bash
modely-ai get hf://datasets/owner/data --local-dir ./data/raw --profile full
modely-ai lock hf://datasets/owner/data --output modely.lock

dvc add data/raw modely.lock
git add data/raw.dvc modely.lock .gitignore
git commit -m "Track external dataset"
```

## Enterprise Phase 3 Contract

For enterprise deployments, DVC pipelines should consume modely-approved assets through lockfiles and approved resolve/install flows.

Recommended flow:

```text
modely-ai policy check modely.lock --profile production
  -> modely-ai asset install --approved --lockfile modely.lock
  -> dvc stage consumes pinned local artifact paths
  -> DVC tracks project-level outputs and metrics
```

Metadata to track:

- `modely.lock` with immutable approved snapshot ID;
- manifest digest and file checksums;
- policy decision and approval refs;
- DVC stage name and dependency path;
- audit/correlation ID where available.

Failure cases:

- blocked/unapproved asset fails before DVC stage execution;
- manifest mismatch fails validation;
- service-account insufficient scope fails approved install;
- DVC remote is not a substitute for modely internal governed storage unless explicitly configured as an approved storage backend.

Tests should use local fixture assets and fake policy/resolve responses rather than live external services.
