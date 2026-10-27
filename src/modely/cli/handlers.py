"""Command handlers for the modely CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

from .. import presenters
from ..application import queries as query_services
from ..application import sync_center as sync_center_services
from ..modelscope import (
    model_file_download,
    dataset_file_download,
    snapshot_download as modelscope_snapshot_download,
    HubApi,
)
from ..hf import hf_file_download, snapshot_download as hf_snapshot_download
from ..github import github_file_download, snapshot_download as github_snapshot_download
from ..search import main as search_main
from ..auth import delete_token, save_token, whoami
from ..audit import list_audit_events, print_audit_events
from ..backends import get_backend_capabilities, list_backends, print_backend_capabilities
from ..analyze import analyze_resource, print_asset_analysis
from ..card import get_card, print_card
from ..compare import compare_resources, print_comparison
from ..compare_many import compare_many_resources, print_many_comparison
from ..detail import get_resource_detail, print_resource_detail
from ..files import do_dry_run, format_file_size, list_repo_files, print_file_list, print_file_tree
from ..get import download_resource
from ..info import get_repo_info, print_repo_info, resolve_repo_ref
from ..labels import (
    export_project,
    list_asset_metadata,
    print_asset_metadata,
    print_project_export,
    update_asset_record,
)
from ..license import license_risk, print_license_risk
from ..manifest import create_download_manifest, create_lock, install_lock, print_lock_validation, validate_lock
from ..mirror import print_mirror_verification, verify_mirror
from ..doctor import doctor_resource, print_doctor_report
from ..choose import choose_resource, print_choice
from ..report import create_resource_report
from ..benchmark import benchmark_sources, print_benchmark_results
from ..batch import create_batch_download_plan, print_batch_download_result, run_batch_download
from ..plan import create_download_plan, print_download_plan
from ..profiles import resolve_download_profile
from ..sources import list_source_profiles, print_probe_results, print_source_profiles, rank_sources
from ..resolve import print_resolve_result, resolve_resource
from ..policy import (
    evaluate_catalog_policy,
    evaluate_scan_policy,
    load_policy,
    print_catalog_policy_result,
    write_policy_template,
)
from ..scan import print_scan_result, scan_path, scan_resource
from ..score import print_asset_score, score_path, score_resource
from ..sync import sync_resource
from ..catalog import (
    diff_catalogs,
    export_catalog,
    list_catalog_snapshots,
    print_catalog_diff,
    print_catalog_report,
    read_catalog_report,
    scan_catalog,
    snapshot_catalog,
    write_catalog_report,
)
from ..uri import concrete_repo_type, parse_modely_uri
from ..version import diff_resource_revisions, print_revision_diff
from ..common import cache
from ..cache_web import serve_cache_browser


def handle_sync_center(args):
    """Dispatch sync-center subcommands."""
    try:
        command = args.sync_center_command
        if command == "add":
            report = sync_center_services.add_sync_target(
                resource=args.resource,
                id=args.id,
                local_dir=args.local_dir,
                source=args.source,
                repo_type=args.repo_type,
                revision=args.revision,
                include=args.include,
                exclude=args.exclude,
                profile=args.profile,
                prefer=args.prefer,
                cache_dir=args.cache_dir,
                token_env=args.token_env,
                checksum=args.checksum,
                force_download=args.force_download,
                manifest=args.manifest,
                report=args.report,
                labels=args.label,
            )
            presenters.present_sync_targets(report, as_json=args.json)
        elif command == "list":
            presenters.present_sync_targets(sync_center_services.list_sync_targets(), as_json=args.json)
        elif command == "show":
            presenters.present_sync_targets(sync_center_services.show_sync_target(args.target_id), as_json=args.json)
        elif command == "remove":
            presenters.present_sync_targets(sync_center_services.remove_sync_target(args.target_id), as_json=args.json)
        elif command == "enable":
            presenters.present_sync_targets(sync_center_services.set_sync_target_enabled(args.target_id, True), as_json=args.json)
        elif command == "disable":
            presenters.present_sync_targets(sync_center_services.set_sync_target_enabled(args.target_id, False), as_json=args.json)
        elif command == "plan":
            report = sync_center_services.plan_sync_targets(target_id=args.target_id, all=args.all, token=args.token)
            presenters.present_sync_plan(report, as_json=args.json)
            if report.summary.get("errors"):
                sys.exit(1)
        elif command == "run":
            report = sync_center_services.run_sync_targets(
                target_id=args.target_id,
                all=args.all,
                token=args.token,
                force_download=args.force_download,
                checksum=args.checksum,
            )
            presenters.present_sync_runs(report, as_json=args.json)
            if report.summary.get("errors"):
                sys.exit(1)
        elif command == "check":
            report = sync_center_services.check_sync_targets(target_id=args.target_id, all=args.all)
            presenters.present_sync_check(report, as_json=args.json)
            if report.summary.get("errors"):
                sys.exit(1)
        elif command == "runs":
            presenters.present_sync_runs(
                sync_center_services.list_sync_runs(target_id=args.target_id, limit=args.limit),
                as_json=args.json,
            )
        elif command == "catalog":
            presenters.present_sync_catalog(
                sync_center_services.catalog_sync_targets(output=args.output, snapshot=args.snapshot),
                as_json=args.json,
            )
        else:
            print("Usage: modely sync-center [add|list|show|remove|enable|disable|plan|run|check|runs|catalog]")
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def _list_hf_files(repo_id, repo_type, revision, token, endpoint):
    """Fetch file listing from Hugging Face Hub."""
    from ..hf import list_files
    try:
        files = list_files(repo_id, repo_type=repo_type, revision=revision, token=token, endpoint=endpoint)
        return [f.to_dict() | {"Path": f.path, "Size": f.size, "Type": f.type} for f in files]
    except Exception as e:
        print(f"Warning: Could not list files from HF: {e}", file=sys.stderr)
        return []


def _list_ms_files(repo_id, repo_type, revision, token):
    """Fetch file listing from ModelScope."""
    from ..modelscope import HubApi
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

def dispatch(args, parser=None):
        if args.command == "ms":
            try:
                repo_type = concrete_repo_type(args.repo_type, "ms")
                # Set ModelScope endpoint if provided
                if getattr(args, 'endpoint', None):
                    os.environ['MODELSCOPE_ENDPOINT'] = args.endpoint

                # --list-files: show remote file listing
                if getattr(args, 'list_files', False):
                    files = _list_ms_files(args.repo_id, repo_type, args.revision, args.token)
                    print_file_list(files, "ms", args.repo_id)
                    return

                # --dry-run: preview what would be downloaded
                if getattr(args, 'dry_run', False):
                    files = _list_ms_files(args.repo_id, repo_type, args.revision, args.token)
                    do_dry_run("ms", args.repo_id, repo_type, args.revision,
                                args.include, args.exclude, files)
                    return

                if args.file:
                    # Download a specific file
                    if repo_type == 'model':
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
                        repo_type=repo_type,
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
                repo_type = concrete_repo_type(args.repo_type, "hf")
                # Set HF endpoint if provided
                if getattr(args, 'endpoint', None):
                    os.environ['HF_ENDPOINT'] = args.endpoint

                # --list-files: show remote file listing
                if getattr(args, 'list_files', False):
                    files = _list_hf_files(args.repo_id, repo_type, args.revision, args.token, args.endpoint)
                    print_file_list(files, "hf", args.repo_id)
                    return

                # --dry-run: preview what would be downloaded
                if getattr(args, 'dry_run', False):
                    files = _list_hf_files(args.repo_id, repo_type, args.revision, args.token, args.endpoint)
                    do_dry_run("hf", args.repo_id, repo_type, args.revision,
                                args.include, args.exclude, files)
                    return

                if args.file:
                    # Download a specific file
                    result = hf_file_download(
                        repo_id=args.repo_id,
                        filename=args.file,
                        repo_type=repo_type,
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
                        repo_type=repo_type,
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
                if getattr(args, 'asset', None):
                    from ..github import github_release_asset_download
                    result = github_release_asset_download(
                        args.repo_id,
                        args.asset,
                        release=args.release,
                        cache_dir=args.cache_dir,
                        local_dir=args.local_dir,
                        token=args.token,
                        force_download=args.force_download,
                    )
                    print(f"Successfully downloaded release asset to: {result}")
                elif args.file:
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
                        force_download=args.force_download,
                        allow_patterns=args.include,
                        ignore_patterns=args.exclude,
                        submodules=args.submodules,
                    )
                    # github_clone() prints its own messages
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "info":
            try:
                info = get_repo_info(args.resource, revision=args.revision, token=args.token, endpoint=args.endpoint,
                                     source=args.source, repo_type=args.repo_type)
                print_repo_info(info, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "files":
            try:
                include, exclude = resolve_download_profile(args.profile, args.include, args.exclude)
                if args.release:
                    ref = parse_modely_uri(args.resource, source=args.source, repo_type=args.repo_type)
                else:
                    ref = resolve_repo_ref(args.resource, revision=args.revision, token=args.token, endpoint=args.endpoint,
                                           source=args.source, repo_type=args.repo_type)
                files = list_repo_files(ref, revision=args.revision, token=args.token, endpoint=args.endpoint,
                                        release=args.release)
                from ..files import filter_files
                files = filter_files(files, include, exclude)
                if args.tree:
                    print_file_tree(files, as_json=args.json)
                else:
                    print_file_list(files, ref.source, ref.repo_id, as_json=args.json, summary=args.summary)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "plan":
            try:
                plan = create_download_plan(args.resource, source=args.source, repo_type=args.repo_type,
                                            revision=args.revision, include=args.include, exclude=args.exclude,
                                            profile=args.profile, token=args.token, endpoint=args.endpoint,
                                            cache_dir=args.cache_dir, local_dir=args.local_dir, release=args.release)
                print_download_plan(plan, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "card":
            try:
                card = get_card(args.resource, revision=args.revision, token=args.token, endpoint=args.endpoint,
                                source=args.source, repo_type=args.repo_type)
                print_card(card, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "detail":
            try:
                detail = get_resource_detail(args.resource, revision=args.revision, token=args.token,
                                             endpoint=args.endpoint, include=args.include, exclude=args.exclude,
                                             profile=args.profile, deep=args.deep,
                                             source=args.source, repo_type=args.repo_type)
                print_resource_detail(detail, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "analyze":
            try:
                analysis = analyze_resource(args.resource, revision=args.revision, token=args.token,
                                            endpoint=args.endpoint, include=args.include, exclude=args.exclude,
                                            profile=args.profile, top_files=args.top_files, deep=args.deep,
                                            source=args.source, repo_type=args.repo_type)
                print_asset_analysis(analysis, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "score":
            # Enterprise admission scoring (--catalog or --server)
            if getattr(args, "catalog", None) or getattr(args, "server", None):
                try:
                    from ..application.intelligence_queries import get_admission_score
                    result = get_admission_score(
                        args.resource,
                        profile_override=getattr(args, "scoring_profile", None),
                    )
                    if args.json:
                        print(json.dumps(result, indent=2, ensure_ascii=False))
                    else:
                        _print_admission_score_table(result)
                except Exception as e:
                    print(f"Error: {e}")
                    sys.exit(1)
                return
            try:
                if args.local or (os.path.exists(args.resource) and "://" not in args.resource):
                    result = score_path(args.resource, deep=not args.no_deep)
                else:
                    result = score_resource(args.resource, revision=args.revision, token=args.token,
                                            endpoint=args.endpoint, include=args.include, exclude=args.exclude,
                                            profile=args.profile, deep=not args.no_deep,
                                            source=args.source, repo_type=args.repo_type)
                print_asset_score(result, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "scan":
            try:
                if args.local or (os.path.exists(args.resource) and "://" not in args.resource):
                    result = scan_path(args.resource, deep=not args.no_deep)
                else:
                    result = scan_resource(args.resource, revision=args.revision, token=args.token,
                                           endpoint=args.endpoint, include=args.include, exclude=args.exclude,
                                           profile=args.profile, deep=not args.no_deep, inspect_files=args.inspect_files,
                                           source=args.source, repo_type=args.repo_type)
                policy_result = evaluate_scan_policy(result, fail_on=args.fail_on, policy=load_policy(args.policy)) if (args.fail_on or args.policy) else None
                if policy_result:
                    result.metadata["policy"] = policy_result
                print_scan_result(result, as_json=args.json)
                if policy_result and not policy_result["ok"]:
                    sys.exit(1)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "license":
            try:
                print_license_risk(license_risk(args.resource, revision=args.revision, token=args.token,
                                                endpoint=args.endpoint, source=args.source, repo_type=args.repo_type),
                                   as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "compare":
            try:
                result = compare_resources(args.left, args.right, revision_left=args.revision_left,
                                           revision_right=args.revision_right, token=args.token,
                                           include_files=args.files, include_card=args.card,
                                           include_formats=args.formats, deep=args.deep)
                print_comparison(result, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "compare-many":
            try:
                result = compare_many_resources(args.resources, revision=args.revision, token=args.token,
                                                endpoint=args.endpoint, include=args.include, exclude=args.exclude,
                                                profile=args.profile, deep=args.deep,
                                                source=args.source, repo_type=args.repo_type)
                print_many_comparison(result, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "version-diff":
            try:
                result = diff_resource_revisions(args.resource, left_revision=args.left_revision, right_revision=args.right_revision,
                                                 token=args.token, endpoint=args.endpoint, source=args.source, repo_type=args.repo_type)
                print_revision_diff(result, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "get":
            try:
                resource_parts = list(args.resource)
                if len(resource_parts) == 2 and resource_parts[0] in {"hf", "ms", "github", "kaggle"} and args.source == "auto":
                    args.source, resource = resource_parts
                elif len(resource_parts) == 1:
                    resource = resource_parts[0]
                else:
                    raise ValueError("Usage: modely get [--source SOURCE] RESOURCE or modely get SOURCE RESOURCE")
                if args.dry_run:
                    plan = create_download_plan(resource, source=args.source, repo_type=args.repo_type,
                                                revision=args.revision, include=args.include, exclude=args.exclude,
                                                profile=args.profile, token=args.token, endpoint=args.endpoint,
                                                cache_dir=args.cache_dir, local_dir=args.local_dir)
                    print_download_plan(plan, as_json=args.json)
                    return
                result = download_resource(
                    resource,
                    source=args.source,
                    repo_type=args.repo_type,
                    revision=args.revision,
                    file=args.file,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    include=args.include,
                    exclude=args.exclude,
                    prefer=args.prefer,
                    fallback=args.fallback,
                    force_download=args.force_download,
                    backend=args.backend,
                    with_lfs=args.with_lfs,
                    profile=args.profile,
                    endpoint=args.endpoint,
                    max_workers=args.max_workers,
                    timeout=args.timeout,
                    retries=args.retries,
                    checksum=args.checksum,
                    resume=not args.no_resume,
                )
                if args.manifest:
                    create_download_manifest(resource if "://" in resource else f"hf://models/{resource}", result,
                                             include=args.include, exclude=args.exclude,
                                             checksum=args.checksum, output=args.manifest)
                print(f"Downloaded to: {result}")
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "sources":
            try:
                if args.sources_command == "list":
                    print_source_profiles(list_source_profiles(args.source), as_json=args.json)
                elif args.sources_command == "probe":
                    candidates = None if args.source == "all" else [args.source]
                    print_probe_results(rank_sources(args.resource, candidates=candidates, timeout=args.timeout), as_json=args.json)
                else:
                    print("Usage: modely sources [list|probe]")
                    sys.exit(1)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "capabilities":
            try:
                if args.backend:
                    items = get_backend_capabilities(args.backend)
                else:
                    items = list_backends()
                    if args.source != "all":
                        items = [item for item in items if item.source == args.source]
                print_backend_capabilities(items, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "login":
            token = sys.stdin.read().strip() if args.stdin else args.token
            if not token:
                print("Error: token is empty")
                sys.exit(1)
            save_token(args.source, token)
            if args.source == "kaggle":
                if getattr(args, "username", None):
                    config = cache._load_config()
                    config["kaggle_username"] = args.username
                    cache._save_config(config)
                    print("Kaggle credentials saved")
                elif not os.environ.get("KAGGLE_USERNAME"):
                    print("Kaggle key saved. Set KAGGLE_USERNAME or configure ~/.kaggle/kaggle.json for Kaggle API authentication.")
                else:
                    print("Kaggle key saved")
            else:
                print(f"Token saved for {args.source}")
        elif args.command == "logout":
            removed = delete_token(args.source)
            print(f"Token removed for {args.source}" if removed else f"No stored token for {args.source}")
        elif args.command == "whoami":
            print(whoami(args.source, args.token))
        elif args.command == "lock":
            try:
                manifest = create_lock(args.resource, revision=args.revision, include=args.include,
                                       exclude=args.exclude, output=args.output, token=args.token,
                                       profile=args.profile, endpoint=args.endpoint, alternatives=args.alternatives,
                                       strict=args.strict, require_checksums=args.require_checksums)
                if args.json:
                    print(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))
                else:
                    print(f"Wrote lockfile to: {args.output} ({len(manifest.files)} file(s))")
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "install":
            try:
                result = install_lock(args.file, local_dir=args.local_dir, cache_dir=args.cache_dir,
                                      token=args.token, force_download=args.force_download,
                                      fallback=args.fallback, prefer=args.prefer)
                print(f"Installed to: {result}")
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "validate-lock":
            try:
                result = validate_lock(args.file, local_dir=args.local_dir, checksum=args.checksum,
                                       strict=args.strict, require_checksums=args.require_checksums)
                print_lock_validation(result, as_json=args.json)
                if not result["ok"]:
                    sys.exit(1)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "catalog":
            try:
                if args.catalog_command == "scan":
                    report = scan_catalog(args.root, cache_dir=args.cache_dir, from_cache=args.cache,
                                          include_scores=args.score, include_scan=args.scan,
                                          use_remote=args.remote, token=args.token, endpoint=args.endpoint)
                    if args.scan and (args.fail_on or args.policy):
                        policy = load_policy(args.policy)
                        failed = False
                        for entry in report.entries:
                            if entry.scan and entry.local_path and not args.remote:
                                scan_result = scan_path(entry.local_path)
                                policy_result = evaluate_scan_policy(scan_result, fail_on=args.fail_on, policy=policy)
                                entry.scan["policy"] = policy_result
                                failed = failed or not policy_result["ok"]
                        report.metadata["policy_failed"] = failed
                    else:
                        failed = False
                    if args.snapshot:
                        report.metadata["snapshot"] = snapshot_catalog(report, history_dir=args.history_dir)
                    if args.output:
                        write_catalog_report(report, args.output)
                    print_catalog_report(report, as_json=args.json)
                    if failed:
                        sys.exit(1)
                elif args.catalog_command == "diff":
                    print_catalog_diff(diff_catalogs(read_catalog_report(args.left), read_catalog_report(args.right)), as_json=args.json)
                elif args.catalog_command == "export":
                    exported = export_catalog(read_catalog_report(args.report), format=args.format)
                    if args.output:
                        with open(args.output, "w") as f:
                            f.write(exported)
                    else:
                        print(exported, end="")
                elif args.catalog_command == "history":
                    snapshots = list_catalog_snapshots(args.dir)
                    if args.json:
                        print(json.dumps(snapshots, indent=2, ensure_ascii=False))
                    else:
                        if snapshots:
                            for item in snapshots:
                                print(f"{item['path']} ({item['size']} bytes)")
                        else:
                            print("No catalog snapshots found.")
                elif args.catalog_command == "gate":
                    result = evaluate_catalog_policy(read_catalog_report(args.report), fail_on=args.fail_on, policy=load_policy(args.policy))
                    print_catalog_policy_result(result, as_json=args.json)
                    if not result["ok"]:
                        sys.exit(1)
                else:
                    print("Usage: modely catalog [scan|diff|export|history]")
                    sys.exit(1)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "label":
            try:
                if args.label_command == "set":
                    favorite = None
                    if args.favorite:
                        favorite = True
                    if args.unfavorite:
                        favorite = False
                    record = update_asset_record(args.resource, source=args.source, repo_type=args.repo_type,
                                                 add_tags=args.tag, remove_tags=args.remove_tag, note=args.note,
                                                 favorite=favorite, status=args.status, project=args.project)
                    print_asset_metadata({"resources": {args.resource: record}, "projects": {}}, as_json=args.json)
                elif args.label_command == "list":
                    print_asset_metadata(list_asset_metadata(project=args.project, favorites=args.favorites), as_json=args.json)
                elif args.label_command == "export":
                    payload = export_project(args.project)
                    if args.output:
                        with open(args.output, "w") as f:
                            json.dump(payload, f, indent=2, ensure_ascii=False)
                        print(f"Wrote project export to: {args.output}")
                    else:
                        print_project_export(payload, as_json=args.json)
                else:
                    print("Usage: modely label [set|list]")
                    sys.exit(1)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "audit":
            try:
                print_audit_events(list_audit_events(limit=args.limit, action=args.action, resource=args.resource), as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "request":
            _handle_request(args)
        elif args.command == "approve":
            _handle_approve(args)
        elif args.command == "reject":
            _handle_reject(args)
        elif args.command == "policy-check":
            _handle_policy_check(args)
        elif args.command == "policy":
            try:
                if args.policy_command == "template":
                    template = write_policy_template(args.name, args.output)
                    if args.output:
                        print(f"Wrote policy template to: {args.output}")
                    else:
                        print(json.dumps(template, indent=2, ensure_ascii=False))
                else:
                    print("Usage: modely policy template [permissive|balanced|strict]")
                    sys.exit(1)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "doctor":
            try:
                print_doctor_report(doctor_resource(args.query, source=args.source, repo_type=args.repo_type,
                                                    strategy=args.strategy, probe=args.probe, limit=args.limit, threshold=args.threshold,
                                                    token=args.token, endpoint=args.endpoint), as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "choose":
            try:
                print_choice(choose_resource(args.query, source=args.source, repo_type=args.repo_type,
                                             strategy=args.strategy, limit=args.limit, threshold=args.threshold,
                                             token=args.token, endpoint=args.endpoint), as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "verify-mirror":
            try:
                print_mirror_verification(verify_mirror(args.left, args.right, token=args.token, deep=not args.no_deep), as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "report":
            # Enterprise compliance report
            if getattr(args, "compliance", False):
                _handle_compliance_report(args)
                return
            try:
                text = create_resource_report(args.resource, format=args.format, source=args.source, repo_type=args.repo_type)
                if args.output:
                    with open(args.output, "w") as f:
                        f.write(text)
                else:
                    print(text, end="")
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "benchmark":
            try:
                candidates = None if args.sources == "all" else [s.strip() for s in args.sources.split(",") if s.strip()]
                print_benchmark_results(benchmark_sources(args.resource, candidates=candidates, url=args.url, timeout=args.timeout), as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "batch-download":
            try:
                plan = create_batch_download_plan(
                    args.keyword,
                    source=args.source,
                    repo_type=args.repo_type,
                    tags=args.tag,
                    limit=args.limit,
                    search_limit=args.search_limit,
                    task=args.task,
                    library=args.library,
                    license=args.license,
                    sort=args.sort,
                    direction=args.direction,
                    author=args.author,
                    after=args.after,
                    before=args.before,
                    full=args.full,
                )
                if args.yes:
                    result = run_batch_download(
                        plan,
                        local_dir=args.local_dir,
                        cache_dir=args.cache_dir,
                        token=args.token,
                        include=args.include,
                        exclude=args.exclude,
                        profile=args.profile,
                        prefer=args.prefer,
                        fallback=args.fallback,
                        force_download=args.force_download,
                        backend=args.backend,
                        with_lfs=args.with_lfs,
                        endpoint=args.endpoint,
                        max_workers=args.max_workers,
                        timeout=args.timeout,
                        retries=args.retries,
                        checksum=args.checksum,
                        resume=not args.no_resume,
                        fail_fast=args.fail_fast,
                    )
                    print_batch_download_result(result, as_json=args.json)
                    if not result["ok"]:
                        sys.exit(1)
                else:
                    print_batch_download_result(plan, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command in {"sync", "mirror"}:
            try:
                result = sync_resource(args.resource, local_dir=args.local_dir, revision=args.revision,
                                       include=args.include, exclude=args.exclude, token=args.token,
                                       cache_dir=args.cache_dir, manifest=args.manifest,
                                       checksum=args.checksum, force_download=args.force_download,
                                       source=args.source, prefer=args.prefer, profile=args.profile,
                                       report=args.report, analyze=args.analyze,
                                       compare_to=args.compare_to, deep=args.deep)
                print(f"Synced to: {result}")
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "sync-center":
            handle_sync_center(args)
        elif args.command == "cache":
            cache_main(args)
        elif args.command == "watch":
            import modely
            modely.watch_main(args)
        elif args.command == "resolve":
            try:
                result = resolve_resource(args.query, source=args.source, repo_type=args.repo_type,
                                          task=args.task, library=args.library, license=args.license,
                                          limit=args.limit, threshold=args.threshold, full=args.full)
                print_resolve_result(result, as_json=args.json)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "search":
            _handle_search(args)
        # ---- enterprise: asset -------------------------------------------------
        elif args.command == "asset":
            _handle_asset(args)
        # ---- enterprise: recommend -------------------------------------------
        elif args.command == "recommend":
            _handle_recommend(args)
        # ---- enterprise: alternatives ----------------------------------------
        elif args.command == "alternatives":
            _handle_alternatives(args)
        # ---- enterprise: graph -----------------------------------------------
        elif args.command == "graph":
            _handle_graph(args)
        # ---- enterprise: catalog-gate ----------------------------------------
        elif args.command == "catalog-gate":
            _handle_catalog_gate(args)
        # ---- Phase 3 enterprise: snapshot ------------------------------------
        elif args.command == "snapshot":
            _handle_snapshot(args)
        # ---- Phase 3 enterprise: manifest-diff -------------------------------
        elif args.command == "manifest-diff":
            _handle_manifest_diff(args)
        # ---- Phase 3 enterprise: resolve-approved ----------------------------
        elif args.command == "resolve-approved":
            _handle_resolve_approved(args)
        # ---- Phase 3 enterprise: install-approved ----------------------------
        elif args.command == "install-approved":
            _handle_install_approved(args)
        # ---- Phase 3 enterprise: token-create --------------------------------
        elif args.command == "token-create":
            _handle_token_create(args)
        # ---- Phase 3 enterprise: token-rotate --------------------------------
        elif args.command == "token-rotate":
            _handle_token_rotate(args)
        # ---- Phase 3 enterprise: token-revoke --------------------------------
        elif args.command == "token-revoke":
            _handle_token_revoke(args)
        else:
            parser.print_help()
            sys.exit(1)



# ---------------------------------------------------------------------------
# Enterprise intelligence command handlers
# ---------------------------------------------------------------------------

def _handle_search(args) -> None:
    """Handle the ``search`` command with optional enterprise mode."""
    from .exit_codes import EXIT_AUTH_DENIED, EXIT_ERROR, EXIT_QUOTA_LIMITED

    # Enterprise catalog search (local)
    if getattr(args, "catalog", None) is not None:
        try:
            from ..application.intelligence_queries import search_catalog
            result = search_catalog(
                args.keyword or "",
                source=getattr(args, "source", None),
                resource_type=getattr(args, "repo_type", None),
                sort="-updated_at",
            )
            _present_json_or_placeholder(result, getattr(args, "json", False))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(EXIT_ERROR)
        return

    # Enterprise server search
    if getattr(args, "server", None) is not None:
        _placeholder_server_message("search", args.server)
        return

    # Fall back to existing source-search behaviour
    search_main(args)


def _handle_asset(args) -> None:
    """``modely-ai asset`` — Enterprise catalog asset operations."""
    command = getattr(args, "asset_command", None)
    if command is None:
        print("Usage: modely asset {search|detail|download-url}")
        sys.exit(1)

    if command == "search":
        query = getattr(args, "query", "")
        try:
            from ..search import main as search_main

            search_args = argparse.Namespace(
                keyword=query if query else None,
                source=getattr(args, "source", None) or "all",
                repo_type=getattr(args, "repo_type", None) or "auto",
                limit=getattr(args, "limit", 20),
                json=getattr(args, "json", False),
            )
            if getattr(args, "server", None):
                _placeholder_server_message("assets", args.server)
                return
            search_main(search_args)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif command == "detail":
        asset_id = getattr(args, "asset_id", "")
        if getattr(args, "server", None):
            _placeholder_server_message(f"assets/{asset_id}", args.server)
            return
        try:
            from ..detail import get_resource_detail, print_resource_detail
            from ..uri import parse_modely_uri

            ref = parse_modely_uri(asset_id)
            detail = get_resource_detail(asset_id, source=ref.source, repo_type=ref.repo_type)
            print_resource_detail(detail, as_json=getattr(args, "json", False))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif command == "download-url":
        asset_id = getattr(args, "asset_id", "")
        if getattr(args, "server", None):
            _placeholder_server_message(f"assets/{asset_id}/download-url", args.server)
            return
        try:
            from ..storage.download_urls import local_download_url
            from ..uri import parse_modely_uri

            ref = parse_modely_uri(asset_id)
            url = local_download_url(f"assets/{ref.source}/{ref.repo_type}/{ref.repo_id}")
            if getattr(args, "json", False):
                print(json.dumps(url.to_dict(), indent=2, ensure_ascii=False))
            else:
                print(f"Download URL: {url.url}")
                if url.expires_at:
                    print(f"Expires:      {url.expires_at}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Unknown asset command: {command}")
        print("Usage: modely asset {search|detail|download-url}")
        sys.exit(1)


def _handle_recommend(args) -> None:
    """Handle ``recommend <asset-id>`` (enterprise)."""
    from .exit_codes import EXIT_ERROR

    try:
        from ..application.intelligence_queries import get_recommendations

        result = get_recommendations(
            args.asset_id,
            top_k=getattr(args, "top", 5),
            min_confidence=getattr(args, "min_confidence", 0.3),
        )

        fmt = getattr(args, "format", "table")
        if fmt == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif fmt == "markdown":
            _print_recommendations_markdown(result)
        else:
            _print_recommendations_table(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


def _handle_alternatives(args) -> None:
    """Handle ``alternatives <asset-id>`` (enterprise)."""
    from .exit_codes import EXIT_ERROR

    try:
        from ..application.intelligence_queries import get_alternatives

        result = get_alternatives(
            args.asset_id,
            top_k=getattr(args, "top", 5),
            only_when_blocked=not getattr(args, "all", False),
        )

        fmt = getattr(args, "format", "table")
        if fmt == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif fmt == "markdown":
            _print_alternatives_markdown(result)
        else:
            _print_alternatives_table(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


def _handle_graph(args) -> None:
    """Handle ``graph asset <asset-id>`` (enterprise)."""
    from .exit_codes import EXIT_ERROR

    if getattr(args, "graph_command", None) != "asset":
        print("Usage: modely graph asset <asset-id> [--max-depth N] [--include-types ...]")
        sys.exit(2)

    try:
        from ..application.intelligence_queries import get_asset_graph

        result = get_asset_graph(
            args.asset_id,
            max_depth=getattr(args, "max_depth", 3),
            include_types=_parse_csv(getattr(args, "include_types", None)),
            direction=getattr(args, "direction", "outgoing"),
        )

        fmt = getattr(args, "format", "summary")
        if fmt == "json" or fmt == "d3":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            _print_graph_tree(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


def _handle_catalog_gate(args) -> None:
    """Handle ``catalog-gate <resource>`` (enterprise CI gate)."""
    from .exit_codes import EXIT_ERROR, EXIT_POLICY_BLOCKED, EXIT_APPROVAL_REQUIRED, EXIT_POLICY_WARN

    try:
        # Reuse existing policy evaluation if available
        from ..policy import evaluate_catalog_policy, load_policy, print_catalog_policy_result

        policy = load_policy(args.profile if hasattr(args, "profile") else "production")
        result = evaluate_catalog_policy(args.resource, policy=policy)
        print_catalog_policy_result(result, as_json=(getattr(args, "format", "json") == "json"))

        decision = getattr(result, "decision", "allow")
        if decision == "block":
            sys.exit(EXIT_POLICY_BLOCKED)
        elif decision == "require_approval":
            sys.exit(EXIT_APPROVAL_REQUIRED)
        elif decision == "warn":
            sys.exit(EXIT_POLICY_WARN)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


def _handle_compliance_report(args) -> None:
    """Handle ``report --compliance`` (enterprise compliance report)."""
    from .exit_codes import EXIT_ERROR

    try:
        from ..application.intelligence_queries import generate_compliance_report
        from ..domain.tenants import TenantScope

        scope_str = getattr(args, "scope", None) or "default:default"
        parts = scope_str.split(":")
        tenant_scope = TenantScope(
            organization_id=parts[0],
            workspace_id=parts[1] if len(parts) > 1 else "default",
        )

        sections = _parse_csv(getattr(args, "sections", None))
        result = generate_compliance_report(
            tenant_scope,
            format=args.format,
            include_sections=sections,
            time_window=getattr(args, "time_window", "30d"),
        )

        if args.format == "json":
            text = json.dumps(result, indent=2, ensure_ascii=False)
        elif args.format == "html":
            text = f"<html><body><h1>Compliance Report</h1><pre>{json.dumps(result, indent=2)}</pre></body></html>"
        else:
            text = _format_compliance_markdown(result)

        if args.output:
            with open(args.output, "w") as f:
                f.write(text)
        else:
            print(text, end="")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


def _format_compliance_markdown(report: dict) -> str:
    """Format a compliance report dict as Markdown."""
    meta = report.get("metadata", {})
    lines = [
        f"# Compliance Report",
        f"",
        f"- **Report ID**: {report.get('report_id', 'N/A')}",
        f"- **Generated**: {report.get('generated_at', 'N/A')}",
        f"- **Scope**: {report.get('tenant_scope', 'N/A')}",
        f"- **Time Window**: {report.get('time_window', 'N/A')}",
        f"- **Coverage**: {meta.get('coverage_percent', 0)}%",
        f"- **Redaction Applied**: {meta.get('redaction_applied', True)}",
        f"",
    ]
    sections = report.get("sections", {})
    if sections:
        for name, data in sections.items():
            lines.append(f"## {name.replace('_', ' ').title()}")
            lines.append("")
            if isinstance(data, dict):
                for k, v in data.items():
                    lines.append(f"- **{k}**: {v}")
            elif isinstance(data, list):
                for item in data[:10]:
                    lines.append(f"- {item}")
            else:
                lines.append(str(data))
            lines.append("")

    warnings = report.get("missing_data_warnings", [])
    if warnings:
        lines.append("## Data Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- ⚠ {w}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------


def _print_recommendations_table(result: dict) -> None:
    """Print recommendations as a human-readable table."""
    recs = result.get("recommendations", [])
    if not recs:
        reason = result.get("reason", "no similar assets found")
        print(f"No recommendations ({reason}).")
        return
    print(f"{'Rank':<5} {'Name':<40} {'Score':<8} {'Risk':<8} {'License':<15}")
    print("-" * 80)
    for i, r in enumerate(recs, 1):
        name = r.get("name", r.get("asset_id", "?"))[:38]
        score = f"{r.get('similarity_score', 0):.0f}"
        risk = r.get("risk_level", "?")
        lic = r.get("license", "?")[:13]
        print(f"{i:<5} {name:<40} {score:<8} {risk:<8} {lic:<15}")


def _print_recommendations_markdown(result: dict) -> None:
    """Print recommendations as Markdown."""
    recs = result.get("recommendations", [])
    print(f"# Recommendations for {result.get('asset_id', '?')}\n")
    if not recs:
        print(f"*No similar assets found ({result.get('reason', 'unknown')}).*")
        return
    print("| # | Name | Similarity | Risk | License | Confidence |")
    print("| --- | --- | --- | --- | --- | --- |")
    for i, r in enumerate(recs, 1):
        name = r.get("name", "?")
        score = f"{r.get('similarity_score', 0):.0f}"
        risk = r.get("risk_level", "?")
        lic = r.get("license", "?")
        conf = f"{r.get('confidence', 0):.0%}"
        print(f"| {i} | {name} | {score} | {risk} | {lic} | {conf} |")
    print()


def _print_alternatives_table(result: dict) -> None:
    """Print alternatives as a human-readable table."""
    alts = result.get("alternatives", [])
    if not alts:
        reason = result.get("reason", "no approved alternatives found")
        print(f"No approved alternatives ({reason}).")
        return
    print(f"{'#':<3} {'Alternative':<40} {'Safety Delta':<25} {'Required Perms':<20}")
    print("-" * 92)
    for i, a in enumerate(alts, 1):
        name = a.get("name", "?")[:38]
        delta = a.get("safety_delta", "?")[:23]
        perms = ", ".join(a.get("required_permissions", []))[:18]
        print(f"{i:<3} {name:<40} {delta:<25} {perms:<20}")


def _print_alternatives_markdown(result: dict) -> None:
    """Print alternatives as Markdown."""
    alts = result.get("alternatives", [])
    print(f"# Approved Alternatives for {result.get('asset_id', '?')}\n")
    if not alts:
        print(f"*No approved alternatives found ({result.get('reason', 'unknown')}).*")
        return
    target_risk = result.get("target_risk", "?")
    target_policy = result.get("target_policy", "?")
    print(f"*Target risk: {target_risk}, Target policy: {target_policy}*\n")
    print("| # | Alternative | Safety Delta | Confidence | Required Permissions |")
    print("| --- | --- | --- | --- | --- |")
    for i, a in enumerate(alts, 1):
        name = a.get("name", "?")
        delta = a.get("safety_delta", "?")
        conf = f"{a.get('confidence', 0):.0%}"
        perms = ", ".join(a.get("required_permissions", []))
        print(f"| {i} | {name} | {delta} | {conf} | {perms} |")
    print()


def _print_graph_tree(result: dict) -> None:
    """Print an asset graph as an indented tree."""
    root = result.get("root_node_id", "?")
    nodes = {n.get("node_id", ""): n for n in result.get("nodes", [])}
    edges = result.get("edges", [])

    print(f"Asset graph for: {root}")
    if result.get("truncated"):
        print(f"  (graph truncated at max_depth={result.get('max_depth', '?')})")

    # Group edges by source for traversal
    adjacency: dict[str, list[dict]] = {}
    for e in edges:
        adjacency.setdefault(e.get("source_node_id", ""), []).append(e)

    visited: set[str] = set()

    def _traverse(node_id: str, depth: int, prefix: str) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        node = nodes.get(node_id, {})
        label = node.get("label", node_id)
        ntype = node.get("node_type", "")
        if depth == 0:
            print(f"  {label} [{ntype}]")
        targets = adjacency.get(node_id, [])
        for i, edge in enumerate(targets):
            is_last = i == len(targets) - 1
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")
            target_id = edge.get("target_node_id", "")
            target_node = nodes.get(target_id, {})
            tlabel = target_node.get("label", target_id)
            ttype = target_node.get("node_type", "")
            etype = edge.get("edge_type", "")
            print(f"{prefix}{connector}{tlabel} [{ttype}] --{etype}-->")
            _traverse(target_id, depth + 1, child_prefix)

    _traverse(root, 0, "")


def _present_json_or_placeholder(result: dict, as_json: bool) -> None:
    """Print a result as JSON or a placeholder message."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status = result.get("_status", "")
        if status == "placeholder":
            print("(Enterprise intelligence services are not yet implemented. "
                  "This is a placeholder response.)")
        else:
            print(json.dumps(result, indent=2))


