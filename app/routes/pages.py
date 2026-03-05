import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)

from app.routes.home import (
    get_page_or_404, get_page_index, save_page_index, get_topic_directory,
    save_topic_directory, delete_topic, add_topic_to_index, get_topic_dir,
    load_site_config,
)
from app.config import PAGES_DIR
from app.models import Directory, PageIndex, TopicEntry
from app.services.block_creator import load_custom_blocks
from app.services.job_manager import create_job, complete_job, run_job_in_background
from app.tools.token_tracker import load_token_usage
from app.agents import organize_with_claude, design_directory, smart_add_with_claude

router = APIRouter()


# --- Parent page view (topic cards + preview sections) ---

@router.get("/page/{slug}", response_class=HTMLResponse)
async def page_view(request: Request, slug: str):
    page = get_page_or_404(slug)
    if not page:
        return HTMLResponse("Page not found", status_code=404)
    index = get_page_index(slug)
    topics_with_data = []
    for t in index.topics:
        d = get_topic_directory(slug, t.slug)
        topics_with_data.append({"entry": t, "directory": d})
    tokens = load_token_usage()
    config = load_site_config()
    custom_blocks = {b["type_name"]: b for b in load_custom_blocks()}
    from app import templates
    return templates.TemplateResponse(
        "page.html", {
            "request": request, "page": page, "index": index,
            "topics": topics_with_data, "tokens": tokens,
            "config": config, "custom_blocks": custom_blocks,
        }
    )


# --- Topic detail view (full sections + blocks) ---

@router.get("/page/{slug}/{topic_slug}", response_class=HTMLResponse)
async def topic_view(request: Request, slug: str, topic_slug: str):
    page = get_page_or_404(slug)
    if not page:
        return HTMLResponse("Page not found", status_code=404)
    directory = get_topic_directory(slug, topic_slug)
    if not directory:
        return HTMLResponse("Topic not found", status_code=404)
    index = get_page_index(slug)
    topic_entry = next((t for t in index.topics if t.slug == topic_slug), None)
    tokens = load_token_usage()
    config = load_site_config()
    custom_blocks = {b["type_name"]: b for b in load_custom_blocks()}
    from app import templates
    return templates.TemplateResponse(
        "topic.html", {
            "request": request, "page": page, "topic_entry": topic_entry,
            "directory": directory, "tokens": tokens, "config": config,
            "custom_blocks": custom_blocks, "topic_slug": topic_slug,
        }
    )


# --- API: page index ---

@router.get("/api/page/{slug}")
async def get_page_data(slug: str):
    return get_page_index(slug).model_dump()


# --- API: add topic to page ---

