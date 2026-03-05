"""Block Designer Agent - creates new custom block types."""

from app.tools.api import call_tool
from app.tools.schemas import BLOCK_TYPE_SCHEMA, BLOCK_CHECK_SCHEMA
from app.services.block_creator import (
    load_custom_blocks,
    get_all_block_type_names,
    register_block_type,
)


async def check_needs_new_block(topic: str, content_context: str) -> dict:
    """Check if content needs a block type that doesn't exist."""
    all_types = get_all_block_type_names()
    type_list = ", ".join(all_types)

    system = f"""You evaluate whether content can be displayed using existing block types.

Available block types: {type_list}

Built-in types handle:
- code_grid: code snippets, install commands
- link_list: URL collections
- info_grid: feature cards with icons
- comparison: pros/cons, side-by-side
- stats: numerical metrics
- steps: sequential tutorials
- tip: single important note
- text: paragraphs
- table: rows and columns of data
- faq: question/answer pairs
- timeline: chronological events
- alert: warnings/notices with severity
- badges: colored tags/labels
- checklist: task lists with checkboxes

Only say needs_new_type=true if the content GENUINELY cannot be represented by ANY existing type. Most content fits existing types."""

    user_msg = f"""Topic: {topic}
Content context: {content_context}

Can this content be displayed using existing block types, or does it need a new specialized block type?"""

    return await call_tool(
        user_message=user_msg,
        system=system,
        tool_name="block_check",
        tool_schema=BLOCK_CHECK_SCHEMA,
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
    )


async def create_new_block_type(content_description: str) -> dict:
    """Create a new block type definition."""
    existing = load_custom_blocks()
    existing_names = [b["type_name"] for b in existing]
    existing_info = ""
    if existing:
        existing_info = "\n\nAlready-created custom types (do NOT duplicate these):\n"
        for b in existing:
            existing_info += f"- {b['type_name']}: {b['description']}\n"

    system = f"""You are a block type designer for a neo-brutalist knowledge base UI.

Design a new block type that handles content that doesn't fit existing types.
The HTML template must:
- Use Tailwind CSS classes
- Follow neo-brutalist style: border-2 border-black, bold colors, font-bold, hover:shadow-lg
- Use {{{{ section.color }}}} for theme color (e.g. bg-{{{{ section.color }}}}-500)
- Access data via block.content (e.g. block.content.get("items", []))
- Use Jinja2 template syntax (for loops, if statements)
- Be wrapped in a div with class "mb-6"
- Include Phosphor icons via <iconify-icon icon="ph:icon-name-bold">

Do NOT create types that duplicate existing ones.
Use snake_case for type_name.
{existing_info}"""

    user_msg = f"""Create a new block type for this content:
{content_description}

Design the type name, describe when to use it, define its content schema, and write the HTML template."""

    result = await call_tool(
        user_message=user_msg,
        system=system,
        tool_name="create_block_type",
        tool_schema=BLOCK_TYPE_SCHEMA,
        max_tokens=2048,
    )

    result.pop("_tokens", None)

    if result["type_name"] in existing_names:
        return {"error": "Block type already exists", "type_name": result["type_name"]}

    register_block_type(result)
    return result
