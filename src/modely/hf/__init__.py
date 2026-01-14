#!/usr/bin/env python
"""
A standalone module to download models from Hugging Face without CLI dependencies.

This module allows downloading models from Hugging Face model hub with minimal 
dependencies. It can download a specific file or an entire model repository.
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Optional, Union
import requests
from tqdm.auto import tqdm


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
    Download a file from a Hugging Face repository.
    
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
    # Build the download URL
    base_url = "https://huggingface.co"
    # Use the repo_id and revision as-is - Hugging Face API expects normal forward slashes
    download_url = f"{base_url}/{repo_id}/resolve/{revision}/{filename}"
    
    # Prepare headers
    headers = {"User-Agent": "modely/hf-download"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    # Determine local file path
    if local_dir:
        local_file_path = os.path.join(local_dir, filename)
    else:
        # Use cache directory if provided, otherwise use current directory
        if cache_dir:
            cache_path = cache_dir
            os.makedirs(cache_path, exist_ok=True)
            # Use repo-specific naming in cache to avoid conflicts between different repos
            local_file_path = os.path.join(cache_path, f"{repo_id.replace('/', '--')}--{filename}")
        else:
            # Use current directory as default and keep original filename
            cache_path = os.getcwd()
            local_file_path = os.path.join(cache_path, filename)
    
    # Create parent directories if they don't exist
    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
    
    # Check if file already exists and force_download is False
    if os.path.exists(local_file_path) and not force_download:
        print(f"File already exists at: {local_file_path}")
        return local_file_path
    
    # Download the file with progress bar
    print(f"Downloading {filename} from {repo_id}...")
    
    # Use requests to get the file
    response = requests.get(download_url, headers=headers, stream=True)
    response.raise_for_status()
    
    # Get the total file size
    total_size = int(response.headers.get('content-length', 0))
    
    # Write the content to the local file
    with open(local_file_path, 'wb') as file, tqdm(
        desc=filename,
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:  # Filter out keep-alive chunks
                file.write(chunk)
                progress_bar.update(len(chunk))
    
    print(f"Successfully downloaded {filename} to: {local_file_path}")
    return local_file_path


def snapshot_download(
    repo_id: str,
    *,
    repo_type: str = "model",
    revision: str = "main",
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    allow_patterns: Optional[list] = None,
    ignore_patterns: Optional[list] = None,
    force_download: bool = False,
) -> str:
    """
    Download all files from a Hugging Face repository.
    
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
    # For now, we'll implement a basic version that gets the file list via the Hugging Face API
    # First, get the list of files in the repository
    api_url = f"https://huggingface.co/api/{repo_type}s/{repo_id}/tree/{revision}"
    
    headers = {"User-Agent": "modely/hf-download"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    
    files = response.json()
    
    # Determine the target directory
    if local_dir:
        target_dir = local_dir
    else:
        # Use cache directory if provided, otherwise use current directory
        if cache_dir:
            cache_path = cache_dir
        else:
            # Use current directory as default
            cache_path = os.getcwd()
        target_dir = os.path.join(cache_path, f"{repo_id.replace('/', '--')}")
    
    # Create the target directory
    os.makedirs(target_dir, exist_ok=True)
    
    # Download each file
    for file_info in files:
        if file_info.get("type") == "file":
            filename = file_info["path"]
            
            # Apply filtering based on patterns if provided
            if allow_patterns:
                if not any(fnmatch(filename, pattern) for pattern in allow_patterns):
                    continue
            
            if ignore_patterns:
                if any(fnmatch(filename, pattern) for pattern in ignore_patterns):
                    continue
            
            try:
                hf_file_download(
                    repo_id=repo_id,
                    filename=filename,
                    repo_type=repo_type,
                    revision=revision,
                    local_dir=target_dir,
                    token=token,
                    force_download=force_download
                )
            except Exception as e:
                print(f"Failed to download {filename}: {e}")
                continue
    
    print(f"Repository {repo_id} downloaded to: {target_dir}")
    return target_dir


def fnmatch(name, pattern):
    """Simple pattern matching for filenames."""
    import re
    # Convert glob pattern to regex
    regex = pattern.replace("*", ".*").replace("?", ".")
    return re.match(regex, name)


def main():
    """Main function to handle command-line arguments for Hugging Face downloads."""
    parser = argparse.ArgumentParser(description='Download models from Hugging Face without CLI dependencies')
    parser.add_argument('repo_id', type=str, help='Repository ID in format namespace/model_name')
    parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    parser.add_argument('--repo-type', choices=['model', 'dataset', 'space'], default='model', help='Type of repository (default: model)')
    parser.add_argument('--revision', type=str, default='main', help='Revision of the model (default: main)')
    parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory for downloaded files')
    parser.add_argument('--local-dir', type=str, default=None, help='Local directory to download files to')
    parser.add_argument('--token', type=str, default=None, help='Access token for private repositories')
    parser.add_argument('--force-download', action='store_true', help='Force re-download even if file exists')
    
    args = parser.parse_args()

    try:
        if args.file:
            # Download a specific file
            result = hf_file_download(
                repo_id=args.repo_id,
                filename=args.file,
                repo_type=args.repo_type,
                revision=args.revision,
                cache_dir=args.cache_dir,
                local_dir=args.local_dir,
                token=args.token,
                force_download=args.force_download
            )
            print(f"Successfully downloaded file to: {result}")
        else:
            # Download entire repository
            result = snapshot_download(
                repo_id=args.repo_id,
                repo_type=args.repo_type,
                revision=args.revision,
                cache_dir=args.cache_dir,
                local_dir=args.local_dir,
                token=args.token,
                force_download=args.force_download
            )
            print(f"Repository download completed. Files are in: {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
