import ipaddress
import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Private/reserved IP ranges to block (SSRF prevention)
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_url(url: str) -> bool:
    """Check if URL resolves to a private/reserved IP."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True
        # Block common private hostnames
        if hostname in ("localhost", "0.0.0.0", "metadata.google.internal"):
            return True
        try:
            addr = ipaddress.ip_address(hostname)
            return any(addr in net for net in _BLOCKED_NETWORKS)
        except ValueError:
            # It's a domain name, not an IP - allow it
            return False
    except Exception:
        return True


async def fetch_url_content(url: str) -> str:
    """Fetch text content from a URL."""
    if _is_private_url(url):
        logger.warning("Blocked SSRF attempt: %s", url)
        return "[URL blocked: private/internal addresses are not allowed]"

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
        logger.error("URL fetch failed for %s: %s", url, e)
        return f"[Error fetching URL]"
