"""Catalog route adapters for Phase 1b/2b enterprise API.

Phase 2b adds visibility-filtered catalog list/detail, governance enrichment,
download authorization checks, and audit event emission.
"""

from __future__ import annotations

from ..schemas.assets import (
    AssetDownloadUrlResponse,
    AssetFileResponse,
    AssetListResponse,
    AssetResponse,
    ScanSummaryResponse,
)
from ..schemas.envelopes import Pagination, error_response, success_response

# Canonical sortable fields matching the domain model.
_SORTABLE_FIELDS: set[str] = {"source", "repo_type", "repo_id", "revision", "license", "operational_state", "visibility", "size", "file_count"}


def list_assets(service, *, request_id: str = "req_unknown", principal=None, **query_params: str) -> dict:
    """Return assets from an injected catalog service, wrapped in the API response envelope.

    Phase 2b: applies visibility filtering via ``check_visibility`` on each
    asset when a ``principal`` is provided.

    When ``principal`` is ``None`` (Phase 1 / diagnostic mode), all assets
    are returned unfiltered — this preserves backward compatibility for
    existing tests and internal tooling. Production servers should always
    inject a principal via the auth middleware.

    Supported query parameters (Phase 1 minimum):
        q: free-text search
        source: filter by source (hf, ms, github, etc.)
        resource_type: filter by resource type (model, dataset, tool)
        operational_state: filter by operational state
        license: filter by license identifier
        visibility: filter by visibility level (organization, workspace, team, project, private, restricted)
        page: 1-based page number (default 1)
        page_size: items per page (default 20)
        sort: field name, optional '-' prefix for descending
    """

    raw = list(service.list_assets())

    # -- visibility filtering (Phase 2b) -----------------------------------------
    # Only apply visibility filtering when a principal is explicitly provided.
    # When principal is None (Phase 1 compat / test mode), return all assets.
    if principal is not None:
        from ...cataloging.visibility import check_visibility

        raw = [a for a in raw if check_visibility(principal, a)]

    # -- filtering ----------------------------------------------------------------
    # Support query-param based single-asset lookup (for IDs with / and :)
    if id_filter := query_params.get("id", "").strip():
        # Normalize -- → / (cache dir convention) for matching
        normalized_filter = id_filter.replace("--", "/")
        raw = [a for a in raw if _field(a, "id") == normalized_filter or _field(a, "id") == id_filter]
        if len(raw) == 1:
            asset = raw[0]
            response = _asset_to_response(asset)
            asset_dict = asset.to_dict() if hasattr(asset, "to_dict") else dict(asset)
            scan_evidence, risk_level, policy_status, _ = _evaluate_asset_policy(asset_dict)
            governance = {
                "visibility": response.visibility,
                "access_rules": _build_access_rules_summary(asset_dict),
                "policy_status": policy_status,
                "risk_level": risk_level,
                "approval_state": _extract_approval_state(asset_dict),
            }
            result = response.to_dict()
            result["governance"] = governance
            return success_response(result, request_id=request_id)
        elif len(raw) == 0:
            return error_response("not_found", f"Asset not found: {id_filter}", request_id=request_id)

    q = query_params.get("q", "").strip()
    if q and q != "*":
        raw = [a for a in raw if _text_matches(a, q)]
    if src := query_params.get("source", "").strip():
        raw = [a for a in raw if _field(a, "source") == src]
    if rt := query_params.get("resource_type", "").strip():
        raw = [a for a in raw if _field(a, "repo_type") == rt]
    if os_ := query_params.get("operational_state", "").strip():
        raw = [a for a in raw if _field(a, "operational_state") == os_]
    if lic := query_params.get("license", "").strip():
        raw = [a for a in raw if (_field(a, "license") or "").lower() == lic.lower()]
    if vis := query_params.get("visibility", "").strip():
        raw = [a for a in raw if _field(a, "visibility") == vis]

    # -- sorting ------------------------------------------------------------------
    sort_raw = query_params.get("sort", "").strip()
    if sort_raw:
        descending = sort_raw.startswith("-")
        sort_key = sort_raw[1:] if descending else sort_raw
        if sort_key in _SORTABLE_FIELDS:
            # Use 0 for numeric fields, "" for string fields
            _numeric = {"size", "file_count"}
            if sort_key in _numeric:
                raw = sorted(raw, key=lambda a: _field(a, sort_key) or 0, reverse=descending)
            else:
                raw = sorted(raw, key=lambda a: _field(a, sort_key) or "", reverse=descending)

    # -- pagination ---------------------------------------------------------------
    try:
        page = max(1, int(query_params.get("page", "1")))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = max(1, min(100, int(query_params.get("page_size", "20"))))
    except (ValueError, TypeError):
        page_size = 20

    total = len(raw)
    start = (page - 1) * page_size
    paged = raw[start : start + page_size]

    assets = [_asset_to_response(a) for a in paged]
    pagination = Pagination(total=total, page=page, page_size=page_size)
    summary = _build_assets_summary(raw)

    # -- audit: asset.search --------------------------------------------------------
    if principal is not None:
        from ...domain.audit_events import AUDIT_CATALOG_ASSET_SEARCH
        from ...governance.audit import emit_audit_event

        tenant_scope_dict: dict | None = None
        if hasattr(principal, "tenant_scope") and principal.tenant_scope is not None:
            ts = principal.tenant_scope
            if hasattr(ts, "to_dict"):
                tenant_scope_dict = ts.to_dict()
            elif hasattr(ts, "organization_id"):
                tenant_scope_dict = {
                    "organization_id": getattr(ts, "organization_id", ""),
                    "workspace_id": getattr(ts, "workspace_id", ""),
                    "project_id": getattr(ts, "project_id", ""),
                    "environment_id": getattr(ts, "environment_id", ""),
                }

        emit_audit_event(
            AUDIT_CATALOG_ASSET_SEARCH,
            resource=query_params.get("q", "") or (query_params.get("source", "") or "all"),
            status="ok",
            actor=getattr(principal, "id", None),
            metadata={
                "request_id": request_id,
                "total": total,
                "page": page,
                "page_size": page_size,
                "filters": {
                    k: v for k, v in query_params.items()
                    if k in ("q", "source", "resource_type", "operational_state", "license", "visibility", "sort")
                    and v
                },
            },
            tenant_scope=tenant_scope_dict,
        )

    return success_response({
        "assets": assets,
        "total": total,
        "summary": summary,
    }, request_id=request_id, pagination=pagination)


