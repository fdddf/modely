#!/usr/bin/env python
"""
A module to download models from Hugging Face using the official huggingface_hub SDK.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Union, List

from huggingface_hub import hf_hub_download, snapshot_download as hf_snapshot_download_sdk
from huggingface_hub.utils import RepositoryNotFoundError, RevisionNotFoundError

from modely.common import cache as hf_cache


def hf_file_download(
    repo_id: str,
    filename: str,
    *,
    repo_type: str = "model",
    revision: str = "main",
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    force_download: bool = False,
    resume_download: bool = False,
) -> str:
    """
    Download a file from a Hugging Face repository using huggingface_hub SDK.

    Args:
        repo_id: Repository ID in the format "namespace/model_name"
        filename: Name of the file to download
        repo_type: Type of repository ("model", "dataset", or "space")
        revision: Revision of the repository to download from
        cache_dir: Directory to cache downloaded files
        local_dir: Local directory to save the file
        token: Authentication token for private repositories
        force_download: Force re-download even if file exists
        resume_download: Resume partial downloads

    Returns:
        Path to the downloaded file
    """
    # Determine cache directory
    if cache_dir is None:
        cache_dir = hf_cache.get_cache_dir()
    else:
        cache_dir = hf_cache.get_cache_dir(cache_dir)

    # Convert repo_type to huggingface_hub format
    repo_type_map = {"model": "model", "dataset": "dataset", "space": "space"}
    hf_repo_type = repo_type_map.get(repo_type, repo_type)

    try:
        file_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type=hf_repo_type,
            revision=revision,
            cache_dir=cache_dir,
            local_dir=local_dir,
            token=token,
            force_download=force_download,
            resume_download=resume_download,
        )
        return file_path
    except (RepositoryNotFoundError, RevisionNotFoundError) as e:
        raise Exception(f"Repository or revision not found: {e}")
    except Exception as e:
        raise Exception(f"Failed to download {filename}: {e}")


def snapshot_download(
    repo_id: str,
    *,
    repo_type: str = "model",
    revision: str = "main",
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    allow_patterns: Optional[List] = None,
    ignore_patterns: Optional[List] = None,
    force_download: bool = False,
) -> str:
    """
    Download all files from a Hugging Face repository using huggingface_hub SDK.

    Args:
        repo_id: Repository ID in the format "namespace/model_name"
        repo_type: Type of repository ("model", "dataset", or "space")
        revision: Revision of the repository to download from
        cache_dir: Directory to cache downloaded files
        local_dir: Local directory to save the files
        token: Authentication token for private repositories
        allow_patterns: Patterns to include files (e.g., ["*.json", "*.bin"])
        ignore_patterns: Patterns to exclude files
        force_download: Force re-download even if file exists

    Returns:
        Path to the directory containing downloaded files
    """
    # Check if entire repo is already cached
    if not force_download:
        cached_path = hf_cache.get_cached_repo_path(
            repo_id, repo_type, revision, "hf", cache_dir
        )
        if cached_path:
            print(f"Repository already cached at: {cached_path}")
            return cached_path

    # Determine cache directory
    if cache_dir is None:
        cache_dir = hf_cache.get_cache_dir()
    else:
        cache_dir = hf_cache.get_cache_dir(cache_dir)

    # Convert repo_type to huggingface_hub format
    repo_type_map = {"model": "model", "dataset": "dataset", "space": "space"}
    hf_repo_type = repo_type_map.get(repo_type, repo_type)

    try:
        repo_path = hf_snapshot_download_sdk(
            repo_id=repo_id,
            repo_type=hf_repo_type,
            revision=revision,
            cache_dir=cache_dir,
            local_dir=local_dir,
            token=token,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            force_download=force_download,
        )
        return repo_path
    except (RepositoryNotFoundError, RevisionNotFoundError) as e:
        raise Exception(f"Repository or revision not found: {e}")
    except Exception as e:
        raise Exception(f"Failed to download repository: {e}")


def main():
    """Main function to handle command-line arguments for Hugging Face downloads."""
    parser = argparse.ArgumentParser(
        description="Download models from Hugging Face using huggingface_hub SDK"
    )
    parser.add_argument("repo_id", type=str, help="Repository ID in format namespace/model_name")
    parser.add_argument("--file", type=str, help="Specific file path to download from the repository")
    parser.add_argument(
        "--repo-type",
        choices=["model", "dataset", "space"],
        default="model",
        help="Type of repository (default: model)",
    )
    parser.add_argument(
        "--revision", type=str, default="main", help="Revision of the model (default: main)"
    )
    parser.add_argument(
        "--cache-dir", type=str, default=None, help="Cache directory for downloaded files"
    )
    parser.add_argument(
        "--local-dir", type=str, default=None, help="Local directory to download files to"
    )
    parser.add_argument(
        "--token", type=str, default=None, help="Access token for private repositories"
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download even if file exists",
    )

    args = parser.parse_args()

    try:
        if args.file:
            result = hf_file_download(
                repo_id=args.repo_id,
                filename=args.file,
                repo_type=args.repo_type,
                revision=args.revision,
                cache_dir=args.cache_dir,
                local_dir=args.local_dir,
                token=args.token,
                force_download=args.force_download,
            )
            print(f"Successfully downloaded file to: {result}")
        else:
            result = snapshot_download(
                repo_id=args.repo_id,
                repo_type=args.repo_type,
                revision=args.revision,
                cache_dir=args.cache_dir,
                local_dir=args.local_dir,
                token=args.token,
                force_download=args.force_download,
            )
            print(f"Repository download completed. Files are in: {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