@router.post("/api/page/{slug}/add-topic")
async def add_topic(slug: str, req: Request):
    page = get_page_or_404(slug)
    if not page:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    try:
        body = await req.json()
        topic = body.get("topic", "").strip()
        description = body.get("description", "").strip()
        urls = body.get("urls", [])
        files = body.get("files", [])
        message = body.get("message", "").strip()
        depth = max(1, min(10, int(body.get("depth", 1))))

        if not topic and not message and not urls and not files:
            return JSONResponse(status_code=400, content={"error": "Topic, message, URL, or file is required"})

        display_topic = topic or message[:80] or (files[0]["name"] if files else "Research")
        job_id = create_job("add-topic", slug=slug, topic=display_topic)

        async def _work():
            import re
            input_text = message or topic or (files[0]["name"] if files else "Research")
            found_urls = re.findall(r'https?://[^\s<>"\']+', message or topic or "")
            all_urls = list(dict.fromkeys(urls + found_urls))

            instructions = description or ""
            if message and not topic:
                instructions = (
                    f"The user is on the '{page.title}' page and sent: \"{message}\"\n"
                    f"Generate comprehensive content about this topic."
                )

            new_dir = await organize_with_claude(
                topic=input_text, instructions=instructions, urls=all_urls, files=files,
                depth=depth,
            )

            # Enhance theming with designer agent
            new_dir = await design_directory(new_dir)

            topic_slug = TopicEntry.slugify(input_text)
            if not topic_slug:
                topic_slug = "topic"

            # Dedupe slug
            index = get_page_index(slug)
            existing_slugs = {t.slug for t in index.topics}
            base_slug = topic_slug
            counter = 2
            while topic_slug in existing_slugs:
                topic_slug = f"{base_slug}-{counter}"
                counter += 1

            save_topic_directory(slug, topic_slug, new_dir)

            entry = TopicEntry(
                slug=topic_slug,
                title=new_dir.title or input_text,
                description=new_dir.subtitle or description,
                icon=new_dir.sections[0].icon_class if new_dir.sections else "i-ph:folder-bold",
                color=new_dir.sections[0].color if new_dir.sections else "orange",
            )
            add_topic_to_index(slug, entry)
            complete_job(job_id)

        run_job_in_background(job_id, _work())
        return {"jobId": job_id, "status": "running", "slug": slug}

    except Exception as e:
        logger.error("Route error", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


# --- API: add content to existing topic ---

@router.post("/api/page/{slug}/{topic_slug}/smart-add")
async def smart_add(slug: str, topic_slug: str, request: Request):
    page = get_page_or_404(slug)
    if not page:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    directory = get_topic_directory(slug, topic_slug)
    if not directory:
        return JSONResponse(status_code=404, content={"error": "Topic not found"})
    try:
        body = await request.json()
        topic = body.get("topic", "")
        description = body.get("description", "")

        if not topic:
            return JSONResponse(status_code=400, content={"error": "Topic is required"})

        job_id = create_job("smart-add", slug=slug, topic=topic)

        async def _work():
            current = get_topic_directory(slug, topic_slug)
            if not current or not current.sections:
                new_dir = await organize_with_claude(topic=topic, instructions=description)
            else:
                new_dir = await smart_add_with_claude(current, topic, description)
            # Enhance theming with designer agent
            new_dir = await design_directory(new_dir)
            save_topic_directory(slug, topic_slug, new_dir)
            complete_job(job_id)

        run_job_in_background(job_id, _work())
        return {"jobId": job_id, "status": "running", "slug": slug}

    except Exception as e:
        logger.error("Route error", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


# --- API: research into existing topic ---

@router.post("/api/page/{slug}/{topic_slug}/research")
async def research_topic(slug: str, topic_slug: str, req: Request):
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
            existing = get_topic_directory(slug, topic_slug)
            new_directory = await organize_with_claude(
                topic=topic, instructions=instructions, urls=urls, files=files,
            )
            # Enhance theming with designer agent
            new_directory = await design_directory(new_directory)

            if existing and existing.sections:
                # Merge into existing
                merged = existing.model_dump()
                existing_titles = {s.title.lower() for s in existing.sections}
                for section in new_directory.model_dump()["sections"]:
                    if section["title"].lower() not in existing_titles:
                        merged["sections"].append(section)
                    else:
                        for i, es in enumerate(merged["sections"]):
                            if es["title"].lower() == section["title"].lower():
                                existing_labels = {b.get("label", "") + b.get("type", "") for b in es.get("blocks", [])}
                                for block in section.get("blocks", []):
                                    key = block.get("label", "") + block.get("type", "")
                                    if key not in existing_labels:
                                        merged["sections"][i]["blocks"].append(block)
                                break
                final = Directory(**merged)
            else:
                final = new_directory
            save_topic_directory(slug, topic_slug, final)
            complete_job(job_id)

        run_job_in_background(job_id, _work())
        return {"jobId": job_id, "status": "running", "slug": slug}

    except Exception as e:
        logger.error("Route error", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


# --- API: delete topic ---

@router.delete("/api/page/{slug}/{topic_slug}")
async def delete_topic_route(slug: str, topic_slug: str):
    delete_topic(slug, topic_slug)
    index = get_page_index(slug)
    index.topics = [t for t in index.topics if t.slug != topic_slug]
    save_page_index(slug, index)
    return {"status": "ok"}


# --- API: clear entire page ---

@router.delete("/api/page/{slug}")
async def clear_page(slug: str):
    """Delete all topics and reset the page index."""
    import shutil
    topic_dir = get_topic_dir(slug)
    if topic_dir.exists():
        shutil.rmtree(topic_dir)
    filepath = PAGES_DIR / f"{slug}.json"
    if filepath.exists():
        filepath.unlink()
    return {"status": "ok"}
