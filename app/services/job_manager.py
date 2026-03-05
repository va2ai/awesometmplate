"""Job Manager - persists AI jobs to disk so they survive refreshes/restarts.

Jobs flow:
1. Route creates a job -> returns jobId immediately
2. Background asyncio task runs the AI work
3. Frontend polls GET /api/jobs/{jobId}
4. On completion, result is saved to the page directory
"""

import asyncio
import json
import traceback
import uuid
from datetime import datetime

from app.config import JOBS_DIR


def _job_path(job_id: str):
    return JOBS_DIR / f"{job_id}.json"


def create_job(job_type: str, slug: str = "", topic: str = "", meta: dict = None) -> str:
    """Create a new job, persist to disk, return jobId."""
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "type": job_type,
        "status": "running",
        "slug": slug,
        "topic": topic,
        "meta": meta or {},
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "error": None,
        "result": None,
    }
    _save_job(job)
    return job_id


def get_job(job_id: str) -> dict | None:
    """Load a job from disk."""
    path = _job_path(job_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def complete_job(job_id: str, result: dict = None, slug: str = None):
    """Mark job as completed with result."""
    job = get_job(job_id)
    if not job:
        return
    job["status"] = "completed"
    job["completed_at"] = datetime.now().isoformat()
    if result is not None:
        job["result"] = result
    if slug is not None:
        job["slug"] = slug
    _save_job(job)


def fail_job(job_id: str, error: str):
    """Mark job as failed with error message."""
    job = get_job(job_id)
    if not job:
        return
    job["status"] = "failed"
    job["completed_at"] = datetime.now().isoformat()
    job["error"] = error
    _save_job(job)


def list_jobs(limit: int = 20) -> list[dict]:
    """List recent jobs, newest first."""
    jobs = []
    for path in sorted(JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                jobs.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
        if len(jobs) >= limit:
            break
    return jobs


def cleanup_old_jobs(max_age_hours: int = 24):
    """Remove jobs older than max_age_hours."""
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    for path in JOBS_DIR.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                job = json.load(f)
            created = datetime.fromisoformat(job["created_at"])
            if created < cutoff:
                path.unlink()
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            continue


def _save_job(job: dict):
    JOBS_DIR.mkdir(exist_ok=True)
    with open(_job_path(job["id"]), "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2, ensure_ascii=False)


def run_job_in_background(job_id: str, coro):
    """Schedule an async coroutine as a background task for the given job."""
    loop = asyncio.get_event_loop()
    loop.create_task(_run_wrapper(job_id, coro))


async def _run_wrapper(job_id: str, coro):
    """Wrapper that catches errors and updates job status."""
    try:
        await coro
    except Exception as e:
        fail_job(job_id, f"{repr(e)}\n{traceback.format_exc()}")