# -- summary helper (computed from the FULL filtered list) ---------------
def _build_assets_summary(raw_assets):
    """Build aggregate summary stats from a list of asset objects."""
    total_size = 0
    total_files = 0
    sources: dict[str, int] = {}
    types: dict[str, int] = {}
    licensed = 0
    statuses: dict[str, int] = {}
    risks: dict[str, int] = {}
    for a in raw_assets:
        total_size += _field(a, "size") or 0
        total_files += _field(a, "file_count") or 0
        s = _field(a, "source") or "unknown"
        sources[s] = sources.get(s, 0) + 1
        t = _field(a, "repo_type") or "unknown"
        types[t] = types.get(t, 0) + 1
        if _field(a, "license"):
            licensed += 1
        st = _field(a, "operational_state") or "discovered"
        statuses[st] = statuses.get(st, 0) + 1
        rl = _derive_risk_level(a)
        risks[rl] = risks.get(rl, 0) + 1
    return {
        "total_count": len(raw_assets),
        "total_size": total_size,
        "total_files": total_files,
        "licensed_count": licensed,
        "by_source": sources,
        "by_type": types,
        "by_status": statuses,
        "by_risk": risks,
    }


def _derive_risk_level(item) -> str:
    """Derive a basic risk level from asset metadata for display purposes.

    Uses the same license risk classification as the governance policy engine
    so the list page and detail page agree on risk levels.  When an asset has
    no license the risk is driven by other signals (empty cache, no tags).
    """
    from ...governance.policy_engine import _LICENSE_RISK

    lic = (_field(item, "license") or "").strip()
    fc = _field(item, "file_count") or 0
    tags = _field(item, "tags") or []

    # Classify license risk using the same table as the policy engine
    license_risk = _LICENSE_RISK.get(lic.lower(), "high") if lic else None

    empty_cache = fc == 0
    no_tags = not tags

    if license_risk is not None:
        # Bump risk up one level for missing tags / empty cache
        risk_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        base = risk_order.get(license_risk, 2)
        if (empty_cache or no_tags) and base < 3:
            base += 1
        reversed_order = {v: k for k, v in risk_order.items()}
        return reversed_order.get(base, "medium")

    # No license at all
    if empty_cache and no_tags:
        return "high"
    if empty_cache or no_tags:
        return "medium"
    if fc > 50:
        return "low"
    return "unknown"


