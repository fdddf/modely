# ModelScope Integration

modely-ai treats ModelScope as a first-class source for cross-platform AI asset workflows.

## What modely-ai does

- Addresses ModelScope assets with `ms://models/...` and `ms://datasets/...` URIs.
- Searches, downloads, lists files where supported, compares, scores, scans, locks, caches, and catalogs ModelScope resources.
- Supports the lightweight built-in backend and optional official ModelScope SDK backend.

## What native ModelScope tools do

Use native ModelScope tooling for platform-specific operations and any deep ModelScope workflows not exposed through modely-ai.

## Recommended combination

Use modely-ai to compare ModelScope assets with Hugging Face, GitHub, or Kaggle alternatives; use ModelScope-native tooling for platform-specific publishing or advanced interactions.

## Examples

```bash
modely-ai search qwen --source ms --repo-type auto
modely-ai info ms://models/AI-ModelScope/gpt2 --json
modely-ai compare hf://models/gpt2 ms://models/AI-ModelScope/gpt2 --files --card --formats --deep
modely-ai get ms://models/AI-ModelScope/gpt2 --profile minimal
modely-ai ms AI-ModelScope/gpt2 --backend official
```
