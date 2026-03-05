import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.routes.home import get_page_directory, get_page_or_404, save_page_directory
from app.services.block_creator import load_custom_blocks
from app.services.job_manager import create_job, complete_job, run_job_in_background
from app.tools.token_tracker import load_token_usage
from app.agents import organize_with_claude, smart_add_with_claude

router = APIRouter()


@router.get("/page/{slug}", response_class=HTMLResponse)
async def page_view(request: Request, slug: str):
    page = get_page_or_404(slug)
    if not page:
        return HTMLResponse("Page not found", status_code=404)
    directory = get_page_directory(slug)
    tokens = load_token_usage()
    from app.routes.home import load_site_config
    config = load_site_config()
    custom_blocks = {b["type_name"]: b for b in load_custom_blocks()}
    from app import templates
    return templates.TemplateResponse(
        "page.html", {"request": request, "page": page, "directory": directory, "tokens": tokens, "config": config, "custom_blocks": custom_blocks}
    )


@router.get("/api/page/{slug}")
async def get_page_data(slug: str):
    return get_page_directory(slug).model_dump()


@router.post("/api/page/{slug}/research")
async def research_topic(slug: str, req: Request):
    page = get_page_or_404(slug)
    if not page:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    try:
        body = await req.json()
        topic = body.get("topic", "")
        instructions = body.get("instructions", "")
        urls = body.get("urls", [])
        files = body.get("files", [])

        job_id = create_job("research", slug=slug, topic=topic or "research")

        async def _work():
            existing = get_page_directory(slug)
            new_directory = await organize_with_claude(
                topic=topic, instructions=instructions, urls=urls, files=files,
            )
            # Merge with existing content instead of overwriting
            if existing.sections:
                merged = existing.model_dump()
                existing_titles = {s.title.lower() for s in existing.sections}
                for section in new_directory.model_dump()["sections"]:
                    if section["title"].lower() not in existing_titles:
                        merged["sections"].append(section)
                    else:
                        # Find matching section and merge blocks
                        for i, es in enumerate(merged["sections"]):
                            if es["title"].lower() == section["title"].lower():
                                existing_labels = {b.get("label", "") + b.get("type", "") for b in es.get("blocks", [])}
                                for block in section.get("blocks", []):
                                    key = block.get("label", "") + block.get("type", "")
                                    if key not in existing_labels:
                                        merged["sections"][i]["blocks"].append(block)
                                break
                from app.models import Directory as DirModel
                directory = DirModel(**merged)
            else:
                directory = new_directory
            save_page_directory(slug, directory)
            complete_job(job_id)

        run_job_in_background(job_id, _work())
        return {"jobId": job_id, "status": "running", "slug": slug}

    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Route error", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@router.post("/api/page/{slug}/smart-add")
async def smart_add(slug: str, request: Request):
    page = get_page_or_404(slug)
    if not page:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    try:
        body = await request.json()
        topic = body.get("topic", "")
        description = body.get("description", "")

        if not topic:
            return JSONResponse(status_code=400, content={"error": "Topic is required"})

        job_id = create_job("smart-add", slug=slug, topic=topic)

        async def _work():
            directory = get_page_directory(slug)
            if not directory.sections:
                new_dir = await organize_with_claude(topic=topic, instructions=description)
            else:
                new_dir = await smart_add_with_claude(directory, topic, description)
            save_page_directory(slug, new_dir)
            complete_job(job_id)

        run_job_in_background(job_id, _work())
        return {"jobId": job_id, "status": "running", "slug": slug}

    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Route error", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@router.post("/api/page/{slug}/organize")
async def organize_existing(slug: str, request: Request):
    page = get_page_or_404(slug)
    if not page:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    try:
        body = await request.json()
        directory = get_page_directory(slug)
        instructions = body.get("instructions", "Reorganize and improve this directory")
        existing_json = json.dumps(directory.model_dump(), indent=2)

        job_id = create_job("organize", slug=slug, topic=directory.title)

        async def _work():
            new_directory = await organize_with_claude(
                topic=directory.title,
                instructions=f"Reorganize this existing directory:\n{existing_json}\n\nInstructions: {instructions}",
            )
            save_page_directory(slug, new_directory)
            complete_job(job_id)

        run_job_in_background(job_id, _work())
        return {"jobId": job_id, "status": "running", "slug": slug}

    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Route error", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@router.delete("/api/page/{slug}")
async def clear_page(slug: str):
    from app.config import PAGES_DIR
    filepath = PAGES_DIR / f"{slug}.json"
    if filepath.exists():
        filepath.unlink()
    return {"status": "ok"}
