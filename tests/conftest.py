"""Pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated DB per test."""
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    monkeypatch.setenv("WINDVANE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("WINDVANE_REPORTS_DIR", str(reports_dir))
    # Ensure no .env leakage
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return data_dir / "windvane.sqlite"
