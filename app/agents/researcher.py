"""Researcher Agent - creates full directories from topics/URLs/files."""

from app.models import Directory
from app.tools.api import call_tool
from app.services.url_fetcher import fetch_url_content
from app.agents.dynamic_schema import get_dynamic_directory_schema
from app.agents.prompts import get_dynamic_system_prompt


async def organize_with_claude(
    topic: str = "", items: list = None, instructions: str = "",
    urls: list = None, files: list = None,
) -> Directory:
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

    data = await call_tool(
        user_message=user_msg,
        system=get_dynamic_system_prompt(),
        tool_name="create_directory",
        tool_schema=get_dynamic_directory_schema(),
    )
    data.pop("_tokens", None)
    return Directory(**data)
