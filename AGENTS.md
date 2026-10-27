# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

modely-ai is a Python package providing a unified CLI and Python API for downloading AI models and datasets from Hugging Face, ModelScope, and GitHub. It features progress tracking, resumable downloads, smart caching, and minimal dependencies.

## Common Commands

### Development Setup
```bash
pip install -e .              # Install in editable mode
```

### Build & Install
```bash
pip install .                  # Regular install
pip install -e .              # Editable mode (for development)
```

### Running the CLI
```bash
modely-ai hf <repo>           # Download from Hugging Face
modely-ai ms <repo>           # Download from ModelScope
modely-ai github <repo>       # Download from GitHub
modely-ai cache <cmd>         # Cache management
```

### Testing
```bash
pip install -e ".[dev]"        # Install with test dependencies

# Unit tests (no network)
pytest tests/ -m "not integration"

# Integration tests (require network)
pytest tests/ -m integration

# All tests
pytest tests/
```

**IMPORTANT**: After any code change, run `pytest tests/ -m "not integration"` to verify unit tests pass.

## Architecture

### Module Structure (src/ layout)

```
src/modely/
├── __init__.py          # CLI entry point, argparse subcommands (hf, ms, github, cache)
├── hf/__init__.py      # Hugging Face downloads (uses huggingface_hub SDK)
├── modelscope/__init__.py  # ModelScope downloads (uses requests + API)
├── github/__init__.py  # GitHub downloads (git clone + raw URL)
└── common/
    └── cache.py        # Unified cache system for all platforms
```

### Key Patterns

**Unified Interface**: Each platform module (hf, modelscope, github) exposes:
- `file_download()` - Download single file
- `snapshot_download()` - Download entire repository/clone
- `main()` - Standalone CLI entry point

**Cache System** (`common/cache.py`):
- Cache directory priority: CLI arg > `MODELY_CACHE` env > config file > `~/.cache/modely`
- Cache structure: `{cache_dir}/{source}/{type}/{repo_id}/{revision}/`
- Source codes: `hf`, `ms`, `github`
- Type codes: `models` (for model), `datasets` (for dataset), `tools` (for GitHub tools)
- Repo ID normalization: `/` replaced with `--` in directory names

**CLI Pattern** (`__init__.py`):
- Uses `argparse` with subparsers for `hf`, `ms`, `github`, `cache` commands
- Each subcommand has its own argument parser with consistent options
- Token auth, cache dir, local dir, and revision are common across platforms

### Dependencies
- `requests>=2.25.0` - HTTP requests (ModelScope API, GitHub raw downloads)
- `tqdm>=4.62.0` - Progress bars
- `huggingface-hub>=0.20.0` - Official HF SDK for reliable downloads
- System: `git` required for GitHub clone feature

### Adding a New Platform

To add support for a new platform (e.g., `newplat`):
1. Create `src/modely/newplat/__init__.py` with `file_download()` and `snapshot_download()` functions
2. Follow the interface pattern of existing modules
3. Import and wire up in `src/modely/__init__.py`
4. Add CLI subcommand with corresponding argument parser
5. Update `README.md` with usage examples
6. Update `__all__` list in `__init__.py`
