"""Researcher Agent - creates full directories from topics/URLs/files."""

from app.models import Directory
from app.tools.api import call_tool
from app.services.url_fetcher import fetch_url_content
from app.services.exa_search import search_exa
from app.agents.dynamic_schema import get_dynamic_directory_schema
from app.agents.prompts import get_dynamic_system_prompt

# Depth config: maps depth 1-10 to research parameters
DEPTH_CONFIG = {
    1:  {"exa_results": 5,  "max_tokens": 4096,  "sections": "2-3", "blocks": "2-3", "style": "Brief overview"},
    2:  {"exa_results": 8,  "max_tokens": 6144,  "sections": "3-4", "blocks": "3-4", "style": "Concise summary"},
    3:  {"exa_results": 10, "max_tokens": 8192,  "sections": "4-5", "blocks": "3-5", "style": "Solid coverage"},
    4:  {"exa_results": 12, "max_tokens": 10240, "sections": "4-6", "blocks": "4-5", "style": "Thorough research"},
    5:  {"exa_results": 15, "max_tokens": 16384, "sections": "5-7", "blocks": "4-6", "style": "Comprehensive deep-dive"},
    6:  {"exa_results": 18, "max_tokens": 20480, "sections": "6-8", "blocks": "4-7", "style": "Detailed analysis with examples"},
    7:  {"exa_results": 22, "max_tokens": 28672, "sections": "7-9", "blocks": "5-7", "style": "Expert-level reference"},
    8:  {"exa_results": 28, "max_tokens": 36864, "sections": "8-10", "blocks": "5-7", "style": "Exhaustive coverage with real data"},
    9:  {"exa_results": 35, "max_tokens": 49152, "sections": "9-12", "blocks": "5-8", "style": "Encyclopedia-grade deep research"},
    10: {"exa_results": 50, "max_tokens": 65536, "sections": "10-15", "blocks": "6-8", "style": "Maximum depth -- leave no stone unturned"},
}


def _get_depth_config(depth: int) -> dict:
    return DEPTH_CONFIG.get(max(1, min(10, depth)), DEPTH_CONFIG[1])


async def organize_with_claude(
    topic: str = "", items: list = None, instructions: str = "",
    urls: list = None, files: list = None, depth: int = 1,
) -> Directory:
    cfg = _get_depth_config(depth)
    user_msg = ""

    if topic:
        user_msg += "Topic: " + topic + "\n"

    if instructions:
        user_msg += "\nInstructions: " + instructions + "\n"

    if urls:
        user_msg += "\n--- SOURCE URLs ---\n"
        for url in urls:
            content = await fetch_url_content(url)
            user_msg += f"\n[URL: {url}]\n{content}\n"

    if files:
        user_msg += "\n--- UPLOADED FILES ---\n"
        for f in files:
            name = f.get("name", "unknown")
            content = f.get("content", "")
            if len(content) > 30000:
                content = content[:30000] + "\n\n[File truncated at 30,000 characters]"
            user_msg += f"\n[File: {name}]\n{content}\n"

    if items:
        user_msg += "\nItems to organize:\n"
        for item in items:
            line = "- " + (item.get("title", "") if isinstance(item, dict) else str(item))
            user_msg += line + "\n"

    # Exa web search for grounding
    if topic:
        exa_results = await search_exa(topic, num_results=cfg["exa_results"])
        if exa_results and not exa_results.startswith("[Exa search failed"):
            user_msg += "\n--- WEB SEARCH RESULTS (use these as real sources) ---\n"
            user_msg += exa_results + "\n"

    depth_instruction = (
        f"\n\nRESEARCH DEPTH: {depth}/10 ({cfg['style']})"
        f"\nCreate {cfg['sections']} sections with {cfg['blocks']} blocks each."
    )

    if not items and not urls and not files:
        user_msg += (
            depth_instruction +
            "\nResearch this topic using the web search results above as primary sources. "
            "Use mixed block types: code_grid for install/examples, info_grid for features, "
            "comparison for pros/cons, stats for metrics, steps for guides, tips for gotchas, "
            "tables for structured data, faq for common questions, timeline for history, "
            "badges for tech stacks, checklist for requirements. "
            "Include real URLs from the search results and accurate data. "
            "Cite sources where possible."
        )
    else:
        user_msg += (
            depth_instruction +
            "\nAnalyze the provided sources and organize the information into a structured directory. "
            "Determine the topic and title from the content. Create sections for each major concept "
            "with mixed block types for rich display. Preserve important details, code examples, "
            "URLs, and data from the sources. Use web search results to supplement and verify."
        )

    data = await call_tool(
        user_message=user_msg,
        system=get_dynamic_system_prompt(),
        tool_name="create_directory",
        tool_schema=get_dynamic_directory_schema(),
        max_tokens=cfg["max_tokens"],
        use_grounding=True,
    )
    data.pop("_tokens", None)
    return Directory(**data)