def _default_policy_profile():
    """Return a lightweight default PolicyProfile for dev-mode governance.

    Evaluates basic checks: license presence, copyleft risk, source
    trustworthiness, and file count sanity.  All rules use ``warn_only``
    mode so nothing is blocked — but the risk_level and policy_status
    will reflect real signals.
    """
    from datetime import datetime, timezone
    from ...domain.policies import PolicyProfile, PolicyRule

    return PolicyProfile(
        id="default-dev",
        name="Default Dev Policy",
        version="1.0.0-dev",
        tenant_scope="",
        environment="dev",
        default_warning_mode="warn_only",
        effective_from=datetime.now(timezone.utc).isoformat(),
        rules=[
            PolicyRule(
                id="rule-license-required",
                category="license",
                action="warn",
                match={"condition": "missing", "field": "license"},
                description="License must be specified",
                severity="high",
            ),
            PolicyRule(
                id="rule-no-copyleft",
                category="license",
                action="warn",
                match={"condition": "copyleft"},
                description="Copyleft licenses (GPL, AGPL) may require legal review",
                severity="medium",
            ),
            PolicyRule(
                id="rule-source-trusted",
                category="unsafe_artifact",
                action="warn",
                match={"condition": "untrusted_source"},
                description="Assets from untrusted sources require review",
                severity="medium",
            ),
            PolicyRule(
                id="rule-no-executables",
                category="executable_binary",
                action="warn",
                match={"condition": "has_executables"},
                description="Repositories with executable binaries should be reviewed",
                severity="low",
            ),
        ],
    )


def get_asset(service, asset_id: str, *, request_id: str = "req_unknown", principal=None) -> dict:
    """Return one asset by id, wrapped in the API response envelope.

    Phase 2b visibility check: a principal that cannot discover the asset
    receives a ``not_found`` error (same response as a nonexistent asset,
    to avoid leaking presence).  Platform Admins bypass visibility checks.

    The response includes catalog detail governance enrichment:
      - ``visibility``: the asset's visibility level (organization, workspace, team, project, private, restricted).
      - ``access_rules``: baseline access rule summary (derived from visibility + tenant scope).
      - ``policy_status``: placeholder for Phase 2d policy evaluation (current: "not_evaluated").
      - ``risk_level``: placeholder for Phase 2d scan findings (current: "unknown"; updated by scan results).
      - ``approval_state``: placeholder for Phase 2c approval lifecycle (current: "none").

    Additional governance fields deferred to later phases:
      - scan findings (Phase 2d): ``scan_summary`` with finding counts, severity breakdown.
      - approval history (Phase 2c): ``approval_request`` with requester, reviewer, status trail.
      - policy-hit records (Phase 2d): ``policy_decisions`` with outcome and matched rules.
      - audit history (Phase 2e): ``audit_trail`` with recent events scoped to this asset.

    Returns a ``not_found`` error envelope when the asset is absent.
    """

    asset = service.get_asset(asset_id)
    if asset is None:
        return error_response("not_found", f"Asset not found: {asset_id}", request_id=request_id)

    # -- visibility check (Phase 2b) ----------------------------------------------
    if principal is not None:
        from ...cataloging.visibility import check_visibility

        if not check_visibility(principal, asset):
            return error_response("not_found", f"Asset not found: {asset_id}", request_id=request_id)

    asset_dict = asset.to_dict() if hasattr(asset, "to_dict") else dict(asset)

    response = _asset_to_response(asset_dict)

    # -- governance enrichment ----------------------------------------------------
    # Phase 2d: policy engine evaluation with real scan evidence
    scan_evidence, risk_level, policy_status, policy_reasons = _evaluate_asset_policy(
        asset_dict=asset_dict, principal=principal
    )

    governance: dict = {
        "visibility": response.visibility,
        "access_rules": _build_access_rules_summary(asset_dict),
        "policy_status": policy_status,
        "risk_level": risk_level,
        "approval_state": _extract_approval_state(asset_dict),
    }

    result = response.to_dict()
    result["governance"] = governance

    # -- audit: asset.view ----------------------------------------------------------
    if principal is not None:
        from ...domain.audit_events import AUDIT_CATALOG_ASSET_VIEW
        from ...governance.audit import emit_audit_event

        tenant_scope_dict: dict | None = None
        if hasattr(principal, "tenant_scope") and principal.tenant_scope is not None:
            ts = principal.tenant_scope
            if hasattr(ts, "to_dict"):
                tenant_scope_dict = ts.to_dict()
            elif hasattr(ts, "organization_id"):
                tenant_scope_dict = {
                    "organization_id": getattr(ts, "organization_id", ""),
                    "workspace_id": getattr(ts, "workspace_id", ""),
                    "project_id": getattr(ts, "project_id", ""),
                    "environment_id": getattr(ts, "environment_id", ""),
                }

        emit_audit_event(
            AUDIT_CATALOG_ASSET_VIEW,
            resource=asset_id,
            status="ok",
            actor=getattr(principal, "id", None),
            metadata={
                "request_id": request_id,
                "source": response.source,
                "repo_type": response.repo_type,
                "repo_id": response.repo_id,
                "visibility": response.visibility,
                "risk_level": risk_level,
                "policy_status": policy_status,
            },
            tenant_scope=tenant_scope_dict,
        )

    return success_response(result, request_id=request_id)


