import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import CONFIG_FILE, PAGES_DIR
from app.models import Directory, Page, PageIndex, SiteConfig, TopicEntry
from app.services.claude import load_directory, save_directory
from app.services.job_manager import create_job, complete_job, fail_job, run_job_in_background
from app.tools.token_tracker import load_token_usage
from app.agents import organize_with_claude, design_directory, route_to_page, smart_add_with_claude

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_PAGES = [
    Page(slug="programming", title="Programming", subtitle="Languages, frameworks, tools & dev resources", icon="i-ph:code-bold", color="violet"),
    Page(slug="va", title="VA", subtitle="Veterans Affairs resources & information", icon="i-ph:shield-check-bold", color="blue"),
    Page(slug="misc", title="Misc", subtitle="Everything else worth knowing", icon="i-ph:lightning-bold", color="orange"),
]


# --- Site Config ---

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


def get_page_or_404(slug: str) -> Page | None:
    config = load_site_config()
    return next((p for p in config.pages if p.slug == slug), None)


# --- Page Index (list of topics) ---

def get_page_index(slug: str) -> PageIndex:
    """Load the parent page index (list of topics)."""
    filepath = PAGES_DIR / f"{slug}.json"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Migration: if old format with "sections", convert
        if "sections" in data and "topics" not in data:
            return _migrate_old_format(slug, data)
        return PageIndex(**data)
    except (FileNotFoundError, json.JSONDecodeError):
        page = get_page_or_404(slug)
        title = page.title.upper() if page else slug.upper()
        subtitle = page.subtitle if page else ""
        return PageIndex(title=title, subtitle=subtitle)


def save_page_index(slug: str, index: PageIndex):
    """Save the parent page index."""
    with open(PAGES_DIR / f"{slug}.json", "w", encoding="utf-8") as f:
        json.dump(index.model_dump(), f, indent=2, ensure_ascii=False)


# --- Topic Directories ---

def get_topic_dir(slug: str) -> "Path":
    """Get the directory path for a page's topics."""
    from pathlib import Path
    d = PAGES_DIR / slug
    d.mkdir(exist_ok=True)
    return d


def get_topic_directory(slug: str, topic_slug: str) -> Directory | None:
    """Load a topic's full content (sections + blocks)."""
    filepath = get_topic_dir(slug) / f"{topic_slug}.json"
    return load_directory(str(filepath))


def save_topic_directory(slug: str, topic_slug: str, directory: Directory):
    """Save a topic's full content."""
    filepath = get_topic_dir(slug) / f"{topic_slug}.json"
    save_directory(directory, str(filepath))


def delete_topic(slug: str, topic_slug: str):
    """Delete a topic's content file."""
    filepath = get_topic_dir(slug) / f"{topic_slug}.json"
    if filepath.exists():
        filepath.unlink()


def add_topic_to_index(slug: str, topic: TopicEntry):
    """Add a topic entry to the page index if not already there."""
    index = get_page_index(slug)
    if not any(t.slug == topic.slug for t in index.topics):
        index.topics.append(topic)
        save_page_index(slug, index)


# --- Migration from old format ---

