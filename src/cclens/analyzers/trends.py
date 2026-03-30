"""Analyze weekly and monthly trends from Claude Code sessions."""

from __future__ import annotations

from collections import Counter, defaultdict

from cclens.parsers.jsonl import SessionData


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read: int = 0,
    cache_creation: int = 0,
) -> float:
    """Estimate USD cost from token counts (sonnet-heavy blended rate)."""
    return (
        input_tokens * 3.0
        + output_tokens * 15.0
        + cache_read * 0.3
        + cache_creation * 3.75
    ) / 1_000_000


def _session_week(session: SessionData) -> str | None:
    """Return ISO week string like '2025-W12' for a session's start_time."""
    if session.start_time is None:
        return None
    iso = session.start_time.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _session_month(session: SessionData) -> str | None:
    """Return month string like '2025-03' for a session's start_time."""
    if session.start_time is None:
        return None
    return session.start_time.strftime("%Y-%m")


def _session_tokens(session: SessionData) -> tuple[int, int, int, int]:
    """Sum (input, output, cache_read, cache_creation) tokens for a session."""
    input_t = 0
    output_t = 0
    cache_read = 0
    cache_creation = 0
    for usage in session.token_usage:
        input_t += usage.get("input_tokens", 0)
        output_t += usage.get("output_tokens", 0)
        cache_read += usage.get("cache_read_input_tokens", 0)
        cache_creation += usage.get("cache_creation_input_tokens", 0)
    return input_t, output_t, cache_read, cache_creation


def _count_skill_calls(session: SessionData) -> int:
    """Count Skill tool invocations in a session."""
    return sum(1 for tu in session.tool_uses if tu.get("tool") == "Skill")


def _count_tool_calls(session: SessionData) -> int:
    """Count all tool invocations in a session."""
    return len(session.tool_uses)


def analyze_trends(sessions: list[SessionData]) -> dict:
    """Analyze weekly and monthly trends across sessions.

    Args:
        sessions: List of parsed SessionData objects.

    Returns:
        Dictionary with keys: weekly, monthly, skill_trends_weekly,
        tool_trends_weekly.
    """
    # --- Aggregate by week and month ---
    week_data: dict[str, dict] = defaultdict(
        lambda: {
            "sessions": 0,
            "skill_calls": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read": 0,
            "cache_creation": 0,
            "lines_changed": 0,
        }
    )
    month_data: dict[str, dict] = defaultdict(
        lambda: {
            "sessions": 0,
            "skill_calls": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read": 0,
            "cache_creation": 0,
            "lines_changed": 0,
        }
    )

    # Per-week counters for skill and tool trends
    skill_week_counter: dict[str, Counter] = defaultdict(Counter)
    tool_week_counter: dict[str, Counter] = defaultdict(Counter)
    total_skill_counter: Counter = Counter()
    total_tool_counter: Counter = Counter()

    for session in sessions:
        week = _session_week(session)
        month = _session_month(session)
        input_t, output_t, cache_r, cache_c = _session_tokens(session)
        skill_calls = _count_skill_calls(session)
        tool_calls = _count_tool_calls(session)

        for key, bucket in [(week, week_data), (month, month_data)]:
            if key is None:
                continue
            agg = bucket[key]
            agg["sessions"] += 1
            agg["skill_calls"] += skill_calls
            agg["tool_calls"] += tool_calls
            agg["input_tokens"] += input_t
            agg["output_tokens"] += output_t
            agg["cache_read"] += cache_r
            agg["cache_creation"] += cache_c
            agg["lines_changed"] += session.lines_changed

        # Per-tool and per-skill tracking (week-level)
        if week is not None:
            for tu in session.tool_uses:
                tool_name = tu.get("tool", "")
                if tool_name:
                    tool_week_counter[tool_name][week] += 1
                    total_tool_counter[tool_name] += 1

                if tool_name == "Skill":
                    skill_name = tu.get("skill", tu.get("skill_original", ""))
                    if skill_name:
                        skill_week_counter[skill_name][week] += 1
                        total_skill_counter[skill_name] += 1

    # --- Build weekly list ---
    weekly = []
    for week in sorted(week_data):
        agg = week_data[week]
        tokens = agg["input_tokens"] + agg["output_tokens"]
        cost = estimate_cost(
            agg["input_tokens"],
            agg["output_tokens"],
            agg["cache_read"],
            agg["cache_creation"],
        )
        weekly.append(
            {
                "week": week,
                "sessions": agg["sessions"],
                "skill_calls": agg["skill_calls"],
                "tool_calls": agg["tool_calls"],
                "tokens": tokens,
                "cost": round(cost, 4),
                "lines_changed": agg["lines_changed"],
            }
        )

    # --- Build monthly list ---
    monthly = []
    for month in sorted(month_data):
        agg = month_data[month]
        tokens = agg["input_tokens"] + agg["output_tokens"]
        cost = estimate_cost(
            agg["input_tokens"],
            agg["output_tokens"],
            agg["cache_read"],
            agg["cache_creation"],
        )
        monthly.append(
            {
                "month": month,
                "sessions": agg["sessions"],
                "skill_calls": agg["skill_calls"],
                "tool_calls": agg["tool_calls"],
                "tokens": tokens,
                "cost": round(cost, 4),
                "lines_changed": agg["lines_changed"],
            }
        )

    # --- Build skill_trends_weekly (skills used >= 3 times total) ---
    all_weeks = sorted(week_data)
    skill_trends_weekly: dict[str, list[dict]] = {}
    for skill_name, total_count in total_skill_counter.items():
        if total_count < 3:
            continue
        week_counts = skill_week_counter[skill_name]
        skill_trends_weekly[skill_name] = [
            {"week": w, "count": week_counts.get(w, 0)} for w in all_weeks
        ]

    # --- Build tool_trends_weekly (top 10 tools) ---
    top_tools = [name for name, _ in total_tool_counter.most_common(10)]
    tool_trends_weekly: dict[str, list[dict]] = {}
    for tool_name in top_tools:
        week_counts = tool_week_counter[tool_name]
        tool_trends_weekly[tool_name] = [
            {"week": w, "count": week_counts.get(w, 0)} for w in all_weeks
        ]

    return {
        "weekly": weekly,
        "monthly": monthly,
        "skill_trends_weekly": skill_trends_weekly,
        "tool_trends_weekly": tool_trends_weekly,
    }