def get_asset_files(service, asset_id: str, *, request_id: str = "req_unknown", principal=None, **query_params: str) -> dict:
    """Return the file list for an asset, wrapped in the API response envelope.

    Phase 2b: applies visibility filtering before returning file data.
    A principal that cannot discover the asset receives ``not_found``.

    Returns a ``not_found`` error envelope when the asset is absent.
    """

    asset = service.get_asset(asset_id)
    if asset is None:
        return error_response("not_found", f"Asset not found: {asset_id}", request_id=request_id)

    # -- visibility check (Phase 2b) ----------------------------------------------
    if principal is not None:
        from ...cataloging.visibility import check_visibility

        if not check_visibility(principal, asset):
            return error_response("not_found", f"Asset not found: {asset_id}", request_id=request_id)

    files_raw = []
    if hasattr(service, "list_asset_files"):
        files_raw = list(service.list_asset_files(asset_id))
    elif hasattr(service, "files") and hasattr(service.files, "list_files"):
        files_raw = list(service.files.list_files(asset_id))

    files = [_file_to_response(f) for f in files_raw]
    return success_response({"asset_id": asset_id, "files": files, "count": len(files)}, request_id=request_id)


def get_asset_download_url(service, asset_id: str, *, request_id: str = "req_unknown", principal=None) -> dict:
    """Return a download URL for an asset, with Phase 2b authorization and policy check.

    Phase 2b additions:
      - Visibility check: principals that cannot discover the asset get ``not_found``.
      - Download authorization check: principals without ``asset:download``
        permission receive ``permission_denied``.
      - Governance policy check: evaluates scan evidence and approval state against
        the active policy profile.
        - ``block`` -> returns ``policy_blocked`` diagnostic response.
        - ``require_approval`` with no valid approval -> returns ``approval_required``.
        - ``warn`` -> allows download but includes warning in response metadata.
      - Audit event emission: every authorized access for a download URL is
        recorded via ``record_audit_event``.
      - Signed URL generation with short TTL via ``generate_signed_url``.

    Without a principal, falls back to Phase 1 diagnostic mode.

    Returns a ``not_found`` error envelope when the asset is absent.
    """

    asset = service.get_asset(asset_id)
    if asset is None:
        return error_response("not_found", f"Asset not found: {asset_id}", request_id=request_id)

    asset_dict = asset.to_dict() if hasattr(asset, "to_dict") else dict(asset)
    metadata = asset_dict.get("metadata", {})

    # -- visibility check (Phase 2b) ----------------------------------------------
    if principal is not None:
        from ...cataloging.visibility import check_visibility

        if not check_visibility(principal, asset):
            return error_response("not_found", f"Asset not found: {asset_id}", request_id=request_id)

    # -- download authorization check (Phase 2b) ---------------------------------
    if principal is not None:
        from ...storage.download_urls import authorize_download

        if not authorize_download(principal, asset_id):
            return error_response(
                "permission_denied",
                f"Principal {principal.id} is not authorized to download asset {asset_id}",
                request_id=request_id,
            )

    # -- governance policy check (Phase 2 step 1) ---------------------------------
    if principal is not None:
        from ...governance.policy_engine import evaluate_governance_policy
        from ...storage.download_urls import (
            _asset_to_policy_dict,
            _has_valid_approval,
            _principal_to_policy_dict,
        )

        policy_asset = _asset_to_policy_dict(asset)
        policy_principal = _principal_to_policy_dict(principal)
        scan_evidence = policy_asset.get("scan_evidence", {}) or {}
        approval_state = policy_asset.get("approval_state", {}) or {}

        policy_decision = evaluate_governance_policy(
            principal=policy_principal,
            asset=policy_asset,
            action="asset:download",
            scan_evidence=scan_evidence,
            approval_state=approval_state,
        )

        if policy_decision.blocked:
            return error_response(
                "policy_blocked",
                f"Download of asset {asset_id} is blocked by governance policy: "
                f"{'; '.join(policy_decision.reasons)}",
                request_id=request_id,
                details={
                    "policy_outcome": "block",
                    "matched_rule_ids": policy_decision.matched_rule_ids,
                    "reasons": policy_decision.reasons,
                    "policy_version": policy_decision.policy_version,
                },
            )

        if policy_decision.outcome == "require_approval" and not _has_valid_approval(approval_state):
            return error_response(
                "approval_required",
                f"Download of asset {asset_id} requires approval: "
                f"{'; '.join(policy_decision.reasons)}",
                request_id=request_id,
                details={
                    "policy_outcome": "require_approval",
                    "matched_rule_ids": policy_decision.matched_rule_ids,
                    "reasons": policy_decision.reasons,
                    "policy_version": policy_decision.policy_version,
                },
            )

        # Record the policy outcome for audit metadata
        policy_outcome = policy_decision.outcome
        policy_warnings = policy_decision.reasons if policy_decision.outcome == "warn" else []
    else:
        policy_outcome = "not_evaluated"
        policy_warnings = []

    # -- signed URL generation (Phase 2b) ----------------------------------------
    # Generate a signed URL with a short TTL for authorized principals.
    # In diagnostic mode (no principal), falls back to local reference.
    signed_url = None
    if principal is not None:
        from ...storage.download_urls import generate_signed_url

        storage_path = metadata.get("local_path") or metadata.get("storage_key") or ""
        signed_url = generate_signed_url(
            asset_id,
            principal_id=principal.id,
            storage_path=storage_path,
            shared_secret="",  # Phase 2b dev mode: no shared secret
            ttl_seconds=300,   # 5-minute TTL for freshness/short link
        )

    # -- audit event emission (Phase 2b + Phase 2 step 1) --------------------------
    if principal is not None:
        from ...governance.audit import record_audit_event

        audit_meta: dict = {
            "request_id": request_id,
            "principal_id": principal.id,
            "roles": getattr(principal, "roles", []),
            "policy_outcome": policy_outcome,
        }
        if policy_warnings:
            audit_meta["policy_warnings"] = policy_warnings

        record_audit_event(
            "asset.download_url_requested",
            resource=asset_id,
            status="ok",
            metadata=audit_meta,
        )

    if signed_url is not None:
        response_meta: dict = {
            "authorized": True,
            "authorization_phase": "2b",
            "ttl_seconds": 300,
            "policy_outcome": policy_outcome,
        }
        if policy_warnings:
            response_meta["policy_warnings"] = policy_warnings

        url_data = AssetDownloadUrlResponse(
            asset_id=asset_id,
            download_mode="signed_url",
            url_ref=signed_url.url,
            manifest_ref=metadata.get("manifest", {}).get("root") if isinstance(metadata.get("manifest"), dict) else None,
            checksum_ref=asset_dict.get("checksum"),
            expires_at=signed_url.expires_at,
            security_warning=(
                "; ".join(policy_warnings) if policy_warnings
                else ""
            ),
            metadata=response_meta,
        )
        return success_response(url_data.to_dict(), request_id=request_id)

    # Fallback: diagnostic mode (Phase 1)
    url_data = AssetDownloadUrlResponse(
        asset_id=asset_id,
        download_mode="local_reference",
        url_ref=metadata.get("local_path") or metadata.get("storage_key") or "redacted",
        manifest_ref=metadata.get("manifest", {}).get("root") if isinstance(metadata.get("manifest"), dict) else None,
        checksum_ref=asset_dict.get("checksum"),
        metadata={"diagnostic_mode": True, "production_authorization_deferred": True},
    )
    return success_response(url_data.to_dict(), request_id=request_id)


