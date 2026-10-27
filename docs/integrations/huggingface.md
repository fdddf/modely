# Hugging Face Integration

modely-ai complements the Hugging Face Hub CLI/SDK by adding a cross-source asset workflow around Hugging Face models, datasets, and Spaces.

## What modely-ai does

- Addresses Hugging Face assets with `hf://models/...`, `hf://datasets/...`, and `hf://spaces/...` URIs.
- Searches, resolves, compares, scores, scans, locks, downloads, and catalogs Hugging Face assets with the same commands used for other sources.
- Uses Hugging Face metadata and file lists for planning, scoring, scanning, lockfiles, and catalog reports.

## What native Hugging Face tools do

Use Hugging Face Hub CLI/SDK for platform-native operations such as:

- repository creation and administration
- upload workflows
- Hub authentication and token management
- Spaces-specific workflows
- deep Hub SDK integrations

## Recommended combination

Use modely-ai before an asset enters a project or registry; use Hugging Face Hub CLI/SDK when you need full Hugging Face platform control.

## Examples

```bash
modely-ai search qwen --source hf --repo-type auto
modely-ai info hf://models/gpt2 --json
modely-ai files hf://models/gpt2 --summary
modely-ai score hf://models/gpt2
modely-ai scan hf://models/gpt2
modely-ai lock hf://models/gpt2 --profile minimal --output modely.lock
modely-ai get hf://models/gpt2 --profile minimal --local-dir ./models/gpt2
```
