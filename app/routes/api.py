from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.routes.home import load_site_config
from app.services.block_creator import load_custom_blocks
from app.agents import create_new_block_type
from app.services.job_manager import create_job, complete_job, fail_job, run_job_in_background
from app.tools.token_tracker import load_token_usage

router = APIRouter()


@router.get("/api/tokens")
async def get_tokens():
    return load_token_usage()


@router.get("/api/pages")
async def list_pages():
    config = load_site_config()
    return config.model_dump()


@router.get("/api/custom-blocks")
async def list_custom_blocks():
    return load_custom_blocks()


@router.post("/api/custom-blocks")
async def create_block_type_endpoint(request: Request):
    try:
        body = await request.json()
        description = body.get("description", "")
        if not description:
            return JSONResponse(status_code=400, content={"error": "description required"})

        job_id = create_job("custom-block", topic=description[:80])

        async def _work():
            result = await create_new_block_type(description)
            if result.get("error"):
                fail_job(job_id, result["error"])
            else:
                complete_job(job_id, result=result)

        run_job_in_background(job_id, _work())
        return {"jobId": job_id, "status": "running"}

    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Route error", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
