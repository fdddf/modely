"""Argument parser construction for the modely CLI."""

from __future__ import annotations

import argparse

from ..profiles import PROFILES
from ..watch import configure_parser as configure_watch_parser

_COMMAND_GROUPS = [
    (
        "Download and sync",
        [
            ("hf", "Download models or datasets from Hugging Face"),
            ("ms", "Download models or datasets from ModelScope"),
            ("github", "Download repositories, files, or release assets from GitHub"),
            ("get", "Download by modely URI or auto-selected source"),
            ("batch-download", "Search, preview, and batch download matching resources"),
            ("sync-center", "Manage registered resource sync targets and runs"),
            ("sync", "Download-only local sync of a resource"),
            ("mirror", "Alias for sync"),
        ],
    ),
    (
        "Query and evaluate",
        [
            ("info", "Show repository metadata for a modely URI"),
            ("files", "List and summarize repository files for a modely URI"),
            ("plan", "Dry-run a download plan without downloading"),
            ("card", "Fetch and parse a model, dataset, or repository card"),
            ("detail", "Show a unified resource detail page"),
            ("analyze", "Analyze metadata, files, cards, and weight formats"),
            ("score", "Score resource health from metadata and file lists"),
            ("scan", "Scan metadata, safety, and reproducibility risks"),
            ("license", "Classify resource license risk"),
            ("compare", "Deep-compare two explicit modely resources"),
            ("compare-many", "Compare several resources in one table"),
            ("version-diff", "Compare files between two resource revisions"),
            ("resolve", "Find likely equivalent resources across sources"),
        ],
    ),
    (
        "Search and choose sources",
        [
            ("search", "Search for models, datasets, and AI/ML repositories"),
            ("doctor", "Diagnose and recommend a modely resource"),
            ("choose", "Choose the best source for a resource query"),
            ("sources", "List or probe source endpoints"),
            ("capabilities", "Show source/backend capability support"),
        ],
    ),
    (
        "Reproducibility and inventory",
        [
            ("lock", "Create a JSON lockfile for a resource"),
            ("install", "Install files from a modely lockfile"),
            ("validate-lock", "Validate a lockfile against local files"),
            ("catalog", "Inventory local or cached modely assets"),
            ("label", "Tag, favorite, and group resources locally"),
            ("request", "Submit an access request for a governed resource"),
            ("approve", "Approve a pending access request"),
            ("reject", "Reject a pending access request"),
            ("policy-check", "Evaluate governance policy for a resource"),
            ("audit", "List local resource operation audit events"),
            ("policy", "Create built-in governance policy templates"),
            ("verify-mirror", "Verify two resources appear mirror-equivalent"),
            ("report", "Generate a resource report"),
            ("benchmark", "Check source endpoint availability and latency"),
        ],
    ),
    (
        "Account, monitoring, and cache",
        [
            ("login", "Store a source token"),
            ("logout", "Remove a stored source token"),
            ("whoami", "Show token status or identity"),
            ("watch", "Watch repositories and download updates"),
            ("cache", "Manage the modely cache"),
        ],
    ),
    (
        "Enterprise catalog & governance  [enterprise]",
        [
            ("asset", "Enterprise catalog asset operations (search/detail/download-url)"),
            ("recommend", "Recommend similar resources for an asset ID"),
            ("alternatives", "Show approved alternatives for blocked/high-risk assets"),
            ("graph", "Show permission-filtered asset relationship graph"),
            ("catalog-gate", "Evaluate policy for a catalog resource (CI gate)"),
            ("policy-check", "Evaluate governance policy for a resource"),
            ("report", "Generate a resource report (--compliance for enterprise)"),
        ],
    ),
    (
        "Enterprise reproducibility & auth  [enterprise]",
        [
            ("snapshot", "Manage approved snapshots (promote/rollback/list)"),
            ("manifest-diff", "Compare two manifests or asset versions"),
            ("resolve-approved", "Resolve latest approved asset snapshot"),
            ("install-approved", "Install/download exact approved asset files"),
            ("token-create", "Issue scoped API token for service account"),
            ("token-rotate", "Rotate an existing API token"),
            ("token-revoke", "Revoke an API token"),
        ],
    ),
]


_COMMAND_HELP = {command: help_text for _, commands in _COMMAND_GROUPS for command, help_text in commands}
_SOURCE_CHOICES = ('hf', 'ms', 'github', 'kaggle', 'auto')
_REPO_TYPE_CHOICES = ('auto', 'model', 'dataset', 'space', 'tool', 'competition')
_GET_REPO_TYPE_CHOICES = ('auto', 'model', 'dataset', 'space', 'tool')


def _add_source_repo_type_args(command_parser, *, repo_type_choices=_REPO_TYPE_CHOICES):
    command_parser.add_argument('--source', choices=_SOURCE_CHOICES, default='auto')
    command_parser.add_argument('--repo-type', choices=repo_type_choices, default='auto')


def _format_command_groups() -> str:
    lines = ["Command categories:"]
    for title, commands in _COMMAND_GROUPS:
        lines.append(f"  {title}:")
        width = max(len(command) for command, _ in commands)
        for command, help_text in commands:
            lines.append(f"    {command:<{width}}  {help_text}")
    return "\n".join(lines)


