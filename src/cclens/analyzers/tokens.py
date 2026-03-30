"""Token usage and cost analysis for Claude Code sessions."""

from __future__ import annotations

from collections import defaultdict

from cclens.parsers.jsonl import SessionData

MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.5,
        "cache_write": 18.75,
    },
    "claude-sonnet-4": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.3,
        "cache_write": 3.75,
    },
    "claude-haiku-4": {
        "input": 0.80,
        "output": 4.0,
        "cache_read": 0.08,
        "cache_write": 1.0,
    },
}

_DEFAULT_PRICING_KEY = "claude-sonnet-4"


def _get_pricing(model: str) -> dict[str, float]:
    """Look up pricing for a model string.

    Matches by checking if the model string starts with a known pricing key.
    Falls back to sonnet pricing if no match is found.
    """
    for key, pricing in MODEL_PRICING.items():
        if model.startswith(key):
            return pricing
    return MODEL_PRICING[_DEFAULT_PRICING_KEY]


def _compute_cost(
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
    pricing: dict[str, float],
) -> float:
    """Compute cost in USD for a single token usage record."""
    return (
        input_tokens * pricing["input"]
        + output_tokens * pricing["output"]
        + cache_creation_tokens * pricing["cache_write"]
        + cache_read_tokens * pricing["cache_read"]
    ) / 1_000_000


def analyze_tokens(sessions: list[SessionData]) -> dict:
    """Analyze token usage and cost across sessions.

    Args:
        sessions: List of parsed session data objects. Each session has
            a ``token_usage`` list of dicts with keys: model, input_tokens,
            output_tokens, cache_creation_tokens, cache_read_tokens, timestamp.

    Returns:
        Dictionary containing aggregated token statistics, cost breakdowns,
        daily costs, and per-model breakdowns.
    """
    total_input = 0
    total_output = 0
    total_cache_creation = 0
    total_cache_read = 0
    total_cost = 0.0

    model_breakdown: dict[str, dict] = defaultdict(
        lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation": 0,
            "cache_read": 0,
            "cost_usd": 0.0,
            "count": 0,
        }
    )

    daily_agg: dict[str, dict] = defaultdict(
        lambda: {
            "cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
    )

    for session in sessions:
        for usage in session.token_usage:
            model = usage.get("model", "unknown")
            inp = usage.get("input_tokens", 0)
            out = usage.get("output_tokens", 0)
            cache_create = usage.get("cache_creation_input_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            timestamp = usage.get("timestamp", "")

            pricing = _get_pricing(model)
            cost = _compute_cost(inp, out, cache_create, cache_read, pricing)

            total_input += inp
            total_output += out
            total_cache_creation += cache_create
            total_cache_read += cache_read
            total_cost += cost

            mb = model_breakdown[model]
            mb["input_tokens"] += inp
            mb["output_tokens"] += out
            mb["cache_creation"] += cache_create
            mb["cache_read"] += cache_read
            mb["cost_usd"] += cost
            mb["count"] += 1

            date_key = timestamp[:10] if len(timestamp) >= 10 else "unknown"
            day = daily_agg[date_key]
            day["cost"] += cost
            day["input_tokens"] += inp
            day["output_tokens"] += out

    denominator = total_cache_read + total_cache_creation + total_input
    cache_hit_rate = total_cache_read / denominator if denominator > 0 else 0.0

    daily_costs = sorted(
        [
            {
                "date": date,
                "cost": vals["cost"],
                "input_tokens": vals["input_tokens"],
                "output_tokens": vals["output_tokens"],
            }
            for date, vals in daily_agg.items()
        ],
        key=lambda x: x["date"],
    )

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_creation_tokens": total_cache_creation,
        "total_cache_read_tokens": total_cache_read,
        "total_cost_usd": total_cost,
        "cache_hit_rate": cache_hit_rate,
        "model_breakdown": dict(model_breakdown),
        "daily_costs": daily_costs,
        "token_type_distribution": {
            "input": total_input,
            "output": total_output,
            "cache_creation": total_cache_creation,
            "cache_read": total_cache_read,
        },
    }
