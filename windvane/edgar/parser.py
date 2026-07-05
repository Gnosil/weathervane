"""Extract Item 1 / Item 1A / Item 7 from 10-K HTML.

10-K layout is not standardized — filers use varying capitalization, anchor
tags, and structure. We do best-effort heuristics:

1. Strip script/style/nav noise, convert to a single text blob.
2. Find every "Item N" heading via a regex matching common variants.
3. The first occurrence of each Item number is usually the TOC; the last
   occurrence is usually the body section. We keep the last.
4. Slice from the heading to the start of the next item.

This is intentionally simple. v0.2 may add an LLM-based chunk router as
fallback for filings where heuristics underperform.
"""

from __future__ import annotations

import re
import warnings
from typing import TypedDict

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# 10-K filings increasingly embed inline XBRL, which makes lxml suspect XML.
# We deliberately parse them as HTML — silence the noisy warning.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


class ExtractedItems(TypedDict):
    item_1: str
    item_1a: str
    item_7: str
    raw_text_len: int


# Matches "Item N", "ITEM N", "Item N." optionally followed by a title.
# 10-K Items run 1-16; sub-items can be 1A, 1B, 1C (Cybersecurity, SEC rule
# adopted 2023), 7A, 9A, 9B, 9C, etc. The letter suffix is critical — Item 1C
# is NOT the body of Item 1; without [A-Za-z] match we'd conflate them.
ITEM_HEADING = re.compile(
    r"(?P<head>(?:^|\n)\s*"
    r"(?:item|ITEM|Item)\s+"
    r"(?P<num>\d{1,2}[A-Za-z]?)\b\s*"
    r"[\.\:\-]?)",
    re.MULTILINE,
)

# Items 8 / 15 give us reliable "right boundaries" for items 7 / 7A respectively,
# but the boundary regex above already picks them up.


def _normalize_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "head", "noscript"]):
        tag.decompose()
    # Use double-newline between block tags so headings stand out
    text = soup.get_text("\n", strip=True)
    # Collapse excessive whitespace but preserve newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _find_boundaries(text: str) -> dict[str, tuple[int, int]]:
    """Map each item number to (body_start, body_end) byte offsets.

    Robust heuristic: for each item number, consider every occurrence and
    pick the one whose subsequent section (until the next item heading) is
    LONGEST. TOC lines are tens of characters; cross-references inside prose
    are also short; only the real body section runs for thousands of chars.
    """
    matches = list(ITEM_HEADING.finditer(text))
    if not matches:
        return {}

    by_num: dict[str, list[int]] = {}
    for idx, m in enumerate(matches):
        num = m.group("num").upper()
        by_num.setdefault(num, []).append(idx)

    boundaries: dict[str, tuple[int, int]] = {}
    for num, idxs in by_num.items():
        best_idx: int | None = None
        best_len = -1
        for idx in idxs:
            start = matches[idx].start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            section_len = end - start
            if section_len > best_len:
                best_len = section_len
                best_idx = idx
        assert best_idx is not None
        s = matches[best_idx].start()
        e = matches[best_idx + 1].start() if best_idx + 1 < len(matches) else len(text)
        boundaries[num] = (s, e)
    return boundaries


def extract_items(html: str) -> ExtractedItems:
    """Return Items 1, 1A, 7 as cleaned text (may be empty if heuristics fail)."""
    text = _normalize_text(html)
    bounds = _find_boundaries(text)

    def get(num: str) -> str:
        if num not in bounds:
            return ""
        s, e = bounds[num]
        return text[s:e].strip()

    return ExtractedItems(
        item_1=get("1"),
        item_1a=get("1A"),
        item_7=get("7"),
        raw_text_len=len(text),
    )
