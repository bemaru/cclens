"""Analyze skill usage from parsed session data."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from cclens.parsers.jsonl import SessionData

CATEGORIES: dict[str, dict[str, str]] = {
    "craft": {"label": "Dev Quality", "color": "#6366f1"},
    "es": {"label": "Work", "color": "#f59e0b"},
    "obsidian": {"label": "PKM", "color": "#10b981"},
    "cc": {"label": "Meta", "color": "#8b5cf6"},
    "feature-dev": {"label": "Feature Dev", "color": "#ec4899"},
    "agent-sdk-dev": {"label": "Agent SDK", "color": "#14b8a6"},
    "frontend-design": {"label": "Frontend", "color": "#f97316"},
    "code-review": {"label": "Code Review", "color": "#ef4444"},
}

SKILL_RELATIONS: list[tuple[str, str, str]] = [
    ("es-daily-scrum", "es-summarize-iteration", "Mon~Thu → Fri"),
    ("obsidian-review-daily-note", "obsidian-summarize-weekly-note", "daily → weekly"),
    ("obsidian-summarize-weekly-note", "obsidian-summarize-monthly-note", "weekly → monthly"),
    ("craft-research", "craft-code-review", "research → review"),
    ("craft-code-review", "craft-review-loop", "review → fix loop"),
    ("craft-code-review", "craft-test-loop", "review → test loop"),
    ("craft-collect-competitor", "craft-ux-audit", "collect → audit"),
    ("cc-review-session", "obsidian-save-note", "extract → save"),
]

_DEFAULT_CATEGORY = {"label": "Other", "color": "#64748b"}

SKILLS_DIR = Path.home() / ".claude" / "skills"


def _categorize(skill_name: str) -> str:
    """Return the category key for a skill name.

    Checks whether the skill name starts with ``prefix-`` for each known
    category prefix.  Returns ``"other"`` when no prefix matches.
    """
    for prefix in CATEGORIES:
        if skill_name.startswith(f"{prefix}-") or skill_name.startswith(f"{prefix}:"):
            return prefix
    return "other"


def _get_registered_skills() -> list[str]:
    """List registered skill names from ~/.claude/skills/ subdirectories."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(d.name for d in SKILLS_DIR.iterdir() if d.is_dir())


def analyze_skills(sessions: list[SessionData]) -> dict:
    """Analyze skill and tool usage across sessions.

    Args:
        sessions: List of parsed session data objects.

    Returns:
        Dictionary with keys: ``skill_counts``, ``tool_counts``,
        ``categories``, ``skill_list``, ``relations``, ``unused_skills``,
        ``renamed_skills``.
    """
    skill_counter: Counter[str] = Counter()
    tool_counter: Counter[str] = Counter()
    renamed_seen: set[tuple[str, str]] = set()

    for session in sessions:
        for tu in session.tool_uses:
            tool_name = tu.get("tool", "")
            if tool_name:
                tool_counter[tool_name] += 1

            # Count skill invocations
            if tool_name == "Skill":
                skill = tu.get("skill", "")
                if skill:
                    skill_counter[skill] += 1

                # Track renames
                original = tu.get("skill_original", "")
                if original and original != skill:
                    renamed_seen.add((original, skill))

    # --- categories ---
    registered = _get_registered_skills()
    used_skills = set(skill_counter.keys())

    categories: dict[str, dict] = {}
    for key, meta in CATEGORIES.items():
        cat_skills = [s for s in registered if _categorize(s) == key]
        cat_used = [s for s in cat_skills if s in used_skills]
        categories[key] = {
            "label": meta["label"],
            "color": meta["color"],
            "count": sum(skill_counter[s] for s in cat_skills),
            "total": len(cat_skills),
            "used": len(cat_used),
        }

    # "other" category for skills that don't match any prefix
    other_skills = [s for s in registered if _categorize(s) == "other"]
    other_used = [s for s in other_skills if s in used_skills]
    if other_skills or any(_categorize(s) == "other" for s in used_skills):
        # Also include used skills not in registered but categorized as other
        all_other = set(other_skills) | {s for s in used_skills if _categorize(s) == "other"}
        categories["other"] = {
            "label": _DEFAULT_CATEGORY["label"],
            "color": _DEFAULT_CATEGORY["color"],
            "count": sum(skill_counter[s] for s in all_other),
            "total": len(other_skills),
            "used": len(other_used),
        }

    # --- skill_list ---
    all_skill_names = set(registered) | used_skills
    skill_list = sorted(
        [
            {
                "name": name,
                "count": skill_counter.get(name, 0),
                "category": _categorize(name),
                "used": name in used_skills,
            }
            for name in all_skill_names
        ],
        key=lambda s: s["count"],
        reverse=True,
    )

    # --- relations ---
    relations = [
        {
            "src": src,
            "dst": dst,
            "label": label,
            "src_count": skill_counter.get(src, 0),
            "dst_count": skill_counter.get(dst, 0),
        }
        for src, dst, label in SKILL_RELATIONS
    ]

    # --- unused ---
    unused_skills = sorted(s for s in registered if s not in used_skills)

    # --- renamed ---
    renamed_skills = sorted(
        [{"original": orig, "current": cur} for orig, cur in renamed_seen],
        key=lambda r: r["original"],
    )

    return {
        "skill_counts": dict(skill_counter),
        "tool_counts": dict(tool_counter),
        "categories": categories,
        "skill_list": skill_list,
        "relations": relations,
        "unused_skills": unused_skills,
        "renamed_skills": renamed_skills,
    }
