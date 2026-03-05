"""Router Agent - lightweight classification using Haiku.

Two roles:
1. Page router: decides which page a topic belongs to
2. Section router: decides which section within a page
"""

from app.tools.api import call_tool
from app.tools.schemas import PAGE_ROUTER_SCHEMA, ROUTER_SCHEMA


async def route_to_page(topic: str, pages: list[dict]) -> dict:
    """Use Haiku to decide which page a topic belongs to."""
    page_list = "\n".join(f"- {p['slug']}: {p['title']} - {p.get('subtitle', '')}" for p in pages)
    system = "You are a topic router. Given a topic and a list of knowledge base pages, decide which page it belongs to. Pick the best fit."
    user_msg = f"Pages:\n{page_list}\n\nTopic: {topic}\n\nWhich page does this belong to? Return the page slug."
    return await call_tool(
        user_message=user_msg,
        system=system,
        tool_name="route_page",
        tool_schema=PAGE_ROUTER_SCHEMA,
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
    )


async def route_to_section(section_summaries: str, new_topic: str, new_description: str) -> dict:
    """Phase 1: Router - lightweight classification on Haiku."""
    system = """You are a content router. Given a directory's section list and a new topic, decide where it belongs.

Prefer fitting into existing sections over creating new ones.
Only suggest 'restructure_needed' if section count is at the limit AND the new item doesn't fit any existing section."""

    user_msg = f"""Current sections:
{section_summaries}

New topic: {new_topic}
{('Description: ' + new_description) if new_description else ''}

Decide: add to an existing section, create a new section, or flag that restructuring is needed."""

    return await call_tool(
        user_message=user_msg,
        system=system,
        tool_name="route_decision",
        tool_schema=ROUTER_SCHEMA,
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
    )