def _asset_to_response(item) -> AssetResponse:
    """Normalise an asset dict or DTO into a stable AssetResponse."""
    if hasattr(item, "to_dict") and not isinstance(item, dict):
        item = item.to_dict()
    identity = item.get("identity", {})
    meta = item.get("metadata", {}) or {}
    source = item.get("source") or identity.get("source", "")
    repo_type = item.get("repo_type") or item.get("resource_type") or identity.get("repo_type", "")
    repo_id = item.get("repo_id") or identity.get("repo_id", "")
    revision = item.get("revision") or identity.get("revision")
    # License and tags may be top-level or nested inside metadata (cache enrichment)
    license_val = item.get("license") or meta.get("license")
    tags_val = list(item.get("tags") or meta.get("tags") or [])
    risk_level = item.get("risk_level") or _derive_risk_level(item)
    return AssetResponse(
        id=item.get("id", ""),
        source=source,
        repo_type=repo_type,
        repo_id=repo_id,
        revision=revision,
        license=license_val,
        tags=tags_val,
        size=item.get("size", 0),
        file_count=item.get("file_count", 0),
        checksum=item.get("checksum"),
        operational_state=item.get("operational_state", "discovered"),
        visibility=item.get("visibility", "organization"),
        metadata={**dict(meta), "risk_level": risk_level},
    )


