"""Stage 1 — extract structured industry-pivot signal + raw_strength.

Uses Claude Sonnet 4.x with extended thinking and prompt caching:
- system prompt: cached (constant across runs)
- prior-year filing: cached (reused for ≥1 year by the same company)
- current-year filing: not cached (always new)

Output is enforced via the `report_industry_pivot_analysis` tool schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from anthropic import Anthropic

from windvane.llm.schemas import STAGE1_TOOL_NAME, STAGE1_TOOL_SCHEMA

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_THINKING_BUDGET = 5000


SYSTEM_PROMPT = """You are a senior financial analyst specializing in detecting \
industry pivots and strategic transformations in US public-company SEC filings \
(10-K and 10-Q).

You will be shown two excerpts:
- The company's CURRENT-PERIOD filing (Items 1 / 1A / 7 if available)
- The SAME-PERIOD PRIOR-YEAR filing

Your task: produce a structured industry-pivot analysis by calling the \
`report_industry_pivot_analysis` tool exactly once.

CRITICAL CONSTRAINTS

1. EVIDENCE IS MANDATORY. Every claim must carry an `evidence` field containing \
   the EXACT quoted text from the filing. If you cannot quote, do not include the claim. \
   Paraphrasing is a tool-schema violation.

2. CALIBRATE raw_strength HONESTLY. Use this reference scale:
   - 0.00-0.20  Routine annual update. Boilerplate refresh.
   - 0.20-0.50  Minor strategic refresh — one new keyword family OR one segment rename.
   - 0.50-0.70  Clear directional shift — narrative re-anchored, multiple converging signals.
   - 0.70-0.90  Major pivot — segment restructure + narrative overhaul + new risk categories.
   - 0.90-1.00  Fundamental business transformation — divestiture of core business + new vertical.

3. STRIP OUT INDUSTRY DRIFT. If a keyword (e.g., "AI", "cloud") was added \
   simply because every company in the industry added it in this filing season, \
   do NOT count it as a company-specific signal. Score what is unique to this filer.

4. SEGMENT RENAMES ARE WEAK SIGNALS. If a segment is renamed but its underlying \
   composition is unchanged, that is `type: "renamed"` with weak evidence — do not \
   inflate raw_strength.

5. ONE TOOL CALL ONLY. Do not narrate outside the tool call."""


class Stage1Output(TypedDict):
    """Parsed `report_industry_pivot_analysis` tool input."""

    segment_changes: list[dict[str, Any]]
    strategic_keywords: dict[str, Any]
    pivot_phrases: list[dict[str, Any]]
    risk_factor_diff: dict[str, Any]
    mdna_narrative_shift: dict[str, Any]
    raw_strength: float
    narrative_summary: str


@dataclass(frozen=True)
class FilingItems:
    """Item 1/1A/7 text bundle for one filing period."""

    accession_no: str
    period_label: str  # e.g. "FY2025" or "Q2 2025"
    item_1: str
    item_1a: str
    item_7: str


def _format_filing(label: str, items: FilingItems) -> str:
    parts = [f"<{label} accession={items.accession_no} period={items.period_label}>"]
    if items.item_1:
        parts.append("=== Item 1 Business ===")
        parts.append(items.item_1)
    if items.item_1a:
        parts.append("=== Item 1A Risk Factors ===")
        parts.append(items.item_1a)
    if items.item_7:
        parts.append("=== Item 7 MD&A ===")
        parts.append(items.item_7)
    parts.append(f"</{label}>")
    return "\n\n".join(parts)


def extract_pivot_signal(
    client: Anthropic,
    *,
    company_name: str,
    current: FilingItems,
    prior: FilingItems,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    thinking_budget: int = DEFAULT_THINKING_BUDGET,
) -> tuple[Stage1Output, dict[str, Any]]:
    """Run stage-1 extraction.

    Returns (parsed_output, raw_response_dict). The raw response dict includes
    usage stats so callers can record cost.
    """
    prior_block = _format_filing("PRIOR_FILING", prior)
    current_block = _format_filing("CURRENT_FILING", current)

    user_intro = (
        f"Company: {company_name}\n"
        f"Compare CURRENT vs PRIOR. Score the industry-pivot signal honestly and "
        f"call `{STAGE1_TOOL_NAME}` once."
    )

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "enabled", "budget_tokens": thinking_budget},
        tools=[STAGE1_TOOL_SCHEMA],
        # Don't force tool_choice — thinking + forced tool_choice can conflict.
        # Instead the system prompt requires one tool call.
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prior_block,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": current_block + "\n\n" + user_intro,
                    },
                ],
            }
        ],
    )

    tool_input: Stage1Output | None = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == STAGE1_TOOL_NAME:
            tool_input = block.input  # type: ignore[assignment]
            break

    if tool_input is None:
        raise RuntimeError(
            f"Stage 1: LLM did not invoke {STAGE1_TOOL_NAME}. stop_reason={response.stop_reason}"
        )

    raw = {
        "model": response.model,
        "stop_reason": response.stop_reason,
        "usage": response.usage.model_dump()
        if hasattr(response.usage, "model_dump")
        else dict(response.usage),
    }
    return tool_input, raw
