"""Single-process concurrency gate for expensive background work.

Free-tier containers cannot survive several concurrent Spark/forecast jobs.
This module caps how many heavy jobs (dataset ingestion, forecast training)
run at once *within this process* using a threading semaphore.

Limitations (documented, by design):
- The cap is per process. Two container instances each allow
  ``MAX_CONCURRENT_JOBS`` jobs. For a student/demo deployment on a single
  small instance this is sufficient and avoids Redis/Celery entirely.
- When full, new job requests get HTTP 429 (with ``Retry-After``) instead
  of queueing silently — the frontend surfaces this as a busy state.
"""
import threading

from fastapi import HTTPException

from app.core.config import get_settings


class JobFull(Exception):
    pass


_semaphore: threading.Semaphore | None = None
_lock = threading.Lock()


def _semaphore_for() -> threading.Semaphore:
    global _semaphore
    with _lock:
        if _semaphore is None:
            _semaphore = threading.Semaphore(max(1, get_settings().max_concurrent_jobs))
        return _semaphore


class job_slot:
    """Non-blocking slot acquisition; raises JobFull when all slots are busy."""

    def __init__(self) -> None:
        self._sem = _semaphore_for()
        self.held = False

    def __enter__(self) -> "job_slot":
        if not self._sem.acquire(blocking=False):
            raise JobFull(f"all {get_settings().max_concurrent_jobs} job slots busy")
        self.held = True
        return self

    def __exit__(self, *exc) -> None:
        if self.held:
            self._sem.release()
            self.held = False


def acquire_or_429() -> job_slot:
    """Acquire a job slot or raise HTTP 429. Caller must exit the slot."""
    try:
        return job_slot().__enter__()
    except JobFull as e:
        raise HTTPException(429, {"message": str(e),
                                  "hint": "a job is already running; retry shortly"}) from e


def reset_for_tests() -> None:
    global _semaphore
    with _lock:
        _semaphore = None
