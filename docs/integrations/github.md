# GitHub Integration

modely-ai treats GitHub repositories as AI tool/repository assets and normalizes them as `tool` resources.

## What modely-ai does

- Addresses repositories with `github://owner/repo` URIs or GitHub URLs.
- Downloads files, clones repositories, downloads release assets, lists files, scans risky files, caches repositories, and catalogs GitHub assets.
- Stores GitHub cache entries under `github/tools/...` even when a caller passes `model` or `auto` as the repo type.

## What native git/GitHub tools do

Use git and GitHub CLI for source-control collaboration:

- branches, commits, tags, and merges
- pull requests and issues
- repository administration
- GitHub Actions and releases management

## Recommended combination

Use modely-ai to treat GitHub repositories as assets in the same discovery, scan, lock, and catalog workflow as models and datasets. Use git/GitHub CLI for collaboration and repository lifecycle operations.

## Enterprise CI gate target

For enterprise Phase 3, GitHub Actions can run the planned `modely-ai policy check` command against lockfiles, manifests, or catalog reports. The command must use scoped service-account/API tokens, stable exit codes, and JSON/SARIF-compatible output as defined in `docs/specs/enterprise-cli.md`.

This target example should be validated against the implemented CLI before production use:

```yaml
- name: modely policy gate
  run: modely-ai policy check modely.lock --profile production --format sarif
```

## Examples

```bash
modely-ai search llama --source github --limit 10
modely-ai info github://keras-team/keras --json
modely-ai files github://keras-team/keras --summary
modely-ai scan github://keras-team/keras
modely-ai github keras-team/keras --include "examples/*" README.md
modely-ai cache list
```
