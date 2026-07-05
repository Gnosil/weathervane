"""Filing download with local file cache."""

from __future__ import annotations

from pathlib import Path

from windvane.edgar.client import EdgarClient
from windvane.edgar.discover import FilingMeta


def filing_cache_path(cache_dir: Path, cik: str, meta: FilingMeta) -> Path:
    """Deterministic cache path for a filing's primary doc."""
    safe_acc = meta.accession_no.replace("-", "")
    return cache_dir / cik.zfill(10) / safe_acc / meta.primary_document


def cache_filing(
    client: EdgarClient,
    cache_dir: Path,
    cik: str,
    meta: FilingMeta,
    *,
    refresh: bool = False,
) -> Path:
    """Ensure the filing's HTML is on disk; return its path.

    Idempotent: skips fetch if already cached unless refresh=True.
    """
    out_path = filing_cache_path(cache_dir, cik, meta)
    if out_path.exists() and not refresh:
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = client.get_filing_html(cik, meta.accession_no, meta.primary_document)
    out_path.write_text(html, encoding="utf-8")
    return out_path
