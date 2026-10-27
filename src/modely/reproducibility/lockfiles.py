"""Lockfile and manifest implementation for reproducibility workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..files import filter_files, list_repo_files
from ..info import get_repo_info
from ..get import download_resource
from ..application.download_profiles import resolve_download_profile
from ..syncing.manifests import create_local_manifest
from ..syncing.reliability import sha256_file
from ..types import DownloadManifest, FileInfo, RepoRef
from ..uri import format_modely_uri, parse_modely_uri
try:
    from importlib.metadata import version
except ImportError:  # pragma: no cover
    version = None



def write_manifest(manifest: DownloadManifest, output: str) -> None:
    """Write a JSON manifest."""
    with open(output, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)


def read_manifest(path: str) -> DownloadManifest:
    """Read a JSON manifest or lockfile."""
    with open(path, "r") as f:
        data = json.load(f)
    files = [FileInfo(**item) for item in data.get("files", [])]
    metadata = migrate_lock_metadata(data.get("metadata") or {}, data)
    return DownloadManifest(
        source=data["source"],
        repo_type=data["repo_type"],
        repo_id=data["repo_id"],
        revision=data.get("revision"),
        local_path=data.get("local_path"),
        files=files,
        include=data.get("include"),
        exclude=data.get("exclude"),
        metadata=metadata,
    )


def create_lock(resource: str, *, revision=None, include=None, exclude=None, output="modely.lock", token=None,
                endpoint=None, profile=None, alternatives=None, strict: bool = False, require_checksums: bool = False,
                list_repo_files_func=None) -> DownloadManifest:
    """Create a lockfile describing the selected remote files."""
    ref = parse_modely_uri(resource)
    if revision:
        ref.revision = revision
    include, exclude = resolve_download_profile(profile, include, exclude)
    requested_revision = ref.revision
    resolved_info = _resolved_info(ref, token=token, endpoint=endpoint)
    resolved_revision = resolved_info.get("resolved_revision") or ref.revision
    if list_repo_files_func is None:
        list_repo_files_func = list_repo_files
    files = filter_files(list_repo_files_func(ref, token=token, endpoint=endpoint), include, exclude)
    summary = lock_summary(DownloadManifest(ref.source, ref.repo_type, ref.repo_id, ref.revision, files=files))
    if require_checksums and summary["missing_checksum_count"]:
        raise ValueError("Cannot create strict lock: missing SHA256 metadata for selected files")
    manifest = DownloadManifest(
        source=ref.source,
        repo_type=ref.repo_type,
        repo_id=ref.repo_id,
        revision=ref.revision,
        files=files,
        include=include,
        exclude=exclude,
        metadata={
            "kind": "lock",
            "schema_version": 3,
            "created_by": "modely-ai",
            "modely_version": _modely_version(),
            "resource": format_modely_uri(ref),
            "requested_revision": requested_revision,
            "resolved_revision": ref.revision,
            "strict": strict,
            "require_checksums": require_checksums,
            "profile": profile,
            "include": include,
            "exclude": exclude,
            "alternatives": _parse_alternatives(alternatives),
        },
    )
    manifest.metadata.update(lock_summary(manifest))
    manifest.metadata["checksum_coverage"] = (manifest.metadata["checksum_count"] / manifest.metadata["file_count"]) if manifest.metadata["file_count"] else 1.0
    manifest.metadata["floating_revision"] = (requested_revision in {None, "main", "master", "latest"}) and not (resolved_info.get("resolved_commit") or resolved_info.get("resolved_version"))
    if strict and manifest.metadata["floating_revision"]:
        raise ValueError("Cannot create strict lock for floating revision without a resolved commit/version")
    write_manifest(manifest, output)
    return manifest


def lock_summary(manifest: DownloadManifest) -> dict:
    """Return summary fields for a lock or manifest."""
    checksum_count = sum(1 for f in manifest.files if f.sha256)
    return {
        "file_count": len(manifest.files),
        "total_size": sum(f.size or 0 for f in manifest.files),
        "checksum_count": checksum_count,
        "missing_checksum_count": len(manifest.files) - checksum_count,
    }


def install_lock(lockfile: str, *, local_dir=None, cache_dir=None, token=None, force_download=False, fallback=False, prefer=None,
                 download_resource_func=None):
    """Install resources described by a lockfile."""
    manifest = read_manifest(lockfile)
    resource = _manifest_uri(manifest)
    alternatives = prefer or ",".join(manifest.metadata.get("alternatives") or [])
    if download_resource_func is None:
        download_resource_func = download_resource
    path = download_resource_func(
        resource if not fallback else manifest.repo_id,
        source="auto" if fallback else manifest.source,
        repo_type=manifest.repo_type,
        revision=manifest.revision,
        cache_dir=cache_dir,
        local_dir=local_dir,
        token=token,
        include=manifest.include,
        exclude=manifest.exclude,
        prefer=alternatives or "default",
        fallback=fallback,
        force_download=force_download,
    )
    manifest.local_path = path
    return path


def create_download_manifest(resource: str, local_path: str, *, include=None, exclude=None, checksum=False, output=None):
    """Create a manifest for files present under local_path."""
    return create_local_manifest(
        resource,
        local_path,
        include=include,
        exclude=exclude,
        checksum=checksum,
        output=output,
    )


def validate_lock(lockfile: str, *, local_dir=None, checksum=False, require_checksums: bool = False, strict: bool = False) -> dict:
    """Validate a lockfile against local files without network access."""
    manifest = read_manifest(lockfile)
    root = Path(local_dir or manifest.local_path or ".")
    missing_files = []
    checksum_mismatches = []
    missing_checksums = []
    size_mismatches = []
    checked_files = 0
    for file_info in manifest.files:
        path = root / file_info.path
        if not path.exists():
            missing_files.append(file_info.path)
            continue
        checked_files += 1
        if file_info.size and path.stat().st_size != file_info.size:
            size_mismatches.append({"path": file_info.path, "expected": file_info.size, "actual": path.stat().st_size})
        if checksum or require_checksums or strict:
            if not file_info.sha256:
                missing_checksums.append(file_info.path)
            else:
                actual = sha256_file(str(path))
                if actual.lower() != file_info.sha256.lower():
                    checksum_mismatches.append({"path": file_info.path, "expected": file_info.sha256, "actual": actual})
    ok = not missing_files and not checksum_mismatches and not size_mismatches and not ((require_checksums or strict) and missing_checksums)
    return {
        "ok": ok,
        "lockfile": lockfile,
        "local_dir": str(root),
        "checked_files": checked_files,
        "total_files": len(manifest.files),
        "missing_files": missing_files,
        "checksum_mismatches": checksum_mismatches,
        "size_mismatches": size_mismatches,
        "missing_checksums": missing_checksums,
        "strict": strict,
        "require_checksums": require_checksums,
    }


def print_lock_validation(result: dict, *, as_json=False) -> None:
    """Print lock validation results."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Lockfile:      {result['lockfile']}")
    print(f"Local dir:     {result['local_dir']}")
    print(f"Status:        {'ok' if result['ok'] else 'failed'}")
    print(f"Checked files: {result['checked_files']}/{result['total_files']}")
    if result["missing_files"]:
        print("Missing files:")
        for path in result["missing_files"]:
            print(f"  - {path}")
    if result["checksum_mismatches"]:
        print("Checksum mismatches:")
        for item in result["checksum_mismatches"]:
            print(f"  - {item['path']}")
    if result.get("size_mismatches"):
        print("Size mismatches:")
        for item in result["size_mismatches"]:
            print(f"  - {item['path']}: expected {item['expected']}, got {item['actual']}")
    if result["missing_checksums"]:
        print("Missing checksums:")
        for path in result["missing_checksums"]:
            print(f"  - {path}")


