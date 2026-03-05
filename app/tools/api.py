"""Low-level Claude API caller. The single point of contact with Anthropic."""

import os

import httpx
from dotenv import load_dotenv

from app.tools.token_tracker import record_tokens

API_URL = "https://api.anthropic.com/v1/messages"


async def call_tool(
    user_message: str,
    system: str,
    tool_name: str,
    tool_schema: dict,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 16384,
) -> dict:
    """Call Claude API with tool_use structured output. Returns the tool input dict."""
    load_dotenv(override=True)
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "tools": [
            {
                "name": tool_name,
                "description": "Produce structured output",
                "input_schema": tool_schema,
            }
        ],
        "tool_choice": {"type": "tool", "name": tool_name},
        "messages": [{"role": "user", "content": user_message}],
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(API_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            raise RuntimeError("Anthropic API " + str(resp.status_code) + ": " + resp.text)
        data = resp.json()

        usage = data.get("usage", {})
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        token_info = record_tokens(input_t, output_t, model)

        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                result = block["input"]
                result["_tokens"] = token_info
                return result
        raise RuntimeError("No tool_use block in response")
