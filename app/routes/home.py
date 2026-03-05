import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import CONFIG_FILE, PAGES_DIR
from app.models import Directory, Page, SiteConfig
from app.services.claude import load_directory, save_directory
from app.services.job_manager import create_job, complete_job, fail_job, run_job_in_background
from app.tools.token_tracker import load_token_usage
from app.agents import organize_with_claude, route_to_page, smart_add_with_claude

router = APIRouter()

DEFAULT_PAGES = [
    Page(slug="programming", title="Programming", subtitle="Languages, frameworks, tools & dev resources", icon="i-ph:code-bold", color="violet"),
    Page(slug="va", title="VA", subtitle="Veterans Affairs resources & information", icon="i-ph:shield-check-bold", color="blue"),
    Page(slug="misc", title="Misc", subtitle="Everything else worth knowing", icon="i-ph:lightning-bold", color="orange"),
]


def load_site_config() -> SiteConfig:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return SiteConfig(**json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        config = SiteConfig(pages=DEFAULT_PAGES)
        save_site_config(config)
        return config


def save_site_config(config: SiteConfig):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)


def get_page_directory(slug: str) -> Directory:
    d = load_directory(str(PAGES_DIR / f"{slug}.json"))
    if d is None:
        config = load_site_config()
        page = next((p for p in config.pages if p.slug == slug), None)
        title = page.title.upper() if page else slug.upper()
        subtitle = page.subtitle if page else ""
        d = Directory(title=title, subtitle=subtitle)
    return d


def save_page_directory(slug: str, directory: Directory):
    save_directory(directory, str(PAGES_DIR / f"{slug}.json"))


def get_page_or_404(slug: str) -> Page | None:
    config = load_site_config()
    return next((p for p in config.pages if p.slug == slug), None)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    config = load_site_config()
    tokens = load_token_usage()
    page_stats = {}
    for page in config.pages:
        d = get_page_directory(page.slug)
        page_stats[page.slug] = len(d.sections)
    from app import templates
    return templates.TemplateResponse(
        "home.html", {"request": request, "config": config, "tokens": tokens, "page_stats": page_stats}
    )


@router.post("/api/add-topic")
async def add_topic_global(request: Request):
    """Route a topic to the correct page via Haiku, then smart-add it. Returns jobId."""
    try:
        body = await request.json()
        topic = body.get("topic", "").strip()
        description = body.get("description", "").strip()
        url = body.get("url", "").strip()
        files = body.get("files", [])

        if not topic and not url and not files:
            return JSONResponse(status_code=400, content={"error": "Topic, URL, or file is required"})

        if not topic:
            topic = url or (files[0]["name"] if files else "Unknown")

        job_id = create_job("add-topic", topic=topic, meta={"url": url, "has_files": bool(files)})

        async def _work():
            config = load_site_config()
            pages_data = [p.model_dump() for p in config.pages]

            route_result = await route_to_page(topic, pages_data)
            route_result.pop("_tokens", None)
            slug = route_result.get("page_slug", "misc")

            if not any(p.slug == slug for p in config.pages):
                slug = "misc"

            directory = get_page_directory(slug)
            urls = [url] if url else []

            if not directory.sections or urls or files:
                new_dir = await organize_with_claude(
                    topic=topic, instructions=description, urls=urls, files=files,
                )
            else:
                new_dir = await smart_add_with_claude(directory, topic, description)

            save_page_directory(slug, new_dir)
            complete_job(job_id, slug=slug)

        run_job_in_background(job_id, _work())
        return {"jobId": job_id, "status": "running", "topic": topic}

    except Exception as e:
        import traceback
        return JSONResponse(status_code=500, content={"error": repr(e), "traceback": traceback.format_exc()})
