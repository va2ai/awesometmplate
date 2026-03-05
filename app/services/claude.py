"""Claude service - thin wrapper that re-exports from tools and agents.

Routes and other code import from here for backwards compatibility.
The actual logic lives in app.tools (API calls, schemas) and app.agents (orchestration).
"""

import json

from app.tools.token_tracker import load_token_usage
from app.tools.api import call_tool as _call_api
from app.agents.researcher import organize_with_claude
from app.agents.smart_adder import smart_add_with_claude
from app.agents.router import route_to_page


def load_directory(filepath: str):
    from app.models import Directory
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Directory(**data)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_directory(directory, filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(directory.model_dump(), f, indent=2, ensure_ascii=False)
