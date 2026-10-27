---
name: modely-ai
description: Download AI models and datasets from Hugging Face, ModelScope, and GitHub with unified CLI. Also provides development guidance for the modely-ai project.
user_invocable: true
---

# Modely-AI Skill

Quick reference for using modely-ai CLI tool and developing the modely-ai project.

## Quick Commands

```bash
modely-ai hf <repo>              # Hugging Face
modely-ai ms <repo>              # ModelScope
modely-ai github <repo>          # GitHub
modely-ai cache <cmd>            # Cache management
```

## Common Usage

```bash
# Download specific file
modely-ai hf gpt2 --file config.json

# Clone entire repo
modely-ai github facebook/react

# ModelScope dataset
modely-ai ms owner/dataset --repo-type dataset

# Cache management
modely-ai cache list
modely-ai cache clean
```

## Python API

```python
from modely import hf_snapshot_download, github_file_download

path = hf_snapshot_download(repo_id="bert-base-uncased")
path = github_file_download(repo_id="owner/repo", filename="README.md")
```

## Development

```bash
pip install -e .              # Install in editable mode
modely-ai hf gpt2 --file config.json  # Test
```

## Architecture

- `src/modely/__init__.py` - CLI entry point, argparse subcommands
- `src/modely/hf/` - Hugging Face (uses huggingface_hub SDK)
- `src/modely/modelscope/` - ModelScope (uses requests + API)
- `src/modely/github/` - GitHub (git clone + raw URL)
- `src/modely/common/cache.py` - Unified cache system

## Cache Structure

```
~/.cache/modely/
├── hf/          # Hugging Face
├── ms/          # ModelScope
└── github/      # GitHub
```
