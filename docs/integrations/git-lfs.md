# Git-LFS Integration

modely-ai and Git-LFS address different concerns around large AI assets.

## What modely-ai does

- Finds, downloads, locks, scans, caches, and catalogs models, datasets, and tool repositories across supported sources.
- Helps decide which external asset should enter a project and records metadata about that asset.

## What Git-LFS does

Use Git-LFS for large files that must be versioned inside Git repositories:

- store large file contents outside normal Git objects
- keep lightweight pointer files in Git
- integrate large assets with clone/pull workflows

## Recommended combination

Use modely-ai to pull and verify external assets. If selected files must become part of a Git-managed project, use Git-LFS to version those large files.

## Examples

```bash
modely-ai get hf://models/gpt2 --local-dir ./models/gpt2 --profile inference

git lfs install
git lfs track "models/**/*.safetensors"
git add .gitattributes models/gpt2
git commit -m "Track selected model assets with Git-LFS"
```
