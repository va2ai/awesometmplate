import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# Environment
ENV = os.getenv("ENV", "dev")
PORT = int(os.getenv("PORT", "3339"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if ENV == "dev" else "INFO")
API_TIMEOUT = float(os.getenv("API_TIMEOUT", "300"))

# Logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PAGES_DIR = DATA_DIR / "pages"
CONFIG_FILE = DATA_DIR / "site_config.json"
TOKEN_FILE = DATA_DIR / "token_usage.json"
CUSTOM_BLOCKS_FILE = DATA_DIR / "custom_blocks.json"
JOBS_DIR = DATA_DIR / "jobs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
PAGES_DIR.mkdir(exist_ok=True)
JOBS_DIR.mkdir(exist_ok=True)

# Pricing per million tokens
PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
}


def validate_env():
    """Validate required env vars at startup. Warns in dev, exits in prod."""
    logger = logging.getLogger(__name__)
    missing = []
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")

    if missing:
        msg = f"Missing required env vars: {', '.join(missing)}"
        if ENV == "prod":
            logger.critical(msg)
            sys.exit(1)
        else:
            logger.warning(msg)