def migrate_lock_metadata(metadata: dict, data: dict | None = None) -> dict:
    """Normalize older lock metadata to the current in-memory shape."""
    data = data or {}
    migrated = dict(metadata or {})
    migrated.setdefault("schema_version", migrated.get("schema_version", 1))
    migrated.setdefault("kind", "lock" if "files" in data else "manifest")
    migrated.setdefault("resource", None)
    migrated.setdefault("requested_revision", data.get("revision"))
    migrated.setdefault("resolved_revision", data.get("revision"))
    migrated.setdefault("resolved_commit", None)
    migrated.setdefault("resolved_version", None)
    migrated.setdefault("alternatives", [])
    migrated.setdefault("alternative_uris", [])
    return migrated


def _resolved_info(ref: RepoRef, *, token=None, endpoint=None) -> dict:
    try:
        info = get_repo_info(ref, token=token, endpoint=endpoint)
    except Exception:
        return {}
    metadata = info.metadata or {}
    resolved = info.revision or ref.revision
    commit = metadata.get("sha") or metadata.get("commit") or metadata.get("commit_hash") or metadata.get("revision")
    version_value = metadata.get("version") or metadata.get("datasetVersion")
    return {"resolved_revision": resolved, "resolved_commit": commit, "resolved_version": version_value}