def _placeholder_server_message(command: str, server_url: str) -> None:
    """Print a message indicating server mode is not yet fully available."""
    print(f"(Enterprise server mode: '{command}' would query {server_url}/api/v1/{command}. "
          "Server integration is available in the full enterprise deployment.)")


# ---------------------------------------------------------------------------
# Phase 2 enterprise CLI handlers (request / approve / reject / policy-check)
# ---------------------------------------------------------------------------


def _handle_request(args) -> None:
    """``modely-ai request`` — Submit an access request for a governed resource."""
    resource = args.resource
    reason = args.reason

    if args.server:
        _placeholder_server_message("governance/requests/submit", args.server)
        return

    try:
        from ..governance.approvals import ApprovalRequest, transition_request

        req = ApprovalRequest(
            id=f"req-{uuid.uuid4().hex[:8]}",
            asset_id=resource,
            requester_principal="cli-user",
            reason=reason,
            requested_actions=["asset:download"],
            state="none",
        )
        req = transition_request(req, "pending")
        result = {"id": req.id, "asset_id": req.asset_id, "state": req.state, "reason": req.reason}
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _handle_approve(args) -> None:
    """``modely-ai approve`` — Approve a pending access request."""
    _handle_review_action(args, "approved", "Approved")


def _handle_reject(args) -> None:
    """``modely-ai reject`` — Reject a pending access request."""
    _handle_review_action(args, "rejected", "Rejected")


