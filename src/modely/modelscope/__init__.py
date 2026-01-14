#!/usr/bin/env python
"""
A standalone script to download models from ModelScope without CLI dependencies.

This script allows downloading models from ModelScope model hub with minimal 
dependencies. It can download a specific file or an entire model repository.
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import urllib
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Dict, List, Optional, Union
import requests
from requests.adapters import Retry
from tqdm.auto import tqdm


# Constants
API_FILE_DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB
API_FILE_DOWNLOAD_RETRY_TIMES = 5
API_FILE_DOWNLOAD_TIMEOUT = 60
DEFAULT_MAX_WORKERS = 8
MODELSCOPE_DOWNLOAD_PARALLELS = 4
MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB = 512
TEMPORARY_FOLDER_NAME = '.tmp'
FILE_HASH = 'Sha256'
DEFAULT_MODEL_REVISION = 'master'
DEFAULT_DATASET_REVISION = 'master'
REPO_TYPE_MODEL = 'model'
REPO_TYPE_DATASET = 'dataset'
REPO_TYPE_SUPPORT = [REPO_TYPE_MODEL, REPO_TYPE_DATASET]
INTRA_CLOUD_ACCELERATION = os.environ.get('INTRA_CLOUD_ACCELERATION', 'false')


def get_endpoint():
    """Get the ModelScope API endpoint."""
    return os.environ.get('MODELSCOPE_ENDPOINT', 'https://modelscope.cn')


def model_id_to_group_owner_name(model_id: str) -> tuple:
    """Convert model_id to group/owner and name."""
    if model_id.count('/') != 1:
        raise ValueError(f"Invalid model id format: {model_id}. Expected format: 'owner/name'")
    return model_id.split('/')


def get_model_cache_root():
    """Get the default model cache directory."""
    cache_root = os.environ.get('MODELSCOPE_CACHE', os.path.join(Path.home(), '.cache', 'modelscope'))
    hub_cache = os.path.join(cache_root, 'hub')
    os.makedirs(hub_cache, exist_ok=True)
    return hub_cache


def get_dataset_cache_root():
    """Get the default dataset cache directory."""
    cache_root = os.environ.get('MODELSCOPE_CACHE', os.path.join(Path.home(), '.cache', 'modelscope'))
    dataset_cache = os.path.join(cache_root, 'datasets')
    os.makedirs(dataset_cache, exist_ok=True)
    return dataset_cache


def get_file_download_url(model_id: str, file_path: str, revision: str, endpoint: Optional[str] = None):
    """Format file download url according to `model_id`, `revision` and `file_path`."""
    file_path = urllib.parse.quote_plus(file_path)
    revision = urllib.parse.quote_plus(revision)
    download_url_template = '{endpoint}/api/v1/models/{model_id}/repo?Revision={revision}&FilePath={file_path}'
    if not endpoint:
        endpoint = get_endpoint()
    return download_url_template.format(
        endpoint=endpoint,
        model_id=model_id,
        revision=revision,
        file_path=file_path,
    )


def get_model_files_url(model_id: str, revision: str, endpoint: Optional[str] = None):
    """Get the URL to list model files."""
    model_id_encoded = urllib.parse.quote_plus(model_id)
    revision = urllib.parse.quote_plus(revision) if revision else 'master'
    
    if not endpoint:
        endpoint = get_endpoint()
    
    return f"{endpoint}/api/v1/models/{model_id_encoded}/repo/files?Revision={revision}"


def file_integrity_validation(file_path: str, expected_hash: str):
    """Validate file integrity by comparing SHA256 hash."""
    with open(file_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    if file_hash.lower() != expected_hash.lower():
        raise ValueError(f'File integrity check failed for {file_path}. '
                         f'Expected hash: {expected_hash}, got: {file_hash}')


def http_get_model_file(
    url: str,
    local_dir: str,
    file_name: str,
    file_size: int,
    cookies: CookieJar,
    headers: Optional[Dict[str, str]] = None,
    disable_tqdm: bool = False,
):
    """Download remote file with progress tracking."""
    
    class TqdmCallback:
        def __init__(self, file_name, file_size):
            self.file_name = file_name
            self.file_size = file_size
            self.progress = None
            if file_size > 0:
                self.progress = tqdm(
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    total=file_size,
                    desc=f'Downloading [{file_name}]',
                )
        
        def update(self, n):
            if self.progress:
                self.progress.update(n)
        
        def end(self):
            if self.progress:
                self.progress.close()
    
    progress_callbacks = []
    if not disable_tqdm:
        progress_callbacks.append(TqdmCallback)
    
    progress_callbacks = [
        callback(file_name, file_size) for callback in progress_callbacks
    ]
    
    get_headers = {} if headers is None else headers.copy()
    get_headers['X-Request-ID'] = str(uuid.uuid4().hex)
    temp_file_path = os.path.join(local_dir, file_name)
    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
    
    # retry sleep 0.5s, 1s, 2s, 4s
    has_retry = False
    hash_sha256 = hashlib.sha256()
    retry = Retry(
        total=API_FILE_DOWNLOAD_RETRY_TIMES,
        backoff_factor=1,
        allowed_methods=['GET'])

    while True:
        try:
            if file_size == 0:
                # Avoid empty file server request
                with open(temp_file_path, 'w+'):
                    for callback in progress_callbacks:
                        callback.update(1)
                break
            # Determine the length of any existing partial download
            partial_length = 0
            # download partial, continue download
            if os.path.exists(temp_file_path):
                # resuming from interrupted download is also considered as retry
                has_retry = True
                with open(temp_file_path, 'rb') as f:
                    partial_length = f.seek(0, io.SEEK_END)
                    for callback in progress_callbacks:
                        callback.update(partial_length)

            # Check if download is complete
            if partial_length >= file_size:
                break
            # closed range[], from 0.
            get_headers['Range'] = 'bytes=%s-%s' % (partial_length, file_size - 1)
            with open(temp_file_path, 'ab+') as f:
                r = requests.get(
                    url,
                    stream=True,
                    headers=get_headers,
                    cookies=cookies,
                    timeout=API_FILE_DOWNLOAD_TIMEOUT)
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=API_FILE_DOWNLOAD_CHUNK_SIZE):
                    if chunk:  # filter out keep-alive new chunks
                        for callback in progress_callbacks:
                            callback.update(len(chunk))
                        f.write(chunk)
                        # hash would be discarded in retry case anyway
                        if not has_retry:
                            hash_sha256.update(chunk)
            break
        except Exception as e:  # no matter what happen, we will retry.
            has_retry = True
            retry = retry.increment('GET', url, error=e)
            retry.sleep()
    
    for callback in progress_callbacks:
        callback.end()
    # if anything went wrong, we would discard the real-time computed hash and return None
    return None if has_retry else hash_sha256.hexdigest()


def parallel_download(url: str,
                      local_dir: str,
                      file_name: str,
                      cookies: CookieJar,
                      headers: Optional[Dict[str, str]] = None,
                      file_size: int = None,
                      disable_tqdm: bool = False):
    """Download large files in parallel."""
    
    class TqdmCallback:
        def __init__(self, file_name, file_size):
            self.file_name = file_name
            self.file_size = file_size
            self.progress = None
            if file_size > 0:
                self.progress = tqdm(
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    total=file_size,
                    desc=f'Downloading [{file_name}]',
                )
        
        def update(self, n):
            if self.progress:
                self.progress.update(n)
        
        def end(self):
            if self.progress:
                self.progress.close()
    
    progress_callbacks = []
    if not disable_tqdm:
        progress_callbacks.append(TqdmCallback)
    
    progress_callbacks = [
        callback(file_name, file_size) for callback in progress_callbacks
    ]
    
    # create temp file
    PART_SIZE = 160 * 1024 * 1024  # every part is 160M
    tasks = []
    file_path = os.path.join(local_dir, file_name)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    for idx in range(int(file_size / PART_SIZE)):
        start = idx * PART_SIZE
        end = (idx + 1) * PART_SIZE - 1
        tasks.append((file_path, progress_callbacks, start, end, url, file_name, cookies, headers))
    
    if end + 1 < file_size:
        tasks.append((file_path, progress_callbacks, end + 1, file_size - 1, url, file_name, cookies, headers))
    
    parallels = min(MODELSCOPE_DOWNLOAD_PARALLELS, 16)
    
    def download_part_with_retry(params):
        # unpack parameters
        model_file_path, progress_callbacks, start, end, url, file_name, cookies, headers = params
        get_headers = {} if headers is None else headers.copy()
        get_headers['X-Request-ID'] = str(uuid.uuid4().hex)
        retry = Retry(
            total=API_FILE_DOWNLOAD_RETRY_TIMES,
            backoff_factor=1,
            allowed_methods=['GET'])
        part_file_name = model_file_path + '_%s_%s' % (start, end)
        while True:
            try:
                partial_length = 0
                if os.path.exists(
                        part_file_name):  # download partial, continue download
                    with open(part_file_name, 'rb') as f:
                        partial_length = f.seek(0, io.SEEK_END)
                        for callback in progress_callbacks:
                            callback.update(partial_length)
                download_start = start + partial_length
                if download_start > end:
                    break  # this part is download completed.
                get_headers['Range'] = 'bytes=%s-%s' % (download_start, end)
                with open(part_file_name, 'ab+') as f:
                    r = requests.get(
                        url,
                        stream=True,
                        headers=get_headers,
                        cookies=cookies,
                        timeout=API_FILE_DOWNLOAD_TIMEOUT)
                    for chunk in r.iter_content(
                            chunk_size=API_FILE_DOWNLOAD_CHUNK_SIZE):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
                            for callback in progress_callbacks:
                                callback.update(len(chunk))
                break
            except (Exception) as e:  # no matter what exception, we will retry.
                retry = retry.increment('GET', url, error=e)
                retry.sleep()
    
    # download every part
    with ThreadPoolExecutor(
            max_workers=parallels, thread_name_prefix='download') as executor:
        list(executor.map(download_part_with_retry, tasks))
    
    for callback in progress_callbacks:
        callback.end()
    
    # merge parts.
    hash_sha256 = hashlib.sha256()
    with open(os.path.join(local_dir, file_name), 'wb') as output_file:
        for task in tasks:
            part_file_name = task[0] + '_%s_%s' % (task[2], task[3])
            with open(part_file_name, 'rb') as part_file:
                while True:
                    chunk = part_file.read(16 * API_FILE_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    output_file.write(chunk)
                    hash_sha256.update(chunk)
            os.remove(part_file_name)
    return hash_sha256.hexdigest()


def download_file(
    url,
    file_meta,
    temporary_cache_dir,
    cache,
    headers,
    cookies,
    disable_tqdm=False,
):
    """Download a file from the given URL."""
    # Get the file size from the file_meta
    file_size = file_meta.get('Size', 0)

    if MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB * 1024 * 1024 < file_size and MODELSCOPE_DOWNLOAD_PARALLELS > 1:  # parallel download large file.
        file_digest = parallel_download(
            url,
            temporary_cache_dir,
            file_meta['Path'],
            headers=headers,
            cookies=None if cookies is None else cookies,
            file_size=file_size,
            disable_tqdm=disable_tqdm,
        )
    else:
        file_digest = http_get_model_file(
            url,
            temporary_cache_dir,
            file_meta['Path'],
            file_size=file_size,
            headers=headers,
            cookies=cookies,
            disable_tqdm=disable_tqdm,
        )

    # check file integrity
    temp_file = os.path.join(temporary_cache_dir, file_meta['Path'])
    if FILE_HASH in file_meta:
        expected_hash = file_meta[FILE_HASH]
        # if a real-time hash has been computed
        if file_digest is not None:
            # if real-time hash mismatched, try to compute it again
            if file_digest != expected_hash:
                print('Mismatched real-time digest found, falling back to lump-sum hash computation')
                file_integrity_validation(temp_file, expected_hash)
        else:
            file_integrity_validation(temp_file, expected_hash)
    
    # put file into cache
    return cache.put_file(file_meta, temp_file)


class HubApi:
    """Simplified API client for ModelScope."""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.endpoint = get_endpoint()
    
    def get_cookies(self, access_token: Optional[str] = None):
        """Get cookies with token authentication."""
        token = access_token or self.token
        if token:
            # Create a simple cookie dict based on token
            return {'Authorization': f'Bearer {token}'}
        return {}
    
    def get_endpoint_for_read(self, repo_id: str, repo_type: str):
        """Get endpoint for reading repository."""
        return self.endpoint
    
    def get_valid_revision(self, repo_id: str, revision: str = None, cookies=None, endpoint=None):
        """Get the valid revision of a repository."""
        if not revision:
            revision = DEFAULT_MODEL_REVISION
        return revision
    
    def get_model_files(self, model_id: str, revision: str = None, recursive: bool = True, use_cookies=None, endpoint=None):
        """Get the list of files in a model repository."""
        if not revision:
            revision = DEFAULT_MODEL_REVISION
        
        # Get the endpoint and cookies
        if not endpoint:
            endpoint = self.endpoint
        if use_cookies is None:
            use_cookies = self.get_cookies()
        
        # Build the URL to get model files
        model_files_url = get_model_files_url(model_id, revision, endpoint)
        
        try:
            response = requests.get(
                model_files_url,
                cookies=use_cookies,
                timeout=API_FILE_DOWNLOAD_TIMEOUT
            )
            response.raise_for_status()
            
            # Parse the response - actual API response format may vary
            data = response.json()
            
            # Extract files from the response - adjust based on actual API response format
            files = data.get('Data', {}).get('Files', []) if isinstance(data, dict) else []
            
            # Format files to match expected structure
            repo_files = []
            for file_info in files:
                if isinstance(file_info, str):
                    # If it's just a filename string, convert to dict format
                    repo_files.append({
                        'Path': file_info,
                        'Name': os.path.basename(file_info),
                        'Type': 'blob',
                        'Size': 0  # Size not available without additional request
                    })
                elif isinstance(file_info, dict):
                    # If it's already in dict format, use it as-is or adjust
                    repo_files.append({
                        'Path': file_info.get('Path', file_info.get('path', file_info.get('name', file_info.get('Name')))),
                        'Name': file_info.get('Name', os.path.basename(file_info.get('Path', ''))),
                        'Type': file_info.get('Type', 'blob'),
                        'Size': file_info.get('Size', file_info.get('size', 0))
                    })
            
            return repo_files
        except Exception as e:
            print(f"Warning: Could not fetch file list from API: {e}")
            # Return an empty list if API call fails, as this is an optional feature for single file downloads
            return []


def model_file_download(
    model_id: str,
    file_path: str,
    revision: Optional[str] = DEFAULT_MODEL_REVISION,
    cache_dir: Optional[str] = None,
    local_files_only: Optional[bool] = False,
    cookies: Optional[CookieJar] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
) -> Optional[str]:
    """Download a specific file from a model repository."""
    return _repo_file_download(
        model_id,
        file_path,
        repo_type=REPO_TYPE_MODEL,
        revision=revision,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        cookies=cookies,
        local_dir=local_dir,
        token=token)


def dataset_file_download(
    dataset_id: str,
    file_path: str,
    revision: Optional[str] = DEFAULT_DATASET_REVISION,
    cache_dir: Union[str, Path, None] = None,
    local_dir: Optional[str] = None,
    local_files_only: Optional[bool] = False,
    cookies: Optional[CookieJar] = None,
    token: Optional[str] = None,
) -> str:
    """Download a specific file from a dataset repository."""
    return _repo_file_download(
        dataset_id,
        file_path,
        repo_type=REPO_TYPE_DATASET,
        revision=revision,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        cookies=cookies,
        local_dir=local_dir,
        token=token)


def _repo_file_download(
    repo_id: str,
    file_path: str,
    *,
    repo_type: str = REPO_TYPE_MODEL,
    revision: Optional[str] = DEFAULT_MODEL_REVISION,
    cache_dir: Optional[str] = None,
    local_files_only: Optional[bool] = False,
    cookies: Optional[CookieJar] = None,
    local_dir: Optional[str] = None,
    disable_tqdm: bool = False,
    token: Optional[str] = None,
) -> Optional[str]:
    """Internal function to download a file from a repository."""
    if repo_type not in REPO_TYPE_SUPPORT:
        raise ValueError(f'Invalid repo type: {repo_type}, only support: {REPO_TYPE_SUPPORT}')

    # Create temporary cache directory and cache object - only use local_dir or current directory
    temporary_cache_dir, cache = create_temporary_directory_and_cache(repo_id, local_dir=local_dir, cache_dir=None, repo_type=repo_type)

    # For this simplified version, we don't check local_files_only since we don't maintain full cache
    if local_files_only:
        print("Local files only mode is not fully implemented in this simplified version")
        return None

    _api = HubApi(token=token)

    headers = {
        'user-agent': 'modelscope/standalone-download',
        'snapshot-identifier': str(uuid.uuid4()),
    }

    if INTRA_CLOUD_ACCELERATION == 'true':
        # This is a simplified version - actual implementation would be more complex
        region_id = os.getenv('INTRA_CLOUD_ACCELERATION_REGION')
        if region_id:
            headers['x-aliyun-region-id'] = region_id

    if cookies is None:
        cookies = _api.get_cookies()
    else:
        # Convert cookies to requests-compatible format if needed
        if isinstance(cookies, dict):
            pass  # Already in correct format
        else:
            cookies = {}

    repo_files = []
    endpoint = _api.get_endpoint_for_read(repo_id=repo_id, repo_type=repo_type)
    file_to_download_meta = None
    if repo_type == REPO_TYPE_MODEL:
        revision = _api.get_valid_revision(repo_id, revision=revision, cookies=cookies, endpoint=endpoint)
        # we need to confirm the version is up-to-date
        # we need to get the file list to check if the latest version is cached, if so return, otherwise download
        repo_files = _api.get_model_files(
            model_id=repo_id,
            revision=revision,
            recursive=True,
            use_cookies=False if cookies is None else cookies,
            endpoint=endpoint)
        for repo_file in repo_files:
            if repo_file['Type'] == 'tree':
                continue

            if repo_file['Path'] == file_path:
                # In this simplified version, we always download (don't check cache)
                file_to_download_meta = repo_file
                break
    elif repo_type == REPO_TYPE_DATASET:
        print("Dataset download is not fully implemented in this standalone version.")
        return temporary_cache_dir

    if file_to_download_meta is None:
        raise Exception(f'The file path: {file_path} not exist in: {repo_id}')

    # we need to download again
    if repo_type == REPO_TYPE_MODEL:
        url_to_download = get_file_download_url(repo_id, file_path, revision, endpoint)
    else:
        raise ValueError(f'Invalid repo type {repo_type}')

    return download_file(url_to_download, file_to_download_meta, temporary_cache_dir, cache, headers, cookies, disable_tqdm=disable_tqdm)


class BasicCache:
    """Basic cache implementation to mimic ModelFileSystemCache."""
    
    def __init__(self, cache_dir: str, group_or_owner: str = None, name: str = None):
        self.cache_dir = cache_dir
        self.group_or_owner = group_or_owner
        self.name = name
        self.root_location_path = os.path.join(cache_dir, group_or_owner, name) if group_or_owner and name else cache_dir
        os.makedirs(self.root_location_path, exist_ok=True)
    
    def exists(self, file_info: Dict):
        """Check if the file already exists in cache with the same hash."""
        # For simplicity, we'll always return False to force download
        # In a full implementation, this would check file hashes
        return False
    
    def get_file_by_path(self, file_path: str):
        """Get file path if it exists in cache."""
        # For simplicity, always return None to force download
        return None
    
    def get_file_by_info(self, file_info: Dict):
        """Get file by info if it exists in cache."""
        # For simplicity, always return None to force download
        return None
    
    def put_file(self, file_info: Dict, temp_file_path: str) -> str:
        """Move the downloaded file to cache location and return its path."""
        file_path = file_info['Path']
        
        # Determine final file path based on cache settings
        final_file_path = os.path.join(self.root_location_path, file_path)
        
        # Create parent directories if needed
        os.makedirs(os.path.dirname(final_file_path), exist_ok=True)
        
        # Move the file from temporary location to final location
        shutil.move(temp_file_path, final_file_path)
        
        return final_file_path
    
    def get_root_location(self):
        """Get the root location of the cache."""
        return self.root_location_path


def create_temporary_directory_and_cache(model_id: str,
                                         local_dir: str = None,
                                         cache_dir: str = None,
                                         repo_type: str = REPO_TYPE_MODEL):
    """Create temporary directory and cache object."""
    # Only use local_dir if specified, otherwise use current directory
    if local_dir is not None:
        temporary_cache_dir = os.path.join(local_dir, TEMPORARY_FOLDER_NAME)
        cache = BasicCache(local_dir)
    else:
        # Use current directory as default
        current_dir = os.getcwd()
        temporary_cache_dir = os.path.join(current_dir, TEMPORARY_FOLDER_NAME)
        cache = BasicCache(current_dir)

    os.makedirs(temporary_cache_dir, exist_ok=True)
    return temporary_cache_dir, cache


def create_temporary_directory(repo_id: str, local_dir: str = None, cache_dir: str = None, repo_type: str = REPO_TYPE_MODEL):
    """Create temporary directory for downloads."""
    # Only use local_dir if specified, otherwise use current directory
    if local_dir is not None:
        temporary_cache_dir = os.path.join(local_dir, TEMPORARY_FOLDER_NAME)
    else:
        # Use current directory as default
        current_dir = os.getcwd()
        temporary_cache_dir = os.path.join(current_dir, TEMPORARY_FOLDER_NAME)

    os.makedirs(temporary_cache_dir, exist_ok=True)
    return temporary_cache_dir


def snapshot_download(
    repo_id: str,
    repo_type: str = REPO_TYPE_MODEL,
    revision: Optional[str] = None,
    cache_dir: Union[str, Path, None] = None,
    local_files_only: Optional[bool] = False,
    cookies: Optional[CookieJar] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
) -> str:
    """Download all files from a repository."""
    if repo_type not in REPO_TYPE_SUPPORT:
        raise ValueError(f'Invalid repo type: {repo_type}, only support: {REPO_TYPE_SUPPORT}')

    if revision is None:
        revision = DEFAULT_DATASET_REVISION if repo_type == REPO_TYPE_DATASET else DEFAULT_MODEL_REVISION

    temporary_cache_dir = create_temporary_directory(repo_id, local_dir=local_dir, cache_dir=cache_dir, repo_type=repo_type)
    
    if local_files_only:
        # In a full implementation, we would check if the files already exist in cache
        print("Local files only mode is not fully implemented in this standalone version")
        return temporary_cache_dir

    _api = HubApi(token=token)
    endpoint = _api.get_endpoint_for_read(repo_id, repo_type)
    
    if cookies is None:
        cookies = _api.get_cookies()
    else:
        if isinstance(cookies, dict):
            pass  # Already in correct format
        else:
            cookies = {}
    
    revision = _api.get_valid_revision(repo_id, revision=revision, cookies=cookies, endpoint=endpoint)
    
    # Get the list of files to download
    if repo_type == REPO_TYPE_MODEL:
        repo_files = _api.get_model_files(
            model_id=repo_id,
            revision=revision,
            recursive=True,
            use_cookies=cookies,
            endpoint=endpoint
        )
    else:
        print("Dataset snapshot download is not fully implemented in this standalone version. "
              "Use dataset_file_download for individual file downloads.")
        return temporary_cache_dir

    # Process each file and download
    for repo_file in repo_files:
        if repo_file.get('Type') == 'tree':
            continue  # Skip directories

        file_path = repo_file['Path']
        print(f"Downloading: {file_path}")

        try:
            # Download this specific file
            _repo_file_download(
                repo_id=repo_id,
                file_path=file_path,
                repo_type=repo_type,
                revision=revision,
                cache_dir=cache_dir,
                local_files_only=local_files_only,
                cookies=cookies,
                local_dir=local_dir,
                disable_tqdm=False,
                token=token
            )
        except Exception as e:
            print(f"Failed to download {file_path}: {e}")
            continue  # Continue with other files

    print("Snapshot download completed!")
    
    # Return the cache directory path
    if local_dir:
        return os.path.abspath(local_dir)
    else:
        return temporary_cache_dir


def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(description='Download models from ModelScope without CLI dependencies')
    parser.add_argument('repo_id', type=str, help='Repository ID in format owner/name')
    parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    parser.add_argument('--repo-type', choices=['model', 'dataset'], default='model', help='Type of repository (default: model)')
    parser.add_argument('--revision', type=str, default=None, help='Revision of the model (default: master)')
    parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory for downloaded files')
    parser.add_argument('--local-dir', type=str, default=None, help='Local directory to download files to')
    parser.add_argument('--token', type=str, default=None, help='Access token for private models')
    
    args = parser.parse_args()

    try:
        if args.file:
            # Download a specific file
            if args.repo_type == 'model':
                result = model_file_download(
                    model_id=args.repo_id,
                    file_path=args.file,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token
                )
            else:
                result = dataset_file_download(
                    dataset_id=args.repo_id,
                    file_path=args.file,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token
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
                token=args.token
            )
            print(f"Repository download completed. Files are in: {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
