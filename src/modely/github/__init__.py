#!/usr/bin/env python
"""
A module to download files and repositories from GitHub.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union
from urllib.parse import quote

import requests
from tqdm import tqdm

from modely.common import cache as github_cache
from modely.types import FileInfo, RepoInfo
from modely.uri import normalize_github_repo_id


def github_file_download(
    repo_id: str,
    filename: str,
    *,
    revision: str = "main",
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    force_download: bool = False,
    timeout: Optional[float] = None,
) -> str:
    """
    Download a single file from a GitHub repository.

    Args:
        repo_id: Repository ID in the format "owner/repo"
        filename: Path to the file in the repository
        revision: Branch, tag, or commit SHA (default: main)
        cache_dir: Directory to cache downloaded files
        local_dir: Local directory to save the file
        token: GitHub personal access token for private repos
        force_download: Force re-download even if file exists

    Returns:
        Path to the downloaded file
    """
    repo_id = normalize_github_repo_id(repo_id)
    # Check cache first
    if not force_download:
        cached = github_cache.is_cached(
            repo_id, filename, revision, "tool", "github", cache_dir
        )
        if cached:
            file_path = github_cache.get_file_path(
                repo_id, filename, revision, "tool", "github", cache_dir
            )
            print(f"File already cached at: {file_path}")
            return file_path

    # Determine save location
    if local_dir:
        file_path = os.path.join(local_dir, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
    else:
        file_path = github_cache.get_file_path(
            repo_id, filename, revision, "tool", "github", cache_dir
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Build raw URL
    encoded_path = quote(filename, safe="/")
    url = f"https://raw.githubusercontent.com/{repo_id}/{revision}/{encoded_path}"

    # Download with requests
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(url, headers=headers, stream=True, timeout=timeout or 30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        with open(file_path, "wb") as f:
            if total_size > 0:
                with tqdm(
                    total=total_size, unit="B", unit_scale=True, desc=filename
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            else:
                f.write(response.content)

        return file_path
    except requests.HTTPError as e:
        if response.status_code == 404:
            raise Exception(
                f"File not found: {filename} in {repo_id} (revision: {revision})"
            )
        raise Exception(f"Failed to download {filename}: {e}")
    except Exception as e:
        raise Exception(f"Failed to download {filename}: {e}")


def _github_headers(token: Optional[str] = None) -> dict:
    headers = {"User-Agent": "modely-ai", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_repo_info(repo_id: str, *, revision: str = "main", token: Optional[str] = None) -> RepoInfo:
    """Get GitHub repository metadata."""
    repo_id = normalize_github_repo_id(repo_id)
    resp = requests.get(f"https://api.github.com/repos/{repo_id}", headers=_github_headers(token), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    license_info = data.get("license") or {}
    return RepoInfo(
        source="github",
        repo_type="tool",
        repo_id=data.get("full_name", repo_id),
        url=data.get("html_url", f"https://github.com/{repo_id}"),
        author=(data.get("owner") or {}).get("login"),
        revision=revision or data.get("default_branch"),
        private=data.get("private"),
        likes=data.get("stargazers_count", 0) or 0,
        forks=data.get("forks_count", 0) or 0,
        created_at=data.get("created_at"),
        last_modified=data.get("updated_at"),
        description=data.get("description"),
        license=license_info.get("spdx_id"),
        tags=data.get("topics") or [],
        metadata={"default_branch": data.get("default_branch")},
    )


def _resolve_tree_sha(repo_id: str, revision: str, token: Optional[str] = None) -> str:
    repo_id = normalize_github_repo_id(repo_id)
    resp = requests.get(
        f"https://api.github.com/repos/{repo_id}/git/trees/{quote(revision, safe='')}",
        params={"recursive": "1"},
        headers=_github_headers(token),
        timeout=30,
    )
    if resp.status_code == 404 and revision == "main":
        default = get_default_branch(repo_id, token)
        if default and default != revision:
            return _resolve_tree_sha(repo_id, default, token)
    resp.raise_for_status()
    return resp.json()


def github_list_files(repo_id: str, *, revision: str = "main", token: Optional[str] = None) -> list[FileInfo]:
    """List files in a GitHub repository using the Git Trees API."""
    data = _resolve_tree_sha(repo_id, revision, token)
    result = []
    for item in data.get("tree", []):
        result.append(FileInfo(
            path=item.get("path", ""),
            size=item.get("size", 0) or 0,
            type="tree" if item.get("type") == "tree" else "blob",
            sha256=item.get("sha"),
            metadata=item,
        ))
    return result


def github_release_assets(repo_id: str, *, release: Optional[str] = None, token: Optional[str] = None) -> list[FileInfo]:
    """List GitHub release assets."""
    if release:
        url = f"https://api.github.com/repos/{repo_id}/releases/tags/{quote(release, safe='')}"
        releases = [requests.get(url, headers=_github_headers(token), timeout=30).json()]
    else:
        url = f"https://api.github.com/repos/{repo_id}/releases"
        r = requests.get(url, headers=_github_headers(token), timeout=30)
        r.raise_for_status()
        releases = r.json()
    assets = []
    for rel in releases:
        for asset in rel.get("assets", []) or []:
            assets.append(FileInfo(
                path=asset.get("name", ""),
                size=asset.get("size", 0) or 0,
                type="asset",
                download_url=asset.get("browser_download_url"),
                metadata={"release": rel.get("tag_name"), "asset_id": asset.get("id")},
            ))
    return assets


def github_release_asset_download(
    repo_id: str,
    asset: str,
    *,
    release: Optional[str] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    force_download: bool = False,
) -> str:
    """Download a GitHub release asset by name."""
    assets = github_release_assets(repo_id, release=release, token=token)
    match = next((a for a in assets if a.path == asset), None)
    if not match or not match.download_url:
        raise Exception(f"Release asset not found: {asset}")
    revision = release or "releases"
    if not force_download and github_cache.is_cached(repo_id, asset, revision, "tool", "github", cache_dir):
        path = github_cache.get_file_path(repo_id, asset, revision, "tool", "github", cache_dir)
        print(f"File already cached at: {path}")
        return path
    if local_dir:
        file_path = os.path.join(local_dir, asset)
        os.makedirs(local_dir, exist_ok=True)
    else:
        file_path = github_cache.get_file_path(repo_id, asset, revision, "tool", "github", cache_dir)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
    headers = _github_headers(token)
    r = requests.get(match.download_url, headers=headers, stream=True, timeout=60)
    r.raise_for_status()
    total_size = int(r.headers.get("content-length", 0))
    with open(file_path, "wb") as f:
        with tqdm(total=total_size, unit="B", unit_scale=True, desc=asset) as pbar:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    return file_path


def get_default_branch(repo_id: str, token: Optional[str] = None) -> Optional[str]:
    """Get the default branch of a GitHub repository via API."""
    repo_id = normalize_github_repo_id(repo_id)
    url = f"https://api.github.com/repos/{repo_id}"
    headers = _github_headers(token)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("default_branch", "main")
    except Exception:
        return None


def github_clone(
    repo_id: str,
    *,
    revision: str = "main",
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    with_lfs: bool = False,
    force_download: bool = False,
    allow_patterns: Optional[list[str]] = None,
    ignore_patterns: Optional[list[str]] = None,
    submodules: bool = False,
) -> str:
    """
    Clone a GitHub repository using git.

    Args:
        repo_id: Repository ID in the format "owner/repo"
        revision: Branch, tag, or commit SHA (default: main)
        cache_dir: Directory to cache downloaded files
        local_dir: Local directory to clone the repository
        token: GitHub personal access token for private repos
        with_lfs: Enable Git LFS support for large files
        force_download: Force re-clone even if cached

    Returns:
        Path to the cloned repository
    """
    repo_id = normalize_github_repo_id(repo_id)
    # Resolve actual revision (use default branch if needed)
    actual_revision = revision
    if not force_download and revision == "main":
        # Try to get default branch for better cache hit
        default_branch = get_default_branch(repo_id, token)
        if default_branch and default_branch != "main":
            actual_revision = default_branch

    # Check cache first
    if not force_download:
        cached_path = github_cache.get_cached_repo_path(
            repo_id, "tool", actual_revision, "github", cache_dir
        )
        if cached_path and os.path.exists(os.path.join(cached_path, ".git")):
            print(f"Repository already cached at: {cached_path}")
            return cached_path

    # Determine target directory
    if local_dir:
        target_dir = local_dir
    else:
        target_dir = github_cache.get_repo_cache_dir(
            repo_id, "tool", actual_revision, "github", cache_dir
        )

    # Build git URL with optional token authentication
    if token:
        git_url = f"https://{token}@github.com/{repo_id}.git"
    else:
        git_url = f"https://github.com/{repo_id}.git"

    # Remove existing directory if force download
    if force_download and os.path.exists(target_dir):
        shutil.rmtree(target_dir)

    # Clone the repository
    # Do NOT pre-create target_dir; let git create it
    parent_dir = os.path.dirname(target_dir)
    repo_name = os.path.basename(target_dir)

    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
    ]
    if allow_patterns:
        cmd.extend(["--filter=blob:none", "--sparse"])
    cmd.extend([
        "--branch",
        revision,
        git_url,
        repo_name,
    ])

    def _cleanup_on_failure(target):
        """Clean up target directory if clone failed."""
        if local_dir and os.path.abspath(target) == os.path.abspath(local_dir):
            return
        if os.path.exists(target) and os.path.isdir(target):
            try:
                shutil.rmtree(target)
            except Exception:
                pass

    def _run_git_clone(clone_cmd, cwd):
        """Run git clone with --progress and stream key progress lines."""
        clone_cmd = list(clone_cmd)
        if "--progress" not in clone_cmd:
            clone_cmd.append("--progress")
        proc = subprocess.Popen(
            clone_cmd,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        stderr_lines = []
        while True:
            line = proc.stderr.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                line = line.rstrip()
                stderr_lines.append(line)
                # Show only key progress lines: done, phase headers, errors, and 10/20/50/80/100% milestones
                if _is_key_progress_line(line):
                    print(line)
        proc.wait()
        return subprocess.CompletedProcess(
            args=clone_cmd, returncode=proc.returncode,
            stdout="", stderr="\n".join(stderr_lines),
        )

    def _is_key_progress_line(line):
        """Check if a git progress line is worth showing to the user."""
        # Always show: done lines, phase start lines, errors/warnings, non-percentage lines
        if not line:
            return False
        if 'done' in line:
            return True
        if line.startswith('Cloning into') or line.startswith('fatal:') or line.startswith('warning:'):
            return True
        # For percentage lines, show only milestones: 10%, 20%, 50%, 80%, 100%
        import re
        m = re.search(r'(\d+)%', line)
        if m:
            pct = int(m.group(1))
            return pct in (10, 20, 50, 80, 100)
        return False

    try:
        print(f"Cloning {repo_id} (revision: {revision})...")
        result = _run_git_clone(cmd, parent_dir)
        if result.returncode != 0:
            _cleanup_on_failure(target_dir)
            # Try without depth if shallow clone is not supported
            if "--depth" in cmd:
                cmd.remove("--depth")
                cmd.remove("1")
                result = _run_git_clone(cmd, parent_dir)
                if result.returncode != 0:
                    _cleanup_on_failure(target_dir)
            # If still fails, try to get default branch and retry
            if result.returncode != 0:
                default_branch = get_default_branch(repo_id, token)
                if default_branch and default_branch != revision:
                    print(f"Branch '{revision}' not found, trying default branch '{default_branch}'...")
                    # Rebuild target_dir with correct branch
                    if not local_dir:
                        target_dir = github_cache.get_repo_cache_dir(
                            repo_id, "tool", default_branch, "github", cache_dir
                        )
                        repo_name = os.path.basename(target_dir)
                        parent_dir = os.path.dirname(target_dir)
                    # Retry clone with default branch
                    retry_cmd = [
                        "git", "clone", "--depth", "1",
                        "--branch", default_branch,
                        git_url, repo_name,
                    ]
                    result = _run_git_clone(retry_cmd, parent_dir)
                    if result.returncode != 0 and "--depth" in retry_cmd:
                        retry_cmd.remove("--depth")
                        retry_cmd.remove("1")
                        result = _run_git_clone(retry_cmd, parent_dir)
                    if result.returncode != 0:
                        _cleanup_on_failure(target_dir)
                    revision = default_branch  # Update revision for LFS and return
                else:
                    # Last resort: clone without branch (uses remote HEAD)
                    simple_cmd = ["git", "clone", git_url, repo_name]
                    result = _run_git_clone(simple_cmd, parent_dir)
                    if result.returncode != 0:
                        _cleanup_on_failure(target_dir)

            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")

        # Apply sparse checkout/include patterns when requested.
        if allow_patterns:
            sparse_cmd = ["git", "sparse-checkout", "set", *allow_patterns]
            sparse_result = subprocess.run(sparse_cmd, cwd=target_dir, capture_output=True, text=True)
            if sparse_result.returncode != 0:
                print(f"Warning: git sparse-checkout failed: {sparse_result.stderr}")

        if submodules:
            submodule_result = subprocess.run(
                ["git", "submodule", "update", "--init", "--recursive"],
                cwd=target_dir,
                capture_output=True,
                text=True,
            )
            if submodule_result.returncode != 0:
                print(f"Warning: git submodule update failed: {submodule_result.stderr}")

        if ignore_patterns:
            _remove_ignored_files(target_dir, ignore_patterns)

        # Git LFS support
        if with_lfs:
            if shutil.which("git-lfs") is None and subprocess.run(["git", "lfs", "version"], capture_output=True).returncode != 0:
                print("Warning: Git LFS is not installed; large files may remain as pointer files.")
                return target_dir
            lfs_result = subprocess.run(
                ["git", "lfs", "pull"],
                cwd=target_dir,
                capture_output=True,
                text=True,
            )
            if lfs_result.returncode != 0:
                print(f"Warning: Git LFS pull failed: {lfs_result.stderr}")

        print(f"Repository cloned to: {target_dir}")
        return target_dir
    except FileNotFoundError:
        raise Exception(
            "git command not found. Please install git to use this feature."
        )
    except Exception as e:
        raise Exception(f"Failed to clone repository: {e}")


def _remove_ignored_files(root: str, ignore_patterns: list[str]) -> None:
    """Remove files matching ignore patterns after clone."""
    import fnmatch
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirpath.split(os.sep):
            continue
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            if any(fnmatch.fnmatch(rel, pat) for pat in ignore_patterns):
                try:
                    os.remove(path)
                except OSError:
                    pass


# Alias for consistency with hf/ms modules
snapshot_download = github_clone


def main():
    """Main function to handle command-line arguments for GitHub downloads."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download from GitHub"
    )
    parser.add_argument(
        "repo_id", type=str, help="Repository ID in format owner/repo"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Specific file to download from the repository",
    )
    parser.add_argument(
        "--revision",
        type=str,
        default="main",
        help="Branch, tag, or commit SHA (default: main)",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Cache directory for downloaded files",
    )
    parser.add_argument(
        "--local-dir",
        type=str,
        default=None,
        help="Local directory to download files to",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="GitHub personal access token for private repositories",
    )
    parser.add_argument(
        "--with-lfs",
        action="store_true",
        help="Enable Git LFS support for large files",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download even if file exists",
    )

    args = parser.parse_args()

    try:
        if args.file:
            result = github_file_download(
                repo_id=args.repo_id,
                filename=args.file,
                revision=args.revision,
                cache_dir=args.cache_dir,
                local_dir=args.local_dir,
                token=args.token,
                force_download=args.force_download,
            )
            print(f"Successfully downloaded file to: {result}")
        else:
            result = github_clone(
                repo_id=args.repo_id,
                revision=args.revision,
                cache_dir=args.cache_dir,
                local_dir=args.local_dir,
                token=args.token,
                with_lfs=args.with_lfs,
                force_download=args.force_download,
            )
            print(f"Repository cloned to: {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