def _handle_review_action(args, target_state: str, default_reason: str) -> None:
    """Shared handler for approve/reject CLI commands.

    Args:
        target_state: Canonical approval state (``"approved"`` or ``"rejected"``).
        default_reason: Default decision reason if none provided.
    """
    endpoint_action = target_state  # "approved" or "rejected"
    if args.server:
        _placeholder_server_message(f"governance/requests/{args.request_id}/{endpoint_action}", args.server)
        return

    reason = getattr(args, "reason", None) or default_reason
    try:
        from ..governance.approvals import ApprovalRequest, transition_request

        req = ApprovalRequest(
            id=args.request_id, asset_id="local-cli-request",
            requester_principal="cli-admin", reason="?", state="pending",
        )
        req = transition_request(req, target_state, reviewer="cli-admin", reason=reason)
        result = {"id": req.id, "state": req.state, "reviewer": req.reviewer, "reason": req.decision_reason}
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _handle_policy_check(args) -> None:
    """``modely-ai policy-check`` — Evaluate governance policy for a resource."""
    resource = args.resource

    if args.server:
        _placeholder_server_message("governance/policy/evaluate", args.server)
        return

    try:
        from ..governance.policy_engine import evaluate_governance_policy

        decision = evaluate_governance_policy(
            principal={"id": "cli-user", "roles": ["Developer"]},
            tenant_scope={"organization_id": "default", "workspace_id": "default"},
            asset={"id": resource, "source": args.source, "repo_type": args.repo_type},
            action="asset:download",
            scan_evidence={},
            approval_state={"status": "none"},
            environment="dev",
            source=args.source,
            request_context={"reason": "CLI policy check"},
        )

        output = {
            "resource": resource,
            "decision": decision.outcome,
            "risk_level": decision.risk_level,
            "reasons": decision.reasons,
            "scanner_coverage": decision.scanner_coverage,
            "missing_evidence": decision.missing_evidence,
        }
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(f"Resource:   {resource}")
            print(f"Decision:   {decision.outcome}")
            print(f"Risk level: {decision.risk_level}")
            if decision.reasons:
                for r in decision.reasons:
                    print(f"  - {r}")
            if decision.missing_evidence:
                print("Missing evidence:")
                for me in decision.missing_evidence:
                    print(f"  - {me}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _parse_csv(value: str | None) -> list[str] | None:
    """Parse a comma-separated string into a list, or return None."""
    if value is None:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


def _print_admission_score_table(result: dict) -> None:
    """Print an enterprise admission score as a human-readable table."""
    score = result.get("overall_score", 0)
    grade = result.get("grade", "N/A")
    print(f"Admission Score: {score}/100 ({grade})")
    print(f"Scoring Version: {result.get('scoring_version', 'N/A')}")
    dims = result.get("dimensions", {})
    if dims:
        print(f"{'Dimension':<30} {'Score':<8} {'Max':<6} {'Weight':<8} {'Status':<14}")
        print("-" * 70)
        for name, d in dims.items():
            s = d.get("score", 0)
            m = d.get("max", 0)
            w = d.get("weight", 0)
            status = d.get("status", "?")
            print(f"{name:<30} {s:<8} {m:<6} {w:<8.2f} {status:<14}")
    if result.get("_status") == "placeholder":
        print("\n(Enterprise admission scoring is not yet implemented. This is a placeholder.)")


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
        config_parser.add_argument("--set-shared", type=str, default=None)
        dedupe_parser = subparsers.add_parser("dedupe")
        dedupe_parser.add_argument("--dry-run", action="store_true")
        dedupe_parser.add_argument("--json", action="store_true")
        serve_parser = subparsers.add_parser("serve")
        serve_parser.add_argument("--host", default="127.0.0.1")
        serve_parser.add_argument("--port", type=int, default=8765)
        serve_parser.add_argument("--open", action="store_true")

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
        if hasattr(args, "set_shared") and args.set_shared:
            cache.set_shared_cache_dir(args.set_shared)
            print(f"Shared cache directory set to: {args.set_shared}")
        if not (getattr(args, "set", None) or getattr(args, "set_shared", None)):
            info = cache.cache_info(cache_dir)
            print(f"Current cache directory: {info['cache_dir']}")
            print(f"Shared cache directory: {info.get('shared_cache_dir') or '-'}")
            config = cache._load_config()
            if "cache_dir" in config or "shared_cache_dir" in config:
                print(f"Configured in: {cache.CONFIG_FILE}")

    elif args.cache_command == "dedupe":
        cache.print_dedupe_report(cache.find_duplicate_files(cache_dir), as_json=getattr(args, "json", False))

    elif args.cache_command == "serve":
        serve_cache_browser(
            cache_dir,
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8765),
            open_browser=getattr(args, "open", False),
        )

    else:
        print("Usage: modely cache [info|list|clean|config|dedupe|serve]")


