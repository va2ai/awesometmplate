"""Exa web search for grounding research in real sources."""

import asyncio
import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _sync_exa_search(api_key: str, query: str, num_results: int, max_chars: int):
    """Run Exa search synchronously (called via asyncio.to_thread)."""
    from exa_py import Exa
    exa = Exa(api_key=api_key)
    return exa.search_and_contents(
        query,
        type="auto",
        num_results=num_results,
        text={"max_characters": max_chars},
    )


async def search_exa(query: str, num_results: int = 8, max_chars: int = 10000) -> str:
    """Search Exa for real web content. Returns formatted text for Claude context."""
    load_dotenv(override=True)
    api_key = os.getenv("EXA_API_KEY", "")
    if not api_key:
        return ""

    try:
        logger.info("Exa search: query=%r num_results=%d", query, num_results)
        results = await asyncio.wait_for(
            asyncio.to_thread(_sync_exa_search, api_key, query, num_results, max_chars),
            timeout=30.0,
        )

        if not results.results:
            logger.info("Exa search returned 0 results")
            return ""

        logger.info("Exa search returned %d results", len(results.results))

        parts = []
        for r in results.results:
            title = getattr(r, "title", "") or ""
            url = getattr(r, "url", "") or ""
            text = getattr(r, "text", "") or ""
            if text:
                text = text[:max_chars]
            parts.append(f"### {title}\nURL: {url}\n{text}\n")

        return "\n---\n".join(parts)
    except asyncio.TimeoutError:
        logger.warning("Exa search timed out after 30s for query=%r", query)
        return "[Exa search timed out]"
    except Exception as e:
        logger.error("Exa search failed: %s", e)
        return f"[Exa search failed: {e}]"
