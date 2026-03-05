import httpx


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
                if len(text) > 50000:
                    text = text[:50000] + "\n\n[Content truncated at 50,000 characters]"
                return text
            return f"[Binary content at {url}, type: {content_type}]"
    except Exception as e:
        return f"[Error fetching {url}: {e}]"
