"""Taxonomist Agent - checks section organization and proposes merges."""

import json

from app.tools.api import call_tool
from app.tools.schemas import TAXONOMY_SCHEMA, DIRECTORY_SCHEMA
from app.agents.prompts import get_dynamic_system_prompt


async def check_taxonomy(section_summaries: str, section_count: int) -> dict:
    """Phase 3a: Should sections be merged?"""
    system = """You are a taxonomy reviewer. Review section groupings and decide if reorganization is needed.
Maximum 8 sections allowed. Propose merges that create logical, broader categories.
Preserve all content -- only regroup, never delete."""

    user_msg = f"""Current sections ({section_count} total):
{section_summaries}

Maximum 8 sections allowed. Should sections be reorganized?
If yes, propose new groupings mapping old section indices to new merged sections."""

    return await call_tool(
        user_message=user_msg,
        system=system,
        tool_name="taxonomy_check",
        tool_schema=TAXONOMY_SCHEMA,
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
    )


async def execute_restructure(merge_plan: list, sections_to_merge: list[dict]) -> dict:
    """Phase 3b: Execute restructure - merge sections per plan."""
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

    return await call_tool(
        user_message=user_msg,
        system=system,
        tool_name="create_directory",
        tool_schema=DIRECTORY_SCHEMA,
        max_tokens=16384,
    )
