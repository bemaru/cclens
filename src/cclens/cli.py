"""cclens CLI - Claude Code session analytics."""

import json
import sys
import webbrowser
from datetime import datetime

import click

from cclens.parsers.jsonl import load_sessions
from cclens.analyzers.skills import analyze_skills
from cclens.analyzers.tokens import analyze_tokens
from cclens.analyzers.productivity import analyze_productivity
from cclens.analyzers.trends import analyze_trends
from cclens.dashboard.generator import generate_dashboard


def _build_data(sessions, days, project_filter):
    """Run all analyzers and assemble dashboard data dict."""
    skills = analyze_skills(sessions)
    tokens = analyze_tokens(sessions)
    productivity = analyze_productivity(sessions)
    trends = analyze_trends(sessions)

    total_tokens = tokens["total_input_tokens"] + tokens["total_output_tokens"]

    # Top active hours display
    active_hours_display = ", ".join(
        f"{h['hour']}시({h['count']})" for h in productivity["active_hours"][:3]
    ) if productivity["active_hours"] else "-"

    return {
        "overview": {
            "sessions": len(sessions),
            "total_cost_usd": round(tokens["total_cost_usd"], 2),
            "total_tokens": total_tokens,
            "total_lines_changed": productivity["total_lines_changed"],
            "cache_hit_rate": round(tokens["cache_hit_rate"] * 100, 1),
            "active_hours_display": active_hours_display,
        },
        "skills": skills,
        "tokens": tokens,
        "productivity": productivity,
        "trends": trends,
        "meta": {
            "days": days,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "project_filter": project_filter,
        },
    }


def _print_text_report(sessions, data):
    """Print terminal text report (compatible with old analyze.py output)."""
    meta = data["meta"]
    overview = data["overview"]
    skills_data = data["skills"]
    tokens_data = data["tokens"]

    print(f"## cclens 분석 리포트 (최근 {meta['days']}일)")
    if meta["project_filter"]:
        print(f"- 프로젝트 필터: {meta['project_filter']}")
    print(f"- 분석 세션 수: {overview['sessions']}")
    print(f"- 총 도구 호출: {sum(skills_data['tool_counts'].values())}")
    print(f"- 스킬 호출: {sum(skills_data['skill_counts'].values())}")
    print(f"- 추정 비용: ${overview['total_cost_usd']:.2f}")
    print(f"- 캐시 히트율: {overview['cache_hit_rate']}%")
    print(f"- 코드 변경량: ~{overview['total_lines_changed']:,} lines")
    print()

    # Top tools
    tool_counts = skills_data["tool_counts"]
    total_tools = sum(tool_counts.values())
    print("### 도구 사용 빈도 (상위 15)")
    print("| # | 도구 | 호출수 | 비율 |")
    print("|---|------|--------|------|")
    for i, (tool, count) in enumerate(
        sorted(tool_counts.items(), key=lambda x: -x[1])[:15], 1
    ):
        pct = count / total_tools * 100 if total_tools else 0
        print(f"| {i} | {tool} | {count} | {pct:.1f}% |")
    print()

    # Skill usage
    skill_counts = skills_data["skill_counts"]
    if skill_counts:
        print("### 스킬 사용 빈도")
        print("| # | 스킬 | 호출수 |")
        print("|---|------|--------|")
        for i, (skill, count) in enumerate(
            sorted(skill_counts.items(), key=lambda x: -x[1]), 1
        ):
            print(f"| {i} | {skill} | {count} |")
        print()

    # Renamed skills
    if skills_data["renamed_skills"]:
        print("### 이름 변경된 스킬 (자동 매핑됨)")
        for r in skills_data["renamed_skills"]:
            print(f"- `{r['original']}` → `{r['current']}`")
        print()

    # Unused skills
    if skills_data["unused_skills"]:
        print("### 미사용 스킬")
        for s in sorted(skills_data["unused_skills"]):
            print(f"- {s}")
        print()

    # Model breakdown
    model_breakdown = tokens_data["model_breakdown"]
    if model_breakdown:
        print("### 모델별 사용량")
        print("| 모델 | 호출수 | 비용 | 입력토큰 | 출력토큰 |")
        print("|------|--------|------|----------|----------|")
        for model, info in sorted(
            model_breakdown.items(), key=lambda x: -x[1]["cost_usd"]
        ):
            print(
                f"| {model} | {info['count']} | "
                f"${info['cost_usd']:.2f} | "
                f"{info['input_tokens']:,} | "
                f"{info['output_tokens']:,} |"
            )
        print()


@click.command()
@click.option("--html", is_flag=True, help="Generate HTML dashboard")
@click.option("--open", "open_browser", is_flag=True, help="Open dashboard in browser")
@click.option("--days", default=30, type=click.IntRange(min=1), help="Number of days to analyze")
@click.option("--project", default=None, help="Filter by project name")
@click.option("--output", default=None, help="Output path for HTML dashboard")
def main(html, open_browser, days, project, output):
    """cclens - Claude Code session analytics."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    sessions = load_sessions(days=days, project_filter=project)
    if not sessions:
        click.echo(f"최근 {days}일간 세션 데이터가 없습니다.")
        return

    data = _build_data(sessions, days, project)

    if html or open_browser:
        path = generate_dashboard(data, output_path=output)
        click.echo(f"Dashboard generated: {path}")
        if open_browser:
            webbrowser.open(f"file://{path}")
    else:
        _print_text_report(sessions, data)


if __name__ == "__main__":
    main()
