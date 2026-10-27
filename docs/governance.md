# modely-ai Governance Workflow

This workflow turns model downloads into auditable asset decisions.

## 1. Diagnose and choose

```bash
modely-ai doctor qwen2.5-7b-instruct --probe --json > doctor.json
modely-ai choose qwen2.5-7b-instruct --strategy safest --json > decision.json
```

The JSON output records resolve, probe, score, scan, and policy evidence so a reviewer can see why a source was selected or rejected.

## 2. Scan before adoption

```bash
modely-ai scan hf://models/Qwen/Qwen2.5-7B-Instruct --inspect-files --json > scan.json
```

`--inspect-files` only fetches small text/code files and avoids model weights.

## 3. Lock and install reproducibly

```bash
modely-ai lock hf://models/Qwen/Qwen2.5-7B-Instruct \
  --strict --require-checksums --alternatives hf,ms \
  --output modely.lock --json
modely-ai install -f modely.lock --fallback --local-dir ./models/qwen
modely-ai validate-lock -f modely.lock --strict --json
```

## 4. Catalog and gate local assets

```bash
modely-ai catalog scan ./models --score --scan --output catalog.json --json
modely-ai catalog gate catalog.json --policy docs/examples/policy.json --json
```

Use the catalog report, decision output, lockfile, and scan report together as an adoption record.
