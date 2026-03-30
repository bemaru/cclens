# cclens

Claude Code 세션 데이터(JSONL)를 분석하여 HTML 대시보드를 생성하는 Python CLI.

## 설치

```bash
uv tool install cclens
```

## 사용법

```bash
cclens                    # 터미널 텍스트 리포트
cclens --html             # HTML 대시보드 생성
cclens --html --open      # 생성 + 브라우저 열기
cclens --days 30          # 기간 지정
cclens --project edr      # 프로젝트 필터
```

## 대시보드 탭

1. **Overview** — 세션수, 비용, 토큰, LoC, 캐시히트율, 활동시간
2. **Skills** — 카테고리 도넛, 사용빈도 막대, 관계도, 미사용 하이라이트
3. **Tokens** — 모델별 비용 추이, 토큰 분포, 캐시 효율
4. **Productivity** — 시간대×요일 히트맵, 세션당 생산성 스코어
5. **Trends** — 주/월별 스킬/비용/토큰 추이

## 차별점

- ccusage/Agentlytics에 없는 **스킬 생태계 분석** (카테고리, 관계도, 미사용 진단)
- 스킬 이름 변경 자동 매핑
- 단일 HTML 파일 대시보드 (Chart.js CDN)
