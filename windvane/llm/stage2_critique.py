"""Stage 2 — self-critique: validate stage-1 evidence and adjust raw_strength.

Acts as a second-opinion reviewer. Cross-checks every `evidence` quote against
the source filings, flags industry-wide keyword drift, and produces a signed
adjustment to the stage-1 raw_strength.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from anthropic import Anthropic

from windvane.llm.schemas import STAGE2_TOOL_NAME, STAGE2_TOOL_SCHEMA
from windvane.llm.stage1_extract import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_THINKING_BUDGET,
    FilingItems,
    Stage1Output,
    _format_filing,
)

CRITIQUE_SYSTEM_PROMPT = """You are a strict quality reviewer of industry-pivot \
analyses produced by a first-pass analyst.

A stage-1 analyst has produced a structured report on a company's filing. Your \
job is to do a SECOND OPINION pass and adjust the raw_strength score.

REVIEW CHECKLIST

1. EVIDENCE CROSS-CHECK
   For each claim with an `evidence` field: verify the quoted text actually \
   appears in either the prior or current filing. Tag the claim as:
     - "valid"             — evidence quote is present and supports the claim
     - "renaming_only"     — a segment name changed but underlying business \
                              composition seems unchanged
     - "extrapolation"     — claim goes beyond what the quote actually says

2. KEYWORD DRIFT vs COMPANY-SPECIFIC
   For each item in `strategic_keywords.new_in_this_filing`, classify:
     - "industry_drift"    — generic term (e.g., "AI", "cloud") added in line \
                              with industry-wide vocabulary shift
     - "company_specific"  — narrative explicitly anchored to this company's \
                              new direction

3. CALIBRATE THE ADJUSTMENT
   - Default adjustment: 0.0 (stage 1 was accurate)
   - Mild critique:      -0.05 to -0.10 (one weak signal filtered)
   - Substantial:        -0.10 to -0.30 (multiple drift keywords + 1 weak claim)
   - The critique should normally LOWER the score; raising is allowed but rare \
     (only when stage 1 clearly under-scored a major pivot).
   - `raw_strength_critiqued = clamp(raw_strength + adjustment, 0, 1)`

4. ONE TOOL CALL ONLY. Output via `critique_industry_pivot_analysis`."""


class Stage2Output(TypedDict):
    evidence_review: list[dict[str, Any]]
    keyword_review: list[dict[str, Any]]
    raw_strength_adjustment: float
    raw_strength_critiqued: float
    critique_summary: str


def critique_pivot_analysis(
    client: Anthropic,
    *,
    company_name: str,
    current: FilingItems,
    prior: FilingItems,
    stage1: Stage1Output,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    thinking_budget: int = DEFAULT_THINKING_BUDGET,
) -> tuple[Stage2Output, dict[str, Any]]:
    """Run stage-2 critique.

    Returns (parsed_output, raw_response_dict).
    """
    prior_block = _format_filing("PRIOR_FILING", prior)
    current_block = _format_filing("CURRENT_FILING", current)
    stage1_json = json.dumps(stage1, indent=2, ensure_ascii=False)

    user_intro = (
        f"Company: {company_name}\n\n"
        f"<STAGE_1_REPORT>\n{stage1_json}\n</STAGE_1_REPORT>\n\n"
        f"Critique the above. Verify each evidence quote against the filings. "
        f"Filter industry drift. Output one call to `{STAGE2_TOOL_NAME}`."
    )

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "enabled", "budget_tokens": thinking_budget},
        tools=[STAGE2_TOOL_SCHEMA],
        system=[
            {
                "type": "text",
                "text": CRITIQUE_SYSTEM_PROMPT,
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
                        "text": current_block,
                    },
                    {
                        "type": "text",
                        "text": user_intro,
                    },
                ],
            }
        ],
    )

    tool_input: Stage2Output | None = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == STAGE2_TOOL_NAME:
            tool_input = block.input  # type: ignore[assignment]
            break

    if tool_input is None:
        raise RuntimeError(
            f"Stage 2: LLM did not invoke {STAGE2_TOOL_NAME}. stop_reason={response.stop_reason}"
        )

    # Defensive clamp — the schema bounds the value 0..1 but the model could
    # still produce an inconsistent (adjustment, critiqued) pair.
    rsc = tool_input["raw_strength_critiqued"]
    if rsc < 0:
        tool_input["raw_strength_critiqued"] = 0.0
    elif rsc > 1:
        tool_input["raw_strength_critiqued"] = 1.0

    raw = {
        "model": response.model,
        "stop_reason": response.stop_reason,
        "usage": response.usage.model_dump()
        if hasattr(response.usage, "model_dump")
        else dict(response.usage),
    }
    return tool_input, raw
