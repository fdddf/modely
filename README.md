# modely-ai

**modely-ai** is a Python package that provides a unified interface for downloading AI models and datasets from multiple platforms including Hugging Face, ModelScope, and GitHub. It offers a simple command-line tool and Python API to efficiently download models and datasets with progress tracking, resumable downloads, and minimal dependencies.

## Features

- 🚀 **Unified interface**: Download from Hugging Face, ModelScope, and GitHub with a single tool
- 🔍 **Model discovery**: Search models and datasets by name, task type, date, and more
- ⚡ **Progress tracking**: Real-time download progress with tqdm
- 🔄 **Resumable downloads**: Resume interrupted downloads automatically
- 📁 **Flexible options**: Download entire repositories or specific files
- 🔐 **Authentication support**: Access private models and datasets with tokens
- 📦 **Official SDKs**: Uses `huggingface-hub` official SDK for reliable downloads
- 📦 **Minimal dependencies**: Only requires `requests`, `tqdm`, and `huggingface-hub`
- 💾 **Smart caching**: Avoid duplicate downloads with unified cache system
- 🗂️ **Cache management**: CLI commands to view, list, and clean cache

## Installation

Install modely-ai using pip:

```bash
pip install modely-ai
```

## Usage

### Command Line Interface

modely-ai provides a command-line interface with subcommands for downloading (`hf`, `ms`, `github`), searching (`search`), monitoring (`watch`), and cache management (`cache`).

#### Download from Hugging Face

Download an entire model repository:
```bash
modely-ai hf bert-base-uncased
```

Download a specific file from a repository:
```bash
modely-ai hf bert-base-uncased --file config.json
```

Download with specific options:
```bash
modely-ai hf facebook/opt-2.7b --repo-type model --revision v1.1.0 --local-dir ./models
```

Download from a private repository:
```bash
modely-ai hf username/private-repo --token YOUR_HUGGINGFACE_TOKEN
```

Download only specific files with patterns:
```bash
modely-ai hf gpt2 --include "config.json" "tokenizer.json"
```

Exclude large model weights:
```bash
modely-ai hf meta-llama/Llama-2-7b --exclude "*.safetensors" "*.bin"
```

Use a mirror endpoint (for regions where Hugging Face is slow):
```bash
modely-ai hf gpt2 --endpoint https://hf-mirror.com
```

List files in a repository without downloading:
```bash
modely-ai hf gpt2 --list-files
```

Preview what would be downloaded (dry-run):
```bash
modely-ai hf gpt2 --dry-run --exclude "*.safetensors" "*.bin"
```

#### Download from ModelScope

Download an entire model repository:
```bash
modely-ai ms owner/model-name
```

Download a specific file:
```bash
modely-ai ms owner/model-name --file config.json
```

Download a dataset:
```bash
modely-ai ms owner/dataset-name --repo-type dataset
```

Download with specific options:
```bash
modely-ai ms owner/model-name --revision main --local-dir ./models
```

Use the optional official ModelScope SDK backend:
```bash
# Install optional SDK support
pip install "modely-ai[modelscope]"

# Auto uses the official SDK when installed, otherwise the lightweight backend
modely-ai ms owner/model-name --backend auto

# Force official SDK or the built-in lightweight downloader
modely-ai ms owner/model-name --backend official
modely-ai ms owner/model-name --backend lightweight
```

#### Download from GitHub

Download an entire repository:
```bash
modely-ai github owner/repo
```

Download a specific file:
```bash
modely-ai github owner/repo --file README.md
```

Download with specific options:
```bash
modely-ai github owner/repo --revision dev --local-dir ./repos
```

Download with Git LFS support (for large files):
```bash
modely-ai github owner/repo --with-lfs
```

Download from a private repository:
```bash
modely-ai github owner/private-repo --token YOUR_GITHUB_TOKEN
```

#### Search Models and Datasets

Search for models, datasets, and AI/ML repositories across Hugging Face, ModelScope, and GitHub with a unified interface:

```bash
# Browse top models without a keyword
modely-ai search --source hf --limit 10

# Search Hugging Face for models matching "gpt2"
modely-ai search gpt2 --source hf --limit 10

# Search ModelScope for models matching "qwen"
modely-ai search qwen --source ms --limit 10

# Search GitHub for AI/ML repositories matching "llama"
modely-ai search llama --source github --limit 10

# Search Hugging Face datasets
modely-ai search glue --source hf --repo-type dataset

# Search ModelScope datasets
modely-ai search mnist --source ms --repo-type dataset

# Filter by task type
modely-ai search bert --task text-classification

# Filter by library and sort by likes
modely-ai search llama --library transformers --sort likes

# Filter by date range (created after 2024)
modely-ai search gpt2 --after 2024-01-01 --sort created_at

# Sort by newest first
modely-ai search qwen --sort lastModified --direction desc

# JSON output for scripting
modely-ai search gpt2 --source hf --json | jq '.[].id'

# Search all three platforms simultaneously
modely-ai search qwen --source all
```

