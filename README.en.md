# Windvane (风向标)

**[中文](README.md) · English**

[![CI](https://github.com/Gnosil/weathervane/actions/workflows/ci.yml/badge.svg)](https://github.com/Gnosil/weathervane/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Quantifying "information risk" in macro markets and single stocks with LLMs.** When a company claims an industry pivot in its filings, is it a *real structural change* — or just an industry buzzword, a shell repackaging, or a narrative that hasn't materialized? Windvane starts from public SEC filings and uses a two-stage LLM pipeline (extract + self-critique) to turn that "how-true-is-this" question into a comparable, back-testable score.

> Output is algorithmic analysis of public information. **Not investment advice.** For research only.

## What it solves

Markets react hard to "transformation narratives," but those narratives are full of noise: every company in a sector bolts "AI / cloud" onto its 10-K the same quarter, a renamed segment gets called a restructuring, shell companies chase whatever's hot. **Information risk = how much of the change you're reading is actually real.** Windvane makes this measurable, verifiable, and reproducible:

- **Detect** — year-over-year 10-K semantic diff; extract real changes in segments, keywords, narrative, and risk factors
- **De-hype** — a second LLM pass independently re-checks the evidence, strips industry-wide drift, and grades shell/repackaging quality
- **Score** — rolling Gaussian z-score normalizes "subjective pivot strength" into a cross-company percentile
- **Validate** — backtest the signal's real performance (α vs SPY), staying honest about "detection ≠ profit"
- **Aggregate** — roll single-stock moves up into a theme × sector macro map

## Architecture

```
SEC EDGAR (S&P 500 10-K / 10-Q)
  │  edgar/  — rate-limited client + Item 1/1A/7 extraction
  ▼
LLM stage 1: extract industry-pivot signal + raw_strength ∈ [0,1]  (with quoted evidence)
  │  llm/stage1_extract.py
  ▼
LLM stage 2: self-critique — evidence re-check + industry-drift filter + shell grading
  │  llm/stage2_critique.py       ← the core "information risk" gate
  ▼
rolling Gaussian z-score (window=200, cold-start prior)
  │  scoring/
  ▼
full-universe scan + ranking  (scan/)  →  Markdown / web leaderboard
  │
  ▼
yfinance backtest (T+5/20/60/120d α vs SPY)   (backtest/)
```

## One honest through-line

**Accurate detection ≠ making money.** Blind tests show the model cleanly separates real pivots from stable names and sees through buzzwords — but the backtest also shows that naively buying after detection underperforms the market at T+60, because many pivots are already priced in when announced. So Windvane is a **quantitative lens on information risk** (what's real, what capital is being reallocated toward), not a return predictor. That constraint is baked into every layer.

## Quick start

```bash
uv sync                            # install deps (Python managed by uv)
cp .env.example .env               # fill ANTHROPIC_API_KEY + EDGAR_USER_AGENT
uv run windvane --help
uv run windvane init               # init SQLite + fixture universe
uv run windvane load-universe      # load the full S&P 500
```

## Commands

```bash
windvane scan                      # L1 full-universe screen
windvane scan --ticker DOCU        # single name
windvane report --date 2026-05-29  # render a day's report
windvane backtest --fixtures       # 12-fixture acceptance backtest
windvane backtest --ticker DOCU --entry 2024-04-01
windvane daemon                    # daily scheduled run
```

## Acceptance fixtures

- **Positives** (z ≥ 2, real pivots): DOCU / TWLO / HON / SNAP / NET
- **Shell counter-examples** (critique must catch + grade): BIRD / CAPS
- **Negatives** (z < 1, stable): KO / PG / JNJ / WMT / JPM

## Contributing 🙌

The project's value is in **algorithm quality** and **breadth of information sources** — both welcome improvement. See [CONTRIBUTING.md](CONTRIBUTING.md).

- **Improve the algorithm** — better semantic diff, stricter industry-drift discrimination, more robust shell grading, z-score calibration, prompt engineering
- **Add market information** — wire in more public sources (8-K events, news streams, 13F/Form 4 ownership, industry data) and fold new information-risk dimensions into the score
- **Extend the backtest** — more samples, more windows, tighter controls

The scoring methodology, prompts, and schemas live in `windvane/llm/` and `windvane/scoring/`.

## License

[MIT](LICENSE) — free to use, modify, distribute. PRs welcome.

## Disclaimer

Output is algorithmic analysis of public information (SEC filings, etc.) and does not constitute investment or financial advice. All investment decisions and outcomes are the user's own responsibility.
