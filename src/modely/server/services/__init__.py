"""Service provider for development / demo mode.

Provides a minimally wired service that reads from the local modely cache
and watch state so the web UI shows real data without a production backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# -- Stub DTO helpers -----------------------------------------------------------


@dataclass
class _Stub:
    """Generic stub that can wrap anything as attribute or dict access."""

    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


def _empty_stub(**overrides: Any) -> _Stub:
    return _Stub(**overrides)


# -- Search helpers used by DevNullServices.search() ---------------------------


def _field_val(item, key: str) -> Any:
    """Extract a field from a dict, DTO, or CatalogEntry-like object."""
    if hasattr(item, "to_dict") and not isinstance(item, dict):
        item = item.to_dict()
    identity = item.get("identity", {})
    meta = item.get("metadata", {}) or {}
    return item.get(key) or meta.get(key) or identity.get(key)


def _set_field(item, key: str, value: Any) -> None:
    """Set a field on a dict or DTO-like item (mutates in place)."""
    if hasattr(item, "__setitem__") and not hasattr(item, "to_dict"):
        item[key] = value
    elif hasattr(item, "__setattr__"):
        object.__setattr__(item, key, value)


def _sync_result_to_cache(job: dict, result: Any) -> None:
    """Copy files from a completed sync result into the modely cache so
    the Assets page and catalog can discover them."""
    import os
    import shutil

    if result.status != "synced":
        return

    # Parse source/type/repo from the worker result (more reliable than URI)
    asset_id = getattr(result, "asset_id", "") or ""
    # asset_id format: "ms:model:qwen--Qwen2.5-0.5B-Instruct"
    parts = asset_id.split(":")
    if len(parts) < 3:
        return
    source = parts[0]
    repo_type = parts[1]
    repo_id = parts[2].replace("--", "/")  # reverse cache encoding
    revision = "master"  # default

    from ...common import cache as cache_mod
    cache_dir = cache_mod.get_repo_cache_dir(repo_id, repo_type, revision, source)
    os.makedirs(cache_dir, exist_ok=True)

    # Copy files from worker result to cache
    for f in getattr(result, "files", []) or []:
        file_path = f.get("path", "")
        # Try uri first (actual filesystem path from StoredObject), then local_path (storage key)
        src = f.get("uri") or f.get("local_path") or ""
        if src and os.path.isfile(src):
            dest = os.path.join(cache_dir, file_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if not os.path.exists(dest):
                shutil.copy2(src, dest)
                job.setdefault("metadata", {}).setdefault("cached_files", []).append(file_path)

    # Write repo info sidecar
    from ...common.cache import write_repo_info
    from ...application.repo_queries import _repo_info_for_ref
    from ...types import RepoRef
    try:
        ref = RepoRef(source=source, repo_type=repo_type, repo_id=repo_id, revision=revision)
        info = _repo_info_for_ref(ref)
        if info:
            write_repo_info(cache_dir, info.to_dict())
    except Exception:
        pass

    # Update watch fingerprint if a matching watch target exists
    _update_watch_fingerprint(source, repo_type, repo_id, revision, cache_dir)
    job.setdefault("metadata", {}).setdefault("watch_updated", True)


def _update_watch_fingerprint(
    source: str, repo_type: str, repo_id: str, revision: str, local_path: str
) -> None:
    """Update the last-checked fingerprint for a matching watch target.

    Writes to BOTH the watch config file (targets array, for compatibility)
    AND the watch state file (state_file in config) so that
    ``list_watch_targets()`` picks up ``last_downloaded_at`` after a sync.
    """
    import json
    import hashlib
    import os
    from datetime import datetime, timezone
    from pathlib import Path

    # Look for watch config files
    watch_dir = Path.home() / ".modely"
    for cfg_path in watch_dir.glob("*-watch.json"):
        try:
            with open(cfg_path, "r") as f:
                cfg = json.load(f)
            targets = cfg.get("targets", [])
            matched_key = None
            fp_hash = None
            now_iso = None
            for t in targets:
                if (t.get("source") == source and t.get("repo_id") == repo_id
                        and t.get("repo_type", "model") == repo_type
                        and t.get("revision", "master") == revision):
                    # Compute a simple fingerprint from the cached files
                    if os.path.isdir(local_path):
                        file_hashes = []
                        for root, _, files in sorted(os.walk(local_path)):
                            for fname in sorted(files):
                                fp = os.path.join(root, fname)
                                try:
                                    st = os.stat(fp)
                                    file_hashes.append(f"{fname}:{st.st_size}:{st.st_mtime}")
                                except OSError:
                                    pass
                        if file_hashes:
                            fp_hash = hashlib.sha256(
                                "\n".join(file_hashes).encode()
                            ).hexdigest()[:16]
                            now_iso = datetime.now(timezone.utc).isoformat()
                            t["fingerprint"] = fp_hash
                            t["last_checked_at"] = now_iso
                            t["last_downloaded_at"] = now_iso
                            matched_key = f"{source}:{repo_type}:{repo_id}:{revision}"
                            break  # only one matching target per config

            if matched_key and fp_hash and now_iso:
                cfg["targets"] = targets
                # (1) Write updated targets back to config file
                with open(cfg_path, "w") as f:
                    json.dump(cfg, f, indent=2)

                # (2) Also update the watch STATE file so list_watch_targets()
                #     can see last_downloaded_at (it reads from the state file,
                #     not the config targets).
                state_file = cfg.get("state_file")
                if state_file:
                    state_file = os.path.expanduser(state_file)
                    try:
                        state: dict = {}
                        if os.path.exists(state_file):
                            with open(state_file, "r") as f:
                                state = json.load(f)
                        previous = state.get(matched_key, {})
                        state[matched_key] = {
                            **previous,
                            "fingerprint": fp_hash,
                            "last_checked_at": now_iso,
                            "last_downloaded_at": now_iso,
                            "last_download_path": str(local_path),
                            "error": None,
                        }
                        os.makedirs(os.path.dirname(state_file), exist_ok=True)
                        with open(state_file, "w") as f:
                            json.dump(state, f, indent=2, sort_keys=True)
                            f.write("\n")
                    except Exception:
                        pass  # best-effort; sync still succeeded
        except Exception:
            pass


def _text_matches_asset(item, query: str) -> bool:
    """Check whether *item* matches *query* (case-insensitive) across
    the same searchable fields used by the catalog list route."""
    if hasattr(item, "to_dict") and not isinstance(item, dict):
        item = item.to_dict()
    identity = item.get("identity", {})
    searchable = [
        item.get("id", ""),
        item.get("source", ""),
        item.get("repo_id", ""),
        item.get("license", ""),
        identity.get("source", ""),
        identity.get("repo_id", ""),
    ]
    tags = item.get("tags", [])
    searchable.extend(tags)
    needle = query.lower()
    return any(needle in (str(v)).lower() for v in searchable if v)


# -- Main service class --------------------------------------------------------


@dataclass
class DevNullServices:
    """Reads assets from the local modely cache so the web UI stays in sync
    with models downloaded by ``modely-ai watch run`` and ``modely-ai get``."""

    repository: Any = None

    # -- AssetRepository (catalog) -----------------------------------------------

    def list_assets(self) -> list[Any]:
        """List assets from the modely cache directory.

        Cache entries map naturally to CatalogEntry rows, which the
        ``list_assets`` route handler already understands.
        """
        from modely.catalog import catalog_from_cache

        return catalog_from_cache()

    def get_asset(self, asset_id: str) -> Any | None:
        """Look up a single asset from the cache by id.

        Asset IDs with ``/`` characters are handled by replacing ``--``
        back to ``/`` before matching (the cache dir convention).
        """
        # Reverse the -- → / encoding used in cache directory names
        normalized = asset_id.replace("--", "/")
        for entry in self.list_assets():
            eid = getattr(entry, "id", None)
            if eid == asset_id or eid == normalized:
                return entry
        return None

    def list_asset_files(self, asset_id: str) -> list[Any]:
        """Return enriched file metadata stored in a cached entry.

        Each file dict is enriched with ``sha256``, ``file_type``, and
        ``mime_type`` where the local cache provides the data.
        """
        entry = self.get_asset(asset_id)
        if entry is None:
            return []
        meta = getattr(entry, "metadata", {}) or {}
        raw_files = meta.get("files", [])
        local_dir = getattr(entry, "local_path", "")

        if not raw_files:
            return []

        from .file_enricher import enrich_file_item

        return [enrich_file_item(f, local_dir) for f in raw_files]

    def get_download_url(self, asset_id: str) -> dict[str, Any] | None:
        """Return a local file:// URL for a cached asset."""
        entry = self.get_asset(asset_id)
        if entry is None:
            return None
        return {
            "asset_id": asset_id,
            "download_mode": "local_cache",
            "url_ref": f"file://{getattr(entry, 'local_path', '')}",
            "manifest_ref": None,
            "checksum_ref": None,
            "security_warning": "Dev mode — no policy enforcement.",
            "metadata": {},
        }

    # -- SnapshotRepository (reproducibility) ------------------------------------

    def list_snapshots(self, asset_id: str | None = None) -> list[Any]:
        snaps = list(self._snapshots.values())
        if asset_id:
            snaps = [s for s in snaps if getattr(s, "asset_id", "") == asset_id]
        return snaps

    def get_snapshot(self, snapshot_id: str) -> Any | None:
        return self._snapshots.get(snapshot_id)

    def create_snapshot(self, **kwargs: Any) -> Any:
        import uuid
        from datetime import datetime, timezone

        snapshot_id = kwargs.get("id") or f"snap-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        snap = _Stub(
            id=snapshot_id,
            tenant_scope=kwargs.get("tenant_scope", "default"),
            asset_id=kwargs.get("asset_id", ""),
            version_id=kwargs.get("version_id", ""),
            manifest_digest=kwargs.get("manifest_digest", ""),
            channel=kwargs.get("channel_name", "dev"),
            created_by=kwargs.get("created_by", ""),
            created_at=now,
            policy_decision_ref=kwargs.get("policy_decision_ref"),
            approval_ref=kwargs.get("approval_ref"),
        )
        self._snapshots[snapshot_id] = snap
        return snap

    def promote_snapshot(self, snapshot_id: str, channel_name: str, **kwargs: Any) -> Any:
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        # Clone the snapshot with the new channel
        import uuid
        from datetime import datetime, timezone

        new_id = f"snap-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        promoted = _Stub(
            id=new_id,
            tenant_scope=getattr(snap, "tenant_scope", "default"),
            asset_id=getattr(snap, "asset_id", ""),
            version_id=getattr(snap, "version_id", ""),
            manifest_digest=getattr(snap, "manifest_digest", ""),
            channel=channel_name,
            created_by=kwargs.get("promoted_by", getattr(snap, "created_by", "")),
            created_at=now,
            policy_decision_ref=getattr(snap, "policy_decision_ref", None),
            approval_ref=getattr(snap, "approval_ref", None),
        )
        self._snapshots[new_id] = promoted
        return promoted

    def rollback_snapshot(self, snapshot_id: str, reason: str | None = None, **kwargs: Any) -> Any:
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        # Rollback: create a new snapshot pointing to the same version, with the same channel
        import uuid
        from datetime import datetime, timezone

        new_id = f"snap-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        rolled = _Stub(
            id=new_id,
            tenant_scope=getattr(snap, "tenant_scope", "default"),
            asset_id=getattr(snap, "asset_id", ""),
            version_id=getattr(snap, "version_id", ""),
            manifest_digest=getattr(snap, "manifest_digest", ""),
            channel=kwargs.get("channel_name", getattr(snap, "channel", "dev")),
            created_by=kwargs.get("rolled_back_by", getattr(snap, "created_by", "")),
            created_at=now,
            policy_decision_ref=getattr(snap, "policy_decision_ref", None),
            approval_ref=getattr(snap, "approval_ref", None),
            metadata={"rollback_reason": reason or "", "rolled_back_from": snapshot_id},
        )
        self._snapshots[new_id] = rolled
        return rolled

    def snapshot_history(self, snapshot_id: str) -> list[Any]:
        return []

    # -- CI gate -----------------------------------------------------------------

    def evaluate_ci_gate(self, lockfile_path: str, profile: str = "production",
                         fail_on_warnings: bool = False, policy_path: str | None = None) -> Any:
        from ...reproducibility.ci_gate import evaluate_ci_gate as _evaluate
        return _evaluate(
            lockfile_path=lockfile_path,
            profile=profile,
            fail_on_warnings=fail_on_warnings,
            policy_path=policy_path,
        )

    # -- Lockfile / manifest reproducibility -------------------------------------

    def validate_lockfile(self, lockfile_path: str) -> Any:
        return _empty_stub(valid=True, errors=[])

    def diff_manifests(self, **kwargs: Any) -> Any:
        return _empty_stub(added=[], removed=[], changed=[], summary={"added": 0, "removed": 0, "changed": 0})

    # -- Sync jobs ---------------------------------------------------------------

    def __post_init__(self) -> None:
        """Initialise in-memory job, snapshot, service account, and token stores."""
        object.__setattr__(self, "_jobs", {})
        object.__setattr__(self, "_snapshots", {})
        from ...governance.service_accounts import InMemoryServiceAccountRepository
        from ...governance.api_tokens import InMemoryTokenRepository
        object.__setattr__(self, "_sa_repo", InMemoryServiceAccountRepository())
        object.__setattr__(self, "_token_repo", InMemoryTokenRepository())

    def create_sync_job(self, **kwargs: Any) -> Any:
        from datetime import datetime, timezone
        from threading import Thread
        import uuid

        job_id = kwargs.get("id") or f"job-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "id": job_id,
            "target_id": kwargs.get("target_id", ""),
            "resource": kwargs.get("resource", ""),
            "status": "syncing",
            "action": kwargs.get("action", "sync"),
            "attempts": 0,
            "error": None,
            "created_at": now,
            "updated_at": now,
            "metadata": kwargs.get("metadata", {}),
        }
        self._jobs[job_id] = job

        # Execute asynchronously in background thread
        worker = getattr(self, "_sync_worker", None)
        if worker is not None:
            def _run():
                try:
                    from ...syncing.jobs import SyncJob, SyncJobIdentity
                    sj = SyncJob(
                        id=job_id,
                        identity=SyncJobIdentity(
                            target_id=job["target_id"],
                            resource=job["resource"],
                            revision=kwargs.get("revision"),
                            idempotency_key=kwargs.get("idempotency_key", job_id),
                            action=job["action"],
                        ),
                        status="syncing",
                        attempts=0,
                        metadata={"include": kwargs.get("include"), "exclude": kwargs.get("exclude")},
                    )
                    result = worker.run(sj)
                    job["status"] = result.status
                    job["error"] = result.error
                    job["metadata"]["worker_result"] = result.to_dict()

                    # Sync downloaded files into modely cache so Assets page sees them
                    _sync_result_to_cache(job, result)
                except Exception as exc:
                    job["status"] = "failed"
                    job["error"] = str(exc)
                job["updated_at"] = datetime.now(timezone.utc).isoformat()

            Thread(target=_run, daemon=True).start()

        return _Stub(**job)

    def get_sync_job(self, job_id: str) -> Any | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return _Stub(**job)

    def list_sync_jobs(self) -> list[Any]:
        return [_Stub(**j) for j in self._jobs.values()]

    # -- Governance --------------------------------------------------------------

    def evaluate_policy(self, asset_id: str) -> Any:
        return _empty_stub(evaluation_id="", decision="allowed", reasons=[])

    def submit_approval(self, asset_id: str, **kwargs: Any) -> Any:
        return _empty_stub(id="stub-request", asset_id=asset_id, status="pending")

    def list_requests(self, filters: dict[str, Any] | None = None) -> list[Any]:
        return []

    def get_request(self, request_id: str) -> Any | None:
        return None

    def approve_request(self, request_id: str, **kwargs: Any) -> Any:
        return _empty_stub(id=request_id, status="approved")

    def reject_request(self, request_id: str, **kwargs: Any) -> Any:
        return _empty_stub(id=request_id, status="rejected")

    def cancel_request(self, request_id: str, **kwargs: Any) -> Any:
        return _empty_stub(id=request_id, status="cancelled")

    # -- Admin: quotas -----------------------------------------------------------

    def list_quotas(self, **kwargs: Any) -> list[Any]:
        return []

    def set_quota(self, **kwargs: Any) -> Any:
        return _empty_stub(**kwargs)

    def get_quota(self, quota_id: str) -> Any | None:
        return None

    def delete_quota(self, quota_id: str) -> None:
        pass

    # -- Admin: credentials ------------------------------------------------------

    def list_credentials(self, **kwargs: Any) -> list[Any]:
        return []

    def get_credential(self, credential_id: str) -> Any | None:
        return None

    def register_credential(self, **kwargs: Any) -> Any:
        return _empty_stub(id="stub-cred", source=kwargs.get("source", "demo"), tenant_scope="default")

    def revoke_credential(self, credential_id: str) -> None:
        pass

    # -- Admin: audit ------------------------------------------------------------

    def list_audit_events(self, **kwargs: Any) -> list[Any]:
        return []

    # -- Intelligence / search (4a) ----------------------------------------------

    def search(self, q: str = "", **kwargs: Any) -> dict[str, Any]:
        """Search the local catalog cache with faceted filters.

        Shares the same data source as ``list_assets`` so the web Search page
        returns the same assets as the Assets page.

        An empty query or ``"*"`` matches all assets (wildcard).
        """
        results = self.list_assets()

        # -- score enrichment (Phase 4 intelligence) ----------------------------
        # Compute actual scores for all results using the local scoring engine so
        # the Search page shows real 0-100 scores instead of all 0.00.
        try:
            from ...cataloging.catalog import _enrich_entries_local
            _enrich_entries_local(results, include_scores=True, include_scan=False, warnings=[])
        except Exception:
            pass

        # -- free-text filter --------------------------------------------------
        if q and q != "*":
            results = [
                a for a in results
                if _text_matches_asset(a, q)
            ]

        # Compute relevance score for free-text matches (before faceted filtering)
        if q and q != "*":
            needle = q.lower()
            for a in results:
                # Boost score based on match quality (best-effort TF-like scoring)
                boost = 0.0
                rid = (_field_val(a, "repo_id") or "").lower()
                if needle == rid:
                    boost = 5.0        # exact repo_id match
                elif needle in rid:
                    boost = 3.0         # partial repo_id match
                elif any(needle in (t or "").lower() for t in (_field_val(a, "tags") or [])):
                    boost = 2.0         # tag match
                if boost > 0:
                    sc = _field_val(a, "score")
                    if isinstance(sc, dict):
                        sc["score"] = min(100, sc.get("score", 0) + boost)
                    else:
                        _set_field(a, "score", max(sc or 0.0, boost))

        # -- faceted filters ---------------------------------------------------
        if src := (kwargs.get("source") or "").strip():
            results = [a for a in results if _field_val(a, "source") == src]
        if rt := (kwargs.get("resource_type") or "").strip():
            results = [a for a in results if _field_val(a, "repo_type") == rt]
        if lic := (kwargs.get("license") or "").strip():
            results = [a for a in results if (_field_val(a, "license") or "").lower() == lic.lower()]
        if rl := (kwargs.get("risk_level") or "").strip():
            results = [a for a in results if _field_val(a, "risk_level") == rl]
        if st := (kwargs.get("operational_state") or "").strip():
            results = [a for a in results if _field_val(a, "operational_state") == st]
        if tags_filter := kwargs.get("tags"):
            if isinstance(tags_filter, str):
                tags_filter = [t.strip() for t in tags_filter.split(",") if t.strip()]
            if tags_filter:
                results = [a for a in results if any(t in (_field_val(a, "tags") or []) for t in tags_filter)]

        # -- sort --------------------------------------------------------------
        def _score_val(item) -> float:
            sc = _field_val(item, "score")
            if isinstance(sc, dict):
                return float(sc.get("score", 0))
            return float(sc or 0)

        sort_raw = (kwargs.get("sort") or "").strip()
        if sort_raw:
            descending = sort_raw.startswith("-")
            sort_key = sort_raw[1:] if descending else sort_raw
            if sort_key == "score":
                results = sorted(results, key=_score_val, reverse=descending)
            elif sort_key in ("size", "file_count"):
                results = sorted(results, key=lambda a: _field_val(a, sort_key) or 0, reverse=descending)
            else:
                results = sorted(results, key=lambda a: _field_val(a, sort_key) or "", reverse=descending)
        elif q and q != "*":
            # Default: sort by relevance score when there's a query
            results = sorted(results, key=_score_val, reverse=True)

        # -- pagination --------------------------------------------------------
        try:
            page = max(1, int(kwargs.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = max(1, min(100, int(kwargs.get("page_size", 20))))
        except (ValueError, TypeError):
            page_size = 20

        total = len(results)
        start = (page - 1) * page_size
        paged = results[start : start + page_size]

        # -- facets (computed from the FULL filtered set, not just the page) ---
        def _facet_counts(key: str, default: str = "unknown", top_k: int | None = None):
            counts: dict[str, int] = {}
            for a in results:
                val = _field_val(a, key) or default
                counts[val] = counts.get(val, 0) + 1
            items = [{"value": k, "count": v} for k, v in counts.items()]
            items.sort(key=lambda x: x["count"], reverse=True)
            return items[:top_k] if top_k else items

        facets: dict[str, list[dict]] = {
            "source": _facet_counts("source"),
            "license": _facet_counts("license", "(none)"),
            "repo_type": _facet_counts("repo_type"),
        }
        # tags facet (top 30)
        _tag_counts: dict[str, int] = {}
        for a in results:
            for t in (_field_val(a, "tags") or []):
                _tag_counts[t] = _tag_counts.get(t, 0) + 1
        facets["tags"] = sorted(
            [{"value": k, "count": v} for k, v in _tag_counts.items()],
            key=lambda x: x["count"], reverse=True,
        )[:30]

        # -- convert to search result shape ------------------------------------
        search_results = [
            {
                "asset_id": _field_val(a, "id"),
                "source": _field_val(a, "source"),
                "repo_type": _field_val(a, "repo_type"),
                "repo_id": _field_val(a, "repo_id"),
                "revision": _field_val(a, "revision"),
                "license": _field_val(a, "license"),
                "tags": _field_val(a, "tags") or [],
                "score": _score_val(a),
            }
            for a in paged
        ]

        return {
            "results": search_results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "facets": facets,
        }

    def get_risk_trends(self, period: str = "30d") -> Any:
        """Derive a simple risk-trends snapshot from the local cache.

        Counts risk signals across cached assets:
        - high: assets missing license + no files
        - medium: assets with missing license OR empty cache entries
        - low: assets with large file counts (> 50 files, harder to audit)
        """
        assets = self.list_assets()
        high = 0
        medium = 0
        low = 0
        for a in assets:
            lic = _field_val(a, "license")
            fc = _field_val(a, "file_count") or 0
            missing_license = not lic
            empty_cache = fc == 0
            large_file_count = fc > 50

            if missing_license and empty_cache:
                high += 1
            elif missing_license or empty_cache:
                medium += 1
            elif large_file_count:
                low += 1

        total = high + medium + low
        if total == 0:
            trend_direction = "stable"
        elif high > 0:
            trend_direction = "worsening"
        else:
            trend_direction = "improving"

        return _empty_stub(
            period=period,
            total_findings=total,
            high_severity=high,
            medium_severity=medium,
            low_severity=low,
            trend_direction=trend_direction,
        )

    def get_usage_popularity(self, asset_id: str = "") -> list[Any]:
        """Derive simple usage-popularity stats from the local cache.

        Each cached asset gets a basic popularity score based on:
        - download_count: derived from file count (proxy for real downloads)
        - popularity_score: 0.0 - 1.0, based on total cached size
        """
        assets = self.list_assets()
        if not assets:
            return []

        max_size = max((_field_val(a, "size") or 0) for a in assets) or 1
        results = []
        for a in assets:
            size = _field_val(a, "size") or 0
            fc = _field_val(a, "file_count") or 0
            download_count = max(fc, 1)  # at least 1 if cached
            popularity_score = round(min(size / max_size, 1.0), 3) if max_size > 0 else 0.0
            results.append(_empty_stub(
                asset_id=_field_val(a, "id") or "",
                download_count=download_count,
                popularity_score=popularity_score,
            ))
        return sorted(results, key=lambda x: x.popularity_score, reverse=True)

    def get_recommendations(self, asset_id: str, limit: int = 5) -> list[Any]:
        return []

    def get_alternatives(self, asset_id: str, limit: int = 5) -> list[Any]:
        return []

    def compute_admission_score(self, asset_id: str) -> Any:
        return _empty_stub(asset_id=asset_id, score=0.0, components={}, evidence={})

    def get_asset_graph(self, asset_id: str, depth: int = 1) -> Any:
        return _empty_stub(asset_id=asset_id, relations=[], metadata={})

    def generate_compliance_report(self, title: str = "", format: str = "json") -> Any:
        return _empty_stub(title=title, generated_at="", format=format, summary="No data available in dev mode.", evidence=[])

    def get_stale_assets(self, threshold_days: int = 90) -> list[Any]:
        return []

    def get_cost_recommendations(self) -> list[Any]:
        return []

    # -- Reproducibility extras --------------------------------------------------

    def resolve_approved(self, asset_id: str) -> Any | None:
        return None

    def record_usage_event(self, **kwargs: Any) -> None:
        pass

    def compute_scores(self, **kwargs: Any) -> list[Any]:
        return []


__all__ = ["DevNullServices"]
