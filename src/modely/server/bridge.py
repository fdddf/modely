"""Server ↔ Worker bridge — synchronous invocation.

Connects Worker functions as injectable services so Server route handlers
can call them directly without a message queue.  Designed for single-node
and development deployments; upgrade to RQ/Celery for production.
"""

from __future__ import annotations

from typing import Any

from .app import ModelyServerApp


def bridge_sync_worker(
    app: ModelyServerApp,
    *,
    worker: Any = None,
    adapter: Any = None,
    storage: Any = None,
    repository: Any = None,
) -> None:
    """Inject a ``LocalMirrorWorker`` into *app* as ``app.services["sync_worker"]``.

    When ``sync_worker`` is present in services, the ``create_sync_job`` route
    will execute the job synchronously after creation instead of deferring to
    an external queue.

    Usage::

        from modely.server.app import create_app
        from modely.server.bridge import bridge_sync_worker

        app = create_app(repository=repo)
        bridge_sync_worker(app, adapter=fixture_adapter, storage=local_storage, repository=repo)
    """
    from ..syncing.workers import LocalMirrorWorker

    if worker is not None:
        app.services["sync_worker"] = worker
    elif adapter is not None and storage is not None:
        app.services["sync_worker"] = LocalMirrorWorker(
            adapter=adapter, storage=storage, repository=repository
        )


def bridge_expiry_worker(app: ModelyServerApp) -> None:
    """Inject the approval expiry worker function into *app* as
    ``app.services["expiry_worker"]``.

    Governance routes can then call ``run_approval_expiry_worker()``
    synchronously (e.g. on a ``POST /admin/expire`` endpoint).
    """
    from ..syncing.workers import run_approval_expiry_worker

    app.services["expiry_worker"] = run_approval_expiry_worker


__all__ = ["bridge_expiry_worker", "bridge_sync_worker"]
