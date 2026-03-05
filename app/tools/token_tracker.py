"""Token usage tracking - records cost per API call."""

import json
import threading
from datetime import datetime

from app.config import DATA_DIR, PRICING, TOKEN_FILE

_lock = threading.Lock()


def load_token_usage() -> dict:
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"total_input": 0, "total_output": 0, "total_cost_usd": 0.0, "calls": 0, "history": []}


def save_token_usage(usage: dict):
    DATA_DIR.mkdir(exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(usage, f, indent=2, ensure_ascii=False)


def record_tokens(input_tokens: int, output_tokens: int, model: str = "claude-sonnet-4-6"):
    rates = PRICING.get(model, PRICING["claude-sonnet-4-6"])
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000

    with _lock:
        usage = load_token_usage()
        usage["total_input"] += input_tokens
        usage["total_output"] += output_tokens
        usage["total_cost_usd"] = round(usage["total_cost_usd"] + cost, 6)
        usage["calls"] += 1
        usage["history"].append({
            "timestamp": datetime.now().isoformat(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "model": model,
        })
        usage["history"] = usage["history"][-100:]
        save_token_usage(usage)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": round(cost, 6), "model": model}
