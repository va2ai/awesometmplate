"""Merger Agent - adds content to existing sections or creates new ones (Sonnet)."""

import json

from app.tools.api import call_tool
from app.tools.schemas import SECTION_SCHEMA
from app.agents.prompts import get_dynamic_system_prompt


async def merge_into_section(target_section: dict, all_titles: str, new_topic: str, new_description: str) -> dict:
    """Phase 2: Merge - focused content generation on Sonnet. Only sends target section."""
    system = get_dynamic_system_prompt() + """

IMPORTANT: You are updating a SINGLE section of an existing directory.
Add the new topic's content to this section using appropriate block types.
Preserve all existing blocks. Add new blocks or enhance existing ones.
The other sections in the directory (listed for context) are:
""" + all_titles

    section_json = json.dumps(target_section, indent=2)
    user_msg = f"""Current section content:
{section_json}

New item to add to this section:
Topic: {new_topic}
{('Description: ' + new_description) if new_description else ''}

Update this section to include the new item. Return the complete updated section."""

    return await call_tool(
        user_message=user_msg,
        system=system,
        tool_name="update_section",
        tool_schema=SECTION_SCHEMA,
        max_tokens=8192,
    )


async def create_section(all_titles: str, new_topic: str, new_description: str) -> dict:
    """Phase 2 (create variant): Generate a brand new section."""
    system = get_dynamic_system_prompt() + """

You are creating a NEW section for an existing directory.
The other sections are:
""" + all_titles + """

Create a rich section with 3-6 blocks using the most appropriate block types."""

    user_msg = f"""Create a new section for:
Topic: {new_topic}
{('Description: ' + new_description) if new_description else ''}

Research this topic and create a comprehensive section."""

    return await call_tool(
        user_message=user_msg,
        system=system,
        tool_name="create_section",
        tool_schema=SECTION_SCHEMA,
        max_tokens=8192,
        use_grounding=True,
    )
