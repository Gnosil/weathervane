"""JSON schemas for the two-stage LLM pipeline.

We use Anthropic's tool-calling API to enforce structured output.
Every claim in stage 1 must carry an `evidence` field (exact filing quote);
the Anthropic API will reject outputs that violate this schema.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Stage 1: extract & score
# ---------------------------------------------------------------------------
STAGE1_TOOL_NAME = "report_industry_pivot_analysis"

STAGE1_TOOL_SCHEMA: dict[str, Any] = {
    "name": STAGE1_TOOL_NAME,
    "description": (
        "Report a structured industry-pivot analysis of a company's filing "
        "compared to its same-period prior-year filing. Every claim must "
        "carry an exact-quote `evidence` field."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "segment_changes": {
                "type": "array",
                "description": "Discrete changes in reportable business segments.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "added",
                                "removed",
                                "renamed",
                                "revenue_share_shift",
                            ],
                        },
                        "name": {"type": "string"},
                        "from_pct": {
                            "type": "number",
                            "description": "Prior period revenue % (revenue_share_shift only).",
                        },
                        "to_pct": {
                            "type": "number",
                            "description": "Current period revenue % (revenue_share_shift only).",
                        },
                        "evidence": {
                            "type": "string",
                            "description": "Exact quoted sentence from the filing.",
                        },
                    },
                    "required": ["type", "name", "evidence"],
                },
            },
            "strategic_keywords": {
                "type": "object",
                "description": "Strategic-vocabulary diff between filings.",
                "properties": {
                    "new_in_this_filing": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Significant terms appearing this year but absent last year.",
                    },
                    "disappeared_from_last": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Significant terms present last year but absent this year.",
                    },
                    "density_changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "keyword": {"type": "string"},
                                "delta": {
                                    "type": "integer",
                                    "description": "Change in occurrence count (positive = more this year).",
                                },
                            },
                            "required": ["keyword", "delta"],
                        },
                    },
                },
                "required": [
                    "new_in_this_filing",
                    "disappeared_from_last",
                    "density_changes",
                ],
            },
            "pivot_phrases": {
                "type": "array",
                "description": "Direct quotes signaling strategic transformation (e.g., 'transition to', 'pivot', 'expand into').",
                "items": {
                    "type": "object",
                    "properties": {
                        "phrase": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["phrase", "evidence"],
                },
            },
            "risk_factor_diff": {
                "type": "object",
                "description": "Risk-factor category changes between filings.",
                "properties": {
                    "new_categories": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "removed_categories": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Supporting quotes from Item 1A.",
                    },
                },
                "required": ["new_categories", "removed_categories", "evidence"],
            },
            "mdna_narrative_shift": {
                "type": "object",
                "description": "How the MD&A (Item 7) narrative has been re-anchored.",
                "properties": {
                    "old_narrative_one_liner": {"type": "string"},
                    "new_narrative_one_liner": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": [
                    "old_narrative_one_liner",
                    "new_narrative_one_liner",
                    "evidence",
                ],
            },
            "raw_strength": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": (
                    "Overall subjective pivot intensity, calibrated 0-1. "
                    "Reference scale: 0.0-0.2 routine annual update; "
                    "0.2-0.5 minor strategic refresh; 0.5-0.7 clear directional shift; "
                    "0.7-0.9 major pivot (segment restructure + narrative + risk overhaul); "
                    "0.9-1.0 fundamental business transformation."
                ),
            },
            "narrative_summary": {
                "type": "string",
                "description": "1-2 sentence plain-English summary of the pivot story.",
            },
        },
        "required": [
            "segment_changes",
            "strategic_keywords",
            "pivot_phrases",
            "risk_factor_diff",
            "mdna_narrative_shift",
            "raw_strength",
            "narrative_summary",
        ],
    },
}


# ---------------------------------------------------------------------------
# Stage 2: critique
# ---------------------------------------------------------------------------
STAGE2_TOOL_NAME = "critique_industry_pivot_analysis"

STAGE2_TOOL_SCHEMA: dict[str, Any] = {
    "name": STAGE2_TOOL_NAME,
    "description": (
        "Critique a stage-1 industry-pivot analysis. For each claim, judge whether "
        "the evidence holds up; flag industry-wide drift (e.g., generic 'AI' mentions) "
        "and adjust raw_strength accordingly."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "evidence_review": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "original_claim": {"type": "string"},
                        "verdict": {
                            "type": "string",
                            "enum": ["valid", "renaming_only", "extrapolation"],
                        },
                        "reasoning": {"type": "string"},
                    },
                    "required": ["original_claim", "verdict", "reasoning"],
                },
            },
            "keyword_review": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string"},
                        "verdict": {
                            "type": "string",
                            "enum": ["industry_drift", "company_specific"],
                        },
                        "reasoning": {"type": "string"},
                    },
                    "required": ["keyword", "verdict", "reasoning"],
                },
            },
            "raw_strength_adjustment": {
                "type": "number",
                "description": (
                    "Signed delta to apply to stage-1 raw_strength. "
                    "Critique typically suggests negative adjustment to filter false signals."
                ),
            },
            "raw_strength_critiqued": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Final raw_strength after applying the adjustment.",
            },
            "critique_summary": {"type": "string"},
        },
        "required": [
            "evidence_review",
            "keyword_review",
            "raw_strength_adjustment",
            "raw_strength_critiqued",
            "critique_summary",
        ],
    },
}