def _file_to_response(item) -> dict:
    """Normalise a file dict or DTO into a stable dict."""
    if hasattr(item, "to_dict") and not isinstance(item, dict):
        item = item.to_dict()
    return AssetFileResponse(
        path=item.get("path", ""),
        size=item.get("size", 0),
        sha256=item.get("sha256"),
        file_type=item.get("file_type", "blob"),
        mime_type=item.get("mime_type"),
        mtime=item.get("mtime"),
        storage_key=item.get("storage_key") or item.get("local_path"),
        manifest_ref=None,
        metadata=dict(item.get("metadata", {})),
    ).to_dict()


def _field(item, key: str):
    """Extract a field from a dict or DTO item."""
    if hasattr(item, "to_dict") and not isinstance(item, dict):
        item = item.to_dict()
    identity = item.get("identity", {})
    meta = item.get("metadata", {}) or {}
    return item.get(key) or meta.get(key) or identity.get(key)


def _text_matches(item, query: str) -> bool:
    """Check if any text fields in an asset item contain the query (case-insensitive)."""
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


def _build_access_rules_summary(asset_dict: dict) -> dict:
    """Build a baseline access rules summary derived from visibility and tenant scope.

    The summary describes who can discover and download this asset based on its
    visibility label.  Full RBAC/policy evaluation is deferred to the governance
    and permission subsystems.
    """
    visibility = _field(asset_dict, "visibility") or "organization"
    tenant_scope = asset_dict.get("tenant_scope")

    rules = {"visibility": visibility, "discoverable": True, "downloadable": False, "scope_required": None}

    if visibility == "private":
        rules["discoverable"] = False   # only owner + platform admins
        rules["downloadable"] = False   # requires explicit grant
        rules["scope_required"] = None
    elif visibility == "restricted":
        rules["discoverable"] = False   # only explicitly authorized
        rules["downloadable"] = False
        rules["scope_required"] = None
    elif visibility == "organization":
        rules["discoverable"] = True
        rules["downloadable"] = True    # any org member with asset:download
        rules["scope_required"] = "organization"
    elif visibility == "workspace":
        rules["discoverable"] = True
        rules["downloadable"] = True
        rules["scope_required"] = "workspace"
    elif visibility == "team":
        rules["discoverable"] = True
        rules["downloadable"] = True
        rules["scope_required"] = "team"
    elif visibility == "project":
        rules["discoverable"] = True
        rules["downloadable"] = True
        rules["scope_required"] = "project"

    if tenant_scope:
        rules["tenant_scope"] = tenant_scope

    return rules


def _extract_approval_state(asset_dict: dict) -> str:
    """Extract the approval status from an asset dict.

    Checks ``approval_state`` (dict with ``status`` key) first, then falls
    back to ``approval`` or ``approval_status`` top-level keys.
    """
    approval = asset_dict.get("approval_state")
    if isinstance(approval, dict):
        return str(approval.get("status", "none"))
    if isinstance(approval, str):
        return approval
    for key in ("approval", "approval_status"):
        val = asset_dict.get(key)
        if isinstance(val, dict) and val.get("status"):
            return str(val["status"])
        if isinstance(val, str) and val:
            return val
    return "none"


