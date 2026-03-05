"""Low-level Gemini API caller. The single point of contact with Google AI."""

import json
import logging
import os

import httpx
from dotenv import load_dotenv

from app.config import API_TIMEOUT
from app.tools.token_tracker import record_tokens

logger = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Map old Claude model names to Gemini models
MODEL_MAP = {
    "claude-sonnet-4-6": "gemini-3.1-flash-lite-preview",
    "claude-haiku-4-5-20251001": "gemini-3.1-flash-lite-preview",
}


async def call_tool(
    user_message: str,
    system: str,
    tool_name: str,
    tool_schema: dict,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 16384,
) -> dict:
    """Call Gemini API with JSON structured output. Returns the parsed dict."""
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY", "")

    gemini_model = MODEL_MAP.get(model, "gemini-2.5-flash")
    url = f"{API_URL}/{gemini_model}:generateContent?key={api_key}"

    # Build schema instruction from the tool schema description
    schema_hint = json.dumps(tool_schema, indent=2)

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": user_message + "\n\nRespond with JSON matching this schema:\n" + schema_hint}]}
        ],
        "systemInstruction": {
            "parts": [{"text": system}]
        },
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingLevel": "HIGH"},
        },
    }

    logger.info("Gemini API call: model=%s tool=%s", gemini_model, tool_name)

    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.error("Gemini API error: %d body=%s", resp.status_code, resp.text[:1000])
            raise RuntimeError(f"Gemini API {resp.status_code}: {resp.text[:500]}")
        data = resp.json()

        # Extract token usage
        usage_meta = data.get("usageMetadata", {})
        input_t = usage_meta.get("promptTokenCount", 0)
        output_t = usage_meta.get("candidatesTokenCount", 0)
        token_info = record_tokens(input_t, output_t, model)

        logger.info(
            "Gemini API response: model=%s in=%d out=%d cost=$%.4f",
            gemini_model, input_t, output_t, token_info["cost_usd"],
        )

        # Parse JSON from response text
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("No candidates in Gemini response")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError("No parts in Gemini response")

        # With thinking enabled, response has multiple parts:
        # thinking parts (thought=True) + the actual text part
        # Find the last non-thought part with text content
        text = ""
        for part in reversed(parts):
            if part.get("thought"):
                continue
            if part.get("text"):
                text = part["text"]
                break
        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini JSON: %s\nRaw: %s", e, text[:500])
            raise RuntimeError(f"Failed to parse Gemini JSON response: {e}")

        result["_tokens"] = token_info
        return result
