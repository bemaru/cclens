"""Parse Claude Code session JSONL files from ~/.claude/projects/."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_RENAME_MAP: dict[str, str] = {
    "log-session": "cc-save-session",
    "lunch": "es-suggest-lunch",
    "reviewing-best-practices": "dev-review-standards",
    "bemaru-skills:analyze-github-repo": "maru-plugins:analyze-github-repo",
    "save-session": "cc-save-session",
    "review-session": "cc-review-session",
    "lint-claude-md": "cc-optimize-claude-md",
    "check-skill-usage": "cc-analyze-skill-usage",
    "check-lunch": "es-suggest-lunch",
    "note-daily": "obsidian-note-daily",
    "note-weekly": "obsidian-note-weekly",
    "note-monthly": "obsidian-note-monthly",
    "summarize-youtube": "obsidian-summarize-youtube",
    "vault-audit": "obsidian-audit-vault",
    "summarize-iteration": "es-summarize-iteration",
    "gitlab-issue": "es-manage-gitlab-issue",
    "review-standards": "dev-review-standards",
    "es-check-lunch": "es-suggest-lunch",
    "cc-check-skill-usage": "cc-analyze-skill-usage",
    "obsidian-vault-audit": "obsidian-audit-vault",
}

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


@dataclass
class SessionData:
    """Parsed data from a single Claude Code session JSONL file."""

    session_id: str
    project: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    messages: list[dict] = field(default_factory=list)
    tool_uses: list[dict] = field(default_factory=list)
    token_usage: list[dict] = field(default_factory=list)
    lines_changed: int = 0


def _parse_timestamp(ts: str | None) -> datetime | None:
    """Parse an ISO format timestamp string, returning None on failure."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _normalize_skill(name: str) -> str:
    """Normalize a skill name using the rename map."""
    return SKILL_RENAME_MAP.get(name, name)


def _estimate_lines(text: str | None) -> int:
    """Estimate line count from text content (content length / 40)."""
    if not text:
        return 0
    return max(1, len(text) // 40)


def _extract_tool_uses(record: dict) -> list[dict]:
    """Extract tool_use blocks from an assistant record's message content."""
    tool_uses: list[dict] = []
    message = record.get("message", {})
    if not isinstance(message, dict):
        return tool_uses

    content = message.get("content", [])
    if not isinstance(content, list):
        return tool_uses

    ts = record.get("timestamp")

    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use":
            continue

        tool_name = block.get("name", "")
        tool_input = block.get("input", {})

        entry: dict = {
            "tool": tool_name,
            "timestamp": ts,
        }

        # Detect Skill tool invocations
        if tool_name == "Skill":
            skill_raw = tool_input.get("skill", "")
            if skill_raw:
                entry["skill_original"] = skill_raw
                entry["skill"] = _normalize_skill(skill_raw)

        if tool_input:
            entry["input"] = tool_input
            # Also store args for convenience if present
            args = tool_input.get("args")
            if args is not None:
                entry["args"] = args

        tool_uses.append(entry)

    return tool_uses


def _extract_token_usage(record: dict) -> dict | None:
    """Extract token usage info from an assistant record."""
    message = record.get("message", {})
    if not isinstance(message, dict):
        return None

    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None

    return {
        "timestamp": record.get("timestamp"),
        "model": message.get("model", ""),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
    }


def _compute_lines_changed(tool_uses: list[dict]) -> int:
    """Estimate lines changed from Write and Edit tool uses."""
    total = 0
    for tu in tool_uses:
        tool = tu.get("tool", "")
        inp = tu.get("input", {})
        if not isinstance(inp, dict):
            continue

        if tool == "Write":
            content = inp.get("content", "")
            total += _estimate_lines(content)
        elif tool == "Edit":
            new_string = inp.get("new_string", "")
            total += _estimate_lines(new_string)

    return total


def parse_session(filepath: str | Path) -> SessionData:
    """Parse a single JSONL session file into a SessionData object.

    Args:
        filepath: Path to the .jsonl file.

    Returns:
        Populated SessionData instance.
    """
    filepath = Path(filepath)
    project = filepath.parent.name

    messages: list[dict] = []
    tool_uses: list[dict] = []
    token_usage: list[dict] = []
    session_id = ""
    timestamps: list[datetime] = []

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(record, dict):
                continue

            # Capture session ID from first record that has one
            if not session_id:
                sid = record.get("sessionId", "")
                if sid:
                    session_id = sid

            record_type = record.get("type", "")
            ts = _parse_timestamp(record.get("timestamp"))
            if ts is not None:
                timestamps.append(ts)

            # Store message summary
            messages.append(
                {
                    "type": record_type,
                    "timestamp": record.get("timestamp"),
                    "sessionId": record.get("sessionId"),
                }
            )

            # Process assistant records for tool uses and token usage
            if record_type == "assistant":
                tool_uses.extend(_extract_tool_uses(record))

                usage_entry = _extract_token_usage(record)
                if usage_entry is not None:
                    token_usage.append(usage_entry)

    start_time = min(timestamps) if timestamps else None
    end_time = max(timestamps) if timestamps else None

    # Fall back to session ID from filename if not found in records
    if not session_id:
        session_id = filepath.stem

    lines_changed = _compute_lines_changed(tool_uses)

    return SessionData(
        session_id=session_id,
        project=project,
        start_time=start_time,
        end_time=end_time,
        messages=messages,
        tool_uses=tool_uses,
        token_usage=token_usage,
        lines_changed=lines_changed,
    )


def load_sessions(
    days: int = 30,
    project_filter: str | None = None,
) -> list[SessionData]:
    """Load all sessions from ~/.claude/projects/.

    Args:
        days: Only include sessions from files modified within this many days.
        project_filter: If set, only load sessions from projects whose
            directory name contains this string.

    Returns:
        List of SessionData objects, sorted by start_time (oldest first).
    """
    if not CLAUDE_PROJECTS_DIR.exists():
        return []

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    cutoff_naive = cutoff.replace(tzinfo=None)
    sessions: list[SessionData] = []

    for jsonl_file in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
        # Skip subagent files
        if "subagents" in str(jsonl_file):
            continue

        # Apply project filter
        if project_filter is not None:
            # The project directory is the parent of the jsonl file
            project_name = jsonl_file.parent.name
            if project_filter not in project_name:
                continue

        # Filter by modification time
        mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
        if mtime < cutoff_naive:
            continue

        try:
            session = parse_session(jsonl_file)
            sessions.append(session)
        except (OSError, UnicodeDecodeError):
            continue

    _epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    sessions.sort(
        key=lambda s: (
            s.start_time.replace(tzinfo=timezone.utc)
            if s.start_time and s.start_time.tzinfo is None
            else s.start_time or _epoch
        )
    )
    return sessions