def _build_scan_evidence(asset_dict: dict) -> dict:
    """Build scan_evidence dict from asset.scan data or asset.scan_evidence field.

    Scans for scan data in the following locations (in priority order):
    1. ``asset_dict["scan_evidence"]`` — already populated
    2. ``asset_dict["scan"]`` — a dict with per-category scan results
    3. ``asset_dict["scan_results"]`` — alternative scan field

    Returns a dict suitable for ``evaluate_governance_policy``.
    """
    # Direct scan_evidence
    evidence = asset_dict.get("scan_evidence")
    if isinstance(evidence, dict) and evidence:
        return dict(evidence)

    # Scan data dict
    for key in ("scan", "scan_results"):
        scan_data = asset_dict.get(key)
        if isinstance(scan_data, dict) and scan_data:
            result: dict[str, Any] = {}
            for category, data in scan_data.items():
                if isinstance(data, dict):
                    result[category] = dict(data)
                elif data is not None:
                    result[category] = {"findings": [data] if isinstance(data, str) else data}
            if result:
                return result

    return {}


def _evaluate_asset_policy(
    asset_dict: dict,
    principal=None,
) -> tuple[dict, str, str, list[str]]:
    """Evaluate governance policy for an asset and return enrichment data.

    Returns a tuple of (scan_evidence, risk_level, policy_status, reasons).

    When ``principal`` is ``None`` (diagnostic mode / listing for admins),
    falls back to ``"not_evaluated"``/``"unknown"`` placeholders.
    """
    scan_evidence = _build_scan_evidence(asset_dict)
    approval_state_raw = _extract_approval_state(asset_dict)

    from ...governance.policy_engine import evaluate_governance_policy
    from ...storage.download_urls import _asset_to_policy_dict, _principal_to_policy_dict

    policy_asset = _asset_to_policy_dict(asset_dict)
    policy_principal = _principal_to_policy_dict(principal) if principal is not None else None
    approval_dict: dict[str, Any] = {}
    if isinstance(asset_dict.get("approval_state"), dict):
        approval_dict = dict(asset_dict["approval_state"])
    else:
        approval_dict = {"status": approval_state_raw}

    decision = evaluate_governance_policy(
        principal=policy_principal,
        asset=policy_asset,
        action="asset:read",
        scan_evidence=scan_evidence,
        approval_state=approval_dict,
        policy_profile=_default_policy_profile(),
    )

    policy_status = decision.outcome
    risk_level = decision.risk_level
    # Fall back to simple heuristic when governance engine returns unknown
    if risk_level == "unknown":
        risk_level = _derive_risk_level(asset_dict)
    reasons = decision.reasons

    return scan_evidence, risk_level, policy_status, reasons


def get_asset_file_preview(service, asset_id: str, *, request_id: str = "req_unknown", file_path: str = "", principal=None) -> dict:
    """Return a safe text preview for a single file within a cached asset.

    GET /api/v1/assets/{id}/files/preview?file_path=config.json

    Only works when the asset has a ``local_path`` pointing to a cached
    directory on disk.  Binary and non-text files return ``previewable:
    false`` with an error message.
    """
    asset = service.get_asset(asset_id)
    if asset is None:
        return error_response("not_found", f"Asset not found: {asset_id}", request_id=request_id)

    # -- visibility check (Phase 2b) ------------------------------------------
    if principal is not None:
        from ...cataloging.visibility import check_visibility

        if not check_visibility(principal, asset):
            return error_response("not_found", f"Asset not found: {asset_id}", request_id=request_id)

    if not file_path:
        return error_response("bad_request", "Missing required query parameter: file_path", request_id=request_id)

    # Extract local directory path from the asset object
    local_dir = ""
    if hasattr(asset, "local_path"):
        local_dir = asset.local_path or ""
    elif hasattr(asset, "get"):
        local_dir = asset.get("local_path", "") or ""
    else:
        local_dir = getattr(asset, "local_path", "") or ""

    if not local_dir:
        return error_response("not_found", "Asset has no local cache directory", request_id=request_id)

    from ..services.file_preview import get_file_preview

    preview = get_file_preview(local_dir, file_path)
    return success_response(preview, request_id=request_id)


__all__ = ["get_asset", "get_asset_download_url", "get_asset_file_preview", "get_asset_files", "list_assets"]
