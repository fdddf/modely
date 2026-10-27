"""modely-server entry point.

Start the enterprise governance API server::

    pip install modely-ai[server]
    python -m modely.server

Or use the console script::

    modely-server
"""

from __future__ import annotations


def main() -> None:
    """Run the modely-server via uvicorn."""
    import uvicorn

    from ..cataloging.repository import InMemoryLocalMirrorRepository
    from ..storage.local import LocalStorageBackend
    from ..syncing.adapters import CompositeSourceAdapter, HfSourceAdapter, ModelScopeSourceAdapter, GitHubSourceAdapter
    from ..syncing.workers import LocalMirrorWorker
    from .app import create_fastapi_app
    from .services import DevNullServices

    repository = InMemoryLocalMirrorRepository()
    service = DevNullServices(repository=repository)

    # Wire sync worker with real network adapters
    import tempfile
    from pathlib import Path
    sync_root = Path(tempfile.gettempdir()) / "modely-sync-dev"
    sync_root.mkdir(parents=True, exist_ok=True)

    adapter = CompositeSourceAdapter(
        adapters={
            "hf": HfSourceAdapter,
            "ms": ModelScopeSourceAdapter,
            "github": GitHubSourceAdapter,
        }
    )
    storage = LocalStorageBackend(root=sync_root)
    worker = LocalMirrorWorker(adapter=adapter, storage=storage, repository=repository)
    service._sync_worker = worker

    app = create_fastapi_app(repository=repository, catalog_service=service)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
