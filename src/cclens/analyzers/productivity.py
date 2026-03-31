"""Analyze session productivity metrics."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone

from cclens.parsers.jsonl import SessionData

_WEEKDAY_NAMES = list(calendar.day_name)  # Monday .. Sunday


def _session_tokens(session: SessionData) -> int:
    """Sum input + output tokens across all usage records in a session."""
    total = 0
    for u in session.token_usage:
        total += u.get("input_tokens", 0) + u.get("output_tokens", 0)
    return total


def _session_duration_min(session: SessionData) -> float:
    """Duration in minutes, or 0 if start/end times are missing."""
    if session.start_time and session.end_time:
        start = session.start_time
        end = session.end_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return (end - start).total_seconds() / 60
    return 0.0


def analyze_productivity(sessions: list[SessionData]) -> dict:
    """Compute productivity analytics from a list of parsed sessions.

    Returns a dict with keys:
        hourly_heatmap, session_scores, avg_session_duration_min,
        total_lines_changed, active_hours, active_days.
    """

    # --- hourly heatmap: 7 weekdays x 24 hours ---
    heatmap: list[list[int]] = [[0] * 24 for _ in range(7)]
    hour_counts: dict[int, int] = {}
    day_counts: dict[int, int] = {}

    for s in sessions:
        if s.start_time is not None:
            wd = s.start_time.weekday()  # 0=Mon
            hr = s.start_time.hour
            heatmap[wd][hr] += 1
            hour_counts[hr] = hour_counts.get(hr, 0) + 1
            day_counts[wd] = day_counts.get(wd, 0) + 1

    # --- session scores ---
    scores: list[dict] = []
    total_duration = 0.0
    total_lines = 0

    for s in sessions:
        dur = _session_duration_min(s)
        tokens = _session_tokens(s)
        lc = s.lines_changed
        score = lc / max(tokens / 1000, 1)

        date_str = s.start_time.date().isoformat() if s.start_time else ""

        scores.append(
            {
                "session_id": s.session_id,
                "project": s.project,
                "date": date_str,
                "duration_min": round(dur, 1),
                "tool_count": len(s.tool_uses),
                "lines_changed": lc,
                "tokens_used": tokens,
                "score": round(score, 2),
            }
        )

        total_duration += dur
        total_lines += lc

    # Sort by date descending
    scores.sort(key=lambda r: r["date"], reverse=True)

    avg_duration = total_duration / len(sessions) if sessions else 0.0

    # --- active hours: top 5 ---
    active_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    active_hours = [{"hour": h, "count": c} for h, c in active_hours]

    # --- active days: all weekdays with counts, sorted by count desc ---
    active_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)
    active_days = [
        {"day": _WEEKDAY_NAMES[wd], "count": c} for wd, c in active_days
    ]

    return {
        "hourly_heatmap": heatmap,
        "session_scores": scores,
        "avg_session_duration_min": round(avg_duration, 1),
        "total_lines_changed": total_lines,
        "active_hours": active_hours,
        "active_days": active_days,
    }
