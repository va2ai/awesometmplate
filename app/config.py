from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PAGES_DIR = DATA_DIR / "pages"
CONFIG_FILE = DATA_DIR / "site_config.json"
TOKEN_FILE = DATA_DIR / "token_usage.json"
CUSTOM_BLOCKS_FILE = DATA_DIR / "custom_blocks.json"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
PAGES_DIR.mkdir(exist_ok=True)

# Pricing per million tokens
PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
}