Search results are displayed as a table showing source, model ID, task type, downloads, likes, created date, last modified date, and the repository's web page URL. The keyword argument is optional — omit it to browse all repositories. GitHub search maps stars to likes and forks to downloads.



#### Watch Hugging Face and ModelScope for Updates

Create a watch configuration:
```bash
modely-ai watch init
```

The generated config starts with an empty `targets` list. Edit `~/.modely/watch.json` to list the repositories to monitor:
```json
{
  "state_file": "~/.modely/watch_state.json",
  "targets": [
    {
      "source": "hf",
      "repo_type": "model",
      "repo_id": "bert-base-uncased",
      "revision": "main",
      "download": "snapshot",
      "ignore_patterns": ["*.safetensors"]
    },
    {
      "source": "ms",
      "repo_type": "dataset",
      "repo_id": "owner/dataset-name",
      "revision": "master",
      "download": "files",
      "files": ["README.md", "data/train.jsonl"]
    }
  ]
}
```

Run one check manually:
```bash
modely-ai watch run
```

Install a recurring check with `crontab`:
```bash
# Every day at 02:30
modely-ai watch install --every day --time 02:30

# Every Monday at 02:30
modely-ai watch install --every week --weekday mon --time 02:30
```

Inspect or remove the installed job:
```bash
modely-ai watch status
modely-ai watch uninstall
```

Watch state is stored in `~/.modely/watch_state.json` by default. Cron output is appended to `~/.modely/watch.log` for the default config, or to `watch.log` next to a custom config file. For private repositories, set `token_env` in the target and put the token in that environment variable instead of writing secrets into the config file. For large models or datasets, prefer `allow_patterns`, `ignore_patterns`, or `download: "files"` so the watcher does not mirror unnecessary large files.

ModelScope dataset file listing may not be available for every repository through the lightweight API. When a ModelScope target uses `download: "files"` with explicit `files`, modely refreshes those files on each scheduled run if remote listing is unavailable. Snapshot downloads and pattern-based ModelScope filtering still require a remote file list.

### Python API

You can also use modely-ai directly in your Python code:

```python
from modely import hf_snapshot_download, model_file_download, github_snapshot_download, github_file_download
from modely.search import search

# Search for models
results = search("gpt2", source="hf", repo_type="model", task="text-generation", limit=5)
for r in results:
    print(f"{r.id}: {r.downloads} downloads, {r.url}")

# Download an entire Hugging Face repository
model_path = hf_snapshot_download(
    repo_id="bert-base-uncased",
    repo_type="model",
    revision="main"
)

# Download a specific file from Hugging Face
file_path = hf_file_download(
    repo_id="bert-base-uncased",
    filename="config.json",
    repo_type="model"
)

# Download from ModelScope
ms_model_path = modelscope_snapshot_download(
    repo_id="owner/model-name",
    repo_type="model",
    revision="master"
)

# Download an entire GitHub repository
repo_path = github_snapshot_download(
    repo_id="owner/repo",
    revision="main"
)

# Download a specific file from GitHub
file_path = github_file_download(
    repo_id="owner/repo",
    filename="README.md",
    revision="main"
)
```

## Cache Management

modely-ai includes a unified cache system to avoid duplicate downloads. Files are organized by source (Hugging Face / ModelScope), repository type, repository ID, and revision.

### Cache Directory Configuration

The cache directory is resolved with the following priority:

1. **CLI argument**: `--cache-dir` (for download commands) or `modely cache --cache-dir <DIR>`
2. **Environment variable**: `MODELY_CACHE`
3. **Config file**: `~/.modely/config.json` (set via `modely cache config --set <DIR>`)
4. **Default**: `~/.cache/modely`

```bash
# Set cache directory via environment variable
export MODELY_CACHE=/path/to/cache

# Or set via config file (persistent)
modely-ai cache config --set /path/to/cache

# Or specify per-command
modely-ai --cache-dir /path/to/cache hf gpt2
```

### Cache Structure

```
~/.cache/modely/
├── hf/                    # Hugging Face cache
│   ├── models/            # repo_type = model
│   │   └── gpt2/
│   │       └── main/     # revision
│   │           ├── config.json
│   │           └── pytorch_model.bin
│   └── datasets/         # repo_type = dataset
├── ms/                    # ModelScope cache
│   ├── models/
│   │   └── owner--model-name/
│   │       └── master/
│   └── datasets/
└── github/                # GitHub cache
    └── tools/             # repo_type = tool
        └── owner--repo/
            └── main/
                ├── README.md
                └── (repository files)
```

### Cache Hit

When downloading the same file again, modely-ai detects the cached file and skips the download:

