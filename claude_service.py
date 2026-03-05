import json
import os
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from models import Directory

load_dotenv(override=True)

# Lazy import to avoid circular
def _get_block_creator():
    import block_creator
    return block_creator

API_URL = "https://api.anthropic.com/v1/messages"
DATA_DIR = Path(__file__).parent / "data"
TOKEN_FILE = DATA_DIR / "token_usage.json"

DIRECTORY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Directory title in ALL CAPS"},
        "subtitle": {"type": "string", "description": "Brief subtitle"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "icon_class": {"type": "string"},
                    "color": {
                        "type": "string",
                        "enum": ["orange", "violet", "blue", "green", "red", "yellow", "pink", "indigo"],
                    },
                    "description": {"type": "string", "description": "1-2 sentence overview"},
                    "url": {"type": "string", "description": "Official website URL"},
                    "stars": {"type": "string", "description": "GitHub stars like 81k"},
                    "blocks": {
                        "type": "array",
                        "description": "Content blocks. Pick the best type for each piece of content.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "link_list",
                                        "code_grid",
                                        "info_grid",
                                        "comparison",
                                        "stats",
                                        "steps",
                                        "tip",
                                        "text",
                                        "table",
                                        "faq",
                                        "timeline",
                                        "alert",
                                        "badges",
                                        "checklist",
                                    ],
                                    "description": "Block layout type",
                                },
                                "label": {"type": "string", "description": "Block heading"},
                                "content": {
                                    "type": "object",
                                    "description": "Block data. Structure depends on type. "
                                    "link_list: {items: [{title, url, description, stars}]}. "
                                    "code_grid: {cards: [{title, description, code, language}]}. "
                                    "info_grid: {cards: [{title, description, icon}]}. "
                                    "comparison: {items: [{label, points: [str]}]}. "
                                    "stats: {cards: [{value, label, description}]}. "
                                    "steps: {items: [{title, description, code}]}. "
                                    "tip: {text: str}. "
                                    "text: {text: str}. "
                                    "table: {headers: [str], rows: [{cells: [str]}]}. "
                                    "faq: {items: [{question, answer}]}. "
                                    "timeline: {events: [{date, title, description}]}. "
                                    "alert: {text: str, severity: 'info'|'warning'|'error'|'success'}. "
                                    "badges: {items: [{label, color}]}. "
                                    "checklist: {items: [{text, checked: bool}]}.",
                                },
                            },
                            "required": ["type", "content"],
                        },
                    },
                },
                "required": ["title", "icon_class", "color", "description", "blocks"],
            },
        },
    },
    "required": ["title", "subtitle", "sections"],
}

# Page router schema - decides which page a topic belongs to
PAGE_ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "page_slug": {"type": "string", "description": "The slug of the page this topic belongs to"},
        "reasoning": {"type": "string", "description": "One sentence explaining why"},
    },
    "required": ["page_slug", "reasoning"],
}


async def route_to_page(topic: str, pages: list[dict]) -> dict:
    """Use Haiku to decide which page a topic belongs to."""
    page_list = "\n".join(f"- {p['slug']}: {p['title']} - {p.get('subtitle', '')}" for p in pages)
    system = "You are a topic router. Given a topic and a list of knowledge base pages, decide which page it belongs to. Pick the best fit."
    user_msg = f"Pages:\n{page_list}\n\nTopic: {topic}\n\nWhich page does this belong to? Return the page slug."
    return await _call_api(
        user_message=user_msg,
        system=system,
        tool_name="route_page",
        tool_schema=PAGE_ROUTER_SCHEMA,
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
    )


# Lightweight schema for Router (Phase 1) - just the decision, no content
ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["add_to_existing", "create_new", "restructure_needed"],
        },
        "target_section": {
            "type": "integer",
            "description": "Index of existing section to add to (null if creating new)",
        },
        "reasoning": {"type": "string", "description": "One sentence explaining the decision"},
        "suggested_title": {"type": "string", "description": "For new sections only"},
    },
    "required": ["action", "reasoning"],
}

# Schema for Merger (Phase 2) - single section output
SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "icon_class": {"type": "string"},
        "color": {
            "type": "string",
            "enum": ["orange", "violet", "blue", "green", "red", "yellow", "pink", "indigo"],
        },
        "description": {"type": "string"},
        "url": {"type": "string"},
        "stars": {"type": "string"},
        "blocks": DIRECTORY_SCHEMA["properties"]["sections"]["items"]["properties"]["blocks"],
    },
    "required": ["title", "icon_class", "color", "description", "blocks"],
}

