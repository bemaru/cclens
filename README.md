# cclens

Analyze Claude Code session data (JSONL) and generate interactive HTML dashboards.

Claude Code 세션 데이터(JSONL)를 분석하여 HTML 대시보드를 생성하는 Python CLI.

## Install

```bash
pip install cclens
# or
uv tool install cclens
```

## Usage

```bash
cclens                    # Terminal text report
cclens --html             # Generate HTML dashboard
cclens --html --open      # Generate + open in browser
cclens --days 30          # Set analysis period
cclens --project edr      # Filter by project name
```

## Dashboard Tabs

1. **Overview** — Sessions, cost, tokens, lines changed, cache hit rate, active hours
2. **Skills** — Category donut, usage bar chart, workflow relations, unused skill detection
3. **Tokens** — Daily cost trend, token distribution, model breakdown, cache efficiency
4. **Productivity** — Weekday x hour heatmap, session productivity scores
5. **Trends** — Weekly/monthly skill, cost, and token trends

## What Makes It Different

- **Skill ecosystem analysis** not found in ccusage/Agentlytics (categories, relations, unused detection)
- Automatic skill rename mapping across name changes
- Single self-contained HTML dashboard (Chart.js CDN)
- Model-aware cost estimation (Opus/Sonnet/Haiku pricing)

## License

MIT
