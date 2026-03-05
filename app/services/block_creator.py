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
        "badges", "checklist",
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
