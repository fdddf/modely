# Kaggle Integration

modely-ai includes experimental Kaggle support to bring Kaggle datasets and competitions into a cross-source asset workflow.

## What modely-ai does

- Addresses Kaggle assets with `kaggle://datasets/<owner>/<dataset>` and `kaggle://competitions/<competition>` URIs.
- Provides best-effort search, source probing, file listing, planning, downloading, cataloging, and governance where the local Kaggle environment supports it.

## What native Kaggle tools do

Use Kaggle CLI/API for platform-native workflows such as:

- competition submissions
- dataset creation, update, and versioning
- notebook/kernel operations
- Kaggle-specific authentication and platform workflows

## Recommended combination

Use modely-ai when Kaggle assets need to be compared or cataloged alongside Hugging Face, ModelScope, or GitHub resources. Use Kaggle CLI/API for Kaggle platform operations.

## Examples

```bash
modely-ai search mnist --source kaggle --repo-type dataset
modely-ai sources probe kaggle://datasets/owner/dataset --source kaggle
modely-ai files kaggle://datasets/owner/dataset
modely-ai get kaggle://datasets/owner/dataset --local-dir ./data/dataset
```