# Schema for Taxonomy Check (Phase 3a) - merge plan
TAXONOMY_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_restructure": {"type": "boolean"},
        "merge_plan": {
            "type": "array",
            "description": "Each entry maps new section title to list of old section indices to merge",
            "items": {
                "type": "object",
                "properties": {
                    "new_title": {"type": "string"},
                    "merge_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Indices of sections to merge into this group",
                    },
                    "new_description": {"type": "string"},
                    "new_icon": {"type": "string"},
                    "new_color": {
                        "type": "string",
                        "enum": ["orange", "violet", "blue", "green", "red", "yellow", "pink", "indigo"],
                    },
                },
                "required": ["new_title", "merge_indices"],
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["needs_restructure", "reasoning"],
}


def _get_block_enum():
    """Get all block type names including custom ones."""
    bc = _get_block_creator()
    return [
        "link_list", "code_grid", "info_grid", "comparison", "stats",
        "steps", "tip", "text", "table", "faq", "timeline", "alert",
        "badges", "checklist",
    ] + [b["type_name"] for b in bc.load_custom_blocks()]


def _get_content_description():
    """Get full content description including custom block schemas."""
    base = (
        "Block data. Structure depends on type. "
        "link_list: {items: [{title, url, description, stars}]}. "
        "code_grid: {cards: [{title, description, code, language}]}. "
        "info_grid: {cards: [{title, description, icon}]}. "
        "comparison: {items: [{label, points: [str]}]}. "
        "stats: {cards: [{value, label, description}]}. "
        "steps: {items: [{title, description, code}]}. "
        "tip: {text: str}. "
        "text: {text: str}. "
        "table: {headers: [str], rows: [{cells: [str]}]}. "
        "faq: {items: [{question, answer}]}. "
        "timeline: {events: [{date, title, description}]}. "
        "alert: {text: str, severity: 'info'|'warning'|'error'|'success'}. "
        "badges: {items: [{label, color}]}. "
        "checklist: {items: [{text, checked: bool}]}."
    )
    bc = _get_block_creator()
    custom_desc = bc.get_schema_description_for_custom()
    if custom_desc:
        base += " " + custom_desc
    return base


def get_dynamic_directory_schema():
    """Build DIRECTORY_SCHEMA with current block types (including custom)."""
    schema = json.loads(json.dumps(DIRECTORY_SCHEMA))  # deep copy
    blocks_items = schema["properties"]["sections"]["items"]["properties"]["blocks"]["items"]
    blocks_items["properties"]["type"]["enum"] = _get_block_enum()
    blocks_items["properties"]["content"]["description"] = _get_content_description()
    return schema


def get_dynamic_system_prompt():
    """Build system prompt with custom block type descriptions."""
    bc = _get_block_creator()
    extra = bc.get_block_descriptions_for_prompt()
    return SYSTEM_PROMPT + extra


SYSTEM_PROMPT = """You are a research organizer that creates rich, detailed directories.

DYNAMICALLY choose the best block types to present each section's content:

- code_grid: For install commands, code examples, configs. Cards with title + code snippet.
- link_list: For collections of related links/resources with URLs.
- info_grid: For feature lists, key concepts, categories. Cards with title + description + icon.
- comparison: For pros/cons, comparing options. Items with label + bullet points.
- stats: For numerical data, metrics, counts. Cards with value + label.
- steps: For tutorials, guides, workflows. Numbered items with optional code.
- tip: For important notes, best practices. Single text block.
- text: For paragraphs, explanations, summaries. Single text block.
- table: For structured data with rows and columns. Headers + rows of cells.
- faq: For Q&A pairs. Items with question + answer.
- timeline: For chronological events, version history, roadmaps. Events with date + title.
- alert: For warnings, errors, success messages, important notices. Text + severity level.
- badges: For tags, labels, technology stacks, categories. Items with label + color.
- checklist: For task lists, requirements, feature checklists. Items with text + checked state.

For each major item, create a SECTION with 3-6 blocks using the most appropriate types.
Mix block types within a section to create a rich cheatsheet-style layout.

Keep code examples under 15 lines. Use real, accurate information.

Phosphor icons: i-ph:rocket-launch-bold, i-ph:code-bold, i-ph:book-open-bold, i-ph:gear-bold, i-ph:folder-bold, i-ph:star-bold, i-ph:lightning-bold, i-ph:shield-check-bold, i-ph:wrench-bold, i-ph:globe-bold, i-ph:database-bold, i-ph:puzzle-piece-bold, i-ph:terminal-bold, i-ph:cloud-bold, i-ph:graduation-cap-bold, i-ph:link-bold, i-ph:check-circle-bold, i-ph:x-circle-bold, i-ph:target-bold, i-ph:package-bold, i-ph:clock-bold, i-ph:question-bold, i-ph:warning-bold, i-ph:list-checks-bold, i-ph:tag-bold, i-ph:table-bold"""


