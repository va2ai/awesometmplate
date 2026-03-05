"""Block Type Creator Agent.

Detects when content doesn't fit existing block types, designs a new one,
and persists it to a registry file for consistency.
"""

import json

from app.config import CUSTOM_BLOCKS_FILE, DATA_DIR

# Schema for the block creator agent's output
BLOCK_TYPE_SCHEMA = {
    "type": "object",
    "properties": {
        "type_name": {
            "type": "string",
            "description": "Snake_case name for the new block type (e.g. 'kanban_board', 'pricing_table')",
        },
        "description": {
            "type": "string",
            "description": "When to use this block type - what kind of content it displays",
        },
        "content_schema": {
            "type": "string",
            "description": "Schema description for the content dict, same format as existing block types (e.g. '{items: [{title, status, priority}]}')",
        },
        "html_template": {
            "type": "string",
            "description": "Jinja2 HTML template snippet that renders this block. Use Tailwind CSS classes, neo-brutalist style (border-2 border-black, bold colors, font-bold). Access data via block.content. Use section.color for theming. Include hover:shadow-lg transitions.",
        },
        "example_content": {
            "type": "object",
            "description": "Example content dict showing what data looks like for this block type",
        },
    },
    "required": ["type_name", "description", "content_schema", "html_template", "example_content"],
}

# Schema for checking if a new block type is needed
BLOCK_CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_new_type": {"type": "boolean"},
        "reasoning": {"type": "string"},
        "content_description": {
            "type": "string",
            "description": "What kind of content needs displaying that doesn't fit existing types",
        },
    },
    "required": ["needs_new_type", "reasoning"],
}


def load_custom_blocks() -> list[dict]:
    """Load all custom block types from registry."""
    try:
        with open(CUSTOM_BLOCKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_custom_blocks(blocks: list[dict]):
    """Save custom block types to registry."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(CUSTOM_BLOCKS_FILE, "w", encoding="utf-8") as f:
        json.dump(blocks, f, indent=2, ensure_ascii=False)


def get_custom_block(type_name: str) -> dict | None:
    """Get a specific custom block type by name."""
    blocks = load_custom_blocks()
    return next((b for b in blocks if b["type_name"] == type_name), None)


def register_block_type(block_def: dict) -> bool:
    """Add a new block type to the registry. Returns False if already exists."""
    blocks = load_custom_blocks()
    if any(b["type_name"] == block_def["type_name"] for b in blocks):
        return False
    blocks.append(block_def)
    save_custom_blocks(blocks)
    return True


def get_all_block_type_names() -> list[str]:
    """Get all block type names (built-in + custom)."""
    builtin = [
        "link_list", "code_grid", "info_grid", "comparison", "stats",
        "steps", "tip", "text", "table", "faq", "timeline", "alert",
        "badges", "checklist", "quote", "key_value", "chart",
        "progress", "accordion", "tabs",
    ]
    custom = [b["type_name"] for b in load_custom_blocks()]
    return builtin + custom


def get_block_descriptions_for_prompt() -> str:
    """Build the block type descriptions for Claude's system prompt, including custom types."""
    custom = load_custom_blocks()
    if not custom:
        return ""
    lines = ["\nCustom block types (created for specialized content):"]
    for b in custom:
        lines.append(f"- {b['type_name']}: {b['description']} Content: {b['content_schema']}")
    return "\n".join(lines)


def get_schema_description_for_custom() -> str:
    """Build the content description addendum for custom block types."""
    custom = load_custom_blocks()
    if not custom:
        return ""
    parts = []
    for b in custom:
        parts.append(f"{b['type_name']}: {b['content_schema']}")
    return " ".join(parts)


async def check_needs_new_block(topic: str, content_context: str) -> dict:
    """Phase 0: Check if content needs a block type that doesn't exist."""
    from app.services.claude import _call_api

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

    return await _call_api(
        user_message=user_msg,
        system=system,
        tool_name="block_check",
        tool_schema=BLOCK_CHECK_SCHEMA,
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
    )


async def create_new_block_type(content_description: str) -> dict:
    """Create a new block type definition."""
    from app.services.claude import _call_api

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

    result = await _call_api(
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
