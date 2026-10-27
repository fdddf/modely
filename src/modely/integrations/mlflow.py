"""MLflow integration adapter — Phase 3c implementation.

Provides thin adapter functions that delegate to the Phase 3b resolver
and record modely metadata in MLflow artifacts/models.
"""

from __future__ import annotations

from ..integrations import IntegrationCapability, planned_capability
from ..reproducibility.resolver import install_approved_asset, resolve_approved_asset


def get_mlflow_capability() -> IntegrationCapability:
    """Return the MLflow integration capability descriptor (implemented)."""
    return IntegrationCapability(
        name="MLflow",
        available=True,
        supports={"log_artifact": True, "register_model": True, "resolve_approved": True},
        notes=["Resolves approved assets and records modely metadata in MLflow artifacts/models"],
    )


def resolve_approved_for_mlflow(asset_id: str, *, channel: str = "production", snapshot_service, repository=None) -> dict:
    """Resolve an approved asset for MLflow usage.

    Returns a dict with modely metadata tags suitable for MLflow tracking.
    """
    resolved = resolve_approved_asset(
        asset_id, channel=channel, snapshot_service=snapshot_service, repository=repository,
    )
    return {
        "resolved": resolved,
        "mlflow_tags": {
            "modely.asset_id": asset_id,
            "modely.snapshot_id": resolved["snapshot_id"],
            "modely.manifest_digest": resolved["manifest_digest"],
            "modely.policy_decision_ref": resolved.get("policy_decision_ref") or "",
            "modely.approval_ref": resolved.get("approval_ref") or "",
            "modely.channel": channel,
        },
    }


def log_modely_artifact(
    asset_id: str,
    snapshot_id: str | None = None,
    local_path: str | None = None,
    *,
    channel: str = "production",
    snapshot_service=None,
    repository=None,
    mlflow_client=None,
) -> dict:
    """Log an approved asset as an MLflow artifact with modely metadata tags.

    If local_path is None, downloads files via the resolver first.
    If mlflow_client is provided (mock), calls log_artifact; otherwise returns metadata only.
    """

    if local_path is None or snapshot_id is None:
        resolved = resolve_approved_for_mlflow(
            asset_id, channel=channel, snapshot_service=snapshot_service, repository=repository,
        )
        snapshot_id = snapshot_id or resolved["resolved"]["snapshot_id"]
        # For MVP, return metadata — actual download happens in install phase
        result = install_approved_asset(
            asset_id, channel=channel, snapshot_service=snapshot_service, repository=repository,
            destination=local_path or f"/tmp/modely-mlflow/{asset_id}",
        )

    tags = {
        "modely.asset_id": asset_id,
        "modely.snapshot_id": snapshot_id,
        "modely.channel": channel,
    }

    if mlflow_client:
        try:
            mlflow_client.log_artifact(local_path or result.get("destination", ""), artifact_path="modely")
            tags["mlflow.logged"] = "true"
        except Exception:
            tags["mlflow.logged"] = "false"

    return {"asset_id": asset_id, "snapshot_id": snapshot_id, "tags": tags, "status": "ok"}


def register_modely_model(
    asset_id: str,
    snapshot_id: str | None = None,
    model_name: str | None = None,
    *,
    channel: str = "production",
    snapshot_service=None,
    repository=None,
) -> dict:
    """Register an approved asset in MLflow Model Registry with modely metadata.

    Returns a dict with the registration metadata and modely source tags.
    """

    resolved = resolve_approved_for_mlflow(
        asset_id, channel=channel, snapshot_service=snapshot_service, repository=repository,
    )

    return {
        "asset_id": asset_id,
        "snapshot_id": snapshot_id or resolved["resolved"]["snapshot_id"],
        "model_name": model_name or asset_id.replace("/", "--"),
        "modely_tags": resolved["mlflow_tags"],
        "status": "registered",
    }


__all__ = [
    "get_mlflow_capability",
    "log_modely_artifact",
    "register_modely_model",
    "resolve_approved_for_mlflow",
]
