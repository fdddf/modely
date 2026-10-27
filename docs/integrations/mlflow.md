# MLflow Integration

modely-ai complements MLflow Model Registry by acting as an external asset intake and governance layer.

## What modely-ai does

- Discovers, evaluates, downloads, locks, scans, and catalogs external models and datasets.
- Produces reports that can support model adoption decisions before assets enter a project or registry.

## What MLflow Model Registry does

Use MLflow Model Registry for internal model lifecycle management:

- registered models and model versions
- aliases, stages, tags, and descriptions
- lineage to MLflow runs and logged models
- organization-level promotion and governance workflows

## Recommended combination

Use modely-ai to assess and import external assets. After validation, register internally produced or accepted models in MLflow.

## Examples

```bash
modely-ai score hf://models/gpt2 --json
modely-ai scan hf://models/gpt2 --json
modely-ai get hf://models/gpt2 --local-dir ./models/gpt2
modely-ai report ./models/gpt2 --format markdown --output gpt2-report.md

# Then register validated artifacts with MLflow in your project workflow.
```

## Enterprise Phase 3 Contract

For enterprise deployments, MLflow integration should record modely-ai governance and reproducibility metadata rather than only local files.

Recommended flow:

```text
modely approved resolve
  -> download or mount approved snapshot
  -> train/evaluate
  -> log MLflow run tags/params/artifacts
  -> optionally register model with MLflow Model Registry
```

Metadata to record in MLflow runs or model versions:

- modely asset ID and source URI;
- immutable approved snapshot ID;
- resolved channel and resolution timestamp, if a channel was used;
- manifest digest and lockfile path/artifact;
- policy decision reference;
- approval reference;
- service-account principal or redacted actor metadata;
- audit/correlation ID.

Failure cases:

- blocked or unapproved asset fails before training starts;
- manifest/checksum mismatch fails the run setup;
- insufficient service-account scope fails resolve;
- expired approval or token fails resolve;
- offline tests use local fixtures and fake server responses.

MLflow stages/aliases may reference modely snapshot IDs, but modely approved snapshots remain the source of external asset intake evidence.