# --- Token tracking ---

def load_token_usage() -> dict:
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"total_input": 0, "total_output": 0, "total_cost_usd": 0.0, "calls": 0, "history": []}


def save_token_usage(usage: dict):
    DATA_DIR.mkdir(exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(usage, f, indent=2, ensure_ascii=False)


def record_tokens(input_tokens: int, output_tokens: int, model: str = "claude-sonnet-4-6"):
    PRICING = {
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    }
    rates = PRICING.get(model, PRICING["claude-sonnet-4-6"])
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000

    usage = load_token_usage()
    usage["total_input"] += input_tokens
    usage["total_output"] += output_tokens
    usage["total_cost_usd"] = round(usage["total_cost_usd"] + cost, 6)
    usage["calls"] += 1
    usage["history"].append({
        "timestamp": datetime.now().isoformat(),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "model": model,
    })
    usage["history"] = usage["history"][-100:]
    save_token_usage(usage)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": round(cost, 6), "model": model}


# --- Claude API ---

async def _call_api(user_message: str, system: str, tool_name: str, tool_schema: dict, model: str = "claude-sonnet-4-6", max_tokens: int = 16384) -> dict:
    """Low-level API call with tool_use structured output."""
    load_dotenv(override=True)
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "tools": [
            {
                "name": tool_name,
                "description": "Produce structured output",
                "input_schema": tool_schema,
            }
        ],
        "tool_choice": {"type": "tool", "name": tool_name},
        "messages": [{"role": "user", "content": user_message}],
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(API_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            raise RuntimeError("Anthropic API " + str(resp.status_code) + ": " + resp.text)
        data = resp.json()

        usage = data.get("usage", {})
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        token_info = record_tokens(input_t, output_t, model)

        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                result = block["input"]
                result["_tokens"] = token_info
                return result
        raise RuntimeError("No tool_use block in response")


async def call_claude_api(user_message: str, system: str = None) -> dict:
    """Call Claude with the full directory schema (for research/organize)."""
    return await _call_api(
        user_message=user_message,
        system=system or get_dynamic_system_prompt(),
        tool_name="create_directory",
        tool_schema=get_dynamic_directory_schema(),
    )


async def fetch_url_content(url: str) -> str:
    """Fetch text content from a URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AwesomeKB/1.0"})
            if resp.status_code != 200:
                return f"[Failed to fetch {url}: HTTP {resp.status_code}]"
            content_type = resp.headers.get("content-type", "")
            if "text" in content_type or "json" in content_type or "xml" in content_type:
                text = resp.text
                # Truncate very long pages
                if len(text) > 50000:
                    text = text[:50000] + "\n\n[Content truncated at 50,000 characters]"
                return text
            return f"[Binary content at {url}, type: {content_type}]"
    except Exception as e:
        return f"[Error fetching {url}: {e}]"


async def organize_with_claude(
    topic: str = "", items: list = None, instructions: str = "",
    urls: list = None, files: list = None,
) -> Directory:
    user_msg = ""

    if topic:
        user_msg += "Topic: " + topic + "\n"

    if instructions:
        user_msg += "\nInstructions: " + instructions + "\n"

    # Fetch and include URL content
    if urls:
        user_msg += "\n--- SOURCE URLs ---\n"
        for url in urls:
            content = await fetch_url_content(url)
            user_msg += f"\n[URL: {url}]\n{content}\n"

    # Include file content
    if files:
        user_msg += "\n--- UPLOADED FILES ---\n"
        for f in files:
            name = f.get("name", "unknown")
            content = f.get("content", "")
            # Truncate very large files
            if len(content) > 30000:
                content = content[:30000] + "\n\n[File truncated at 30,000 characters]"
            user_msg += f"\n[File: {name}]\n{content}\n"

    if items:
        user_msg += "\nItems to organize:\n"
        for item in items:
            line = "- " + (item.get("title", "") if isinstance(item, dict) else str(item))
            user_msg += line + "\n"

    if not items and not urls and not files:
        user_msg += (
            "\nResearch this topic thoroughly. Create a section for each major item "
            "with mixed block types: code_grid for install/examples, info_grid for features, "
            "comparison for pros/cons, stats for metrics, steps for guides, tips for gotchas, "
            "tables for structured data, faq for common questions, timeline for history, "
            "badges for tech stacks, checklist for requirements. "
            "Include real URLs and GitHub stars where applicable."
        )
    else:
        user_msg += (
            "\nAnalyze the provided sources and organize the information into a structured directory. "
            "Determine the topic and title from the content. Create sections for each major concept "
            "with mixed block types for rich display. Preserve important details, code examples, "
            "URLs, and data from the sources."
        )

    data = await call_claude_api(user_msg)
    data.pop("_tokens", None)
    return Directory(**data)


# --- Three-Phase Smart Add ---

async def _phase1_route(section_summaries: str, new_topic: str, new_description: str) -> dict:
    """Phase 1: Router - lightweight classification on Haiku. ~300-500 tokens."""
    system = """You are a content router. Given a directory's section list and a new topic, decide where it belongs.

Prefer fitting into existing sections over creating new ones.
Only suggest 'restructure_needed' if section count is at the limit AND the new item doesn't fit any existing section."""

    user_msg = f"""Current sections:
{section_summaries}

New topic: {new_topic}
{('Description: ' + new_description) if new_description else ''}

Decide: add to an existing section, create a new section, or flag that restructuring is needed."""

    return await _call_api(
        user_message=user_msg,
        system=system,
        tool_name="route_decision",
        tool_schema=ROUTER_SCHEMA,
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
    )


async def _phase2_merge(target_section: dict, all_titles: str, new_topic: str, new_description: str) -> dict:
    """Phase 2: Merger - focused content generation on Sonnet. Only sends target section."""
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

    return await _call_api(
        user_message=user_msg,
        system=system,
        tool_name="update_section",
        tool_schema=SECTION_SCHEMA,
        max_tokens=8192,
    )


async def _phase2_create(all_titles: str, new_topic: str, new_description: str) -> dict:
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

    return await _call_api(
        user_message=user_msg,
        system=system,
        tool_name="create_section",
        tool_schema=SECTION_SCHEMA,
        max_tokens=8192,
    )


async def _phase3a_taxonomy_check(section_summaries: str, section_count: int) -> dict:
    """Phase 3a: Taxonomy check - should sections be merged? ~500-800 tokens."""
    system = """You are a taxonomy reviewer. Review section groupings and decide if reorganization is needed.
Maximum 8 sections allowed. Propose merges that create logical, broader categories.
Preserve all content -- only regroup, never delete."""

    user_msg = f"""Current sections ({section_count} total):
{section_summaries}

Maximum 8 sections allowed. Should sections be reorganized?
If yes, propose new groupings mapping old section indices to new merged sections."""

    return await _call_api(
        user_message=user_msg,
        system=system,
        tool_name="taxonomy_check",
        tool_schema=TAXONOMY_SCHEMA,
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
    )


async def _phase3b_restructure(merge_plan: list, sections_to_merge: list[dict]) -> dict:
    """Phase 3b: Execute restructure - merge sections per plan. Uses full directory schema."""
    plan_text = ""
    for group in merge_plan:
        indices = group["merge_indices"]
        plan_text += f"\nMerge into '{group['new_title']}': sections at indices {indices}\n"

    sections_json = json.dumps(sections_to_merge, indent=2)

    system = get_dynamic_system_prompt() + """

You are reorganizing sections according to a merge plan.
RULES:
1. Each original section's blocks are preserved within the merged section.
2. Add ONE overview block at the top of each merged section.
3. Consolidate DUPLICATE information across sections into comparison blocks.
4. If a merged section exceeds 12 blocks, prioritize: overview > code > comparisons > metrics > tips.
5. Generate new section descriptions covering the full merged category.
6. Choose appropriate colors and icons. Use visual variety."""

    user_msg = f"""MERGE PLAN:
{plan_text}

Sections to merge:
{sections_json}

Execute this merge plan. Return a complete directory with the merged sections."""

    return await _call_api(
        user_message=user_msg,
        system=system,
        tool_name="create_directory",
        tool_schema=DIRECTORY_SCHEMA,
        max_tokens=16384,
    )


def _build_section_summaries(directory: Directory) -> str:
    """Build a compact summary of sections for routing/taxonomy calls."""
    lines = []
    for i, sec in enumerate(directory.sections):
        block_count = len(sec.blocks)
        lines.append(f"{i}. {sec.title} - {sec.description} ({block_count} blocks)")
    return "\n".join(lines)


def _build_title_list(directory: Directory) -> str:
    """Build just section titles for context."""
    return "\n".join(f"- {sec.title}" for sec in directory.sections)


async def smart_add_with_claude(
    existing_directory: Directory, new_topic: str, new_description: str = ""
) -> Directory:
    """Three-phase smart add: Route -> Merge/Create -> optional Taxonomy Check."""
    sections = existing_directory.sections
    section_count = len(sections)
    summaries = _build_section_summaries(existing_directory)
    titles = _build_title_list(existing_directory)

    # Phase 1: Route (Haiku - cheap)
    route = await _phase1_route(summaries, new_topic, new_description)
    route.pop("_tokens", None)
    action = route.get("action", "create_new")
    target_idx = route.get("target_section")

    # Phase 2: Merge or Create (Sonnet - targeted)
    if action == "add_to_existing" and target_idx is not None and 0 <= target_idx < section_count:
        target = sections[target_idx].model_dump()
        updated = await _phase2_merge(target, titles, new_topic, new_description)
        updated.pop("_tokens", None)
        # Patch the updated section back into the directory
        dir_data = existing_directory.model_dump()
        dir_data["sections"][target_idx] = updated
        result_dir = Directory(**dir_data)
    elif action == "restructure_needed" and section_count >= 8:
        # Skip Phase 2, go straight to restructure with the new topic added first
        new_section = await _phase2_create(titles, new_topic, new_description)
        new_section.pop("_tokens", None)
        dir_data = existing_directory.model_dump()
        dir_data["sections"].append(new_section)
        result_dir = Directory(**dir_data)
    else:
        # Create new section
        new_section = await _phase2_create(titles, new_topic, new_description)
        new_section.pop("_tokens", None)
        dir_data = existing_directory.model_dump()
        dir_data["sections"].append(new_section)
        result_dir = Directory(**dir_data)

    # Phase 3: Taxonomy Check (conditional - only if >8 sections)
    if len(result_dir.sections) > 8:
        new_summaries = _build_section_summaries(result_dir)
        tax_check = await _phase3a_taxonomy_check(new_summaries, len(result_dir.sections))
        tax_check.pop("_tokens", None)

        if tax_check.get("needs_restructure") and tax_check.get("merge_plan"):
            merge_plan = tax_check["merge_plan"]
            # Collect all sections that need merging
            all_merge_indices = set()
            for group in merge_plan:
                all_merge_indices.update(group["merge_indices"])

            sections_data = result_dir.model_dump()["sections"]
            sections_to_merge = [sections_data[i] for i in sorted(all_merge_indices) if i < len(sections_data)]

            restructured = await _phase3b_restructure(merge_plan, sections_to_merge)
            restructured.pop("_tokens", None)

            # Keep unmerged sections + add restructured ones
            merged_sections = restructured.get("sections", [])
            unmerged = [s for i, s in enumerate(sections_data) if i not in all_merge_indices]
            final_sections = unmerged + merged_sections

            dir_data = result_dir.model_dump()
            dir_data["sections"] = final_sections
            # Preserve original title/subtitle
            dir_data["title"] = existing_directory.title
            dir_data["subtitle"] = existing_directory.subtitle
            result_dir = Directory(**dir_data)

    return result_dir


def load_directory(filepath: str) -> Directory | None:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Directory(**data)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_directory(directory: Directory, filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(directory.model_dump(), f, indent=2, ensure_ascii=False)
