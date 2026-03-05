"""Exa web search for grounding research in real sources."""

import asyncio
import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Lazy-initialized async client
_exa_client = None


def _get_exa_client():
    """Get or create the AsyncExa client."""
    global _exa_client
    load_dotenv(override=True)
    api_key = os.getenv("EXA_API_KEY", "")
    if not api_key:
        return None
    if _exa_client is None:
        from exa_py import AsyncExa
        _exa_client = AsyncExa(api_key=api_key)
    return _exa_client


async def search_exa(query: str, num_results: int = 8, max_chars: int = 10000) -> str:
    """Search Exa for real web content. Returns formatted text for Claude context."""
    client = _get_exa_client()
    if not client:
        return ""

    try:
        logger.info("Exa search: query=%r num_results=%d", query, num_results)
        results = await asyncio.wait_for(
            client.search_and_contents(
                query,
                type="auto",
                num_results=num_results,
                text={"max_characters": max_chars},
            ),
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