# ---------------------------------------------------------------------------
# Phase 3 enterprise CLI command handlers
# ---------------------------------------------------------------------------

def _handle_snapshot(args) -> None:
    """Handle ``snapshot <subcommand>`` (enterprise Phase 3)."""
    cmd = getattr(args, "snapshot_command", "list")
    server = getattr(args, "server", None)

    if cmd == "list":
        from ..reproducibility.snapshots import list_snapshots
        from ..cataloging.repository import InMemorySnapshotRepository
        repo = InMemorySnapshotRepository()
        snaps = list_snapshots(args.asset_id or "", repository=repo)
        if snaps:
            for s in snaps:
                print(f"{s.id}  {s.asset_id}  {s.channel}  {s.created_at}")
        else:
            print("No snapshots found. Use a server-backed catalog or local snapshot data.")
    elif cmd == "promote":
        if server:
            import requests
            resp = requests.post(f"{server}/api/v1/snapshots/promote", json={"snapshot_id": args.snapshot_id, "channel_name": args.channel})
            print(resp.text)
        else:
            print("Server mode required: use --server <url>")
    elif cmd == "rollback":
        if server:
            import requests
            resp = requests.post(f"{server}/api/v1/snapshots/{args.snapshot_id}/rollback", json={"reason": args.reason})
            print(resp.text)
        else:
            print("Server mode required: use --server <url>")
    else:
        print("Usage: modely snapshot [list|promote|rollback]")


