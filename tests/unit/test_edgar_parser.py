"""10-K Item 1/1A/7 extraction heuristics."""

from __future__ import annotations

from windvane.edgar.parser import extract_items


def _fake_10k(item1: str, item1a: str, item7: str, item8: str = "Financial data.") -> str:
    """Build a minimal 10-K-shaped HTML with a TOC + body."""
    return f"""
<html><body>
<h2>Table of Contents</h2>
<p>Item 1. Business ............ 5</p>
<p>Item 1A. Risk Factors ....... 12</p>
<p>Item 7. MD&amp;A ............... 30</p>
<p>Item 8. Financial Statements .. 50</p>

<h1>Item 1. Business</h1>
<p>{item1}</p>

<h1>Item 1A. Risk Factors</h1>
<p>{item1a}</p>

<h1>Item 7. Management's Discussion and Analysis</h1>
<p>{item7}</p>

<h1>Item 8. Financial Statements</h1>
<p>{item8}</p>
</body></html>
"""


def test_extracts_all_three_items() -> None:
    html = _fake_10k(
        item1="We are a SaaS company providing X.",
        item1a="Our principal risks include competition.",
        item7="Revenue grew 15% YoY.",
    )
    items = extract_items(html)
    assert "SaaS company" in items["item_1"]
    assert "principal risks" in items["item_1a"]
    assert "Revenue grew" in items["item_7"]
    assert items["raw_text_len"] > 0


def test_toc_vs_body_disambiguation() -> None:
    """The 'last occurrence' heuristic should pick the body, not the TOC line."""
    html = _fake_10k(
        item1="UNIQUE_BODY_MARKER_FOR_ITEM_1",
        item1a="UNIQUE_BODY_MARKER_FOR_ITEM_1A",
        item7="UNIQUE_BODY_MARKER_FOR_ITEM_7",
    )
    items = extract_items(html)
    assert "UNIQUE_BODY_MARKER_FOR_ITEM_1" in items["item_1"]
    # The TOC line "Item 1. Business ............ 5" should NOT be the slice
    assert "............ 5" not in items["item_1"]


def test_item_boundaries_stop_at_next_item() -> None:
    html = _fake_10k(
        item1="Business content here.",
        item1a="Risk content here.",
        item7="MDNA content here.",
        item8="DO_NOT_LEAK_INTO_ITEM_7",
    )
    items = extract_items(html)
    assert "DO_NOT_LEAK_INTO_ITEM_7" not in items["item_7"]


def test_missing_item_returns_empty() -> None:
    html = "<html><body><p>Item 1. Business</p><p>Some content.</p></body></html>"
    items = extract_items(html)
    assert items["item_1"] != ""
    assert items["item_1a"] == ""
    assert items["item_7"] == ""


def test_item_1c_does_not_clobber_item_1() -> None:
    """Regression: Item 1C (Cybersecurity, new in 2023) must NOT be parsed
    as Item 1's body. This was a real bug found on the DOCU FY2026 10-K."""
    html = """
<html><body>
<p>Item 1. Business</p>
<p>Item 1A. Risk Factors</p>
<p>Item 1B. Unresolved Staff Comments</p>
<p>Item 1C. Cybersecurity</p>

<h1>Item 1. Business</h1>
<p>BUSINESS_BODY_MARKER We make widgets.</p>

<h1>Item 1A. Risk Factors</h1>
<p>RISK_BODY_MARKER We face competition.</p>

<h1>Item 1B. Unresolved Staff Comments</h1>
<p>None.</p>

<h1>Item 1C. Cybersecurity</h1>
<p>CYBER_BODY_MARKER We manage cyber risk.</p>

<h1>Item 2. Properties</h1>
<p>HQ in San Francisco.</p>
</body></html>
"""
    items = extract_items(html)
    assert "BUSINESS_BODY_MARKER" in items["item_1"]
    assert "CYBER_BODY_MARKER" not in items["item_1"]
    assert "RISK_BODY_MARKER" in items["item_1a"]
