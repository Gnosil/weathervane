# 风向标 Windvane

**中文 · [English](README.en.md)**

**用 LLM 量化分析宏观市场与个股的"信息风险"** —— 公司在财报里宣称的产业转型,到底是**真实结构性变化**,还是**行业流行词 / 套壳 / 尚未落地的叙事**?Windvane 从 SEC 公开文件出发,用两阶段 LLM(抽取 + 自我批判)把这种"信息真伪/风险"量化成可比较、可回测的分数。

> 本工具输出基于公开信息的算法分析,**不构成任何投资建议**,仅供研究参考。

## 它解决什么

市场对"转型叙事"反应剧烈,但叙事里混着大量噪声:同一季度全行业都在往财报里塞 "AI / cloud",分部改个名就号称重构,套壳公司蹭风口。**信息风险 = 你读到的变化有多少是真的。** Windvane 把这件事做成一条可量化、可验证、可复现的流水线:

- **识别**:逐年 10-K 语义对比,抽取分部/关键词/叙事/风险因子的实质变化
- **祛魅**:第二阶段 LLM 独立复核证据、剥离行业漂移(industry drift)、给套壳分级
- **打分**:滚动高斯 z-score,把"主观转向强度"标准化成跨公司可比的分位
- **验证**:回测识别信号的真实表现(α vs SPY),诚实面对"识别 ≠ 赚钱"
- **聚合**:把个股动向聚合成"主题 × 板块"的宏观风向图

## 架构

```
SEC EDGAR (S&P 500 的 10-K / 10-Q)
  │  edgar/  —— 限速客户端 + Item 1/1A/7 抽取
  ▼
LLM 阶段 1:抽取产业转向信号 + raw_strength ∈ [0,1]   (带原文证据引用)
  │  llm/stage1_extract.py
  ▼
LLM 阶段 2:自我批判 —— 证据复核 + industry-drift 过滤 + 套壳分级
  │  llm/stage2_critique.py       ← 这里是"信息风险"的核心闸门
  ▼
滚动高斯 z-score (window=200,冷启动先验)
  │  scoring/
  ▼
全市场扫描 + 排名  (scan/)  →  Markdown / 网页榜单
  │
  ▼
yfinance 回测 (T+5/20/60/120d α vs SPY)   (backtest/)
```

## 一个贯穿始终的诚实结论

**识别准 ≠ 能赚钱。** 盲测显示模型能把真转型与稳定股干净分离、识破 buzzword;但回测同时显示:识别后简单买入 T+60 平均跑输大盘 —— 大量转型在宣布时已被市场 price in。所以 Windvane 的定位是**信息风险的量化透镜**(什么是真的、什么在被重配),而不是收益预测器。这条约束刻在每一层里。

## 快速开始

```bash
uv sync                            # 装依赖 (Python 由 uv 管理)
cp .env.example .env               # 填 ANTHROPIC_API_KEY + EDGAR_USER_AGENT
uv run windvane --help
uv run windvane init               # 初始化 SQLite + fixture universe
uv run windvane load-universe      # 载入完整 S&P 500
```

## 命令

```bash
windvane scan                      # L1 全市场粗筛
windvane scan --ticker DOCU        # 单只
windvane report --date 2026-05-29  # 生成当日报告
windvane backtest --fixtures       # 12 fixtures 回测验收
windvane backtest --ticker DOCU --entry 2024-04-01
windvane daemon                    # 每日调度常驻
```

## 验收 fixtures

- **正样本**(z ≥ 2,真转型):DOCU / TWLO / HON / SNAP / NET
- **套壳反例**(critique 必须识别并分级):BIRD / CAPS
- **负样本**(z < 1,稳定股):KO / PG / JNJ / WMT / JPM

## 欢迎贡献 🙌

这个项目的价值在于**算法质量**和**信息源广度**,两条都欢迎优化:

- **优化算法**:更好的语义 diff、更严的 industry-drift 判别、更稳的套壳分级、z-score 校准、prompt 工程
- **添加市场信息**:接入更多公开源(8-K 事件、新闻流、13F/Form4 股东结构、行业数据),把更多"信息风险"维度纳入打分
- **扩展回测**:更多样本、更多时窗、更严的对照

开 issue 讨论想法,或直接 PR。评分方法论、prompt、schema 都在 `windvane/llm/` 与 `windvane/scoring/` 里,改起来直接。

## License

[MIT](LICENSE) —— 自由使用、修改、分发,欢迎 PR。

## 免责

本系统输出基于公开信息(SEC 文件等)的算法分析,不构成任何投资建议或财务建议。实际投资决策与盈亏由用户独立承担。
