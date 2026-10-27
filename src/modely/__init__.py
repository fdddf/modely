import os
import sys
import argparse
from .modelscope import (
    main as modelscope_main,
    model_file_download,
    dataset_file_download,
    snapshot_download as modelscope_snapshot_download,
    HubApi
)
from .hf import (
    hf_file_download,
    snapshot_download as hf_snapshot_download,
    main as hf_main
)
from .github import (
    github_file_download,
    snapshot_download as github_snapshot_download,
    main as github_main
)
from .watch import (
    configure_parser as configure_watch_parser,
    main as watch_main,
    run_watch,
    list_targets as watch_list_targets,
)
from .search import SearchResult, main as search_main
from .common import cache


def _format_file_size(size_bytes):
    """Format bytes into human-readable form."""
    if size_bytes is None or size_bytes == 0:
        return "-"
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.1f} GB"
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    if size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.1f} KB"
    return f"{size_bytes} B"


def _print_file_list(files, source, repo_id):
    """Print a formatted table of repository files."""
    if not files:
        print(f"No files found in {repo_id}")
        return

    headers = ["Path", "Size", "Type"]
    rows = []
    col_widths = [len(h) for h in headers]

    for f in files:
        row = [
            f.get("Path", f.get("path", "-")),
            _format_file_size(f.get("Size", f.get("size", 0))),
            f.get("Type", f.get("type", "blob")),
        ]
        rows.append(row)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Truncate long paths
    max_path = min(col_widths[0], 70)
    separator = "  ".join("-" * w for w in col_widths)
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))

    print(f"\n[{source.upper()}] {repo_id}\n")
    print(header_line)
    print(separator)
    for row in rows:
        path = str(row[0])
        if len(path) > 70:
            path = path[:67] + "..."
        print(f"{path.ljust(col_widths[0])}  {str(row[1]).ljust(col_widths[1])}  {str(row[2]).ljust(col_widths[2])}")
    print(f"\n{len(files)} file(s) shown.\n")


def _do_dry_run(source, repo_id, repo_type, revision, allow_patterns, ignore_patterns, files):
    """Simulate what would be downloaded and print a summary."""
    import fnmatch

    blobs = [f for f in files if f.get("Type", f.get("type", "")) != "tree"]

    # Apply filters
    filtered = blobs
    if allow_patterns:
        filtered = [f for f in filtered
                    if any(fnmatch.fnmatch(f.get("Path", f.get("path", "")), p) for p in allow_patterns)]
    if ignore_patterns:
        filtered = [f for f in filtered
                    if not any(fnmatch.fnmatch(f.get("Path", f.get("path", "")), p) for p in ignore_patterns)]

    total_size = sum(f.get("Size", f.get("size", 0)) or 0 for f in filtered)

    print(f"\n[{source.upper()}] {repo_id} (dry-run)")
    print(f"  Repository type: {repo_type}")
    print(f"  Revision:        {revision}")
    print(f"  Total files:     {len(blobs)}")
    if allow_patterns:
        print(f"  Include:         {' '.join(allow_patterns)}")
    if ignore_patterns:
        print(f"  Exclude:         {' '.join(ignore_patterns)}")
    print(f"  Would download:  {len(filtered)} file(s), {_format_file_size(total_size)}")
    print()


def _list_hf_files(repo_id, repo_type, revision, token, endpoint):
    """Fetch file listing from Hugging Face Hub."""
    from huggingface_hub import HfApi
    api = HfApi(endpoint=endpoint, token=token)
    try:
        paths = api.list_repo_files(repo_id, repo_type=repo_type, revision=revision)
        # Get size info for each file
        try:
            info_list = api.get_paths_info(repo_id, paths, repo_type=repo_type, revision=revision)
        except Exception:
            return [{"Path": p, "Size": 0, "Type": "blob"} for p in paths]
        return [
            {"Path": p, "Size": getattr(info, "size", 0) or 0, "Type": "blob"}
            for p, info in zip(paths, info_list)
        ]
    except Exception as e:
        print(f"Warning: Could not list files from HF: {e}", file=sys.stderr)
        return []


def _list_ms_files(repo_id, repo_type, revision, token):
    """Fetch file listing from ModelScope."""
    from .modelscope import HubApi
    api = HubApi(token=token)
    try:
        if repo_type == "model":
            files = api.get_model_files(repo_id, revision=revision)
        else:
            files = api.get_dataset_files(repo_id, revision=revision)
        return files
    except Exception as e:
        print(f"Warning: Could not list files from ModelScope: {e}", file=sys.stderr)
        return []