```bash
# First download
modely-ai hf gpt2 --file config.json
# Output: Downloading config.json from gpt2...

# Second download (cached)
modely-ai hf gpt2 --file config.json
# Output: File already cached at: ~/.cache/modely/hf/models/gpt2/main/config.json
```

### Cache Commands

```bash
# Show cache directory and total size
modely-ai cache info

# List all cached repositories
modely-ai cache list

# List with detailed file information
modely-ai cache list --detail

# Clean all cache
modely-ai cache clean

# Clean specific repository cache
modely-ai cache clean gpt2

# Show current cache directory configuration
modely-ai cache config

# Set new cache directory
modely-ai cache config --set /tmp/my-cache
```

## Command Reference

### Hugging Face Commands

```bash
modely-ai hf <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file path to download from the repository
- `--repo-type {model,dataset,space}`: Type of repository (default: model)
- `--revision REVISION`: Revision of the model (default: main)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: Access token for private repositories
- `--force-download`: Force re-download even if file exists
- `--include PATTERN [PATTERN ...]`: Glob patterns to include (e.g., `"*.json" "*.safetensors"`)
- `--exclude PATTERN [PATTERN ...]`: Glob patterns to exclude (e.g., `"*.bin" "*.msgpack"`)
- `--endpoint URL`: HF API endpoint for mirrors (e.g., `https://hf-mirror.com`)
- `--list-files`: List remote repository files without downloading
- `--dry-run`: Show what would be downloaded (count, total size) without downloading

### ModelScope Commands

```bash
modely-ai ms <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file path to download from the repository
- `--repo-type {model,dataset}`: Type of repository (default: model)
- `--revision REVISION`: Revision of the model (default: master)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: Access token for private models
- `--backend {auto,official,lightweight}`: ModelScope backend to use (default: auto)
- `--include PATTERN [PATTERN ...]`: Glob patterns to include (e.g., `"*.json" "*.safetensors"`)
- `--exclude PATTERN [PATTERN ...]`: Glob patterns to exclude (e.g., `"*.bin" "*.msgpack"`)
- `--endpoint URL`: ModelScope API endpoint
- `--list-files`: List remote repository files without downloading
- `--dry-run`: Show what would be downloaded (count, total size) without downloading

### GitHub Commands

```bash
modely-ai github <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file to download from the repository
- `--revision REVISION`: Branch, tag, or commit SHA (default: main)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: GitHub personal access token for private repositories
- `--with-lfs`: Enable Git LFS support for large files
- `--force-download`: Force re-download even if file exists

### Watch Commands

```bash
modely-ai watch <init|run|list|install|status|uninstall> [OPTIONS]
```

Options:
- `init --config FILE --force`: Create a JSON watch config template
- `run --config FILE`: Check configured targets once and download changed repositories
- `list --config FILE`: Show configured targets and their last known state
- `install --config FILE --every {day,week} --time HH:MM --weekday mon`: Install a crontab job
- `status --config FILE`: Show the installed crontab job
- `uninstall --config FILE`: Remove the installed crontab job

### Search Commands

```bash
modely-ai search [keyword] [OPTIONS]
```

Search is available across Hugging Face (models and datasets), ModelScope (models and datasets), and GitHub (AI/ML repositories). The keyword is optional — omit it to browse all repositories. GitHub search maps stars to likes and forks to downloads.

Options:
- `--source, -s {hf,ms,github,all}`: Platform to search (default: all)
- `--repo-type, -t {model,dataset,tool}`: Type of repository (default: model; GitHub uses `tool`)
- `--task TASK`: Filter by task type (e.g., text-classification, text-generation)
- `--library LIBRARY`: Filter by library, HF only (e.g., transformers, pytorch)
- `--license LICENSE`: Filter by license, HF only
- `--sort {downloads,lastModified,likes,created_at}`: Sort field (default: downloads)
- `--direction {asc,desc}`: Sort direction (default: desc)
- `--limit, -n N`: Max results per source (default: 20)
- `--author AUTHOR`: Filter by author/owner
- `--after DATE`: Only repos modified after this date (YYYY-MM-DD)
- `--before DATE`: Only repos modified before this date (YYYY-MM-DD)
- `--json`: Output results as JSON instead of a table

## Requirements

- Python 3.10 or higher
- requests >= 2.25.0
- tqdm >= 4.62.0
- huggingface-hub >= 0.20.0
- Optional: modelscope >= 1.0.0 for `modely-ai[modelscope]` official ModelScope SDK backend

## Development

### Setup

```bash
pip install -e ".[dev]"
```

### Running Tests

Unit tests (no network required):
```bash
pytest tests/ -m "not integration"
```

Integration tests (require network access):
```bash
pytest tests/ -m integration
```

All tests:
```bash
pytest tests/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue to improve the functionality or documentation.

## Support

If you encounter any issues or have questions, please open an issue on the GitHub repository.
