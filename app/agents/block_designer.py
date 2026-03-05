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

    system = f"""You evaluate whether content could benefit from a custom block type for better visual presentation.

Available block types: {type_list}

Built-in types handle standard layouts: code snippets, links, feature cards, comparisons, stats, steps, tips, text, tables, FAQs, timelines, alerts, badges, checklists, quotes, key-value pairs, charts, progress bars, accordions, tabs.

Say needs_new_type=true when:
- The content has a unique structure that would look SIGNIFICANTLY better with a custom layout (e.g., rating systems with stars, scoreboards, recipe cards, skill trees, org charts, pricing tables, kanban boards, flashcards, before/after sliders, leaderboards)
- A custom block would make the content more interactive, visual, or engaging than any existing type
- The content represents a well-known UI pattern not covered by existing types

Lean toward creativity -- if a custom block would make the page more visually interesting and unique, go for it."""

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

    system = f"""You are an inventive block type designer for a neo-brutalist knowledge base UI. You create VISUALLY STUNNING custom blocks that make pages feel unique and delightful.

Design a new block type that creates a memorable visual experience. Think beyond basic layouts -- create blocks that feel like custom-designed UI components.

The HTML template must:
- Use Tailwind CSS classes with creative combinations (gradients via bg-gradient-to-r, shadows, rounded corners, transforms)
- Follow neo-brutalist style: border-2 border-black, bold colors, font-bold, hover:shadow-lg, but push the boundaries with creative flourishes
- Use {{{{ section.color }}}} for theme color (e.g. bg-{{{{ section.color }}}}-500, bg-{{{{ section.color }}}}-100)
- Access data via block.content (e.g. block.content.get("items", []))
- Use Jinja2 template syntax (for loops, if statements)
- Be wrapped in a div with class "mb-6"
- Include Phosphor icons via <iconify-icon icon="ph:icon-name-bold">
- Add hover effects, transitions (transition-all duration-200), and visual polish
- Consider using CSS grid or flexbox for interesting layouts

Make the block feel SPECIAL -- it should be obvious this isn't a generic component. Add visual details like decorative borders, icon accents, color-coded elements, or creative spacing.

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
