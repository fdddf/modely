# modely-ai

**modely-ai** is a Python package that provides a unified interface for downloading AI models and datasets from multiple platforms including Hugging Face and ModelScope. It offers a simple command-line tool and Python API to efficiently download models and datasets with progress tracking, resumable downloads, and minimal dependencies.

## Features

- 🚀 **Unified interface**: Download from both Hugging Face and ModelScope with a single tool
- ⚡ **Progress tracking**: Real-time download progress with tqdm
- 🔄 **Resumable downloads**: Resume interrupted downloads automatically
- 📁 **Flexible options**: Download entire repositories or specific files
- 🔐 **Authentication support**: Access private models and datasets with tokens
- 📦 **Minimal dependencies**: Only requires `requests` and `tqdm`

## Installation

Install modely-ai using pip:

```bash
pip install modely-ai
```

## Usage

### Command Line Interface

modely-ai provides a command-line interface with two main subcommands: `hf` for Hugging Face and `ms` for ModelScope.

#### Download from Hugging Face

Download an entire model repository:
```bash
modely hf bert-base-uncased
```

Download a specific file from a repository:
```bash
modely hf bert-base-uncased --file config.json
```

Download with specific options:
```bash
modely hf facebook/opt-2.7b --repo-type model --revision v1.1.0 --local-dir ./models
```

Download from a private repository:
```bash
modely hf username/private-repo --token YOUR_HUGGINGFACE_TOKEN
```

#### Download from ModelScope

Download an entire model repository:
```bash
modely ms owner/model-name
```

Download a specific file:
```bash
modely ms owner/model-name --file config.json
```

Download a dataset:
```bash
modely ms owner/dataset-name --repo-type dataset
```

Download with specific options:
```bash
modely ms owner/model-name --revision main --local-dir ./models
```

### Python API

You can also use modely-ai directly in your Python code:

```python
from modely import hf_snapshot_download, model_file_download

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
```

## Command Reference

### Hugging Face Commands

```bash
modely hf <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file path to download from the repository
- `--repo-type {model,dataset,space}`: Type of repository (default: model)
- `--revision REVISION`: Revision of the model (default: main)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: Access token for private repositories
- `--force-download`: Force re-download even if file exists

### ModelScope Commands

```bash
modely ms <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file path to download from the repository
- `--repo-type {model,dataset}`: Type of repository (default: model)
- `--revision REVISION`: Revision of the model (default: master)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: Access token for private models

## Requirements

- Python 3.10 or higher
- requests >= 2.25.0
- tqdm >= 4.62.0

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue to improve the functionality or documentation.

## Support

If you encounter any issues or have questions, please open an issue on the GitHub repository.