def _configure_sync_center_parser(subparsers) -> None:
    sync_center_parser = subparsers.add_parser("sync-center", help=_COMMAND_HELP["sync-center"])
    sync_subparsers = sync_center_parser.add_subparsers(dest="sync_center_command")

    add_parser = sync_subparsers.add_parser("add", help="Register a resource sync target")
    add_parser.add_argument("resource", type=str)
    add_parser.add_argument("--id", default=None)
    add_parser.add_argument("--local-dir", required=True)
    _add_source_repo_type_args(add_parser)
    add_parser.add_argument("--revision", default=None)
    add_parser.add_argument("--include", nargs="+", default=None)
    add_parser.add_argument("--exclude", nargs="+", default=None)
    add_parser.add_argument("--profile", choices=list(PROFILES), default=None)
    add_parser.add_argument("--prefer", default="default")
    add_parser.add_argument("--cache-dir", default=None)
    add_parser.add_argument("--token-env", default=None)
    add_parser.add_argument("--checksum", action="store_true")
    add_parser.add_argument("--force-download", action="store_true")
    add_parser.add_argument("--manifest", default=None)
    add_parser.add_argument("--report", default=None)
    add_parser.add_argument("--label", action="append", default=[])
    add_parser.add_argument("--json", action="store_true")

    list_parser = sync_subparsers.add_parser("list", help="List registered sync targets")
    list_parser.add_argument("--json", action="store_true")

    show_parser = sync_subparsers.add_parser("show", help="Show a sync target")
    show_parser.add_argument("target_id")
    show_parser.add_argument("--json", action="store_true")

    remove_parser = sync_subparsers.add_parser("remove", help="Remove a sync target from the registry")
    remove_parser.add_argument("target_id")
    remove_parser.add_argument("--json", action="store_true")

    enable_parser = sync_subparsers.add_parser("enable", help="Enable a sync target")
    enable_parser.add_argument("target_id")
    enable_parser.add_argument("--json", action="store_true")

    disable_parser = sync_subparsers.add_parser("disable", help="Disable a sync target")
    disable_parser.add_argument("target_id")
    disable_parser.add_argument("--json", action="store_true")

    plan_parser = sync_subparsers.add_parser("plan", help="Create dry-run plans for sync targets")
    plan_parser.add_argument("target_id", nargs="?")
    plan_parser.add_argument("--all", action="store_true")
    plan_parser.add_argument("--token", default=None)
    plan_parser.add_argument("--json", action="store_true")

    run_parser = sync_subparsers.add_parser("run", help="Run sync targets")
    run_parser.add_argument("target_id", nargs="?")
    run_parser.add_argument("--all", action="store_true")
    run_parser.add_argument("--force-download", action="store_true", default=None)
    run_parser.add_argument("--checksum", action="store_true", default=None)
    run_parser.add_argument("--token", default=None)
    run_parser.add_argument("--json", action="store_true")

    check_parser = sync_subparsers.add_parser("check", help="Check remote drift for sync targets")
    check_parser.add_argument("target_id", nargs="?")
    check_parser.add_argument("--all", action="store_true")
    check_parser.add_argument("--json", action="store_true")

    runs_parser = sync_subparsers.add_parser("runs", help="List sync-center runs")
    runs_parser.add_argument("--target", dest="target_id", default=None)
    runs_parser.add_argument("--limit", type=int, default=50)
    runs_parser.add_argument("--json", action="store_true")

    catalog_parser = sync_subparsers.add_parser("catalog", help="Catalog registered target directories")
    catalog_parser.add_argument("--output", default=None)
    catalog_parser.add_argument("--snapshot", action="store_true")
    catalog_parser.add_argument("--json", action="store_true")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="modely",
        description="Modely - unified model and dataset download, discovery, and governance CLI",
        epilog=_format_command_groups(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", help=argparse.SUPPRESS)

    # ModelScope subcommand (renamed to "ms")
    ms_parser = subparsers.add_parser("ms", help=_COMMAND_HELP["ms"])
    ms_parser.add_argument('repo_id', type=str, help='Repository ID in format owner/name')
    ms_parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    ms_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset'], default='auto', help='Type of repository (default: auto)')
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
    cache_parser = subparsers.add_parser("cache", help=_COMMAND_HELP["cache"])
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
    cache_config_parser.add_argument("--set-shared", type=str, default=None, help="Set shared team cache directory to this path")

    cache_dedupe_parser = cache_subparsers.add_parser("dedupe", help="Report duplicate files in cache")
    cache_dedupe_parser.add_argument("--dry-run", action="store_true", help="Report only; do not modify files")
    cache_dedupe_parser.add_argument("--json", action="store_true")
    cache_serve_parser = cache_subparsers.add_parser("serve", help="Serve a read-only local cache browser")
    cache_serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    cache_serve_parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    cache_serve_parser.add_argument("--open", action="store_true", help="Open the browser after starting")

    # Hugging Face subcommand
    hf_parser = subparsers.add_parser("hf", help=_COMMAND_HELP["hf"])
    hf_parser.add_argument('repo_id', type=str, help='Repository ID in format namespace/model_name')
    hf_parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    hf_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'space'], default='auto', help='Type of repository (default: auto)')
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
    github_parser = subparsers.add_parser("github", help=_COMMAND_HELP["github"])
    github_parser.add_argument('repo_id', type=str, help='Repository ID in format owner/repo')
    github_parser.add_argument('--file', type=str, help='Specific file to download')
    github_parser.add_argument('--revision', type=str, default='main', help='Branch, tag, or commit SHA (default: main)')
    github_parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory for downloaded files')
    github_parser.add_argument('--local-dir', type=str, default=None, help='Local directory to download files to')
    github_parser.add_argument('--token', type=str, default=None, help='GitHub personal access token for private repositories')
    github_parser.add_argument('--with-lfs', action='store_true', help='Enable Git LFS support for large files')
    github_parser.add_argument('--force-download', action='store_true', help='Force re-download even if file exists')
    github_parser.add_argument('--include', nargs='+', default=None, help='Sparse checkout/include patterns')
    github_parser.add_argument('--exclude', nargs='+', default=None, help='Glob patterns to remove after clone')
    github_parser.add_argument('--release', type=str, default=None, help='GitHub release tag for asset downloads/listing')
    github_parser.add_argument('--asset', type=str, default=None, help='GitHub release asset name to download')
    github_parser.add_argument('--submodules', action='store_true', help='Initialize git submodules after clone')

    # Unified info/files/download commands
    info_parser = subparsers.add_parser("info", help=_COMMAND_HELP["info"])
    info_parser.add_argument("resource", type=str, help="Resource URI, e.g. hf://models/gpt2")
    _add_source_repo_type_args(info_parser)
    info_parser.add_argument('--revision', type=str, default=None)
    info_parser.add_argument('--token', type=str, default=None)
    info_parser.add_argument('--endpoint', type=str, default=None)
    info_parser.add_argument('--json', action='store_true')

    files_parser = subparsers.add_parser("files", help=_COMMAND_HELP["files"])
    files_parser.add_argument("resource", type=str, help="Resource URI, e.g. hf://models/gpt2")
    _add_source_repo_type_args(files_parser)
    files_parser.add_argument('--revision', type=str, default=None)
    files_parser.add_argument('--token', type=str, default=None)
    files_parser.add_argument('--endpoint', type=str, default=None)
    files_parser.add_argument('--release', type=str, default=None)
    files_parser.add_argument('--include', nargs='+', default=None)
    files_parser.add_argument('--exclude', nargs='+', default=None)
    files_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    files_parser.add_argument('--summary', action='store_true')
    files_parser.add_argument('--tree', action='store_true', help='Show files as a categorized tree')
    files_parser.add_argument('--json', action='store_true')

    plan_parser = subparsers.add_parser("plan", help=_COMMAND_HELP["plan"])
    plan_parser.add_argument("resource", type=str)
    _add_source_repo_type_args(plan_parser)
    plan_parser.add_argument('--revision', type=str, default=None)
    plan_parser.add_argument('--include', nargs='+', default=None)
    plan_parser.add_argument('--exclude', nargs='+', default=None)
    plan_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    plan_parser.add_argument('--cache-dir', default=None)
    plan_parser.add_argument('--local-dir', default=None)
    plan_parser.add_argument('--token', default=None)
    plan_parser.add_argument('--endpoint', default=None)
    plan_parser.add_argument('--release', default=None)
    plan_parser.add_argument('--json', action='store_true')

    card_parser = subparsers.add_parser("card", help=_COMMAND_HELP["card"])
    card_parser.add_argument("resource", type=str)
    _add_source_repo_type_args(card_parser)
    card_parser.add_argument('--revision', type=str, default=None)
    card_parser.add_argument('--token', default=None)
    card_parser.add_argument('--endpoint', default=None)
    card_parser.add_argument('--json', action='store_true')

    detail_parser = subparsers.add_parser("detail", help=_COMMAND_HELP["detail"])
    detail_parser.add_argument("resource", type=str)
    _add_source_repo_type_args(detail_parser)
    detail_parser.add_argument('--revision', type=str, default=None)
    detail_parser.add_argument('--token', default=None)
    detail_parser.add_argument('--endpoint', default=None)
    detail_parser.add_argument('--include', nargs='+', default=None)
    detail_parser.add_argument('--exclude', nargs='+', default=None)
    detail_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    detail_parser.add_argument('--deep', action='store_true')
    detail_parser.add_argument('--json', action='store_true')

    analyze_parser = subparsers.add_parser("analyze", help=_COMMAND_HELP["analyze"])
    analyze_parser.add_argument("resource", type=str)
    _add_source_repo_type_args(analyze_parser)
    analyze_parser.add_argument('--revision', type=str, default=None)
    analyze_parser.add_argument('--token', default=None)
    analyze_parser.add_argument('--endpoint', default=None)
    analyze_parser.add_argument('--include', nargs='+', default=None)
    analyze_parser.add_argument('--exclude', nargs='+', default=None)
    analyze_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    analyze_parser.add_argument('--top-files', type=int, default=5)
    analyze_parser.add_argument('--deep', action='store_true', help='Add metadata-derived format, quantization, profile, and risk analysis')
    analyze_parser.add_argument('--json', action='store_true')

    score_parser = subparsers.add_parser("score", help=_COMMAND_HELP["score"])
    score_parser.add_argument("resource")
    _add_source_repo_type_args(score_parser)
    score_parser.add_argument('--revision', type=str, default=None)
    score_parser.add_argument('--token', default=None)
    score_parser.add_argument('--endpoint', default=None)
    score_parser.add_argument('--include', nargs='+', default=None)
    score_parser.add_argument('--exclude', nargs='+', default=None)
    score_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    score_parser.add_argument('--no-deep', action='store_true', help='Disable deep metadata-derived scoring')
    score_parser.add_argument('--local', action='store_true', help='Score a local directory without network access')
    score_parser.add_argument('--json', action='store_true')
    # Enterprise admission scoring extensions
    score_parser.add_argument('--catalog', type=str, default=None, metavar="PATH", help='[enterprise] Use local enterprise catalog for admission scoring')
    score_parser.add_argument('--server', type=str, default=None, metavar="URL", help='[enterprise] Use enterprise modely-server for admission scoring')
    score_parser.add_argument('--scoring-profile', choices=['model', 'dataset', 'tool', 'space', 'notebook'], default=None, help='[enterprise] Override automatic scoring profile selection')

    scan_parser = subparsers.add_parser("scan", help=_COMMAND_HELP["scan"])
    scan_parser.add_argument("resource")
    _add_source_repo_type_args(scan_parser)
    scan_parser.add_argument('--revision', type=str, default=None)
    scan_parser.add_argument('--token', default=None)
    scan_parser.add_argument('--endpoint', default=None)
    scan_parser.add_argument('--include', nargs='+', default=None)
    scan_parser.add_argument('--exclude', nargs='+', default=None)
    scan_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    scan_parser.add_argument('--no-deep', action='store_true', help='Disable deep metadata-derived scanning')
    scan_parser.add_argument('--local', action='store_true', help='Scan a local directory without network access')
    scan_parser.add_argument('--inspect-files', action='store_true', help='Inspect small remote text/code files for suspicious patterns')
    scan_parser.add_argument('--fail-on', choices=['low', 'medium', 'high'], default=None, help='Exit nonzero if findings meet this severity')
    scan_parser.add_argument('--policy', default=None, help='JSON policy file for scan evaluation')
    scan_parser.add_argument('--json', action='store_true')

    license_parser = subparsers.add_parser("license", help=_COMMAND_HELP["license"])
    license_parser.add_argument("resource")
    _add_source_repo_type_args(license_parser)
    license_parser.add_argument('--revision', type=str, default=None)
    license_parser.add_argument('--token', default=None)
    license_parser.add_argument('--endpoint', default=None)
    license_parser.add_argument('--json', action='store_true')

    compare_parser = subparsers.add_parser("compare", help=_COMMAND_HELP["compare"])
    compare_parser.add_argument("left", type=str)
    compare_parser.add_argument("right", type=str)
    compare_parser.add_argument('--revision-left', default=None)
    compare_parser.add_argument('--revision-right', default=None)
    compare_parser.add_argument('--token', default=None)
    compare_parser.add_argument('--files', action='store_true', help='Include added/removed/common file details')
    compare_parser.add_argument('--card', action='store_true', help='Include normalized card metadata differences')
    compare_parser.add_argument('--formats', action='store_true', help='Include weight format differences')
    compare_parser.add_argument('--deep', action='store_true', help='Run deep analysis before comparing')
    compare_parser.add_argument('--json', action='store_true')

    compare_many_parser = subparsers.add_parser("compare-many", help=_COMMAND_HELP["compare-many"])
    compare_many_parser.add_argument("resources", nargs="+")
    compare_many_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'auto'], default='auto')
    compare_many_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'space', 'tool', 'competition'], default='auto')
    compare_many_parser.add_argument('--revision', type=str, default=None)
    compare_many_parser.add_argument('--token', default=None)
    compare_many_parser.add_argument('--endpoint', default=None)
    compare_many_parser.add_argument('--include', nargs='+', default=None)
    compare_many_parser.add_argument('--exclude', nargs='+', default=None)
    compare_many_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    compare_many_parser.add_argument('--deep', action='store_true')
    compare_many_parser.add_argument('--json', action='store_true')

    version_diff_parser = subparsers.add_parser("version-diff", help=_COMMAND_HELP["version-diff"])
    version_diff_parser.add_argument("resource")
    version_diff_parser.add_argument("--left-revision", required=True)
    version_diff_parser.add_argument("--right-revision", required=True)
    _add_source_repo_type_args(version_diff_parser)
    version_diff_parser.add_argument('--token', default=None)
    version_diff_parser.add_argument('--endpoint', default=None)
    version_diff_parser.add_argument('--json', action='store_true')

    get_parser = subparsers.add_parser("get", help=_COMMAND_HELP["get"])
    get_parser.add_argument("resource", nargs="+", help="Resource URI/repo, or SOURCE RESOURCE for compatibility")
    _add_source_repo_type_args(get_parser, repo_type_choices=_GET_REPO_TYPE_CHOICES)
    get_parser.add_argument('--revision', type=str, default=None)
    get_parser.add_argument('--file', type=str, default=None)
    get_parser.add_argument('--cache-dir', type=str, default=None)
    get_parser.add_argument('--local-dir', type=str, default=None)
    get_parser.add_argument('--token', type=str, default=None)
    get_parser.add_argument('--include', nargs='+', default=None)
    get_parser.add_argument('--exclude', nargs='+', default=None)
    get_parser.add_argument('--prefer', type=str, default='default')
    get_parser.add_argument('--fallback', action='store_true')
    get_parser.add_argument('--force-download', action='store_true')
    get_parser.add_argument('--backend', default='auto', help='Backend preference or registered backend name')
    get_parser.add_argument('--with-lfs', action='store_true')
    get_parser.add_argument('--manifest', type=str, default=None)
    get_parser.add_argument('--checksum', action='store_true')
    get_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    get_parser.add_argument('--endpoint', type=str, default=None)
    get_parser.add_argument('--max-workers', type=int, default=None)
    get_parser.add_argument('--timeout', type=float, default=None)
    get_parser.add_argument('--retries', type=int, default=None)
    get_parser.add_argument('--no-resume', action='store_true', help='Disable backend resume behavior where supported')
    get_parser.add_argument('--dry-run', action='store_true', help='Show a download plan and warnings without downloading')
    get_parser.add_argument('--json', action='store_true', help='Print dry-run plan as JSON')

    sources_parser = subparsers.add_parser("sources", help=_COMMAND_HELP["sources"])
    sources_subparsers = sources_parser.add_subparsers(dest="sources_command")
    sources_list_parser = sources_subparsers.add_parser("list", help="List source profiles")
    sources_list_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    sources_list_parser.add_argument('--json', action='store_true')
    sources_probe_parser = sources_subparsers.add_parser("probe", help="Probe source endpoints")
    sources_probe_parser.add_argument('resource', nargs='?', default=None)
    sources_probe_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    sources_probe_parser.add_argument('--timeout', type=float, default=5)
    sources_probe_parser.add_argument('--json', action='store_true')

    capabilities_parser = subparsers.add_parser("capabilities", help=_COMMAND_HELP["capabilities"])
    capabilities_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'http', 'all'], default='all')
    capabilities_parser.add_argument('--backend', default=None, help='Specific backend or source alias to inspect')
    capabilities_parser.add_argument('--json', action='store_true')

    login_parser = subparsers.add_parser("login", help=_COMMAND_HELP["login"])
    login_parser.add_argument('source', choices=['hf', 'ms', 'github', 'kaggle'])
    login_parser.add_argument('--username', help='Kaggle username; stored guidance only, prefer KAGGLE_USERNAME for runtime')
    login_group = login_parser.add_mutually_exclusive_group(required=True)
    login_group.add_argument('--token')
    login_group.add_argument('--stdin', action='store_true', help='Read token from stdin')
    logout_parser = subparsers.add_parser("logout", help=_COMMAND_HELP["logout"])
    logout_parser.add_argument('source', choices=['hf', 'ms', 'github', 'kaggle'])
    whoami_parser = subparsers.add_parser("whoami", help=_COMMAND_HELP["whoami"])
    whoami_parser.add_argument('source', choices=['hf', 'ms', 'github', 'kaggle'])
    whoami_parser.add_argument('--token', default=None)

    lock_parser = subparsers.add_parser("lock", help=_COMMAND_HELP["lock"])
    lock_parser.add_argument('resource', type=str)
    lock_parser.add_argument('--revision', type=str, default=None)
    lock_parser.add_argument('--include', nargs='+', default=None)
    lock_parser.add_argument('--exclude', nargs='+', default=None)
    lock_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    lock_parser.add_argument('--endpoint', default=None)
    lock_parser.add_argument('--output', '-o', default='modely.lock')
    lock_parser.add_argument('--token', default=None)
    lock_parser.add_argument('--alternatives', default=None, help='Comma-separated fallback source list to record in the lockfile')
    lock_parser.add_argument('--strict', action='store_true', help='Fail if lock metadata is not fully reproducible')
    lock_parser.add_argument('--require-checksums', action='store_true', help='Require SHA256 metadata for all selected files')
    lock_parser.add_argument('--json', action='store_true')

    install_parser = subparsers.add_parser("install", help=_COMMAND_HELP["install"])
    install_parser.add_argument('-f', '--file', required=True)
    install_parser.add_argument('--local-dir', default=None)
    install_parser.add_argument('--cache-dir', default=None)
    install_parser.add_argument('--token', default=None)
    install_parser.add_argument('--force-download', action='store_true')
    install_parser.add_argument('--fallback', action='store_true', help='Try alternate sources from lock metadata or --prefer')
    install_parser.add_argument('--prefer', default=None, help='Comma-separated source order for fallback installs')

    validate_lock_parser = subparsers.add_parser("validate-lock", help=_COMMAND_HELP["validate-lock"])
    validate_lock_parser.add_argument('-f', '--file', required=True)
    validate_lock_parser.add_argument('--local-dir', default=None)
    validate_lock_parser.add_argument('--checksum', action='store_true')
    validate_lock_parser.add_argument('--strict', action='store_true', help='Require sizes and checksums to match')
    validate_lock_parser.add_argument('--require-checksums', action='store_true', help='Fail when lock entries lack checksums')
    validate_lock_parser.add_argument('--json', action='store_true')

    catalog_parser = subparsers.add_parser("catalog", help=_COMMAND_HELP["catalog"])
    catalog_subparsers = catalog_parser.add_subparsers(dest="catalog_command")
    catalog_scan_parser = catalog_subparsers.add_parser("scan", help="Scan a local directory or modely cache into a catalog report")
    catalog_scan_parser.add_argument("root", nargs="?", default=None, help="Local root directory to scan")
    catalog_scan_parser.add_argument('--cache', action='store_true', help='Catalog the modely cache instead of a local root')
    catalog_scan_parser.add_argument('--cache-dir', default=None)
    catalog_scan_parser.add_argument('--score', action='store_true', help='Attach score summaries using local analysis by default')
    catalog_scan_parser.add_argument('--scan', action='store_true', help='Attach scan summaries')
    catalog_scan_parser.add_argument('--remote', action='store_true', help='Allow network metadata calls for score/scan enrichment')
    catalog_scan_parser.add_argument('--fail-on', choices=['low', 'medium', 'high'], default=None, help='Policy threshold for attached scan summaries')
    catalog_scan_parser.add_argument('--policy', default=None, help='JSON policy file for scan evaluation')
    catalog_scan_parser.add_argument('--snapshot', action='store_true', help='Save the catalog report as a history snapshot')
    catalog_scan_parser.add_argument('--history-dir', default='.modely/catalog', help='Catalog snapshot directory')
    catalog_scan_parser.add_argument('--token', default=None)
    catalog_scan_parser.add_argument('--endpoint', default=None)
    catalog_scan_parser.add_argument('--output', '-o', default=None, help='Write JSON report to a file')
    catalog_scan_parser.add_argument('--json', action='store_true')
    catalog_diff_parser = catalog_subparsers.add_parser("diff", help="Compare two catalog reports")
    catalog_diff_parser.add_argument("left")
    catalog_diff_parser.add_argument("right")
    catalog_diff_parser.add_argument('--json', action='store_true')
    catalog_export_parser = catalog_subparsers.add_parser("export", help="Export a catalog report")
    catalog_export_parser.add_argument("report")
    catalog_export_parser.add_argument('--format', choices=['csv'], default='csv')
    catalog_export_parser.add_argument('--output', '-o', default=None)
    catalog_history_parser = catalog_subparsers.add_parser("history", help="List catalog snapshots")
    catalog_history_parser.add_argument('--dir', default='.modely/catalog')
    catalog_history_parser.add_argument('--json', action='store_true')
    catalog_gate_parser = catalog_subparsers.add_parser("gate", help="Evaluate a catalog report against scan policy")
    catalog_gate_parser.add_argument("report")
    catalog_gate_parser.add_argument('--fail-on', choices=['low', 'medium', 'high'], default=None)
    catalog_gate_parser.add_argument('--policy', default=None)
    catalog_gate_parser.add_argument('--json', action='store_true')

    label_parser = subparsers.add_parser("label", help=_COMMAND_HELP["label"])
    label_subparsers = label_parser.add_subparsers(dest="label_command")
    label_set_parser = label_subparsers.add_parser("set", help="Set local metadata for a resource")
    label_set_parser.add_argument("resource")
    _add_source_repo_type_args(label_set_parser)
    label_set_parser.add_argument('--tag', action='append', default=None, help='Add a tag; repeatable')
    label_set_parser.add_argument('--remove-tag', action='append', default=None)
    label_set_parser.add_argument('--note', default=None)
    label_set_parser.add_argument('--favorite', action='store_true')
    label_set_parser.add_argument('--unfavorite', action='store_true')
    label_set_parser.add_argument('--status', choices=['candidate', 'evaluating', 'approved', 'production', 'deprecated'], default=None)
    label_set_parser.add_argument('--project', default=None)
    label_set_parser.add_argument('--json', action='store_true')
    label_list_parser = label_subparsers.add_parser("list", help="List saved resource metadata")
    label_list_parser.add_argument('--project', default=None)
    label_list_parser.add_argument('--favorites', action='store_true')
    label_list_parser.add_argument('--json', action='store_true')
    label_export_parser = label_subparsers.add_parser("export", help="Export a project resource set")
    label_export_parser.add_argument("project")
    label_export_parser.add_argument('--output', '-o', default=None)
    label_export_parser.add_argument('--json', action='store_true')

    audit_parser = subparsers.add_parser("audit", help=_COMMAND_HELP["audit"])
    audit_parser.add_argument('--limit', type=int, default=50)
    audit_parser.add_argument('--action', default=None)
    audit_parser.add_argument('--resource', default=None)
    audit_parser.add_argument('--json', action='store_true')

    request_parser = subparsers.add_parser("request", help=_COMMAND_HELP["request"])
    request_parser.add_argument("resource", help="modely URI or asset ID to request access to")
    request_parser.add_argument("--reason", required=True, help="Usage reason (required)")
    request_parser.add_argument("--server", default=None, help="modely-server URL (local API if omitted)")

    approve_parser = subparsers.add_parser("approve", help=_COMMAND_HELP["approve"])
    approve_parser.add_argument("request_id", help="Approval request ID")
    approve_parser.add_argument("--reason", default="Approved", help="Decision reason")
    approve_parser.add_argument("--server", default=None, help="modely-server URL (local API if omitted)")

    reject_parser = subparsers.add_parser("reject", help=_COMMAND_HELP["reject"])
    reject_parser.add_argument("request_id", help="Approval request ID")
    reject_parser.add_argument("--reason", default="Rejected", help="Decision reason")
    reject_parser.add_argument("--server", default=None, help="modely-server URL (local API if omitted)")

    policy_check_parser = subparsers.add_parser("policy-check", help=_COMMAND_HELP["policy-check"])
    policy_check_parser.add_argument("resource", help="modely URI or asset ID to evaluate")
    policy_check_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'auto'], default='auto')
    policy_check_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'tool'], default='auto')
    policy_check_parser.add_argument('--server', default=None, help="modely-server URL (local API if omitted)")
    policy_check_parser.add_argument('--json', action='store_true')

    policy_parser = subparsers.add_parser("policy", help=_COMMAND_HELP["policy"])
    policy_subparsers = policy_parser.add_subparsers(dest="policy_command")
    policy_template_parser = policy_subparsers.add_parser("template", help="Print or write a built-in policy template")
    policy_template_parser.add_argument("name", nargs="?", choices=['permissive', 'balanced', 'strict'], default="balanced")
    policy_template_parser.add_argument('--output', '-o', default=None)
    policy_template_parser.add_argument('--json', action='store_true')

    doctor_parser = subparsers.add_parser("doctor", help=_COMMAND_HELP["doctor"])
    doctor_parser.add_argument("query")
    doctor_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    doctor_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'tool'], default='auto')
    doctor_parser.add_argument('--strategy', choices=['balanced', 'safest', 'fastest', 'freshest'], default='balanced')
    doctor_parser.add_argument('--probe', action='store_true')
    doctor_parser.add_argument('--limit', type=int, default=5)
    doctor_parser.add_argument('--threshold', type=float, default=0.35)
    doctor_parser.add_argument('--token', default=None)
    doctor_parser.add_argument('--endpoint', default=None)
    doctor_parser.add_argument('--json', action='store_true')

    choose_parser = subparsers.add_parser("choose", help=_COMMAND_HELP["choose"])
    choose_parser.add_argument("query")
    choose_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    choose_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'tool'], default='auto')
    choose_parser.add_argument('--strategy', choices=['balanced', 'safest', 'fastest', 'freshest'], default='balanced')
    choose_parser.add_argument('--limit', type=int, default=5)
    choose_parser.add_argument('--threshold', type=float, default=0.35)
    choose_parser.add_argument('--token', default=None)
    choose_parser.add_argument('--endpoint', default=None)
    choose_parser.add_argument('--json', action='store_true')

    mirror_verify_parser = subparsers.add_parser("verify-mirror", help=_COMMAND_HELP["verify-mirror"])
    mirror_verify_parser.add_argument("left")
    mirror_verify_parser.add_argument("right")
    mirror_verify_parser.add_argument('--token', default=None)
    mirror_verify_parser.add_argument('--no-deep', action='store_true')
    mirror_verify_parser.add_argument('--json', action='store_true')

    report_parser = subparsers.add_parser("report", help=_COMMAND_HELP["report"])
    report_parser.add_argument("resource")
    report_parser.add_argument('--format', choices=['markdown', 'html', 'json'], default='markdown')
    report_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    report_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'tool'], default='auto')
    report_parser.add_argument('--output', '-o', default=None)
    # Enterprise compliance report extensions
    report_parser.add_argument('--compliance', action='store_true', help='[enterprise] Generate an enterprise compliance evidence report')
    report_parser.add_argument('--scope', type=str, default=None, metavar="ORG:WS", help='[enterprise] Tenant scope for compliance report (org_id:ws_id)')
    report_parser.add_argument('--sections', type=str, default=None, help='[enterprise] Comma-separated report sections to include')
    report_parser.add_argument('--time-window', type=str, default='30d', help='[enterprise] Time window for compliance report (default: 30d)')
    report_parser.add_argument('--catalog', type=str, default=None, metavar="PATH", help='[enterprise] Local enterprise catalog file')
    report_parser.add_argument('--server', type=str, default=None, metavar="URL", help='[enterprise] Enterprise modely-server API')

    benchmark_parser = subparsers.add_parser("benchmark", help=_COMMAND_HELP["benchmark"])
    benchmark_parser.add_argument("resource", nargs="?", default=None)
    benchmark_parser.add_argument('--source', '--sources', dest='sources', default='all')
    benchmark_parser.add_argument('--url', default=None)
    benchmark_parser.add_argument('--timeout', type=float, default=5)
    benchmark_parser.add_argument('--json', action='store_true')

    batch_parser = subparsers.add_parser("batch-download", help=_COMMAND_HELP["batch-download"])
    batch_parser.add_argument("keyword", nargs="?", default=None)
    batch_parser.add_argument('--tag', action='append', default=None, help='Filter by tag; repeat for AND matching')
    batch_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    batch_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset'], default='auto')
    batch_parser.add_argument('--limit', type=int, default=20, help='Maximum matching resources to download')
    batch_parser.add_argument('--search-limit', type=int, default=None, help='Maximum results to fetch per source before tag filtering')
    batch_parser.add_argument('--task', default=None)
    batch_parser.add_argument('--library', default=None)
    batch_parser.add_argument('--license', default=None)
    batch_parser.add_argument('--sort', choices=['downloads', 'lastModified', 'likes', 'created_at'], default='downloads')
    batch_parser.add_argument('--direction', choices=['asc', 'desc'], default='desc')
    batch_parser.add_argument('--author', default=None)
    batch_parser.add_argument('--after', default=None)
    batch_parser.add_argument('--before', default=None)
    batch_parser.add_argument('--full', action='store_true')
    batch_parser.add_argument('--local-dir', default=None)
    batch_parser.add_argument('--cache-dir', default=None)
    batch_parser.add_argument('--token', default=None)
    batch_parser.add_argument('--include', nargs='+', default=None)
    batch_parser.add_argument('--exclude', nargs='+', default=None)
    batch_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    batch_parser.add_argument('--prefer', default='default')
    batch_parser.add_argument('--fallback', action='store_true')
    batch_parser.add_argument('--force-download', action='store_true')
    batch_parser.add_argument('--backend', default='auto', help='Backend preference or registered backend name')
    batch_parser.add_argument('--with-lfs', action='store_true')
    batch_parser.add_argument('--endpoint', default=None)
    batch_parser.add_argument('--max-workers', type=int, default=None)
    batch_parser.add_argument('--timeout', type=float, default=None)
    batch_parser.add_argument('--retries', type=int, default=None)
    batch_parser.add_argument('--checksum', action='store_true')
    batch_parser.add_argument('--no-resume', action='store_true')
    batch_parser.add_argument('--fail-fast', action='store_true')
    batch_parser.add_argument('--yes', action='store_true', help='Execute downloads instead of dry-run')
    batch_parser.add_argument('--json', action='store_true')

    sync_parser = subparsers.add_parser("sync", help=_COMMAND_HELP["sync"])
    mirror_parser = subparsers.add_parser("mirror", help=_COMMAND_HELP["mirror"])
    for p in (sync_parser, mirror_parser):
        p.add_argument('resource', type=str)
        p.add_argument('--local-dir', required=True)
        p.add_argument('--revision', type=str, default=None)
        p.add_argument('--include', nargs='+', default=None)
        p.add_argument('--exclude', nargs='+', default=None)
        p.add_argument('--token', default=None)
        p.add_argument('--cache-dir', default=None)
        p.add_argument('--manifest', default=None)
        p.add_argument('--checksum', action='store_true')
        p.add_argument('--force-download', action='store_true')
        p.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'auto'], default='auto')
        p.add_argument('--prefer', default='default')
        p.add_argument('--profile', choices=list(PROFILES), default=None)
        p.add_argument('--report', default=None, help='Write a JSON sync/mirror report')
        p.add_argument('--analyze', action='store_true', help='Include remote asset analysis in the report')
        p.add_argument('--compare-to', default=None, help='Compare the synced resource to another modely URI in the report')
        p.add_argument('--deep', action='store_true', help='Use deep analysis for report analysis/comparison')

    _configure_sync_center_parser(subparsers)

    # Watch subcommand
    watch_parser = subparsers.add_parser("watch", help=_COMMAND_HELP["watch"])
    configure_watch_parser(watch_parser)

    # Resolve subcommand
    resolve_parser = subparsers.add_parser("resolve", help=_COMMAND_HELP["resolve"])
    resolve_parser.add_argument("query", type=str, help="Model/dataset name or modely URI to resolve")
    resolve_parser.add_argument(
        "--source", "-s", choices=["hf", "ms", "github", "kaggle", "all"], default="all",
        help="Platform to search (default: all)",
    )
    resolve_parser.add_argument(
        "--repo-type", "-t", choices=["auto", "model", "dataset", "tool"], default="auto",
        help="Type of repository (default: auto)",
    )
    resolve_parser.add_argument("--task", default=None, help="Filter by task type")
    resolve_parser.add_argument("--library", default=None, help="Filter by library where supported")
    resolve_parser.add_argument("--license", default=None, help="Filter by license where supported")
    resolve_parser.add_argument("--limit", "-n", type=int, default=10, help="Max results per source")
    resolve_parser.add_argument("--threshold", type=float, default=0.35, help="Minimum confidence to include")
    resolve_parser.add_argument("--full", action="store_true", help="Request richer backend metadata where supported")
    resolve_parser.add_argument("--json", action="store_true", help="Output result as JSON")

    # Search subcommand
    search_parser = subparsers.add_parser("search", help=_COMMAND_HELP["search"])
    search_parser.add_argument("keyword", type=str, nargs="?", default=None, help="Search keyword for model/dataset name")
    search_parser.add_argument(
        "--source", "-s", choices=["hf", "ms", "github", "kaggle", "all"], default="all",
        help="Platform to search (default: all)",
    )
    search_parser.add_argument(
        "--repo-type", "-t", choices=["auto", "model", "dataset", "tool"], default="auto",
        help="Type of repository (default: auto)",
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
    search_parser.add_argument(
        "--dedupe", action="store_true",
        help="Group search results by normalized repository name",
    )
    search_parser.add_argument(
        "--compare", action="store_true",
        help="Show grouped search-result comparison rows",
    )

    search_parser.add_argument(
        "--catalog", type=str, default=None, metavar="PATH",
        help="[enterprise] Search a local enterprise catalog file instead of external sources",
    )
    search_parser.add_argument(
        "--server", type=str, default=None, metavar="URL",
        help="[enterprise] Search an enterprise modely-server API",
    )

    # ---- enterprise: asset ------------------------------------------------------
    asset_parser = subparsers.add_parser("asset", help=_COMMAND_HELP["asset"])
    asset_subparsers = asset_parser.add_subparsers(dest="asset_command")
    asset_search_parser = asset_subparsers.add_parser("search", help="Search enterprise catalog assets")
    asset_search_parser.add_argument("query", nargs="?", default="")
    asset_search_parser.add_argument("--source", default=None)
    asset_search_parser.add_argument("--repo-type", default=None)
    asset_search_parser.add_argument("--limit", type=int, default=20)
    asset_search_parser.add_argument("--server", default=None)
    asset_search_parser.add_argument("--json", action="store_true")
    asset_detail_parser = asset_subparsers.add_parser("detail", help="Show enterprise asset detail")
    asset_detail_parser.add_argument("asset_id", help="Enterprise asset ID")
    asset_detail_parser.add_argument("--server", default=None)
    asset_detail_parser.add_argument("--json", action="store_true")
    asset_dl_parser = asset_subparsers.add_parser("download-url", help="Get download URL for an enterprise asset")
    asset_dl_parser.add_argument("asset_id", help="Enterprise asset ID")
    asset_dl_parser.add_argument("--server", default=None)
    asset_dl_parser.add_argument("--json", action="store_true")

    # ---- enterprise: recommend -----------------------------------------------
    recommend_parser = subparsers.add_parser("recommend", help=_COMMAND_HELP["recommend"])
    recommend_parser.add_argument("asset_id", type=str, help="Enterprise asset ID to find recommendations for")
    recommend_parser.add_argument("--top", type=int, default=5, help="Number of recommendations (default: 5)")
    recommend_parser.add_argument("--min-confidence", type=float, default=0.3, help="Minimum confidence threshold (default: 0.3)")
    recommend_parser.add_argument("--catalog", type=str, default=None, metavar="PATH", help="Local enterprise catalog file")
    recommend_parser.add_argument("--server", type=str, default=None, metavar="URL", help="Enterprise modely-server API")
    recommend_parser.add_argument("--format", choices=["table", "json", "markdown"], default="table", help="Output format (default: table)")

    # ---- enterprise: alternatives --------------------------------------------
    alt_parser = subparsers.add_parser("alternatives", help=_COMMAND_HELP["alternatives"])
    alt_parser.add_argument("asset_id", type=str, help="Enterprise asset ID to find alternatives for")
    alt_parser.add_argument("--top", type=int, default=5, help="Number of alternatives (default: 5)")
    alt_parser.add_argument("--all", action="store_true", help="Show alternatives even for allowed assets")
    alt_parser.add_argument("--catalog", type=str, default=None, metavar="PATH", help="Local enterprise catalog file")
    alt_parser.add_argument("--server", type=str, default=None, metavar="URL", help="Enterprise modely-server API")
    alt_parser.add_argument("--format", choices=["table", "json", "markdown"], default="table", help="Output format (default: table)")

    # ---- enterprise: graph ---------------------------------------------------
    graph_parser = subparsers.add_parser("graph", help=_COMMAND_HELP["graph"])
    graph_sub = graph_parser.add_subparsers(dest="graph_command", help="Graph subcommands")
    graph_asset_parser = graph_sub.add_parser("asset", help="Show asset relationship graph")
    graph_asset_parser.add_argument("asset_id", type=str, help="Enterprise asset ID")
    graph_asset_parser.add_argument("--max-depth", type=int, default=3, help="Maximum traversal depth (default: 3)")
    graph_asset_parser.add_argument("--include-types", type=str, default=None, help="Comma-separated node types to include")
    graph_asset_parser.add_argument("--direction", choices=["outgoing", "incoming", "both"], default="outgoing")
    graph_asset_parser.add_argument("--catalog", type=str, default=None, metavar="PATH", help="Local enterprise catalog file")
    graph_asset_parser.add_argument("--server", type=str, default=None, metavar="URL", help="Enterprise modely-server API")
    graph_asset_parser.add_argument("--format", choices=["summary", "json", "d3"], default="summary", help="Output format (default: summary)")

    # ---- enterprise: catalog-gate --------------------------------------------
    gate_parser = subparsers.add_parser("catalog-gate", help=_COMMAND_HELP["catalog-gate"])
    gate_parser.add_argument("resource", type=str, help="Resource URI or asset ID")
    gate_parser.add_argument("--catalog", type=str, default=None, metavar="PATH", help="Local enterprise catalog file")
    gate_parser.add_argument("--server", type=str, default=None, metavar="URL", help="Enterprise modely-server API")
    gate_parser.add_argument("--profile", type=str, default="production", help="Policy profile (default: production)")
    gate_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json)")

    # ---- enterprise: snapshot --------------------------------------------------
    snap_parser = subparsers.add_parser("snapshot", help=_COMMAND_HELP["snapshot"])
    snap_sub = snap_parser.add_subparsers(dest="snapshot_command", help="Snapshot subcommands")
    snap_list_p = snap_sub.add_parser("list", help="List approved snapshots")
    snap_list_p.add_argument("--asset-id", type=str, default=None, help="Filter by asset ID")
    snap_list_p.add_argument("--server", type=str, default=None, metavar="URL")
    snap_promote_p = snap_sub.add_parser("promote", help="Promote a snapshot to channel")
    snap_promote_p.add_argument("snapshot_id", type=str, help="Snapshot ID to promote")
    snap_promote_p.add_argument("--channel", type=str, default="production")
    snap_promote_p.add_argument("--server", type=str, default=None, metavar="URL")
    snap_rollback_p = snap_sub.add_parser("rollback", help="Rollback a channel")
    snap_rollback_p.add_argument("snapshot_id", type=str, help="Snapshot ID to rollback")
    snap_rollback_p.add_argument("--reason", type=str, default="")
    snap_rollback_p.add_argument("--server", type=str, default=None, metavar="URL")

    # ---- enterprise: manifest-diff ---------------------------------------------
    md_parser = subparsers.add_parser("manifest-diff", help=_COMMAND_HELP["manifest-diff"])
    md_parser.add_argument("left", type=str, help="Left manifest path or version ID")
    md_parser.add_argument("right", type=str, help="Right manifest path or version ID")
    md_parser.add_argument("--format", choices=["json", "summary"], default="json")

    # ---- enterprise: resolve-approved ------------------------------------------
    ra_parser = subparsers.add_parser("resolve-approved", help=_COMMAND_HELP["resolve-approved"])
    ra_parser.add_argument("asset_id", type=str, help="Enterprise asset ID")
    ra_parser.add_argument("--channel", type=str, default="production")
    ra_parser.add_argument("--server", type=str, default=None, metavar="URL")
    ra_parser.add_argument("--format", choices=["json", "summary"], default="json")

    # ---- enterprise: install-approved ------------------------------------------
    ia_parser = subparsers.add_parser("install-approved", help=_COMMAND_HELP["install-approved"])
    ia_parser.add_argument("asset_id", type=str, help="Enterprise asset ID")
    ia_parser.add_argument("--destination", type=str, default=".", help="Install destination directory")
    ia_parser.add_argument("--channel", type=str, default="production")
    ia_parser.add_argument("--server", type=str, default=None, metavar="URL")

    # ---- enterprise: token-create ----------------------------------------------
    tc_parser = subparsers.add_parser("token-create", help=_COMMAND_HELP["token-create"])
    tc_parser.add_argument("--service-account-id", type=str, required=True, help="Service account ID")
    tc_parser.add_argument("--scopes", type=str, default="asset:read", help="Comma-separated permission scopes")
    tc_parser.add_argument("--expires-in-days", type=int, default=90)
    tc_parser.add_argument("--server", type=str, default=None, metavar="URL")

    # ---- enterprise: token-rotate ----------------------------------------------
    tr_parser = subparsers.add_parser("token-rotate", help=_COMMAND_HELP["token-rotate"])
    tr_parser.add_argument("token_id", type=str, help="Token ID to rotate")
    tr_parser.add_argument("--grace-period", type=int, default=0, help="Grace period in seconds for old token")
    tr_parser.add_argument("--server", type=str, default=None, metavar="URL")

    # ---- enterprise: token-revoke ----------------------------------------------
    tv_parser = subparsers.add_parser("token-revoke", help=_COMMAND_HELP["token-revoke"])
    tv_parser.add_argument("token_id", type=str, help="Token ID to revoke")
    tv_parser.add_argument("--server", type=str, default=None, metavar="URL")

    return parser
