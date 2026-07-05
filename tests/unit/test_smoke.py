"""Smoke tests: package import, version, fixture roster."""

from __future__ import annotations

import windvane
from windvane.universe import FIXTURES, find_fixture, fixtures_by_role


def test_version() -> None:
    assert windvane.__version__ == "0.1.0"


def test_fixture_roster_has_12() -> None:
    assert len(FIXTURES) == 12


def test_fixture_role_counts() -> None:
    assert len(fixtures_by_role("positive")) == 5
    assert len(fixtures_by_role("shell")) == 2
    assert len(fixtures_by_role("negative")) == 5


def test_find_fixture_case_insensitive() -> None:
    t = find_fixture("docu")
    assert t is not None
    assert t.symbol == "DOCU"
    assert t.cik == "0001261333"


def test_find_fixture_missing() -> None:
    assert find_fixture("ZZZZZ") is None
