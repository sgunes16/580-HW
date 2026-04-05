from __future__ import annotations

import logging
import threading
import uuid
from typing import Any

from app.services import ingest

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def create_job() -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "status": "queued",
            "progress": 0.0,
            "message": "",
            "error": None,
            "result": None,
        }
    return job_id


def update_job(job_id: str, **kwargs: Any) -> None:
    with _lock:
        if job_id not in _jobs:
            return
        _jobs[job_id].update(kwargs)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        j = _jobs.get(job_id)
        return dict(j) if j else None


def _run(job_id: str, filename: str | None, reset_store: bool) -> None:
    try:
        update_job(
            job_id,
            status="running",
            progress=0.0,
            message="Starting…",
            error=None,
            result=None,
        )

        def cb(pct: float, msg: str) -> None:
            update_job(job_id, progress=round(pct, 2), message=msg)

        if filename:
            result = ingest.index_one_pdf(filename, progress_callback=cb)
        else:
            result = ingest.index_all_pdfs(progress_callback=cb, reset_store=reset_store)

        update_job(
            job_id,
            status="completed",
            progress=100.0,
            message="Done",
            result=result,
            error=None,
        )
    except Exception as exc:
        logger.exception("Reindex job %s failed", job_id)
        update_job(
            job_id,
            status="failed",
            error=str(exc),
            message=str(exc),
        )


def start_reindex_job(filename: str | None, reset_store: bool = False) -> str:
    job_id = create_job()
    t = threading.Thread(
        target=_run,
        args=(job_id, filename, reset_store),
        daemon=True,
        name=f"reindex-{job_id[:8]}",
    )
    t.start()
    return job_id
