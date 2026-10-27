"""Async worker queue abstraction for modely-worker — Phase 4 infrastructure.

Defines a protocol for asynchronous task execution that can be backed by
an in-process runner (MVP), RQ, or Celery in production.

The sync LocalMirrorWorker from Phase 1 remains the core execution unit;
this module adds queue/dispatch semantics so the same worker can run
behind a future queue backend without changing sync-job orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class TaskQueue(Protocol):
    """Protocol for a background task queue (RQ, Celery, in-process)."""

    def enqueue(self, func: Callable, *args, **kwargs) -> str:
        """Enqueue a task for async execution. Returns a job/task ID."""
        ...

    def get_result(self, task_id: str) -> dict | None:
        """Poll for a task result. Returns None if not yet complete."""
        ...


@dataclass
class WorkerTask:
    """A serializable task description that can be enqueued."""

    task_id: str = ""
    task_type: str = ""  # sync, scan, report, index, lifecycle, cost, compliance
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: dict | None = None
    error: str | None = None


class InProcessTaskQueue:
    """Deterministic in-process task queue for MVP and testing.

    Tasks execute synchronously in the calling thread.  This is the
    default backend until RQ/Celery is deployed in production.
    """

    def __init__(self):
        self._results: dict[str, dict] = {}
        self._counter = 0

    def enqueue(self, func: Callable, *args, **kwargs) -> str:
        self._counter += 1
        task_id = f"task_{self._counter}"
        try:
            result = func(*args, **kwargs)
            self._results[task_id] = {"status": "completed", "result": result.to_dict() if hasattr(result, "to_dict") else result}
        except Exception as exc:
            self._results[task_id] = {"status": "failed", "error": str(exc)}
        return task_id

    def get_result(self, task_id: str) -> dict | None:
        return self._results.get(task_id)


def enqueue_sync_job(job: Any, *, queue: TaskQueue, worker) -> str:
    """Enqueue a sync job on the worker queue."""
    return queue.enqueue(worker.run, job)


def enqueue_scan_job(asset_id: str, *, queue: TaskQueue) -> str:
    """Enqueue a scan job for an asset."""
    return queue.enqueue(lambda: {"asset_id": asset_id, "status": "scanned"})


def enqueue_report_job(report_type: str, *, queue: TaskQueue, **params) -> str:
    """Enqueue a report generation job."""
    return queue.enqueue(lambda: {"report_type": report_type, "status": "generated", "params": params})


__all__ = [
    "InProcessTaskQueue",
    "TaskQueue",
    "WorkerTask",
    "enqueue_sync_job",
    "enqueue_scan_job",
    "enqueue_report_job",
]