def _alternative_uris(ref: RepoRef, alternatives, revision) -> list[str]:
    uris = []
    for item in _parse_alternatives(alternatives):
        if "://" in item:
            uris.append(item)
            continue
        try:
            uris.append(format_modely_uri(RepoRef(item, ref.repo_type, ref.repo_id, revision)))
        except Exception:
            continue
    return uris


def _parse_alternatives(alternatives) -> list[str]:
    if not alternatives:
        return []
    if isinstance(alternatives, str):
        return [item.strip() for item in alternatives.split(",") if item.strip()]
    return [str(item).strip() for item in alternatives if str(item).strip()]


def _manifest_uri(manifest: DownloadManifest) -> str:
    return format_modely_uri(RepoRef(manifest.source, manifest.repo_type, manifest.repo_id, manifest.revision))


def _modely_version() -> str:
    if version is None:
        return "unknown"
    try:
        return version("modely-ai")
    except Exception:
        return "unknown"


# -- Enterprise lockfile (Schema v4) -------------------------------------------------

from dataclasses import asdict, dataclass, field as dc_field

ENTERPRISE_LOCK_SCHEMA_VERSION = 4


@dataclass
class LockfileEntry:
    """A single resource entry in an enterprise lockfile."""

    uri: str
    internal_asset_id: str | None = None
    pinned_revision: str | None = None
    manifest_digest: str | None = None
    files: list[dict] = dc_field(default_factory=list)
    checksums: dict[str, str] = dc_field(default_factory=dict)
    approved_snapshot_ref: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    policy_status: str = "not_evaluated"
    source_url: str | None = None
    internal_url: str | None = None
    fallback_urls: list[str] = dc_field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LockfileEntry":
        return cls(
            uri=data.get("uri", ""),
            internal_asset_id=data.get("internal_asset_id"),
            pinned_revision=data.get("pinned_revision"),
            manifest_digest=data.get("manifest_digest"),
            files=data.get("files", []),
            checksums=data.get("checksums", {}),
            approved_snapshot_ref=data.get("approved_snapshot_ref"),
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            policy_status=data.get("policy_status", "not_evaluated"),
            source_url=data.get("source_url"),
            internal_url=data.get("internal_url"),
            fallback_urls=data.get("fallback_urls", []),
        )


@dataclass
class EnterpriseLockfile:
    """Enterprise lockfile (schema v4) with approval/policy/reproducibility metadata."""

    schema_version: int = ENTERPRISE_LOCK_SCHEMA_VERSION
    resources: list[LockfileEntry] = dc_field(default_factory=list)
    metadata: dict = dc_field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "resources": [r.to_dict() for r in self.resources],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EnterpriseLockfile":
        return cls(
            schema_version=data.get("schema_version", ENTERPRISE_LOCK_SCHEMA_VERSION),
            resources=[LockfileEntry.from_dict(r) for r in data.get("resources", [])],
            metadata=data.get("metadata", {}),
        )


def read_enterprise_lock(path: str) -> EnterpriseLockfile:
    """Read an enterprise lockfile, auto-detecting JSON vs YAML.

    Backward-compatible: accepts schema v3 manifests (converted on read)
    and schema v4 enterprise lockfiles.
    """

    raw = _read_lockfile_raw(path)
    schema_ver = raw.get("schema_version", 3)

    if schema_ver >= ENTERPRISE_LOCK_SCHEMA_VERSION:
        return EnterpriseLockfile.from_dict(raw)

    # Upgrade schema v3 manifest to enterprise format
    manifest = read_manifest(path)
    entry = LockfileEntry(
        uri=_manifest_uri(manifest),
        pinned_revision=manifest.revision,
        files=[f.to_dict() for f in manifest.files],
        checksums={f.path: f.sha256 for f in manifest.files if f.sha256},
        source_url=manifest.metadata.get("resource"),
    )
    return EnterpriseLockfile(
        schema_version=ENTERPRISE_LOCK_SCHEMA_VERSION,
        resources=[entry],
        metadata={"upgraded_from_schema_v3": True, "original_schema_version": schema_ver},
    )


