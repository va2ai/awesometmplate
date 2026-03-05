"""Designer Agent - enhances Directory theming after the Researcher produces content."""

import logging

from app.models import Directory
from app.tools.api import call_tool
from app.agents.designer_prompt import DESIGNER_SYSTEM_PROMPT
from app.agents.dynamic_schema import get_dynamic_directory_schema

logger = logging.getLogger(__name__)


async def design_directory(directory: Directory) -> Directory:
    """Take a researcher-produced Directory and enhance its visual theming.

    The designer does NOT change content text or add/remove sections.
    It enhances: colors, icons, animation choices, and block type upgrades.
    """
    dir_data = directory.model_dump()

    user_msg = (
        "Enhance the visual theming of this Directory. "
        "Analyze the topic and apply the best matching theme from your gallery. "
        "Return the full enhanced Directory JSON.\n\n"
        f"DIRECTORY TO ENHANCE:\n{__import__('json').dumps(dir_data, indent=2)}"
    )

    schema = get_dynamic_directory_schema()

    try:
        result = await call_tool(
            user_message=user_msg,
            system=DESIGNER_SYSTEM_PROMPT,
            tool_name="enhance_directory",
            tool_schema=schema,
            max_tokens=16384,
            use_grounding=False,
        )
        result.pop("_tokens", None)
        result.pop("design_notes", None)
        return Directory(**result)
    except Exception as e:
        logger.error("Designer agent failed, returning original: %s", e)
        return directory
