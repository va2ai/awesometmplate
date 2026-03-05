"""Smart Adder - orchestrates the three-phase smart add pipeline.

Phase 1: Router (Haiku) -> Phase 2: Merger/Creator (Sonnet) -> Phase 3: Taxonomist (conditional)
"""

from app.models import Directory
from app.agents.router import route_to_section
from app.agents.merger import merge_into_section, create_section
from app.agents.taxonomist import check_taxonomy, execute_restructure


def _build_section_summaries(directory: Directory) -> str:
    lines = []
    for i, sec in enumerate(directory.sections):
        block_count = len(sec.blocks)
        lines.append(f"{i}. {sec.title} - {sec.description} ({block_count} blocks)")
    return "\n".join(lines)


def _build_title_list(directory: Directory) -> str:
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
    route = await route_to_section(summaries, new_topic, new_description)
    route.pop("_tokens", None)
    action = route.get("action", "create_new")
    target_idx = route.get("target_section")

    # Phase 2: Merge or Create (Sonnet - targeted)
    if action == "add_to_existing" and target_idx is not None and 0 <= target_idx < section_count:
        target = sections[target_idx].model_dump()
        updated = await merge_into_section(target, titles, new_topic, new_description)
        updated.pop("_tokens", None)
        dir_data = existing_directory.model_dump()
        dir_data["sections"][target_idx] = updated
        result_dir = Directory(**dir_data)
    elif action == "restructure_needed" and section_count >= 8:
        new_section = await create_section(titles, new_topic, new_description)
        new_section.pop("_tokens", None)
        dir_data = existing_directory.model_dump()
        dir_data["sections"].append(new_section)
        result_dir = Directory(**dir_data)
    else:
        new_section = await create_section(titles, new_topic, new_description)
        new_section.pop("_tokens", None)
        dir_data = existing_directory.model_dump()
        dir_data["sections"].append(new_section)
        result_dir = Directory(**dir_data)

    # Phase 3: Taxonomy Check (conditional - only if >8 sections)
    if len(result_dir.sections) > 8:
        new_summaries = _build_section_summaries(result_dir)
        tax_check = await check_taxonomy(new_summaries, len(result_dir.sections))
        tax_check.pop("_tokens", None)

        if tax_check.get("needs_restructure") and tax_check.get("merge_plan"):
            merge_plan = tax_check["merge_plan"]
            all_merge_indices = set()
            for group in merge_plan:
                all_merge_indices.update(group["merge_indices"])

            sections_data = result_dir.model_dump()["sections"]
            sections_to_merge = [sections_data[i] for i in sorted(all_merge_indices) if i < len(sections_data)]

            restructured = await execute_restructure(merge_plan, sections_to_merge)
            restructured.pop("_tokens", None)

            merged_sections = restructured.get("sections", [])
            unmerged = [s for i, s in enumerate(sections_data) if i not in all_merge_indices]
            final_sections = unmerged + merged_sections

            dir_data = result_dir.model_dump()
            dir_data["sections"] = final_sections
            dir_data["title"] = existing_directory.title
            dir_data["subtitle"] = existing_directory.subtitle
            result_dir = Directory(**dir_data)

    return result_dir
