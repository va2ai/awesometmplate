"""Exa web search for grounding research in real sources."""

import os
from dotenv import load_dotenv


async def search_exa(query: str, num_results: int = 8, max_chars: int = 10000) -> str:
    """Search Exa for real web content. Returns formatted text for Claude context."""
    load_dotenv(override=True)
    api_key = os.getenv("EXA_API_KEY", "")
    if not api_key:
        return ""

    try:
        from exa_py import Exa
        exa = Exa(api_key=api_key)
        results = exa.search_and_contents(
            query,
            type="auto",
            num_results=num_results,
            text={"max_characters": max_chars},
        )

        if not results.results:
            return ""

        parts = []
        for r in results.results:
            title = getattr(r, "title", "") or ""
            url = getattr(r, "url", "") or ""
            text = getattr(r, "text", "") or ""
            if text:
                text = text[:max_chars]
            parts.append(f"### {title}\nURL: {url}\n{text}\n")

        return "\n---\n".join(parts)
    except Exception as e:
        return f"[Exa search failed: {e}]"