def main():
    parser = argparse.ArgumentParser(prog="modely", description="Modely - A tool for downloading models from various sources")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ModelScope subcommand (renamed to "ms")
    ms_parser = subparsers.add_parser("ms", help="Download models from ModelScope")
    ms_parser.add_argument('repo_id', type=str, help='Repository ID in format owner/name')
    ms_parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    ms_parser.add_argument('--repo-type', choices=['model', 'dataset'], default='model', help='Type of repository (default: model)')
    ms_parser.add_argument('--revision', type=str, default=None, help='Revision of the model (default: master)')
    ms_parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory for downloaded files')
    ms_parser.add_argument('--local-dir', type=str, default=None, help='Local directory to download files to')
    ms_parser.add_argument('--token', type=str, default=None, help='Access token for private models')
    ms_parser.add_argument('--include', nargs='+', default=None, help='Glob patterns to include (e.g., "*.json" "*.safetensors")')
    ms_parser.add_argument('--exclude', nargs='+', default=None, help='Glob patterns to exclude (e.g., "*.bin" "*.msgpack")')
    ms_parser.add_argument('--endpoint', type=str, default=None, help='ModelScope API endpoint')
    ms_parser.add_argument('--backend', choices=['auto', 'official', 'lightweight'], default='auto', help='ModelScope backend to use (default: auto)')
    ms_parser.add_argument('--list-files', action='store_true', help='List remote repository files without downloading')
    ms_parser.add_argument('--dry-run', action='store_true', help='Show what would be downloaded without downloading')

    # Cache management subcommand
    cache_parser = subparsers.add_parser("cache", help="Manage modely cache")
    cache_parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory to use')
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache commands")

    # modely cache info
    cache_info_parser = cache_subparsers.add_parser("info", help="Show cache information")

    # modely cache list
    cache_list_parser = cache_subparsers.add_parser("list", help="List cached repositories")
    cache_list_parser.add_argument("--detail", action="store_true", help="Show detailed file list")

    # modely cache clean
    cache_clean_parser = cache_subparsers.add_parser("clean", help="Clean cache")
    cache_clean_parser.add_argument("repo_id", nargs="?", default=None, help="Specific repo to clean (optional)")

    # modely cache config
    cache_config_parser = cache_subparsers.add_parser("config", help="Show or set cache directory")
    cache_config_parser.add_argument("--set", type=str, default=None, help="Set cache directory to this path")

    # Hugging Face subcommand
    hf_parser = subparsers.add_parser("hf", help="Download models from Hugging Face")
    hf_parser.add_argument('repo_id', type=str, help='Repository ID in format namespace/model_name')
    hf_parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    hf_parser.add_argument('--repo-type', choices=['model', 'dataset', 'space'], default='model', help='Type of repository (default: model)')
    hf_parser.add_argument('--revision', type=str, default='main', help='Revision of the model (default: main)')
    hf_parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory for downloaded files')
    hf_parser.add_argument('--local-dir', type=str, default=None, help='Local directory to download files to')
    hf_parser.add_argument('--token', type=str, default=None, help='Access token for private repositories')
    hf_parser.add_argument('--force-download', action='store_true', help='Force re-download even if file exists')
    hf_parser.add_argument('--include', nargs='+', default=None, help='Glob patterns to include (e.g., "*.json" "*.safetensors")')
    hf_parser.add_argument('--exclude', nargs='+', default=None, help='Glob patterns to exclude (e.g., "*.bin" "*.msgpack")')
    hf_parser.add_argument('--endpoint', type=str, default=None, help='HF API endpoint (e.g., https://hf-mirror.com)')
    hf_parser.add_argument('--list-files', action='store_true', help='List remote repository files without downloading')
    hf_parser.add_argument('--dry-run', action='store_true', help='Show what would be downloaded without downloading')

    # GitHub subcommand
    github_parser = subparsers.add_parser("github", help="Download from GitHub")
    github_parser.add_argument('repo_id', type=str, help='Repository ID in format owner/repo')
    github_parser.add_argument('--file', type=str, help='Specific file to download')
    github_parser.add_argument('--revision', type=str, default='main', help='Branch, tag, or commit SHA (default: main)')
    github_parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory for downloaded files')
    github_parser.add_argument('--local-dir', type=str, default=None, help='Local directory to download files to')
    github_parser.add_argument('--token', type=str, default=None, help='GitHub personal access token for private repositories')
    github_parser.add_argument('--with-lfs', action='store_true', help='Enable Git LFS support for large files')
    github_parser.add_argument('--force-download', action='store_true', help='Force re-download even if file exists')

    # Watch subcommand
    watch_parser = subparsers.add_parser("watch", help="Watch repositories and download updates")
    configure_watch_parser(watch_parser)

    # Search subcommand
    search_parser = subparsers.add_parser("search", help="Search for models and datasets")
    search_parser.add_argument("keyword", type=str, nargs="?", default=None, help="Search keyword for model/dataset name")
    search_parser.add_argument(
        "--source", "-s", choices=["hf", "ms", "github", "all"], default="all",
        help="Platform to search (default: all)",
    )
    search_parser.add_argument(
        "--repo-type", "-t", choices=["model", "dataset", "tool"], default="model",
        help="Type of repository (default: model)",
    )
    search_parser.add_argument(
        "--task", type=str, default=None,
        help="Filter by task type (e.g., text-classification)",
    )
    search_parser.add_argument(
        "--library", type=str, default=None,
        help="Filter by library (HF only, e.g., transformers, pytorch)",
    )
    search_parser.add_argument(
        "--license", type=str, default=None,
        help="Filter by license (HF only)",
    )
    search_parser.add_argument(
        "--sort", type=str, default="downloads",
        choices=["downloads", "lastModified", "likes", "created_at"],
        help="Sort field (default: downloads)",
    )
    search_parser.add_argument(
        "--direction", choices=["asc", "desc"], default="desc",
        help="Sort direction (default: desc)",
    )
    search_parser.add_argument(
        "--limit", "-n", type=int, default=20,
        help="Max results per source (default: 20)",
    )
    search_parser.add_argument(
        "--author", type=str, default=None,
        help="Filter by author/owner",
    )
    search_parser.add_argument(
        "--after", type=str, default=None,
        help="Only repos modified after this date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--before", type=str, default=None,
        help="Only repos modified before this date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--full", action="store_true",
        help="Return full model/dataset info (HF only)",
    )
    search_parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    if args.command == "ms":
        try:
            # Set ModelScope endpoint if provided
            if getattr(args, 'endpoint', None):
                os.environ['MODELSCOPE_ENDPOINT'] = args.endpoint

            # --list-files: show remote file listing
            if getattr(args, 'list_files', False):
                files = _list_ms_files(args.repo_id, args.repo_type, args.revision, args.token)
                _print_file_list(files, "ms", args.repo_id)
                return

            # --dry-run: preview what would be downloaded
            if getattr(args, 'dry_run', False):
                files = _list_ms_files(args.repo_id, args.repo_type, args.revision, args.token)
                _do_dry_run("ms", args.repo_id, args.repo_type, args.revision,
                            args.include, args.exclude, files)
                return

            if args.file:
                # Download a specific file
                if args.repo_type == 'model':
                    result = model_file_download(
                        model_id=args.repo_id,
                        file_path=args.file,
                        revision=args.revision,
                        cache_dir=args.cache_dir,
                        local_dir=args.local_dir,
                        token=args.token,
                        backend=args.backend
                    )
                else:
                    result = dataset_file_download(
                        dataset_id=args.repo_id,
                        file_path=args.file,
                        revision=args.revision,
                        cache_dir=args.cache_dir,
                        local_dir=args.local_dir,
                        token=args.token,
                        backend=args.backend
                    )
                print(f"Successfully downloaded file to: {result}")
            else:
                # Download entire repository
                result = modelscope_snapshot_download(
                    repo_id=args.repo_id,
                    repo_type=args.repo_type,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    allow_patterns=args.include,
                    ignore_patterns=args.exclude,
                    backend=args.backend,
                )
                if result is not None:
                    print(f"Repository download completed. Files are in: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "hf":
        try:
            # Set HF endpoint if provided
            if getattr(args, 'endpoint', None):
                os.environ['HF_ENDPOINT'] = args.endpoint

            # --list-files: show remote file listing
            if getattr(args, 'list_files', False):
                files = _list_hf_files(args.repo_id, args.repo_type, args.revision, args.token, args.endpoint)
                _print_file_list(files, "hf", args.repo_id)
                return

            # --dry-run: preview what would be downloaded
            if getattr(args, 'dry_run', False):
                files = _list_hf_files(args.repo_id, args.repo_type, args.revision, args.token, args.endpoint)
                _do_dry_run("hf", args.repo_id, args.repo_type, args.revision,
                            args.include, args.exclude, files)
                return

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
                result = hf_snapshot_download(
                    repo_id=args.repo_id,
                    repo_type=args.repo_type,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    allow_patterns=args.include,
                    ignore_patterns=args.exclude,
                    force_download=args.force_download
                )
                if result is not None:
                    print(f"Repository download completed. Files are in: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "github":
        try:
            if args.file:
                # Download a specific file
                result = github_file_download(
                    repo_id=args.repo_id,
                    filename=args.file,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    force_download=args.force_download
                )
                print(f"Successfully downloaded file to: {result}")
            else:
                # Clone entire repository
                result = github_snapshot_download(
                    repo_id=args.repo_id,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    with_lfs=args.with_lfs,
                    force_download=args.force_download
                )
                # github_clone() prints its own messages
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "cache":
        cache_main(args)
    elif args.command == "watch":
        watch_main(args)
    elif args.command == "search":
        search_main(args)
    else:
        parser.print_help()
        sys.exit(1)


def cache_main(args=None):
    """Handle cache subcommand."""
    if args is None:
        # If called directly
        parser = argparse.ArgumentParser(description="Manage modely cache")
        subparsers = parser.add_subparsers(dest="cache_command")

        info_parser = subparsers.add_parser("info")
        list_parser = subparsers.add_parser("list")
        list_parser.add_argument("--detail", action="store_true")
        clean_parser = subparsers.add_parser("clean")
        clean_parser.add_argument("repo_id", nargs="?", default=None)
        config_parser = subparsers.add_parser("config")
        config_parser.add_argument("--set", type=str, default=None)

        args = parser.parse_args()

    # Get cache_dir from args if provided
    cache_dir = getattr(args, "cache_dir", None)

    if args.cache_command == "info":
        info = cache.cache_info(cache_dir)
        print(f"Cache directory: {info['cache_dir']}")
        print(f"Total size: {info['total_size_str']}")
        print(f"Config file: {info['config_file']}")

    elif args.cache_command == "list":
        repos = cache.list_cache(cache_dir, detail=args.detail if hasattr(args, "detail") else False)
        if not repos:
            print("No cached repositories found.")
        else:
            for repo in repos:
                print(f"\n[{repo['source']}] {repo['repo_type']}: {repo['repo_id']} ({repo['revision']})")
                print(f"  Path: {repo['path']}")
                print(f"  Size: {repo['size_str']}")
                if args.detail and "files" in repo:
                    for f in repo["files"]:
                        print(f"    - {f['name']} ({f['size_str']})")

    elif args.cache_command == "clean":
        if args.repo_id:
            cleaned = cache.clean_cache(repo_id=args.repo_id, cache_dir=cache_dir)
            print(f"Cleaned {cache._format_size(cleaned)} for {args.repo_id}")
        else:
            cleaned = cache.clean_cache(cache_dir=cache_dir)
            print(f"Cleaned all cache: {cache._format_size(cleaned)}")

    elif args.cache_command == "config":
        if hasattr(args, "set") and args.set:
            cache.set_cache_dir(args.set)
            print(f"Cache directory set to: {args.set}")
        else:
            info = cache.cache_info(cache_dir)
            print(f"Current cache directory: {info['cache_dir']}")
            config = cache._load_config()
            if "cache_dir" in config:
                print(f"Configured in: {cache.CONFIG_FILE}")

    else:
        print("Usage: modely cache [info|list|clean|config]")
        sys.exit(1)


__all__ = [
    "main",
    "model_file_download",
    "dataset_file_download",
    "modelscope_snapshot_download",
    "hf_file_download",
    "hf_snapshot_download",
    "github_file_download",
    "github_snapshot_download",
    "HubApi",
    "cache",
    "cache_main",
    "watch_main",
    "run_watch",
    "watch_list_targets",
    "search",
    "SearchResult",
    "search_main",
]
