import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, ENV, validate_env

logger = logging.getLogger(__name__)

templates: Jinja2Templates = None


def render_custom_block(template_str: str, block: dict, section: dict) -> str:
    """Render a custom block type's HTML template with the block data."""
    from jinja2 import Template
    from markupsafe import Markup
    try:
        tmpl = Template(template_str)
        return Markup(tmpl.render(block=block, section=section))
    except Exception:
        return Markup('<div class="bg-red-50 border-2 border-red-300 p-4 mb-6 text-sm text-red-700">Custom block render error</div>')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    from app.services.job_manager import recover_stuck_jobs, cleanup_old_jobs
    validate_env()
    recover_stuck_jobs()
    cleanup_old_jobs(max_age_hours=48)
    logger.info("App started (env=%s)", ENV)
    yield
    logger.info("App shutting down")


def create_app() -> FastAPI:
    global templates

    app = FastAPI(
        title="Awesome Knowledge Base",
        docs_url="/docs" if ENV == "dev" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if ENV == "dev" else [],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    templates.env.autoescape = True
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
