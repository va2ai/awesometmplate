from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR

templates: Jinja2Templates = None


def render_custom_block(template_str: str, block: dict, section: dict) -> str:
    """Render a custom block type's HTML template with the block data."""
    from jinja2 import Template
    try:
        tmpl = Template(template_str)
        return tmpl.render(block=block, section=section)
    except Exception:
        return f'<div class="bg-red-50 border-2 border-red-300 p-4 mb-6 text-sm text-red-700">Custom block render error for type: {block.get("type", "unknown")}</div>'


def create_app() -> FastAPI:
    global templates

    app = FastAPI(title="Awesome Knowledge Base")

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    templates.env.globals["render_custom_block"] = render_custom_block

    from app.routes.home import router as home_router
    from app.routes.pages import router as pages_router
    from app.routes.api import router as api_router
    from app.routes.jobs import router as jobs_router

    app.include_router(home_router)
    app.include_router(pages_router)
    app.include_router(api_router)
    app.include_router(jobs_router)

    return app