def write_enterprise_lock(lockfile: EnterpriseLockfile, output: str) -> None:
    """Write an enterprise lockfile as JSON."""
    with open(output, "w") as f:
        json.dump(lockfile.to_dict(), f, indent=2, ensure_ascii=False)


def write_enterprise_lock_yaml(lockfile: EnterpriseLockfile, output: str) -> None:
    """Write an enterprise lockfile as YAML matching spec example shape."""
    import yaml

    payload = {
        "schema_version": lockfile.schema_version,
        "resources": [
            {
                "uri": r.uri,
                "revision": r.pinned_revision,
                "files": [
                    {"path": f.get("path", ""), "sha256": f.get("sha256", "")} for f in r.files
                ],
                "source_url": r.source_url,
                "internal_url": r.internal_url,
                "approved_by": r.approved_by,
                "approved_at": r.approved_at,
            }
            for r in lockfile.resources
        ],
        "metadata": lockfile.metadata,
    }
    with open(output, "w") as f:
        yaml.safe_dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def validate_enterprise_lock(
    *,
    path: str | None = None,
    content: dict | None = None,
    profile: str = "production",
    fail_on_warnings: bool = False,
) -> dict:
    """Validate an enterprise lockfile against policy and integrity rules.

    Returns a dict with per-resource results and a summary.
    """

    if path:
        lockfile = read_enterprise_lock(path)
    elif content:
        lockfile = EnterpriseLockfile.from_dict(content)
    else:
        raise ValueError("Either path or content is required")

    resources = []
    for entry in lockfile.resources:
        errors = []
        warnings_list = []

        # Checksum validation
        if not entry.checksums:
            warnings_list.append(f"No checksums recorded for {entry.uri}")
        elif entry.files and len(entry.files) != len(entry.checksums):
            warnings_list.append(f"Checksum count mismatch for {entry.uri}")

        # Snapshot ref validation
        if not entry.approved_snapshot_ref:
            warnings_list.append(f"No approved snapshot ref for {entry.uri}")

        # Policy status check
        if entry.policy_status == "blocked":
            errors.append(f"Policy blocked for {entry.uri}")
        elif entry.policy_status in ("not_evaluated", "unknown"):
            warnings_list.append(f"Policy not evaluated for {entry.uri}")

        # Determine per-resource status
        if errors:
            status = "failed"
        elif warnings_list and fail_on_warnings:
            status = "failed"
        elif warnings_list:
            status = "warning"
        else:
            status = "passed"

        resources.append({
            "uri": entry.uri,
            "status": status,
            "checksum_ok": not bool(errors) and len(entry.checksums) > 0,
            "approval_ok": bool(entry.approved_snapshot_ref),
            "policy_ok": entry.policy_status not in ("blocked",),
            "snapshot_ref_valid": bool(entry.approved_snapshot_ref),
            "errors": errors,
            "warnings": warnings_list,
        })

    return {
        "lockfile_path": path,
        "schema_version": lockfile.schema_version,
        "resources": resources,
        "summary": {
            "total": len(resources),
            "passed": sum(1 for r in resources if r["status"] == "passed"),
            "failed": sum(1 for r in resources if r["status"] == "failed"),
            "warning": sum(1 for r in resources if r["status"] == "warning"),
        },
    }


def _read_lockfile_raw(path: str) -> dict:
    """Read a lockfile, auto-detecting JSON vs YAML by extension."""
    if path.endswith((".yaml", ".yml")):
        import yaml

        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    with open(path, "r") as f:
        return json.load(f)


__all__ = [
    "EnterpriseLockfile",
    "LockfileEntry",
    "create_lock",
    "create_download_manifest",
    "install_lock",
    "lock_summary",
    "migrate_lock_metadata",
    "print_lock_validation",
    "read_enterprise_lock",
    "read_manifest",
    "validate_enterprise_lock",
    "validate_lock",
    "write_enterprise_lock",
    "write_manifest",
]
