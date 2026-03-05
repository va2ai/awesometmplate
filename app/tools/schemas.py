"""All tool schemas used with Claude's tool_use structured output."""

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
                                        "link_list", "code_grid", "info_grid", "comparison",
                                        "stats", "steps", "tip", "text", "table", "faq",
                                        "timeline", "alert", "badges", "checklist",
                                        "quote", "key_value", "chart", "progress",
                                        "accordion", "tabs",
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
                                    "checklist: {items: [{text, checked: bool}]}. "
                                    "quote: {text: str, attribution: str, source: str}. "
                                    "key_value: {items: [{key: str, value: str}]}. "
                                    "chart: {type: 'bar'|'pie'|'line'|'doughnut', title: str, labels: [str], datasets: [{label: str, data: [number], color: str}]}. "
                                    "progress: {items: [{label: str, value: number, max: number, color: str}]}. "
                                    "accordion: {items: [{title: str, content: str}]}. "
                                    "tabs: {tabs: [{label: str, content: str}]}.",
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

PAGE_ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "page_slug": {"type": "string", "description": "The slug of the page this topic belongs to"},
        "reasoning": {"type": "string", "description": "One sentence explaining why"},
    },
    "required": ["page_slug", "reasoning"],
}

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
