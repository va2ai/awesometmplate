"""Dynamic schema builders that incorporate custom block types."""

import json

from app.tools.schemas import DIRECTORY_SCHEMA
from app.services.block_creator import (
    load_custom_blocks,
    get_schema_description_for_custom,
)


def _get_block_enum():
    return [
        "link_list", "code_grid", "info_grid", "comparison", "stats",
        "steps", "tip", "text", "table", "faq", "timeline", "alert",
        "badges", "checklist",
    ] + [b["type_name"] for b in load_custom_blocks()]


def _get_content_description():
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
    custom_desc = get_schema_description_for_custom()
    if custom_desc:
        base += " " + custom_desc
    return base


def get_dynamic_directory_schema():
    """Build DIRECTORY_SCHEMA with current block types (including custom)."""
    schema = json.loads(json.dumps(DIRECTORY_SCHEMA))
    blocks_items = schema["properties"]["sections"]["items"]["properties"]["blocks"]["items"]
    blocks_items["properties"]["type"]["enum"] = _get_block_enum()
    blocks_items["properties"]["content"]["description"] = _get_content_description()
    return schema