def _migrate_old_format(slug: str, data: dict) -> PageIndex:
    """Migrate old sections-based format to topics-based format."""
    logger.info("Migrating page '%s' from old format to topic-based format", slug)
    page = get_page_or_404(slug)
    title = data.get("title", page.title.upper() if page else slug.upper())
    subtitle = data.get("subtitle", page.subtitle if page else "")

    sections = data.get("sections", [])
    if not sections:
        return PageIndex(title=title, subtitle=subtitle)

    # Derive topic name from content, not the parent page title
    first = sections[0]
    # Try to get a meaningful name from the first section or its description
    topic_title = first.get("title", "") or first.get("description", "")[:80] or title
    if topic_title == title:
        # Last resort: use description from blocks if available
        blocks = first.get("blocks", [])
        for b in blocks:
            label = b.get("label", "")
            if label and label != title:
                topic_title = label
                break
    topic_slug = TopicEntry.slugify(topic_title)
    if not topic_slug or topic_slug == slug:
        topic_slug = "content"

    # Save sections as a topic directory
    topic_dir = Directory(
        title=topic_title,
        subtitle=first.get("description", ""),
        sections=[],
    )
    from app.models import Section
    for s in sections:
        topic_dir.sections.append(Section(**s))

    save_topic_directory(slug, topic_slug, topic_dir)

    # Build topic entry
    entry = TopicEntry(
        slug=topic_slug,
        title=topic_title,
        description=first.get("description", ""),
        icon=first.get("icon_class", "i-ph:folder-bold"),
        color=first.get("color", "orange"),
        stars=first.get("stars", ""),
        url=first.get("url", ""),
    )

    # Save new index
    index = PageIndex(title=page.title.upper() if page else title, subtitle=page.subtitle if page else subtitle, topics=[entry])
    save_page_index(slug, index)
    return index


# --- Legacy compat: get_page_directory / save_page_directory ---
# These are still used by pages.py for topic-level content.

def get_page_directory(slug: str) -> Directory:
    """Legacy compat - loads first topic or empty directory."""
    index = get_page_index(slug)
    if index.topics:
        d = get_topic_directory(slug, index.topics[0].slug)
        if d:
            return d
    page = get_page_or_404(slug)
    title = page.title.upper() if page else slug.upper()
    subtitle = page.subtitle if page else ""
    return Directory(title=title, subtitle=subtitle)


def save_page_directory(slug: str, directory: Directory):
    """Legacy compat - saves to first topic."""
    index = get_page_index(slug)
    if index.topics:
        save_topic_directory(slug, index.topics[0].slug, directory)
    else:
        save_directory(directory, str(PAGES_DIR / f"{slug}.json"))


# --- Routes ---

@router.get("/", response_class=HTMLResponse)
async def index_route(request: Request):
    config = load_site_config()
    tokens = load_token_usage()
    page_stats = {}
    for page in config.pages:
        idx = get_page_index(page.slug)
        page_stats[page.slug] = len(idx.topics)
    from app import templates
    return templates.TemplateResponse(
        "home.html", {"request": request, "config": config, "tokens": tokens, "page_stats": page_stats}
    )


@router.post("/api/add-topic")
async def add_topic_global(request: Request):
    """Route a topic to the correct page, generate content, save as a new topic."""
    try:
        body = await request.json()
        topic = body.get("topic", "").strip()
        description = body.get("description", "").strip()
        url = body.get("url", "").strip()
        files = body.get("files", [])
        depth = max(1, min(10, int(body.get("depth", 1))))

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

            urls = [url] if url else []

            # Generate content for this topic
            new_dir = await organize_with_claude(
                topic=topic, instructions=description or "", urls=urls, files=files,
                depth=depth,
            )

            # Enhance theming with designer agent
            new_dir = await design_directory(new_dir)

            # Create topic slug and save
            topic_slug = TopicEntry.slugify(topic)
            if not topic_slug:
                topic_slug = "topic"

            # Dedupe slug if needed
            index = get_page_index(slug)
            existing_slugs = {t.slug for t in index.topics}
            base_slug = topic_slug
            counter = 2
            while topic_slug in existing_slugs:
                topic_slug = f"{base_slug}-{counter}"
                counter += 1

            save_topic_directory(slug, topic_slug, new_dir)

            # Add to page index
            entry = TopicEntry(
                slug=topic_slug,
                title=new_dir.title or topic,
                description=new_dir.subtitle or description,
                icon=new_dir.sections[0].icon_class if new_dir.sections else "i-ph:folder-bold",
                color=new_dir.sections[0].color if new_dir.sections else "orange",
            )
            add_topic_to_index(slug, entry)

            complete_job(job_id, slug=slug)

        run_job_in_background(job_id, _work())
        return {"jobId": job_id, "status": "running", "topic": topic}

    except Exception as e:
        logging.getLogger(__name__).error("add_topic_global failed", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
