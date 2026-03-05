from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.job_manager import get_job, list_jobs, cleanup_old_jobs

router = APIRouter()


@router.get("/api/jobs/{job_id}")
async def poll_job(job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    # Don't send full result in poll - just status + slug
    response = {
        "id": job["id"],
        "type": job["type"],
        "status": job["status"],
        "slug": job.get("slug", ""),
        "topic": job.get("topic", ""),
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
        "error": job["error"],
    }
    return response


@router.get("/api/jobs")
async def list_active_jobs():
    jobs = list_jobs(limit=20)
    return [
        {
            "id": j["id"],
            "type": j["type"],
            "status": j["status"],
            "slug": j.get("slug", ""),
            "topic": j.get("topic", ""),
            "created_at": j["created_at"],
            "completed_at": j["completed_at"],
        }
        for j in jobs
    ]


@router.delete("/api/jobs/cleanup")
async def cleanup_jobs():
    cleanup_old_jobs(max_age_hours=24)
    return {"status": "ok"}