def _handle_manifest_diff(args) -> None:
    """Handle ``manifest-diff <left> <right>`` (enterprise Phase 3)."""
    from ..reproducibility.manifest_diff import diff_manifest_files
    try:
        result = diff_manifest_files(args.left, args.right)
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")


def _handle_resolve_approved(args) -> None:
    """Handle ``resolve-approved <asset-id>`` (enterprise Phase 3)."""
    if getattr(args, "server", None):
        import requests
        resp = requests.post(f"{args.server}/api/v1/assets/{args.asset_id}/resolve-approved", json={"requested_channel": args.channel})
        print(resp.text)
    else:
        print("Server mode required: use --server <url>")


def _handle_install_approved(args) -> None:
    """Handle ``install-approved <asset-id>`` (enterprise Phase 3)."""
    if getattr(args, "server", None):
        import requests
        resp = requests.post(f"{args.server}/api/v1/assets/{args.asset_id}/install", json={"channel": args.channel, "destination": args.destination})
        print(resp.text)
    else:
        print("Server mode required: use --server <url>")


def _handle_token_create(args) -> None:
    """Handle ``token-create`` (enterprise Phase 3)."""
    if getattr(args, "server", None):
        import requests
        resp = requests.post(f"{args.server}/api/v1/service-accounts/{args.service_account_id}/tokens",
                             json={"scopes": [s.strip() for s in args.scopes.split(",")], "expires_in_days": args.expires_in_days})
        data = resp.json()
        if "data" in data and "token" in data["data"]:
            print(f"Token created! Secret (shown once): {data['data']['token']}")
        else:
            print(resp.text)
    else:
        print("Server mode required: use --server <url>")


def _handle_token_rotate(args) -> None:
    """Handle ``token-rotate <token-id>`` (enterprise Phase 3)."""
    if getattr(args, "server", None):
        import requests
        resp = requests.post(f"{args.server}/api/v1/api-tokens/{args.token_id}/rotate",
                             json={"grace_period_seconds": args.grace_period})
        data = resp.json()
        if "data" in data and "token" in data["data"]:
            print(f"Token rotated! New secret (shown once): {data['data']['token']}")
        else:
            print(resp.text)
    else:
        print("Server mode required: use --server <url>")


def _handle_token_revoke(args) -> None:
    """Handle ``token-revoke <token-id>`` (enterprise Phase 3)."""
    if getattr(args, "server", None):
        import requests
        resp = requests.post(f"{args.server}/api/v1/api-tokens/{args.token_id}/revoke")
        print(resp.text)
    else:
        print("Server mode required: use --server <url>")
        sys.exit(1)
