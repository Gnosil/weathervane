"""Schema sanity tests (structural, no LLM call)."""

from __future__ import annotations

from windvane.llm.schemas import (
    STAGE1_TOOL_NAME,
    STAGE1_TOOL_SCHEMA,
    STAGE2_TOOL_NAME,
    STAGE2_TOOL_SCHEMA,
)


def test_stage1_schema_required_fields() -> None:
    required = STAGE1_TOOL_SCHEMA["input_schema"]["required"]
    expected = {
        "segment_changes",
        "strategic_keywords",
        "pivot_phrases",
        "risk_factor_diff",
        "mdna_narrative_shift",
        "raw_strength",
        "narrative_summary",
    }
    assert expected.issubset(set(required))


def test_stage1_raw_strength_bounded() -> None:
    rs = STAGE1_TOOL_SCHEMA["input_schema"]["properties"]["raw_strength"]
    assert rs["type"] == "number"
    assert rs["minimum"] == 0
    assert rs["maximum"] == 1


def test_stage1_segment_changes_require_evidence() -> None:
    seg = STAGE1_TOOL_SCHEMA["input_schema"]["properties"]["segment_changes"]
    item_required = seg["items"]["required"]
    assert "evidence" in item_required


def test_stage1_pivot_phrases_require_evidence() -> None:
    pivots = STAGE1_TOOL_SCHEMA["input_schema"]["properties"]["pivot_phrases"]
    assert "evidence" in pivots["items"]["required"]


def test_stage2_schema_required_fields() -> None:
    required = STAGE2_TOOL_SCHEMA["input_schema"]["required"]
    expected = {
        "evidence_review",
        "keyword_review",
        "raw_strength_adjustment",
        "raw_strength_critiqued",
        "critique_summary",
    }
    assert expected.issubset(set(required))


def test_stage2_raw_strength_critiqued_bounded() -> None:
    rsc = STAGE2_TOOL_SCHEMA["input_schema"]["properties"]["raw_strength_critiqued"]
    assert rsc["minimum"] == 0
    assert rsc["maximum"] == 1


def test_tool_names_distinct() -> None:
    assert STAGE1_TOOL_NAME != STAGE2_TOOL_NAME
