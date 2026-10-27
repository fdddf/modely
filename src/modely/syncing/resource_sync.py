"""Download-only sync implementation."""

from __future__ import annotations

import json

from ..get import download_resource
from ..reproducibility.lockfiles import create_download_manifest


def sync_resource(resource: str, *, local_dir: str, revision=None, include=None, exclude=None,
                  token=None, cache_dir=None, manifest=None, checksum=False, force_download=False,
                  source="auto", prefer="default", profile=None, report=None,
                  analyze=False, compare_to=None, deep=False, download_resource_func=None,
                  create_download_manifest_func=None):
    """Ensure a remote resource is materialized locally. No upload is performed."""
    if download_resource_func is None:
        download_resource_func = download_resource
    if create_download_manifest_func is None:
        create_download_manifest_func = create_download_manifest
    path = download_resource_func(
        resource,
        source=source,
        revision=revision,
        local_dir=local_dir,
        cache_dir=cache_dir,
        token=token,
        include=include,
        exclude=exclude,
        prefer=prefer,
        fallback=True,
        force_download=force_download,
        profile=profile,
        checksum=checksum,
    )
    manifest_obj = None
    normalized_resource = resource if "://" in resource else f"hf://models/{resource}"
    if manifest:
        manifest_obj = create_download_manifest_func(normalized_resource, path,
                                                include=include, exclude=exclude, checksum=checksum, output=manifest)
    if report:
        if manifest_obj is None:
            manifest_obj = create_download_manifest_func(normalized_resource, path,
                                                    include=include, exclude=exclude, checksum=checksum)
        payload = _build_sync_report(
            normalized_resource,
            path,
            manifest_obj=manifest_obj,
            revision=revision,
            token=token,
            analyze=analyze,
            compare_to=compare_to,
            deep=deep,
        )
        with open(report, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def _build_sync_report(resource: str, local_path: str, *, manifest_obj=None, revision=None,
                       token=None, analyze=False, compare_to=None, deep=False) -> dict:
    payload = {
        "resource": resource,
        "local_path": local_path,
        "status": "ok",
        "manifest": manifest_obj.to_dict() if manifest_obj else None,
        "warnings": [],
    }
    if analyze:
        from ..analyze import analyze_resource
        analysis = analyze_resource(resource, revision=revision, token=token, deep=deep)
        payload["analysis"] = analysis.to_dict()
        payload["warnings"].extend(analysis.warnings)
    if compare_to:
        from ..compare import compare_resources
        comparison = compare_resources(resource, compare_to, revision_left=revision, token=token,
                                       include_files=True, include_card=True, include_formats=True, deep=deep)
        payload["comparison"] = comparison.to_dict()
        payload["warnings"].extend(comparison.warnings)
    return payload


__all__ = ["sync_resource"]
