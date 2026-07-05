# Contributing to Windvane · 贡献指南

Thanks for your interest! Windvane's value lies in two things: **algorithm quality** and **breadth of information sources**. Both are open for improvement.

感谢参与!这个项目的价值在**算法质量**与**信息源广度**,两条都欢迎优化。

## Ways to contribute · 怎么贡献

1. **Improve the algorithm · 优化算法**
   - Better year-over-year semantic diff of filings
   - Stricter *industry-drift* discrimination (generic "AI/cloud" vs company-specific)
   - More robust shell / repackaging grading
   - z-score calibration, cold-start priors
   - Prompt engineering for stage-1 extract / stage-2 critique
   - Files: `windvane/llm/`, `windvane/scoring/`

2. **Add market information · 接入更多信息源**
   - 8-K material events, news streams, 13F / Form 4 ownership, industry datasets
   - Fold new *information-risk* dimensions into the score
   - Keep each source behind a small, testable interface (see `windvane/edgar/` as the reference shape)

3. **Extend validation · 扩展回测**
   - More samples, more windows, tighter controls in `windvane/backtest/`

## The one rule that matters most · 最重要的一条

**Stay honest about "detection ≠ profit."** This project is a lens on *information risk*, not a return predictor. Don't add features that quietly turn it into buy/sell signals or imply guaranteed returns. Every output carries a "not investment advice" disclaimer — keep it that way.

**诚实面对"识别 ≠ 赚钱"。** 本项目是信息风险的透镜,不是收益预测器。不要偷偷把它变成买卖信号或暗示稳赚;每个输出都带"非投资建议"免责,请保留。

## Dev setup · 开发环境

```bash
uv sync
cp .env.example .env          # fill ANTHROPIC_API_KEY + EDGAR_USER_AGENT
uv run pytest -q              # all tests should pass
uv run ruff check windvane    # lint must be clean
```

- Python ≥ 3.11, managed by [uv](https://docs.astral.sh/uv/).
- SEC EDGAR requires a real `User-Agent` (your contact) — see `.env.example`.

## Workflow · 流程

1. Open an issue first for non-trivial changes (use the templates) so we align on approach.
2. Branch from `main`; keep each PR focused on one thing.
3. **TDD**: write a failing test, make it pass, keep the suite green. New behavior needs tests; tests must be offline (no live network in the suite — mock/fixture external calls).
4. Run `uv run pytest -q` and `uv run ruff check .` before pushing.
5. Open a PR against `main` and fill in the template.

## Style · 代码风格

- Small, focused modules with clear interfaces — one responsibility per file.
- Follow the surrounding code's idiom, naming, and comment density.
- Evidence-first for LLM outputs: any claim the model makes must carry a quoted source (see the stage-1 schema).
- Lint with ruff; no unused imports, no bare `except`.

## Reporting security / data issues

If you find a way the tool mishandles credentials, leaks data, or violates SEC access etiquette (rate limits, User-Agent), open an issue tagged `security` — or note it privately in the PR description.

## License

By contributing, you agree your contributions are licensed under the project's [MIT License](LICENSE).
